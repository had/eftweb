from easyfrenchtax import TaxField
from flask import jsonify, request, abort
from flask_cors import CORS

from taxhelpers import prepare_tax_input, simulate_tax
from . import api
from ..main.models import Project
from ..tax.models import *

CORS(api, origins=["http://localhost:5173"])


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


@api.route("/api/projects")
def get_projects():
    projects = Project.query.all()
    return jsonify([p.to_dict() for p in projects])

@api.route("/api/projects/<int:project_id>")
def get_project(project_id):
    statements = TaxStatement.query.filter_by(project_id=project_id).all()
    if statements:
        return jsonify([s.to_dict() for s in statements])
    else:
        abort(404)


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

