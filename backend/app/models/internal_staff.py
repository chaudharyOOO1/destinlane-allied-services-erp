from sqlalchemy import Column, Integer, String, JSON, ForeignKey, CheckConstraint
from app.models.base import BaseModel


class InternalStaff(BaseModel):
    __tablename__ = 'internal_staff'
    __table_args__ = (CheckConstraint("status in ('DRAFT','PENDING','ACTIVE','INACTIVE','TERMINATED')", name='internal_staff_status'),)
    staff_code = Column(String(30), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(10), nullable=False, unique=True)
    profile = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default='DRAFT')
    approver_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    status_reason = Column(String(1000), nullable=False, default='')
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    updated_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))


class StaffCodeCounter(BaseModel):
    __tablename__ = 'internal_staff_code_counter'
    __table_args__ = (CheckConstraint('id = 1', name='internal_staff_single_counter'),)
    next_number = Column(Integer, nullable=False, default=10)


class StaffHistory(BaseModel):
    __tablename__ = 'internal_staff_history'
    staff_id = Column(Integer, ForeignKey('internal_staff.id', ondelete='RESTRICT'), nullable=False, index=True)
    snapshot = Column(JSON, nullable=False)
    changed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    action = Column(String(30), nullable=False)


class StaffApprovalSettings(BaseModel):
    __tablename__ = 'internal_staff_approval_settings'
    __table_args__ = (CheckConstraint('id = 1', name='internal_staff_single_approval_settings'),)
    approver_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    version = Column(Integer, nullable=False, default=1)
