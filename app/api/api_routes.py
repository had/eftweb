from datetime import date
from decimal import Decimal, InvalidOperation

from easyfrenchtax import TaxField
from flask import abort, jsonify, request
from sqlalchemy.exc import IntegrityError

from taxhelpers import prepare_tax_input, simulate_tax

from ..family.models import Family, FamilyMember, IncomeStatement, TaxReturn
from ..main.models import Project, db
from ..tax.models import (
    CharitySegment,
    FixedIncomeInvestmentSegment,
    IncomeSegment,
    OtherInvestmentsSegment,
    RetirementInvestmentSegment,
    ServicesChargesSegment,
    ShareholdingSegment,
    TaxStatement,
)
from . import api


@api.after_request
def after_request(response):
    # response.headers['Access-Control-Allow-Origin'] = '*'
    print("Response headers:")
    for k, v in response.headers.items():
        print(f"{k}: {v}")
    return response

@api.before_request
def log_request():
    print(f">>> Flask sees request to: {request.path} from {request.origin}")


def family_or_404(family_id):
    family = Family.query.get(family_id)
    if not family:
        abort(404)
    if family.is_archived:
        return None
    return family


TAX_RETURN_CONFIGURATION_FIELDS = (
    "has_income_statements",
    "has_donation_statements",
    "has_investment_statements",
)

INCOME_STATEMENT_AMOUNT_FIELDS = (
    "known_employment_income",
    "income_tax_withheld",
    "supplementary_pension_contributions",
)


def tax_return_configuration(data, existing=None):
    if not isinstance(data, dict):
        raise ValueError("Tax return data must be an object")

    configuration = {}
    for field in TAX_RETURN_CONFIGURATION_FIELDS:
        value = data.get(field, getattr(existing, field) if existing else False)
        if not isinstance(value, bool):
            raise ValueError(f"{field} must be a boolean")
        configuration[field] = value
    return configuration


def active_tax_return_or_404(tax_return_id):
    tax_return = TaxReturn.query.get(tax_return_id)
    if not tax_return:
        abort(404)
    if tax_return.is_archived or tax_return.family.is_archived:
        return None
    return tax_return


def income_statement_from_payload(data, tax_return):
    if not isinstance(data, dict):
        raise ValueError("Income statement data must be an object")

    taxpayer_role = data.get("taxpayer_role")
    allowed_roles = {"taxpayer1"}
    if tax_return.family.taxpayer2:
        allowed_roles.add("taxpayer2")
    if taxpayer_role not in allowed_roles:
        raise ValueError("Select a taxpayer in this family")

    employer_name = data.get("employer_name")
    if not isinstance(employer_name, str) or not employer_name.strip():
        raise ValueError("Employer name is required")

    amounts = {}
    for field in INCOME_STATEMENT_AMOUNT_FIELDS:
        value = data.get(field)
        if value is None or value == "":
            amounts[field] = None
            continue
        if isinstance(value, bool):
            raise ValueError(f"{field} must be a non-negative monetary amount")
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"{field} must be a non-negative monetary amount") from error
        if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
            raise ValueError(f"{field} must be a non-negative monetary amount with at most two decimals")
        amounts[field] = amount

    if not any(amount is not None for amount in amounts.values()):
        raise ValueError("Enter at least one monetary amount")

    return IncomeStatement(
        taxpayer_role=taxpayer_role,
        employer_name=employer_name.strip(),
        **amounts,
    )


def member_from_payload(payload, role, position):
    if not isinstance(payload, dict):
        raise ValueError("Each family member must be an object")

    first_name = payload.get("first_name")
    last_name = payload.get("last_name")
    date_of_birth = payload.get("date_of_birth")
    if not all(isinstance(value, str) and value.strip() for value in (first_name, last_name, date_of_birth)):
        raise ValueError("Each family member needs a first name, last name, and date of birth")

    try:
        birth_date = date.fromisoformat(date_of_birth)
    except ValueError as error:
        raise ValueError("Dates of birth must use the YYYY-MM-DD format") from error

    return FamilyMember(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        date_of_birth=birth_date,
        role=role,
        position=position,
    )


