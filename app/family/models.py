from app import db


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

    @property
    def taxpayer1(self):
        return next(
            (member for member in self.members if member.role == "taxpayer1" and member.position == 1),
            None,
        )

    @property
    def taxpayer2(self):
        return next(
            (member for member in self.members if member.role == "taxpayer2" and member.position == 1),
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
    family_id = db.Column(db.Integer, db.ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
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
    family_id = db.Column(db.Integer, db.ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    has_income_statements = db.Column(db.Boolean, nullable=False, default=False)
    has_donation_statements = db.Column(db.Boolean, nullable=False, default=False)
    has_investment_statements = db.Column(db.Boolean, nullable=False, default=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    family = db.relationship("Family", back_populates="tax_returns")

    def to_dict(self):
        return {
            "id": self.id,
            "family_id": self.family_id,
            "year": self.year,
            "has_income_statements": self.has_income_statements,
            "has_donation_statements": self.has_donation_statements,
            "has_investment_statements": self.has_investment_statements,
            "is_archived": self.is_archived,
        }
