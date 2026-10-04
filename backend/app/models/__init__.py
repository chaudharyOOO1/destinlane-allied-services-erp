"""SQLAlchemy models registry."""
from app.core.database import Base
from app.models.base import BaseModel, TimestampMixin
from app.models.enums import (
    UserRole,
    GuardStatus,
    ShiftType,
    RosterStatus,
    AttendanceStatus,
    InvoiceStatus,
)
from app.models.user import User
from app.models.client import Client, ClientCodeCounter, ClientStaffAssignment, ClientHistory
from app.models.site import Site
from app.models.guard import GuardProfile
from app.models.roster import ShiftRoster
from app.models.attendance import Attendance
from app.models.invoice import Invoice
from app.models.company import CompanySettings, CompanySettingsHistory, CompanyDocument

__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "UserRole",
    "GuardStatus",
    "ShiftType",
    "RosterStatus",
    "AttendanceStatus",
    "InvoiceStatus",
    "User",
    "Client",
    "Site",
    "GuardProfile",
    "ShiftRoster",
    "Attendance",
    "Invoice",
]

from app.models.internal_staff import InternalStaff, StaffCodeCounter, StaffHistory, StaffApprovalSettings

from app.models.account_audit import AccountAccessAudit
from app.models.commercial import ClientContract, SiteRateCard, SiteCodeCounter, CommercialHistory
