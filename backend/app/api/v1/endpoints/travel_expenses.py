"""Travel requests, independent review and exactly-once accounting posting.

All writes lock the claim and check its version. No endpoint accepts a requester,
reviewer, total, status or accounting reference supplied by the browser.
"""
import hashlib
import re
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.api.deps import get_current_active_user
from app.api.permissions import has_permission
from app.core.business_time import business_date
from app.core.database import get_db
from app.models.company import CompanySettings
from app.models.user import User
from app.models.travel_expense import TravelExpenseClaim as Claim, TravelExpenseReceipt as Receipt, TravelExpenseHistory as History
from app.schemas.travel_expense import TravelClaimInput, TravelClaimUpdate, VersionInput, TravelDecision, TravelPayment
from app.services import travel_storage as storage
from app.services import idempotency

router = APIRouter()


def travel_user(db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    if not has_permission(db, user, 'travel_expenses.view'):
        raise HTTPException(403, 'Travel Expenses access is required.')
    return user


def can_review(db, user):
    return has_permission(db, user, 'travel_expenses.approve') or has_permission(db, user, 'travel_expenses.pay')


def get_claim(db, claim_id, user, version=None, own=False):
    query = db.query(Claim).filter(Claim.id == claim_id)
    if version is not None:
        query = query.with_for_update()
    row = query.first()
    if not row or (row.requester_id != user.id and (own or not can_review(db, user))):
        raise HTTPException(404, 'Travel claim not found.')
    if version is not None and row.version != version:
        raise HTTPException(409, 'This claim changed. Reopen it before continuing.')
    return row


def require_editable(row):
    if row.status not in {'DRAFT', 'REJECTED'}:
        raise HTTPException(409, 'Only draft or rejected claims can be changed.')


def validate_branch(db, branch):
    if not branch:
        return
    settings = db.get(CompanySettings, 1)
    branches = (settings.profile if settings else {}).get('branches', [])
    if not any(b.get('code') == branch and b.get('is_active', True) for b in branches):
        raise HTTPException(422, 'Select an existing active company branch.')


def apply_input(row, data):
    values = data.model_dump(mode='json', exclude={'version'})
    for key, value in values.items():
        if key not in {'start_date', 'end_date'}:
            setattr(row, key, value)
    row.start_date, row.end_date = data.start_date, data.end_date
    row.total_amount = sum((item.amount for item in data.items), Decimal('0.00'))


def summary(row, name):
    fields = ['id','requester_id','purpose','origin','destination','start_date','end_date','branch','status','version','submitted_at','reviewed_by','reviewed_at','review_remarks','paid_by','payment_date','payment_reference','expense_id','created_at','updated_at']
    return {**{key: getattr(row, key) for key in fields}, 'claim_code': f'TRAVEL{row.id:06d}',
            'requester_name': name, 'total_amount': str(row.total_amount), 'currency': 'INR'}


def detail(db, row):
    result = summary(row, db.get(User, row.requester_id).full_name)
    result.update(items=row.items, missing_receipt_reason=row.missing_receipt_reason)
    result['receipts'] = [dict(id=r.id, filename=r.filename, mime_type=r.mime_type, size_bytes=r.size_bytes)
                          for r in db.query(Receipt).filter_by(claim_id=row.id).order_by(Receipt.id)]
    result['history'] = [dict(action=h.action, version=h.version, actor_id=h.actor_id, created_at=h.created_at, details=h.details)
                         for h in db.query(History).filter_by(claim_id=row.id).order_by(History.id)]
    return result


def finish(db, row, user, action, changes=None, idempotency_token=None):
    if action != 'CREATE':
        row.version += 1
    db.add(History(claim_id=row.id, actor_id=user.id, action=action, version=row.version,
                   details=changes or {'status': row.status, 'total_amount': str(row.total_amount)}))
    try:
        db.flush()
        response = detail(db, row)
        idempotency.save(db,idempotency_token,response)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This travel action conflicts with an existing record. Reopen the claim.') from None
    return response


@router.get('/options')
def options(db: Session = Depends(get_db), user=Depends(travel_user)):
    settings = db.get(CompanySettings, 1)
    branches = (settings.profile if settings else {}).get('branches', [])
    return {'branches': [{'code': b['code'], 'name': b['name']} for b in branches if b.get('is_active', True)]}


@router.get('')
def list_claims(scope: str = Query('mine', pattern='^(mine|all)$'), status: str = '',
                db: Session = Depends(get_db), user=Depends(travel_user)):
    if scope == 'all' and not can_review(db, user):
        raise HTTPException(403, 'Approval or reimbursement permission is required to view other claims.')
    query = db.query(Claim, User.full_name).join(User, User.id == Claim.requester_id)
    if scope == 'mine':
        query = query.filter(Claim.requester_id == user.id)
    if status:
        if status not in {'DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'PAID'}:
            raise HTTPException(422, 'Unknown travel claim status.')
        query = query.filter(Claim.status == status)
    rows = query.order_by(Claim.updated_at.desc(), Claim.id.desc()).limit(201).all()
    return {'claims': [summary(row, name) for row, name in rows[:200]], 'has_more': len(rows) > 200}


@router.post('', status_code=201)
def create_claim(data: TravelClaimInput, db: Session = Depends(get_db), user=Depends(travel_user)):
    validate_branch(db, data.branch)
    row = Claim(requester_id=user.id, status='DRAFT', version=1)
    apply_input(row, data)
    db.add(row)
    db.flush()
    return finish(db, row, user, 'CREATE', data.model_dump(mode='json'))


@router.get('/{claim_id}')
def read_claim(claim_id: int, db: Session = Depends(get_db), user=Depends(travel_user)):
    return detail(db, get_claim(db, claim_id, user))


@router.put('/{claim_id}')
def update_claim(claim_id: int, data: TravelClaimUpdate, db: Session = Depends(get_db), user=Depends(travel_user)):
    row = get_claim(db, claim_id, user, data.version, own=True)
    require_editable(row)
    validate_branch(db, data.branch)
    apply_input(row, data)
    row.status = 'DRAFT'
    return finish(db, row, user, 'UPDATE', data.model_dump(mode='json', exclude={'version'}))


@router.post('/{claim_id}/submit')
def submit_claim(claim_id: int, data: VersionInput, db: Session = Depends(get_db), user=Depends(travel_user)):
    row = get_claim(db, claim_id, user, data.version, own=True)
    require_editable(row)
    if row.end_date > business_date():
        raise HTTPException(422, 'Submit reimbursement after the travel has ended.')
    validate_branch(db, row.branch)
    if not db.query(Receipt).filter_by(claim_id=row.id).first() and not row.missing_receipt_reason:
        raise HTTPException(422, 'Attach a receipt or explain why receipts are unavailable.')
    row.status, row.submitted_at = 'SUBMITTED', datetime.now(timezone.utc)
    row.reviewed_by, row.reviewed_at, row.review_remarks = None, None, ''
    return finish(db, row, user, 'SUBMIT')


@router.post('/{claim_id}/decision')
def decide_claim(claim_id: int, data: TravelDecision, db: Session = Depends(get_db), user=Depends(travel_user)):
    row = get_claim(db, claim_id, user, data.version)
    if row.requester_id == user.id:
        raise HTTPException(403, 'You cannot approve or reject your own claim.')
    if row.status != 'SUBMITTED':
        raise HTTPException(409, 'Only submitted claims can be reviewed.')
    row.status = 'APPROVED' if data.decision == 'APPROVE' else 'REJECTED'
    row.reviewed_by, row.reviewed_at, row.review_remarks = user.id, datetime.now(timezone.utc), data.remarks
    return finish(db, row, user, data.decision, {'remarks': data.remarks, 'total_amount': str(row.total_amount)})


@router.post('/{claim_id}/pay')
def pay_claim(claim_id: int, data: TravelPayment, db: Session = Depends(get_db), user=Depends(travel_user),
              idempotency_key: str | None = Header(default=None, alias='Idempotency-Key')):
    # Preserve claim access control before replaying an earlier payment response.
    get_claim(db, claim_id, user)
    replay, marker = idempotency.begin(db,user.id,'travel.reimbursement.pay',idempotency_key,
                                       {'claim_id':claim_id,'payment':data.model_dump(mode='json')})
    if replay is not None: return replay
    row = get_claim(db, claim_id, user, data.version)
    if row.requester_id == user.id:
        raise HTTPException(403, 'Another authorised person must record your reimbursement.')
    if row.status != 'APPROVED' or row.expense_id:
        raise HTTPException(409, 'Only approved, unpaid claims can be reimbursed.')
    if data.payment_date > business_date() or data.payment_date < row.reviewed_at.astimezone(ZoneInfo('Asia/Kolkata')).date():
        raise HTTPException(422, 'Payment date must be on or after approval and cannot be in the future.')
    # Lock + version check + transaction prevents duplicate posting on retries.
    expense_id = str(uuid4())
    db.execute(text("""insert into expenses(id,branch,category,description,amount,expense_date)
        values(cast(:id as uuid),:branch,'TRAVEL',:description,:amount,:date)"""),
        {'id': expense_id, 'branch': row.branch or None, 'description': f'TRAVEL{row.id:06d}: {row.purpose}',
         'amount': row.total_amount, 'date': data.payment_date})
    row.status, row.paid_by, row.payment_date = 'PAID', user.id, data.payment_date
    row.payment_reference, row.expense_id = data.payment_reference, expense_id
    return finish(db, row, user, 'PAY', {'reference': data.payment_reference, 'expense_id': expense_id},
                  idempotency_token=marker)


@router.post('/{claim_id}/receipts', status_code=201)
async def upload_receipt(claim_id: int, version: int = Form(...), file: UploadFile = File(...),
                         db: Session = Depends(get_db), user=Depends(travel_user)):
    row = get_claim(db, claim_id, user, version, own=True)
    require_editable(row)
    if db.query(Receipt).filter_by(claim_id=row.id).count() >= 10:
        raise HTTPException(422, 'A claim supports at most 10 receipts.')
    mime = (file.content_type or '').split(';')[0].lower()
    if mime not in storage.MIME_SIGNATURES:
        raise HTTPException(415, 'Upload a PDF, JPG or PNG receipt.')
    content = await file.read(storage.MAX_BYTES + 1)
    if len(content) > storage.MAX_BYTES:
        raise HTTPException(413, 'Maximum receipt size is 3 MiB.')
    if not content or not content.startswith(storage.MIME_SIGNATURES[mime]):
        raise HTTPException(422, 'Receipt is empty or does not match its declared type.')
    sha = hashlib.sha256(content).hexdigest()
    if db.query(Receipt).filter_by(claim_id=row.id, sha256=sha).first():
        raise HTTPException(409, 'This receipt is already attached to the claim.')
    extension = {'application/pdf': 'pdf', 'image/jpeg': 'jpg', 'image/png': 'png'}[mime]
    path = f'{row.id}/{uuid4()}.{extension}'
    filename = re.sub(r'[\x00-\x1f\x7f]', '', (file.filename or 'receipt').replace('\\', '/').split('/')[-1])[:255] or f'receipt.{extension}'
    storage.upload(path, content, mime)
    db.add(Receipt(claim_id=row.id, filename=filename, storage_path=path, mime_type=mime,
                   size_bytes=len(content), sha256=sha, uploaded_by=user.id))
    try:
        return finish(db, row, user, 'RECEIPT', {'filename': filename, 'sha256': sha})
    except Exception:
        db.rollback()
        try:
            # A lost commit response is uncertain: retain the object unless the DB
            # can confirm that no metadata row was committed.
            if not db.query(Receipt).filter_by(storage_path=path).first():
                storage.remove_uncommitted(path)
        except (HTTPException, SQLAlchemyError):
            pass
        raise


@router.get('/{claim_id}/receipts/{receipt_id}/sign')
def sign_receipt(claim_id: int, receipt_id: int, db: Session = Depends(get_db), user=Depends(travel_user)):
    get_claim(db, claim_id, user)
    receipt = db.query(Receipt).filter_by(id=receipt_id, claim_id=claim_id).first()
    if not receipt:
        raise HTTPException(404, 'Receipt not found.')
    return {'url': storage.signed_url(receipt.storage_path), 'expires_in': 60}
