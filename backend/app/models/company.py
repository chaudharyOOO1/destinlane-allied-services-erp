from sqlalchemy import Column, Integer, JSON, ForeignKey, CheckConstraint, DateTime, String, Boolean
from app.models.base import BaseModel


class CompanySettings(BaseModel):
    __tablename__ = 'company_settings'
    __table_args__ = (CheckConstraint('id = 1', name='company_settings_single_company'),)
    profile = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    updated_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    submitted_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)


class CompanySettingsHistory(BaseModel):
    __tablename__ = 'company_settings_history'
    profile = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, unique=True)
    changed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(30), nullable=False, default='UPDATE')


class CompanyDocument(BaseModel):
    __tablename__ = 'company_documents'
    document_type = Column(String(40), nullable=False)
    title = Column(String(200), nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False, unique=True)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, unique=True)
    document_number = Column(String(100), nullable=False, default='')
    issue_date = Column(String(10), nullable=False, default='')
    expiry_date = Column(String(10), nullable=False, default='')
    uploaded_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    archived_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
