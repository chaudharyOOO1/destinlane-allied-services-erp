import hashlib
import re
from datetime import date, datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.api.deps import require_admin, require_owner
from app.api.v1.endpoints.company import require_company_staff, assert_company_editable
from app.core.database import get_db
from app.models.company import CompanyDocument
from app.services.company_storage import ALLOWED_MIME, MAX_BYTES, upload_company_file, signed_company_url, remove_failed_upload, ensure_private_bucket

router = APIRouter()
DOCUMENT_TYPES = {'COI': 'Certificate of Incorporation', 'MOA': 'Memorandum of Association', 'AOA': 'Articles of Association', 'GST': 'GST Certificate', 'PAN': 'Company PAN', 'TAN': 'TAN Certificate', 'UDYAM': 'Udyam Registration', 'PF': 'PF Registration', 'ESIC': 'ESIC Registration', 'PSARA': 'PSARA Licence', 'LABOUR': 'Labour Registration', 'OTHER': 'Other Legal Document'}


@router.get('/storage-status')
def storage_status(current_user=Depends(require_company_staff)):
    ensure_private_bucket()
    return {'ready': True, 'private': True, 'max_file_bytes': MAX_BYTES}


def response_document(row):
    return {key: getattr(row, key) for key in ['id', 'document_type', 'title', 'original_filename', 'mime_type', 'size_bytes', 'document_number', 'issue_date', 'expiry_date', 'uploaded_by', 'created_at', 'is_archived', 'archived_by', 'archived_at']}


@router.get('')
def list_documents(db: Session = Depends(get_db), current_user=Depends(require_company_staff)):
    query = db.query(CompanyDocument)
    if current_user.role.value != 'OWNER':
        query = query.filter(CompanyDocument.is_archived.is_(False))
    return {'document_types': DOCUMENT_TYPES, 'documents': [response_document(row) for row in query.order_by(CompanyDocument.created_at.desc()).all()]}


@router.post('', status_code=201)
async def upload_document(document_type: str = Form(...), title: str = Form(''), document_number: str = Form(''), issue_date: str = Form(''), expiry_date: str = Form(''), file: UploadFile = File(...), db: Session = Depends(get_db), current_user=Depends(require_admin)):
    assert_company_editable(db, current_user)
    document_type = document_type.strip().upper()
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(422, 'Choose a supported legal document category.')
    title = title.strip() or DOCUMENT_TYPES[document_type]
    document_number = document_number.strip()
    if len(title) > 200 or len(document_number) > 100:
        raise HTTPException(422, 'Document title or number is too long.')
    try:
        dates = [date.fromisoformat(value) if value else None for value in [issue_date, expiry_date]]
    except ValueError:
        raise HTTPException(422, 'Document dates must use YYYY-MM-DD.') from None
    if dates[0] and dates[1] and dates[1] < dates[0]:
        raise HTTPException(422, 'Expiry date cannot be before the issue date.')
    mime = (file.content_type or '').split(';')[0].lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(415, 'Upload a PDF, JPG or PNG document.')
    content = await file.read(MAX_BYTES + 1)
    if not content or not content.startswith(ALLOWED_MIME[mime]):
        raise HTTPException(422, 'File is empty or does not match its declared type.')
    if len(content) > MAX_BYTES:
        raise HTTPException(413, 'Maximum company document size is 3 MB.')
    sha = hashlib.sha256(content).hexdigest()
    if db.query(CompanyDocument).filter(CompanyDocument.sha256 == sha).first():
        raise HTTPException(409, 'This exact document is already stored, including archived records.')
    extension = {'application/pdf': 'pdf', 'image/jpeg': 'jpg', 'image/png': 'png'}[mime]
    path = f'{document_type}/{uuid4()}.{extension}'
    filename = re.sub(r'[\x00-\x1f\x7f]', '', (file.filename or 'document').replace('\\', '/').split('/')[-1])[:255] or f'document.{extension}'
    upload_company_file(path, content, mime)
    try:
        # Recheck under the same row lock used by submission. A staff upload
        # started before submission cannot be attached after the profile is locked.
        assert_company_editable(db, current_user, lock=True)
        row = CompanyDocument(document_type=document_type, title=title, original_filename=filename, storage_path=path, mime_type=mime, size_bytes=len(content), sha256=sha, document_number=document_number, issue_date=issue_date, expiry_date=expiry_date, uploaded_by=current_user.id)
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        try:
            # A commit can succeed before a refresh/network error reaches us.
            # Delete only after confirming no metadata record was committed.
            # If the database cannot answer, retain the private object safely.
            persisted = db.query(CompanyDocument).filter(CompanyDocument.storage_path == path).first()
            if not persisted:
                remove_failed_upload(path)
        except (HTTPException, SQLAlchemyError):
            pass
        if isinstance(exc, IntegrityError):
            raise HTTPException(409, 'This document is already stored.') from None
        raise
    return response_document(row)


@router.get('/{document_id}/download')
def download_document(document_id: int, db: Session = Depends(get_db), current_user=Depends(require_company_staff)):
    row = db.get(CompanyDocument, document_id)
    if not row or (row.is_archived and current_user.role.value != 'OWNER'):
        raise HTTPException(404, 'Company document not found.')
    return {'url': signed_company_url(row.storage_path), 'expires_in': 60}


@router.post('/{document_id}/archive')
def archive_document(document_id: int, db: Session = Depends(get_db), current_user=Depends(require_owner)):
    row = db.get(CompanyDocument, document_id)
    if not row:
        raise HTTPException(404, 'Company document not found.')
    if not row.is_archived:
        row.is_archived, row.archived_by, row.archived_at = True, current_user.id, datetime.now(timezone.utc)
        db.commit()
    return response_document(row)
