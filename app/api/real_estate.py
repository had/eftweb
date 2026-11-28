"""Family properties and confirmed, atomic principal-home replacement."""

from contextlib import contextmanager
from datetime import date

from flask import current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.family.models import Family, RealEstateProperty

from . import api
from .api_routes import family_or_404, required_monetary_amount


@contextmanager
def property_write(family_id):
    try:
        if db.engine.dialect.name == "sqlite":
            db.session.execute(text("BEGIN IMMEDIATE"))
        else:
            db.session.query(Family).filter_by(id=family_id).with_for_update().first()
        yield
    finally:
        db.session.rollback()


def property_fields(data):
    if not isinstance(data, dict):
        raise ValueError("Property data must be an object")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 256:
        raise ValueError("Enter a property name of at most 256 characters")
    principal = data.get("is_principal_home", False)
    if not isinstance(principal, bool):
        raise ValueError("is_principal_home must be a boolean")
    amount = required_monetary_amount(data.get("estimated_value"), "Estimated value")
    if amount >= 1_000_000_000_000:
        raise ValueError("Estimated value must be at most 999999999999.99")
    replacement = data.get("replace_principal_home_id")
    if replacement is not None and (type(replacement) is not int or replacement <= 0):
        raise ValueError("replace_principal_home_id must be a positive integer")
    dates = {}
    for field, label in (("acquisition_date", "Acquisition date"), ("sell_date", "Sell date")):
        value = data.get(field)
        if field == "sell_date" and value in (None, ""):
            dates[field] = None
            continue
        try:
            parsed = date.fromisoformat(value) if isinstance(value, str) else None
            if parsed is None or parsed.isoformat() != value:
                raise ValueError()
        except ValueError as error:
            raise ValueError(f"{label} must be a valid date in YYYY-MM-DD format") from error
        dates[field] = parsed
    if dates["sell_date"] is not None and dates["sell_date"] < dates["acquisition_date"]:
        raise ValueError("Sell date must be on or after the acquisition date")
    return {
        "name": name.strip(),
        "is_principal_home": principal,
        "estimated_value": amount,
        **dates,
    }


@api.route("/api/families/<int:family_id>/properties", methods=["GET", "POST"])
@api.route("/api/families/<int:family_id>/properties/<int:property_id>", methods=["PUT", "DELETE"])
def family_properties(family_id, property_id=None):
    if request.method == "GET":
        if family_or_404(family_id) is None:
            return jsonify({"error": "Family is archived"}), 410
        properties = RealEstateProperty.query.filter_by(family_id=family_id).order_by(
            RealEstateProperty.name, RealEstateProperty.id
        )
        return jsonify([item.to_dict() for item in properties])

    try:
        with property_write(family_id):
            if family_or_404(family_id) is None:
                return jsonify({"error": "Family is archived"}), 410
            item = None
            if property_id is not None:
                item = RealEstateProperty.query.filter_by(
                    id=property_id, family_id=family_id
                ).first()
                if item is None:
                    return jsonify({"error": "Property not found for this family"}), 404
            if request.method == "DELETE":
                db.session.delete(item)
                db.session.commit()
                return "", 204

            data = request.get_json(silent=True)
            try:
                fields = property_fields(data)
            except ValueError as error:
                return jsonify({"error": str(error)}), 400

            if fields["is_principal_home"]:
                previous = RealEstateProperty.query.filter_by(
                    family_id=family_id, is_principal_home=True
                ).first()
                if previous is not None and previous.id != property_id:
                    if data.get("replace_principal_home_id") != previous.id:
                        return (
                            jsonify(
                                {
                                    "error": "Confirm replacement of the current principal home",
                                    "principal_home": previous.to_dict(),
                                }
                            ),
                            409,
                        )
                    previous.is_principal_home = False
                    # Release the unique principal-home slot before inserting/updating its replacement.
                    db.session.flush()

            if item is None:
                item = RealEstateProperty(family_id=family_id, **fields)
                db.session.add(item)
            else:
                for field, value in fields.items():
                    setattr(item, field, value)
            db.session.commit()
            return jsonify(item.to_dict()), 201 if property_id is None else 200
    except SQLAlchemyError:
        current_app.logger.exception("Could not save property changes")
        return jsonify({"error": "Could not save property changes. Please try again."}), 500
