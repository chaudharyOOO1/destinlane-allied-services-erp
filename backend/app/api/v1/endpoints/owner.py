"""Management overview backed by the same permission-scoped operational sources."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_management
from app.api.permissions import effective_permissions
from app.core.business_time import business_date
from app.core.database import get_db
from app.services.dashboard import build_dashboard

router = APIRouter()


@router.get('/executive-summary')
def executive_summary(db: Session = Depends(get_db), current_user=Depends(require_management)):
    """owner.view permits this page, not unrestricted access to every source.

    This response intentionally shares the operational dashboard's sectioned
    contract. Gross invoice values and duplicated payroll joins are not a P&L.
    Accurate financial statements remain in the separately protected MD books.
    """
    return build_dashboard(db, effective_permissions(db, current_user), business_date(),
                           datetime.now(timezone.utc))
