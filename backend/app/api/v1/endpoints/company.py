from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_admin, get_current_active_user
from app.core.database import get_db
from app.models.company import CompanySettings, CompanySettingsHistory
from app.models.enums import UserRole
from app.schemas.company import CompanyUpdate
from app.services.company import company_response, company_document_profile

router = APIRouter()
INTERNAL_ROLES = {UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR, UserRole.OPERATIONS, UserRole.ACCOUNTS}


def require_company_staff(current_user=Depends(get_current_active_user)):
    if current_user.role not in INTERNAL_ROLES:
        raise HTTPException(403, 'Company legal records are available to internal staff only.')
    return current_user


def assert_company_editable(db, current_user, *, lock=False):
    row = db.get(CompanySettings, 1, with_for_update=lock, populate_existing=lock)
    if row and row.submitted_at and current_user.role != UserRole.OWNER:
        raise HTTPException(403, 'This company profile has been submitted. Only the Owner can make changes.')
    return row


@router.get('/profile')
def document_profile(db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    # General document header information only. Legal identifiers/documents are
    # served separately through the internal-staff boundary below.
    return company_document_profile(db)


@router.get('')
def read_company(db: Session = Depends(get_db), current_user=Depends(require_company_staff)):
    return company_response(db)


@router.put('')
def save_company(payload: CompanyUpdate, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    row = assert_company_editable(db, current_user, lock=True)
    was_submitted = bool(row and row.submitted_at)
    profile = payload.profile.model_dump(mode='json')
    if row:
        old_codes = {b['code'] for b in row.profile.get('branches', [])}
        new_codes = {b['code'] for b in profile['branches']}
        if not old_codes <= new_codes:
            raise HTTPException(422, 'Existing branch codes cannot be removed or renamed. Mark the branch inactive instead.')
    if payload.submit and not profile['registration_date']:
        raise HTTPException(422, 'Enter the company registration date before submitting the profile.')
    now = datetime.now(timezone.utc)
    submitted_at = row.submitted_at if row else None
    submitted_by = row.submitted_by if row else None
    if payload.submit and not submitted_at:
        submitted_at, submitted_by = now, current_user.id
    if payload.version == 0:
        if row:
            raise HTTPException(409, 'Company settings changed. Reload before saving again.')
        db.add(CompanySettings(id=1, profile=profile, version=1, updated_by=current_user.id, submitted_at=submitted_at, submitted_by=submitted_by))
    else:
        result = db.execute(update(CompanySettings).where(CompanySettings.id == 1, CompanySettings.version == payload.version).values(
            profile=profile, version=payload.version + 1, updated_by=current_user.id, updated_at=now, submitted_at=submitted_at, submitted_by=submitted_by))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, 'Company settings changed. Reload before saving again.')
    action = 'SUBMIT' if payload.submit and not was_submitted else 'UPDATE'
    db.add(CompanySettingsHistory(profile=profile, version=payload.version + 1, changed_by=current_user.id, action=action))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Company settings changed. Reload before saving again.') from None
    db.expire_all()
    return company_response(db)
