from app import db

from .donation_types import DONATION_TYPE_CODES
from .ifu_fields import IFU_FIELD_KEYS


class Family(db.Model):
    __tablename__ = "families"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    members = db.relationship(
        "FamilyMember",
        back_populates="family",
        cascade="all, delete-orphan",
        order_by="FamilyMember.role, FamilyMember.position",
    )
    tax_returns = db.relationship(
        "TaxReturn",
        back_populates="family",
        cascade="all, delete-orphan",
        order_by="TaxReturn.year.desc()",
    )
    stocks = db.relationship(
        "Stock",
        back_populates="family",
        cascade="all, delete-orphan",
        order_by="Stock.name, Stock.id",
    )
    properties = db.relationship(
        "RealEstateProperty",
        back_populates="family",
        cascade="all, delete-orphan",
        order_by="RealEstateProperty.name, RealEstateProperty.id",
    )

    @property
    def taxpayer1(self):
        return next(
            (
                member
                for member in self.members
                if member.role == "taxpayer1" and member.position == 1
            ),
            None,
        )

    @property
    def taxpayer2(self):
        return next(
            (
                member
                for member in self.members
                if member.role == "taxpayer2" and member.position == 1
            ),
            None,
        )

    @property
    def children(self):
        return [member for member in self.members if member.role == "child"]

    def to_dict(self):
        return {
            "id": self.id,
            "taxpayer1": self.taxpayer1.to_dict() if self.taxpayer1 else None,
            "taxpayer2": self.taxpayer2.to_dict() if self.taxpayer2 else None,
            "children": [child.to_dict() for child in self.children],
        }


