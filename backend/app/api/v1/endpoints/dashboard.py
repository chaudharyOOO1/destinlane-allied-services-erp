"""Read-only operational overview; private MD books are never a data source."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_accounts_or_admin
from app.api.permissions import effective_permissions
from app.core.business_time import business_date
from app.core.database import get_db
from app.services.dashboard import build_dashboard

router = APIRouter()


@router.get("")
def dashboard(db: Session = Depends(get_db), current_user=Depends(require_accounts_or_admin)):
    """Require dashboard.view plus the dashboard's existing office role gate.

    Each source is independently permission checked by the service. A dashboard
    grant cannot grant access to workforce, attendance, finance or MD books.
    """
    return build_dashboard(db, effective_permissions(db, current_user), business_date(),
                           datetime.now(timezone.utc))
