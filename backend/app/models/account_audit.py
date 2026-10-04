from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from app.models.base import BaseModel


class AccountAccessAudit(BaseModel):
    __tablename__ = 'account_access_audit'
    actor_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    target_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    action = Column(String(40), nullable=False)
    details = Column(JSON, nullable=False)
