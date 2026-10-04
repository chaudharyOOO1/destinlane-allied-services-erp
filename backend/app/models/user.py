from sqlalchemy import Column, String, Boolean, DateTime, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.enums import UserRole


class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    login_id = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=True)
    role = Column(
        SQLEnum(UserRole, name="user_role_enum", native_enum=True),
        default=UserRole.STAFF,
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)
    session_version = Column(Integer, default=0, nullable=False)
    password_initialized_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    guard_profile = relationship(
        "GuardProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    client_profile = relationship(
        "Client",
        back_populates="user",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, login_id='{self.login_id}', email='{self.email}', role='{self.role}')>"
