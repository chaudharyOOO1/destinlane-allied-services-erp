from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Text, JSON, Date
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Client(BaseModel):
    __tablename__ = "clients"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, unique=True)
    client_code = Column(String(50),unique=True,nullable=True)
    gstin = Column(String(50),nullable=True,unique=True)
    branch = Column(String(100),nullable=True)
    branch_region = Column(String(30),nullable=True)
    credit_terms_days = Column(Integer,nullable=False,default=30)
    registration_no = Column(String(100),nullable=True)
    billing_cycle = Column(String(30),nullable=True,default='MONTHLY')
    contract_start_date = Column(Date,nullable=True)
    contract_end_date = Column(Date,nullable=True)
    profile = Column(JSON,nullable=False,default=dict)
    version = Column(Integer,nullable=False,default=1)
    company_name = Column(String(255), unique=True, index=True, nullable=False)
    contact_person = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=False)
    billing_address = Column(Text, nullable=False)
    gst_number = Column(String(50), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="client_profile")
    sites = relationship("Site", back_populates="client", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, company_name='{self.company_name}')>"


from sqlalchemy import JSON, UniqueConstraint, CheckConstraint


class ClientCodeCounter(BaseModel):
    __tablename__ = 'client_code_counter'
    __table_args__ = (CheckConstraint('id = 1', name='client_single_counter'),)
    next_number = Column(Integer, nullable=False, default=1)


class ClientStaffAssignment(BaseModel):
    __tablename__ = 'client_staff_assignments'
    __table_args__ = (UniqueConstraint('client_id','staff_id',name='client_staff_unique'),)
    client_id = Column(Integer, ForeignKey('clients.id',ondelete='RESTRICT'),nullable=False,index=True)
    staff_id = Column(Integer, ForeignKey('internal_staff.id',ondelete='RESTRICT'),nullable=False,index=True)
    is_active = Column(Boolean,nullable=False,default=True)


class ClientHistory(BaseModel):
    __tablename__ = 'client_master_history'
    client_id = Column(Integer,ForeignKey('clients.id',ondelete='RESTRICT'),nullable=False,index=True)
    snapshot = Column(JSON,nullable=False)
    changed_by = Column(Integer,ForeignKey('users.id',ondelete='SET NULL'))
    action = Column(String(30),nullable=False)