class RealEstateProperty(db.Model):
    __tablename__ = "real_estate_properties"
    __table_args__ = (
        db.CheckConstraint(
            "estimated_value >= 0 AND estimated_value <= 999999999999.99",
            name="ck_property_estimated_value",
        ),
        db.CheckConstraint(
            "sell_date IS NULL OR (acquisition_date IS NOT NULL AND sell_date >= acquisition_date)",
            name="ck_property_dates",
        ),
        db.Index(
            "uq_property_family_principal_home",
            "family_id",
            unique=True,
            sqlite_where=db.text("is_principal_home = 1"),
            postgresql_where=db.text("is_principal_home = true"),
        ),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(
        db.Integer, db.ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = db.Column(db.String(256), nullable=False)
    is_principal_home = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    estimated_value = db.Column(db.Numeric(14, 2), nullable=False)
    # Older properties have unknown acquisition dates; new/edited properties require one in the API.
    acquisition_date = db.Column(db.Date, nullable=True)
    sell_date = db.Column(db.Date, nullable=True)

    family = db.relationship("Family", back_populates="properties")

    def to_dict(self):
        return {
            "id": self.id,
            "family_id": self.family_id,
            "name": self.name,
            "is_principal_home": self.is_principal_home,
            "estimated_value": format(self.estimated_value, ".2f"),
            "acquisition_date": self.acquisition_date.isoformat() if self.acquisition_date else None,
            "sell_date": self.sell_date.isoformat() if self.sell_date else None,
        }


class FamilyMember(db.Model):
    __tablename__ = "family_members"
    __table_args__ = (
        db.CheckConstraint(
            "(role IN ('taxpayer1', 'taxpayer2') AND position = 1) "
            "OR (role = 'child' AND position BETWEEN 1 AND 6)",
            name="ck_family_members_role_position",
        ),
        db.UniqueConstraint("family_id", "role", "position", name="uq_family_member_slot"),
    )

    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(
        db.Integer, db.ForeignKey("families.id", ondelete="CASCADE"), nullable=False
    )
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    role = db.Column(db.String(16), nullable=False)
    position = db.Column(db.Integer, nullable=False)

    family = db.relationship("Family", back_populates="members")

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "date_of_birth": self.date_of_birth,
        }


class TaxReturn(db.Model):
    __tablename__ = "tax_returns"
    __table_args__ = (db.UniqueConstraint("family_id", "year", name="uq_tax_return_family_year"),)

    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(
        db.Integer, db.ForeignKey("families.id", ondelete="CASCADE"), nullable=False
    )
    year = db.Column(db.Integer, nullable=False)
    has_income_statements = db.Column(db.Boolean, nullable=False, default=False)
    has_donation_statements = db.Column(db.Boolean, nullable=False, default=False)
    has_investment_statements = db.Column(db.Boolean, nullable=False, default=False)
    has_stock_statements = db.Column(db.Boolean, nullable=False, default=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    family = db.relationship("Family", back_populates="tax_returns")
    income_statements = db.relationship(
        "IncomeStatement",
        back_populates="tax_return",
        cascade="all, delete-orphan",
        order_by="IncomeStatement.id",
    )
    donation_statements = db.relationship(
        "DonationStatement",
        back_populates="tax_return",
        cascade="all, delete-orphan",
        order_by="DonationStatement.id",
    )
    ifu_statements = db.relationship(
        "IfuStatement",
        back_populates="tax_return",
        cascade="all, delete-orphan",
        order_by="IfuStatement.id",
    )

    stock_tax_receipts = db.relationship("StockTaxReceipt", cascade="all, delete-orphan")
    capital_gain_statements = db.relationship(
        "CapitalGainStatement",
        back_populates="tax_return",
        cascade="all, delete-orphan",
        order_by="CapitalGainStatement.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "family_id": self.family_id,
            "year": self.year,
            "has_income_statements": self.has_income_statements,
            "has_donation_statements": self.has_donation_statements,
            "has_investment_statements": self.has_investment_statements,
            "has_stock_statements": self.has_stock_statements,
            "is_archived": self.is_archived,
        }


class IncomeStatement(db.Model):
    __tablename__ = "income_statements"
    __table_args__ = (
        db.CheckConstraint(
            "taxpayer_role IN ('taxpayer1', 'taxpayer2')",
            name="ck_income_statements_taxpayer_role",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    tax_return_id = db.Column(
        db.Integer,
        db.ForeignKey("tax_returns.id", ondelete="CASCADE"),
        nullable=False,
    )
    taxpayer_role = db.Column(db.String(16), nullable=False)
    employer_name = db.Column(db.String(255), nullable=False)
    known_employment_income = db.Column(db.Numeric(12, 2), nullable=True)
    income_tax_withheld = db.Column(db.Numeric(12, 2), nullable=True)
    supplementary_pension_contributions = db.Column(db.Numeric(12, 2), nullable=True)

    tax_return = db.relationship("TaxReturn", back_populates="income_statements")

    @staticmethod
    def amount_to_dict(amount):
        return format(amount, ".2f") if amount is not None else None

    def to_dict(self):
        return {
            "id": self.id,
            "tax_return_id": self.tax_return_id,
            "taxpayer_role": self.taxpayer_role,
            "employer_name": self.employer_name,
            "known_employment_income": self.amount_to_dict(self.known_employment_income),
            "income_tax_withheld": self.amount_to_dict(self.income_tax_withheld),
            "supplementary_pension_contributions": self.amount_to_dict(
                self.supplementary_pension_contributions
            ),
        }


class DonationStatement(db.Model):
    __tablename__ = "donation_statements"
    __table_args__ = (
        db.CheckConstraint(
            "donation_type IN ({})".format(
                ", ".join(f"'{donation_type}'" for donation_type in DONATION_TYPE_CODES)
            ),
            name="ck_donation_statements_type",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    tax_return_id = db.Column(
        db.Integer,
        db.ForeignKey("tax_returns.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    donation_type = db.Column(db.String(32), nullable=False)

    tax_return = db.relationship("TaxReturn", back_populates="donation_statements")

    def to_dict(self):
        return {
            "id": self.id,
            "tax_return_id": self.tax_return_id,
            "name": self.name,
            "amount": IncomeStatement.amount_to_dict(self.amount),
            "donation_type": self.donation_type,
        }


class IfuStatement(db.Model):
    __tablename__ = "ifu_statements"

    id = db.Column(db.Integer, primary_key=True)
    tax_return_id = db.Column(
        db.Integer,
        db.ForeignKey("tax_returns.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(255), nullable=False)
    box_2tr = db.Column(db.Numeric(12, 2), nullable=True)
    box_2tt = db.Column(db.Numeric(12, 2), nullable=True)
    box_2dc = db.Column(db.Numeric(12, 2), nullable=True)
    box_2cg = db.Column(db.Numeric(12, 2), nullable=True)
    box_2bh = db.Column(db.Numeric(12, 2), nullable=True)
    box_2ck = db.Column(db.Numeric(12, 2), nullable=True)
    box_2df = db.Column(db.Numeric(12, 2), nullable=True)
    box_2dh = db.Column(db.Numeric(12, 2), nullable=True)
    box_2yy = db.Column(db.Numeric(12, 2), nullable=True)
    box_2zz = db.Column(db.Numeric(12, 2), nullable=True)

    tax_return = db.relationship("TaxReturn", back_populates="ifu_statements")

    def to_dict(self):
        return {
            "id": self.id,
            "tax_return_id": self.tax_return_id,
            "title": self.title,
            **{
                field: IncomeStatement.amount_to_dict(getattr(self, field))
                for field in IFU_FIELD_KEYS
            },
        }


class CapitalGainStatement(db.Model):
    __tablename__ = "capital_gain_statements"
    __table_args__ = (db.UniqueConstraint("tax_return_id", "source_key", name="uq_capital_source"),)
    id = db.Column(db.Integer, primary_key=True)
    tax_return_id = db.Column(
        db.Integer, db.ForeignKey("tax_returns.id", ondelete="CASCADE"), nullable=False
    )
    source_key = db.Column(db.String(80), nullable=True)
    title = db.Column(db.String(256), nullable=False)
    stock_id = db.Column(
        db.Integer, nullable=True
    )  # Snapshot identity, independent of the live ledger.
    computed = db.Column(db.JSON, nullable=False, default=dict)
    reported = db.Column(db.JSON, nullable=False, default=dict)
    metadata_snapshot = db.Column(db.JSON, nullable=False, default=dict)
    tax_return = db.relationship("TaxReturn", back_populates="capital_gain_statements")
    lines = db.relationship(
        "CapitalGainHelperLine",
        cascade="all, delete-orphan",
        order_by="CapitalGainHelperLine.position",
    )

    def to_dict(self, details=False):
        result = {
            "id": self.id,
            "tax_return_id": self.tax_return_id,
            "title": self.title,
            "stock_id": self.stock_id,
            "source_key": self.source_key,
            "computed": self.computed,
            "reported": self.reported,
            "metadata": self.metadata_snapshot,
        }
        if details:
            result["lines"] = [line.data for line in self.lines]
        return result


class CapitalGainHelperLine(db.Model):
    __tablename__ = "capital_gain_helper_lines"
    id = db.Column(db.Integer, primary_key=True)
    statement_id = db.Column(
        db.Integer, db.ForeignKey("capital_gain_statements.id", ondelete="CASCADE"), nullable=False
    )
    position = db.Column(db.Integer, nullable=False)
    data = db.Column(db.JSON, nullable=False)


class StockTaxReceipt(db.Model):
    __tablename__ = "stock_tax_receipts"
    __table_args__ = (db.UniqueConstraint("tax_return_id", "token", name="uq_stock_tax_receipt"),)
    id = db.Column(db.Integer, primary_key=True)
    tax_return_id = db.Column(
        db.Integer, db.ForeignKey("tax_returns.id", ondelete="CASCADE"), nullable=False
    )
    token = db.Column(db.String(36), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    result = db.Column(db.JSON, nullable=False)


class UsdEurRate(db.Model):
    __tablename__ = "usd_eur_rates"
    date = db.Column(db.Date, primary_key=True)
    usd_per_eur = db.Column(db.Numeric(20, 12), nullable=False)
    source = db.Column(db.String(256), nullable=False, default="ECB")


class FxCoverage(db.Model):
    __tablename__ = "fx_coverage"
    id = db.Column(db.Integer, primary_key=True)
    first_date = db.Column(db.Date, nullable=False)
    last_date = db.Column(db.Date, nullable=False)