def members_from_payload(data):
    if not isinstance(data, dict):
        raise ValueError("Family data must be an object")

    taxpayer1 = data.get("taxpayer1")
    if not taxpayer1:
        raise ValueError("Taxpayer 1 is required")

    members = [member_from_payload(taxpayer1, "taxpayer1", 1)]
    taxpayer2 = data.get("taxpayer2")
    if taxpayer2 is not None:
        members.append(member_from_payload(taxpayer2, "taxpayer2", 1))

    children = data.get("children", [])
    if not isinstance(children, list):
        raise ValueError("Children must be a list")
    if len(children) > 6:
        raise ValueError("A family can have at most six children")
    members.extend(member_from_payload(child, "child", index) for index, child in enumerate(children, start=1))
    return members


@api.route("/api/families")
def get_families():
    archived = request.args.get("archived", "false").lower() == "true"
    families = Family.query.filter_by(is_archived=archived).order_by(Family.id.desc()).all()
    return jsonify([family.to_dict() for family in families])


@api.route("/api/families", methods=["POST"])
def create_family():
    try:
        members = members_from_payload(request.get_json(silent=True))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    family = Family(members=members)
    db.session.add(family)
    db.session.commit()
    return jsonify(family.to_dict()), 201


@api.route("/api/families/<int:family_id>")
def get_family(family_id):
    family = family_or_404(family_id)
    if family is None:
        return jsonify({"error": "Family is archived"}), 410
    return jsonify(family.to_dict())


@api.route("/api/families/<int:family_id>", methods=["PUT"])
def update_family(family_id):
    family = family_or_404(family_id)
    if family is None:
        return jsonify({"error": "Family is archived"}), 410

    try:
        members = members_from_payload(request.get_json(silent=True))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    family.members.clear()
    db.session.flush()
    family.members = members
    db.session.commit()
    return jsonify(family.to_dict())


@api.route("/api/families/<int:family_id>", methods=["DELETE"])
def archive_family(family_id):
    family = Family.query.get(family_id)
    if not family:
        abort(404)
    if family.is_archived:
        return jsonify({"error": "Family is already archived"}), 410

    family.is_archived = True
    db.session.commit()
    return jsonify({"message": "Family archived successfully"})


@api.route("/api/families/<int:family_id>/tax-returns")
def get_tax_returns(family_id):
    family = family_or_404(family_id)
    if family is None:
        return jsonify({"error": "Family is archived"}), 410
    archived = request.args.get("archived", "false").lower() == "true"
    tax_returns = (
        TaxReturn.query.filter_by(family_id=family.id, is_archived=archived)
        .order_by(TaxReturn.year.desc())
        .all()
    )
    return jsonify([tax_return.to_dict() for tax_return in tax_returns])


@api.route("/api/families/<int:family_id>/tax-returns", methods=["POST"])
def create_tax_return(family_id):
    family = family_or_404(family_id)
    if family is None:
        return jsonify({"error": "Family is archived"}), 410

    data = request.get_json(silent=True)
    year = data.get("year") if isinstance(data, dict) else None
    if isinstance(year, bool) or not isinstance(year, int):
        return jsonify({"error": "Tax return year must be an integer"}), 400
    if TaxReturn.query.filter_by(family_id=family.id, year=year).first():
        return jsonify({"error": "A tax return already exists for this year"}), 409

    try:
        configuration = tax_return_configuration(data)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    tax_return = TaxReturn(family_id=family.id, year=year, **configuration)
    db.session.add(tax_return)
    db.session.commit()
    return jsonify(tax_return.to_dict()), 201


@api.route("/api/tax-returns/<int:tax_return_id>", methods=["PUT"])
def update_tax_return(tax_return_id):
    tax_return = TaxReturn.query.get(tax_return_id)
    if not tax_return:
        abort(404)
    if tax_return.is_archived or tax_return.family.is_archived:
        return jsonify({"error": "Tax return is archived"}), 410

    try:
        configuration = tax_return_configuration(request.get_json(silent=True), existing=tax_return)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    for field, value in configuration.items():
        setattr(tax_return, field, value)
    db.session.commit()
    return jsonify(tax_return.to_dict())


@api.route("/api/tax-returns/<int:tax_return_id>", methods=["DELETE"])
def archive_tax_return(tax_return_id):
    tax_return = TaxReturn.query.get(tax_return_id)
    if not tax_return:
        abort(404)
    if tax_return.is_archived:
        return jsonify({"error": "Tax return is already archived"}), 410
    if tax_return.family.is_archived:
        return jsonify({"error": "Family is archived"}), 410

    tax_return.is_archived = True
    db.session.commit()
    return jsonify({"message": "Tax return archived successfully"})


