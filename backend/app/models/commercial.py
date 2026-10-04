from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, JSON, Date, Numeric, CheckConstraint
from app.models.base import BaseModel


class ClientContract(BaseModel):
    __tablename__ = 'client_contracts'
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='RESTRICT'), nullable=False, index=True)
    contract_number = Column(String, nullable=False, unique=True)
    contract_start_date = Column(Date, nullable=False)
    contract_end_date = Column(Date, nullable=False)
    billing_cycle = Column(String, nullable=False, default='MONTHLY')
    credit_terms_days = Column(Integer, nullable=False, default=30)
    wage_indexation_percent = Column(Numeric(7,3), nullable=False, default=0)
    status = Column(String, nullable=False, default='DRAFT')
    renewal_notes = Column(String, nullable=True)
    profile = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)


class SiteRateCard(BaseModel):
    __tablename__ = 'site_rate_cards'
    site_id = Column(Integer, ForeignKey('sites.id', ondelete='RESTRICT'), nullable=False, index=True)
    contract_id = Column(Integer, ForeignKey('client_contracts.id', ondelete='RESTRICT'), nullable=True, index=True)
    vertical = Column(String, nullable=False)
    category = Column(String, nullable=False)
    hourly_rate = Column(Numeric(12,2), nullable=False, default=0)
    daily_rate = Column(Numeric(12,2), nullable=False, default=0)
    monthly_rate = Column(Numeric(12,2), nullable=False, default=0)
    rate_basis = Column(String, nullable=False, default='DAILY')
    duty_hours = Column(Numeric(5,2), nullable=False, default=8)
    billable_days = Column(Integer, nullable=False, default=26)
    wage_indexation_percent = Column(Numeric(7,3), nullable=False, default=0)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    notes = Column(String, nullable=False, default='')


class SiteCodeCounter(BaseModel):
    __tablename__ = 'site_code_counter'
    __table_args__ = (CheckConstraint('id = 1', name='site_single_counter'),)
    next_number = Column(Integer, nullable=False, default=1)


class CommercialHistory(BaseModel):
    __tablename__ = 'commercial_master_history'
    # References keep each record and its revision trail linked by foreign key.
    site_id = Column(Integer, ForeignKey('sites.id', ondelete='RESTRICT'), nullable=True, index=True)
    contract_id = Column(Integer, ForeignKey('client_contracts.id', ondelete='RESTRICT'), nullable=True, index=True)
    rate_id = Column(Integer, ForeignKey('site_rate_cards.id', ondelete='RESTRICT'), nullable=True, index=True)
    changed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = Column(String(30), nullable=False)
    snapshot = Column(JSON, nullable=False)
