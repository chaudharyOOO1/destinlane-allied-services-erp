"""Travel claims are owned by the requester; lifecycle changes are versioned."""
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, JSON, ForeignKey, CheckConstraint, UniqueConstraint, Uuid
from app.models.base import BaseModel


class TravelExpenseClaim(BaseModel):
    __tablename__ = 'travel_expense_claims'
    __table_args__ = (
        CheckConstraint("status in ('DRAFT','SUBMITTED','APPROVED','REJECTED','PAID')", name='travel_claim_status'),
        CheckConstraint('total_amount > 0', name='travel_claim_positive_amount'),
        CheckConstraint('end_date >= start_date', name='travel_claim_dates'),
    )
    requester_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    purpose = Column(String(500), nullable=False)
    origin = Column(String(150), nullable=False)
    destination = Column(String(150), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    branch = Column(String(100), nullable=False, default='')
    items = Column(JSON, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    missing_receipt_reason = Column(String(1000), nullable=False, default='')
    status = Column(String(20), nullable=False, default='DRAFT', index=True)
    version = Column(Integer, nullable=False, default=1)
    submitted_at = Column(DateTime(timezone=True))
    reviewed_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'))
    reviewed_at = Column(DateTime(timezone=True))
    review_remarks = Column(String(1000), nullable=False, default='')
    paid_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'))
    payment_date = Column(Date)
    payment_reference = Column(String(150))
    expense_id = Column(Uuid(as_uuid=False), unique=True)


class TravelExpenseReceipt(BaseModel):
    __tablename__ = 'travel_expense_receipts'
    __table_args__ = (UniqueConstraint('claim_id', 'sha256'),)
    claim_id = Column(Integer, ForeignKey('travel_expense_claims.id', ondelete='RESTRICT'), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(300), nullable=False, unique=True)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    uploaded_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)


class TravelExpenseHistory(BaseModel):
    __tablename__ = 'travel_expense_history'
    claim_id = Column(Integer, ForeignKey('travel_expense_claims.id', ondelete='RESTRICT'), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    action = Column(String(30), nullable=False)
    version = Column(Integer, nullable=False)
    details = Column(JSON, nullable=False, default=dict)