@api.route("/api/tax-returns/<int:tax_return_id>/income-statements")
def get_income_statements(tax_return_id):
    tax_return = active_tax_return_or_404(tax_return_id)
    if tax_return is None:
        return jsonify({"error": "Tax return is archived"}), 410
    return jsonify([statement.to_dict() for statement in tax_return.income_statements])


@api.route("/api/tax-returns/<int:tax_return_id>/income-statements", methods=["POST"])
def create_income_statement(tax_return_id):
    tax_return = active_tax_return_or_404(tax_return_id)
    if tax_return is None:
        return jsonify({"error": "Tax return is archived"}), 410
    if not tax_return.has_income_statements:
        return jsonify({"error": "Income statements are not enabled for this tax return"}), 409

    try:
        statement = income_statement_from_payload(request.get_json(silent=True), tax_return)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    tax_return.income_statements.append(statement)
    db.session.commit()
    return jsonify(statement.to_dict()), 201


def active_income_statement_or_404(income_statement_id):
    statement = IncomeStatement.query.get(income_statement_id)
    if not statement:
        abort(404)
    if statement.tax_return.is_archived or statement.tax_return.family.is_archived:
        return None
    return statement


@api.route("/api/income-statements/<int:income_statement_id>", methods=["PUT"])
def update_income_statement(income_statement_id):
    statement = active_income_statement_or_404(income_statement_id)
    if statement is None:
        return jsonify({"error": "Tax return is archived"}), 410
    if not statement.tax_return.has_income_statements:
        return jsonify({"error": "Income statements are not enabled for this tax return"}), 409

    try:
        updated_statement = income_statement_from_payload(
            request.get_json(silent=True), statement.tax_return
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    statement.taxpayer_role = updated_statement.taxpayer_role
    statement.employer_name = updated_statement.employer_name
    for field in INCOME_STATEMENT_AMOUNT_FIELDS:
        setattr(statement, field, getattr(updated_statement, field))
    db.session.commit()
    return jsonify(statement.to_dict())


@api.route("/api/income-statements/<int:income_statement_id>", methods=["DELETE"])
def delete_income_statement(income_statement_id):
    statement = active_income_statement_or_404(income_statement_id)
    if statement is None:
        return jsonify({"error": "Tax return is archived"}), 410
    db.session.delete(statement)
    db.session.commit()
    return jsonify({"message": "Income statement deleted successfully"})


@api.route("/api/projects")
def get_projects():
    projects = Project.query.filter_by(is_deleted=False).all()
    return jsonify([p.to_dict() for p in projects])

@api.route("/api/projects/<int:project_id>")
def get_project(project_id):
    statements = TaxStatement.query.filter_by(project_id=project_id).all()
    if statements:
        return jsonify([s.to_dict() for s in statements])
    else:
        abort(404)


@api.route("/api/projects/<int:project_id>/tax-statements")
def get_tax_statements(project_id):
    project = Project.query.get(project_id)
    if not project or project.is_deleted:
        abort(404)

    statements = (
        TaxStatement.query.filter_by(project_id=project_id)
        .order_by(TaxStatement.year.desc())
        .all()
    )
    return jsonify([statement.to_dict() for statement in statements])


@api.route("/api/projects/<int:project_id>/tax-statements", methods=["POST"])
def create_tax_statement(project_id):
    project = Project.query.get(project_id)
    if not project or project.is_deleted:
        abort(404)

    data = request.get_json(silent=True)
    year = data.get("year") if isinstance(data, dict) else None
    if isinstance(year, bool) or not isinstance(year, int):
        return jsonify({"error": "Tax return year must be an integer"}), 400

    existing_statement = TaxStatement.query.filter_by(project_id=project_id, year=year).first()
    if existing_statement:
        return jsonify({"error": "A tax return already exists for this year"}), 409

    statement = TaxStatement(project_id=project_id, year=year)
    db.session.add(statement)
    db.session.commit()
    return jsonify(statement.to_dict()), 201

@api.route("/api/projects", methods=["POST"])
def create_project():
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({'error': 'Project name is required'}), 400

    project = Project(
        name=data['name'],
        married=data.get('married', False),
        nb_children=data.get('nb_children', 0)
    )

    db.session.add(project)
    try:
        db.session.commit()
        return jsonify(project.to_dict()), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Project name already exists'}), 409

@api.route("/api/projects/<int:project_id>", methods=["PUT"])
def update_project(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'name' in data:
        project.name = data['name']
    if 'married' in data:
        project.married = data['married']
    if 'nb_children' in data:
        project.nb_children = data['nb_children']

    try:
        db.session.commit()
        return jsonify(project.to_dict()), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Project name already exists'}), 409

@api.route("/api/projects/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if project.is_deleted:
        return jsonify({'error': 'Project already deleted'}), 410

    project.is_deleted = True
    try:
        db.session.commit()
        return jsonify({'message': 'Project deleted successfully'}), 200
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete project'}), 500


@api.route("/api/taxes/<int:taxstatement_id>")
def get_taxstatement(taxstatement_id):
    try:
        # unfiltered_flag = (request.args.get('unfiltered', "") == "True")
        print(f"Requesting tax statement {taxstatement_id}")
        statement = TaxStatement.query.get(taxstatement_id)
        hydrated_statement = statement.to_dict()
        if statement.income_id:
            income_segment = IncomeSegment.query.get(statement.income_id)
            filtered_income_segment = {k:v for k,v in income_segment.to_dict().items() if v}
            if filtered_income_segment:
                hydrated_statement['income_segment'] = filtered_income_segment
        if statement.charity_id:
            charity_segment = CharitySegment.query.get(statement.charity_id)
            filtered_charity_segment = {k:v for k,v in charity_segment.to_dict().items() if v}
            if filtered_charity_segment:
                hydrated_statement['charity_segment'] = filtered_charity_segment
        if statement.retirementinvestment_id:
            retirement_investment_segment = RetirementInvestmentSegment.query.get(statement.retirementinvestment_id)
            filtered_retirement_investment_segment = {k:v for k,v in retirement_investment_segment.to_dict().items() if v}
            if filtered_retirement_investment_segment:
                hydrated_statement['retirement_investment_segment'] = filtered_retirement_investment_segment
        if statement.servicecharges_id:
            services_charges_segment = ServicesChargesSegment.query.get(statement.servicecharges_id)
            filtered_services_charges_segment = {k:v for k,v in services_charges_segment.to_dict().items() if v}
            if filtered_services_charges_segment:
                hydrated_statement['services_charges_segment'] = filtered_services_charges_segment
        if statement.fixedincomeinvestment_id:
            fixed_income_segment = FixedIncomeInvestmentSegment.query.get(statement.fixedincomeinvestment_id)
            filtered_fixed_income_segment = {k:v for k,v in fixed_income_segment.to_dict().items() if v}
            if filtered_fixed_income_segment:
                hydrated_statement['fixed_income_segment'] = filtered_fixed_income_segment
        if statement.otherinvestments_id:
            other_investments_segment = OtherInvestmentsSegment.query.get(statement.otherinvestments_id)
            filtered_other_investments_segment = {k:v for k,v in other_investments_segment.to_dict().items() if v}
            if filtered_other_investments_segment:
                hydrated_statement['other_investments_segment'] = filtered_other_investments_segment
        if statement.shareholding_id:
            shareholding_segment = ShareholdingSegment.query.get(statement.shareholding_id)
            filtered_shareholding_segment = {k:v for k,v in shareholding_segment.to_dict().items() if v}
            if filtered_shareholding_segment:
                hydrated_statement['shareholding_segment'] = filtered_shareholding_segment

        return jsonify(hydrated_statement)
    except Exception as e:
        print(e)
        abort(404)


@api.route("/api/taxes/<int:taxstatement_id>/estimation")
def get_taxestimation(taxstatement_id):
    taxstatement = TaxStatement.query.get(taxstatement_id)
    project = Project.query.get(taxstatement.project_id)

    tax_input, rendering_elements = prepare_tax_input(project, taxstatement)
    tax_result, tax_flags = simulate_tax(taxstatement.year, tax_input)
    total_taxes = tax_result[TaxField.NET_TAXES] + tax_result[TaxField.NET_SOCIAL_TAXES]
    return jsonify({'total_taxes': total_taxes, 'details': tax_result, 'flags': tax_flags})
