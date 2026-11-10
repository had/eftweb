from easyfrenchtax import StockType

from .. import db
from ..constants import JAVASCRIPT_MAX_SAFE_INTEGER


class Stock(db.Model):
    __tablename__ = "stocks"
    __table_args__ = (db.UniqueConstraint("family_id", "symbol", name="uq_stock_family_symbol"),)

    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    symbol = db.Column(db.String(16), nullable=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    family = db.relationship("Family", back_populates="stocks")
    grants = db.relationship(
        "StockGrant", back_populates="stock", cascade="all, delete-orphan",
        order_by="StockGrant.grant_date, StockGrant.id",
    )

    sales = db.relationship(
        "StockSale", back_populates="stock", cascade="all, delete-orphan",
        order_by="StockSale.transaction_date, StockSale.id",
    )
    purchases = db.relationship(
        "StockPurchase", back_populates="stock", cascade="all, delete-orphan",
        order_by="StockPurchase.purchase_date, StockPurchase.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "family_id": self.family_id,
            "name": self.name,
            "symbol": self.symbol,
            "is_archived": self.is_archived,
        }


class StockGrant(db.Model):
    __tablename__ = "stock_grants"
    __table_args__ = (
        db.UniqueConstraint("stock_id", "creation_token", name="uq_stock_grant_creation_token"),
        db.UniqueConstraint("stock_id", "grant_number", name="uq_stock_grant_number"),
        db.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_stock_grant_quantity",
        ),
        db.CheckConstraint("schedule_type IN ('quarterly', 'cliff-quarterly')", name="ck_stock_grant_schedule_type"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    grant_number = db.Column(db.String(256), nullable=True)
    grant_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.BigInteger, nullable=False)
    vesting_start_date = db.Column(db.Date, nullable=False)
    schedule_type = db.Column(db.String(32), nullable=False)
    customized = db.Column(db.Boolean, nullable=False, default=False)
    creation_token = db.Column(db.String(36), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)

    stock = db.relationship("Stock", back_populates="grants")
    vestings = db.relationship(
        "GrantVesting", back_populates="grant", cascade="all, delete-orphan",
        order_by="GrantVesting.date, GrantVesting.id",
    )

    def to_dict(self):
        return {
            "id": self.id, "stock_id": self.stock_id, "title": self.title,
            "grant_date": self.grant_date.isoformat(), "quantity": self.quantity,
            "vesting_start_date": self.vesting_start_date.isoformat(),
            "grant_number": self.grant_number,
            "schedule_type": self.schedule_type, "customized": self.customized,
            "vestings": [vesting.to_dict() for vesting in self.vestings],
        }


class GrantVesting(db.Model):
    __tablename__ = "grant_vestings"
    __table_args__ = (
        db.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_grant_vesting_quantity",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    grant_id = db.Column(db.Integer, db.ForeignKey("stock_grants.id", ondelete="CASCADE"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.BigInteger, nullable=False)
    grant = db.relationship("StockGrant", back_populates="vestings")

    def to_dict(self):
        return {"id": self.id, "date": self.date.isoformat(), "quantity": self.quantity}


class StockPurchase(db.Model):
    __tablename__ = "stock_purchases"
    __table_args__ = (
        db.UniqueConstraint("stock_id", "creation_token", name="uq_stock_purchase_creation_token"),
        db.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_stock_purchase_quantity",
        ),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(
        db.Integer, db.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purchase_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.BigInteger, nullable=False)
    plan_name = db.Column(db.String(256), nullable=False, default="ESPP")
    creation_token = db.Column(db.String(36), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)

    stock = db.relationship("Stock", back_populates="purchases")

    def to_dict(self):
        return {
            "id": self.id,
            "stock_id": self.stock_id,
            "purchase_date": self.purchase_date.isoformat(),
            "quantity": self.quantity,
            "plan_name": self.plan_name,
        }


class StockSale(db.Model):
    __tablename__ = "stock_sales"
    __table_args__ = (
        db.UniqueConstraint("stock_id", "creation_token", name="uq_stock_sale_creation_token"),
        db.UniqueConstraint(
            "stock_id", "import_source", "source_order_number", "transaction_date",
            "proceeds_per_share", "currency", name="uq_stock_sale_source_group",
        ),
        db.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_stock_sale_quantity",
        ),
        db.CheckConstraint("proceeds_per_share > 0", name="ck_stock_sale_price"),
        db.CheckConstraint("currency = 'USD'", name="ck_stock_sale_currency"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(
        db.Integer, db.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.BigInteger, nullable=False)
    proceeds_per_share = db.Column(db.Numeric(14, 6), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")
    import_source = db.Column(db.String(32), nullable=True)
    source_order_number = db.Column(db.String(256), nullable=True)
    source_fingerprint = db.Column(db.String(64), nullable=True)
    creation_token = db.Column(db.String(36), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)

    stock = db.relationship("Stock", back_populates="sales")
    allocations = db.relationship(
        "StockSaleAllocation",
        back_populates="sale",
        cascade="all, delete-orphan",
        order_by="StockSaleAllocation.vesting_id, StockSaleAllocation.purchase_id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "stock_id": self.stock_id,
            "transaction_date": self.transaction_date.isoformat(),
            "quantity": self.quantity,
            "proceeds_per_share": format(self.proceeds_per_share, ".6f"),
            "currency": self.currency,
            "import_source": self.import_source,
            "source_order_number": self.source_order_number,
            "source_fingerprint": self.source_fingerprint,
            "allocations": [allocation.to_dict() for allocation in self.allocations],
        }


class StockSaleAllocation(db.Model):
    __tablename__ = "stock_sale_allocations"
    __table_args__ = (
        db.UniqueConstraint("sale_id", "vesting_id", name="uq_stock_sale_allocation_vesting"),
        db.UniqueConstraint("sale_id", "purchase_id", name="uq_stock_sale_allocation_purchase"),
        db.CheckConstraint(
            "(vesting_id IS NOT NULL AND purchase_id IS NULL) OR "
            "(vesting_id IS NULL AND purchase_id IS NOT NULL)",
            name="ck_stock_sale_allocation_source",
        ),
        db.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_stock_sale_allocation_quantity",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(
        db.Integer, db.ForeignKey("stock_sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vesting_id = db.Column(
        db.Integer,
        db.ForeignKey("grant_vestings.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    purchase_id = db.Column(
        db.Integer,
        db.ForeignKey("stock_purchases.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    quantity = db.Column(db.BigInteger, nullable=False)

    sale = db.relationship("StockSale", back_populates="allocations")

    def to_dict(self):
        source = (
            {"vesting_id": self.vesting_id}
            if self.vesting_id is not None
            else {"purchase_id": self.purchase_id}
        )
        return {**source, "quantity": self.quantity}


class StockImportReceipt(db.Model):
    __tablename__ = "stock_import_receipts"
    __table_args__ = (
        db.UniqueConstraint("stock_id", "creation_token", name="uq_stock_import_token"),
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    creation_token = db.Column(db.String(36), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    result = db.Column(db.JSON, nullable=False)


class DirectStocksPlan(db.Model):
    __tablename__ = "direct_stocks_plan"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    name = db.Column(db.String(256))
    symbol = db.Column(db.String(16))
    stock_currency = db.Column(db.String(3))


class DirectStocks(db.Model):
    __tablename__ = "direct_stocks"
    id = db.Column(db.Integer, primary_key=True)
    direct_stocks_plan_id = db.Column(db.Integer, db.ForeignKey('direct_stocks_plan.id'))
    quantity = db.Column(db.Integer)
    acquisition_date = db.Column(db.Date)
    acquisition_price = db.Column(db.Float)


class RSUPlan(db.Model):
    __tablename__ = "rsu_plans"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    name = db.Column(db.String(256))
    approval_date = db.Column(db.Date)
    symbol = db.Column(db.String(16))
    stock_currency = db.Column(db.String(3))


class RSUVesting(db.Model):
    __tablename__ = "rsu_stocks"
    id = db.Column(db.Integer, primary_key=True)
    rsu_plan_id = db.Column(db.Integer, db.ForeignKey('rsu_plans.id'))
    count = db.Column(db.Integer)
    vesting_date = db.Column(db.Date)
    release_date = db.Column(db.Date)
    acquisition_price = db.Column(db.Float)  # expressed in rsu_plans.stock_currency


class StockOptionPlan(db.Model):
    __tablename__ = "stockoption_plans"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    name = db.Column(db.String(256))
    taxpayer_owner = db.Column(db.Integer)  # 1 or 2, used for some tax return fields
    symbol = db.Column(db.String(16))
    stock_currency = db.Column(db.String(3))
    strike_price = db.Column(db.Float)


class StockOptionVesting(db.Model):
    __tablename__ = "stockoption_vestings"
    id = db.Column(db.Integer, primary_key=True)
    stockoption_plan_id = db.Column(db.Integer, db.ForeignKey('stockoption_plans.id'))
    count = db.Column(db.Integer)
    vesting_date = db.Column(db.Date)


class SaleEvent(db.Model):
    __tablename__ = "sale_events"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    type = db.Column(db.Enum(StockType))
    symbol = db.Column(db.String(16))
    quantity = db.Column(db.Integer)
    sell_date = db.Column(db.Date)
    sell_price = db.Column(db.Float)
    sell_currency = db.Column(db.String(3))
    fees = db.Column(db.Float)  # in sell_currency
