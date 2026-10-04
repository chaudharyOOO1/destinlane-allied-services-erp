import hashlib
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_hr_or_admin
from app.api.permissions import has_permission
from app.core.business_time import business_date
from app.services.employee_workflow import employee as joining_employee,audit,refresh_compliance
from app.core.config import settings
from app.core.database import get_db

router = APIRouter()

ALLOWED_MIME = {
    "application/pdf": {b"%PDF-"},
    "image/jpeg": {b"\xff\xd8\xff"},
    "image/png": {b"\x89PNG\r\n\x1a\n"},
    "image/webp": {b"RIFF"},
}
MAX_FILE_BYTES = 3 * 1024 * 1024

DOCUMENT_TYPES = {
    "PHOTO": "Employee Photograph",
    "AADHAAR": "Aadhaar Card",
    "PAN": "PAN Card",
    "FORM_11": "Form 11",
    "FORM_11A": "Form 11A",
    "POLICE_VERIFICATION": "Police Verification",
    "MEDICAL_FITNESS": "Medical / Fitness Certificate",
    "ESIC_FORM": "ESIC Form",
    "BANK_PASSBOOK": "Bank Passbook",
    "BANK_CHEQUE": "Cancelled Cheque",
    "ADDRESS_PROOF": "Address Proof",
    "PSARA_CERTIFICATE": "PSARA Certificate",
    "GUN_LICENSE": "Gun Licence",
    "NOMINEE_ID": "Nominee ID",
    "OTHER": "Other",
}

def _storage_config():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(503, "Private document storage is not configured on the backend.")
    return settings.SUPABASE_URL.rstrip("/"), settings.SUPABASE_SERVICE_ROLE_KEY

def _storage_request(method: str, path: str, body: bytes | None = None, content_type: str | None = None):
    base, key = _storage_config()
    url = f"{base}/storage/v1/{path.lstrip('/')}"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, "Document storage could not complete this request.")
    except urllib.error.URLError as exc:
        raise HTTPException(503, "Document storage is temporarily unavailable.")

def _magic_ok(mime: str, content: bytes) -> bool:
    signatures = ALLOWED_MIME.get(mime)
    if not signatures:
        return False
    if mime == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return any(content.startswith(signature) for signature in signatures)

def _safe_ext(filename: str, mime: str) -> str:
    ext = mimetypes.guess_extension(mime) or ""
    original = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = {"pdf": "pdf", "jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp"}
    return allowed.get(original, ext.lstrip(".") or "bin")

def _employee_or_404(employee_id: UUID, db: Session):
    row = db.execute(text("select id, employee_code, name from employees where id=:id"), {"id": str(employee_id)}).mappings().first()
    if not row:
        raise HTTPException(404, "Employee not found.")
    return row

@router.get("/{employee_id}/documents")
def list_documents(employee_id: UUID, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    _employee_or_404(employee_id, db)
    rows = db.execute(
        text("""
            select id, employee_id, document_type, original_filename, mime_type, size_bytes,
                   document_number, issuing_authority, issue_date, expiry_date,
                   status, verification_status, verification_notes, sha256,
                   uploaded_by, verified_by, verified_at, created_at, updated_at
            from employee_documents
            where employee_id=:employee_id
            order by created_at desc
        """),
        {"employee_id": str(employee_id)},
    ).mappings().all()
    return [dict(r) for r in rows]

@router.post("/{employee_id}/documents", status_code=201)
async def upload_document(
    employee_id: UUID,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    document_number: str | None = Form(None),
    issuing_authority: str | None = Form(None),
    issue_date: str | None = Form(None),
    expiry_date: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_hr_or_admin),
):
    employee = joining_employee(db,employee_id,True)
    if employee['status'].upper() in {'PENDING_APPROVAL','TERMINATED'}:
        raise HTTPException(409,'Submitted or terminated employee files do not accept uploads. Ask the assigned approver to return the file.')
    for key,value in [('issue_date',issue_date),('expiry_date',expiry_date)]:
        if value:
            try: date.fromisoformat(value)
            except ValueError: raise HTTPException(422,f'{key} must be a valid date.')
    if issue_date and date.fromisoformat(issue_date)>business_date(): raise HTTPException(422,'Document issue date cannot be in the future.')
    if issue_date and expiry_date and expiry_date<issue_date: raise HTTPException(422,'Expiry date cannot precede issue date.')
    if document_type.upper()=='MEDICAL_FITNESS' and not issue_date: raise HTTPException(422,'Medical fitness requires the examination / issue date for annual renewal.')
    if document_type.upper()=='MEDICAL_FITNESS' and issue_date:
        issued=date.fromisoformat(issue_date)
        try: annual=issued.replace(year=issued.year+1)
        except ValueError: annual=issued.replace(year=issued.year+1,day=28)
        if not expiry_date or date.fromisoformat(expiry_date)>annual: expiry_date=annual.isoformat()
    if document_type.upper() in {'POLICE_VERIFICATION','MEDICAL_FITNESS','GUN_LICENSE'} and not expiry_date:
        raise HTTPException(422,'This compliance document requires an expiry date.')
    document_type = document_type.strip().upper()
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(422, f"Unsupported document type. Allowed: {', '.join(DOCUMENT_TYPES)}")

    mime = (file.content_type or "").split(";")[0].lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(415, "Only PDF, JPG/JPEG, PNG and WEBP documents are accepted.")

    content = await file.read(MAX_FILE_BYTES + 1)
    if not content:
        raise HTTPException(422, "The uploaded file is empty.")
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "Document is too large. Maximum allowed size is 3 MB.")
    if not _magic_ok(mime, content):
        raise HTTPException(422, "File integrity check failed: the file content does not match its declared type.")

    sha256 = hashlib.sha256(content).hexdigest()
    duplicate = db.execute(
        text("select id from employee_documents where employee_id=:employee_id and sha256=:sha256 limit 1"),
        {"employee_id": str(employee_id), "sha256": sha256},
    ).first()
    if duplicate:
        raise HTTPException(409, "This exact document is already uploaded for this employee.")

    doc_id = uuid4()
    ext = _safe_ext(file.filename or "document", mime)
    storage_path = f"{employee_code_safe(employee['employee_code'])}/{document_type}/{doc_id}.{ext}"

    _storage_request(
        "POST",
        f"object/{settings.EMPLOYEE_DOCUMENT_BUCKET}/{urllib.parse.quote(storage_path, safe='/')}",
        body=content,
        content_type=mime,
    )

    metadata = {
        "integrity_check": "PASSED",
        "declared_mime": mime,
        "magic_signature_check": "PASSED",
        "document_type_label": DOCUMENT_TYPES[document_type],
    }
    try:
        row = db.execute(
            text("""
                insert into employee_documents
                  (id, employee_id, document_type, document_url, document_number,
                   issuing_authority, issue_date, expiry_date, status, metadata,
                   original_filename, storage_path, mime_type, size_bytes, sha256,
                   verification_status, uploaded_by)
                values
                  (:id, :employee_id, :document_type, null, :document_number,
                   :issuing_authority, :issue_date, :expiry_date, 'VALID', cast(:metadata as jsonb),
                   :original_filename, :storage_path, :mime_type, :size_bytes, :sha256,
                   'PENDING_REVIEW', :uploaded_by)
                returning id, employee_id, document_type, original_filename, mime_type,
                          size_bytes, document_number, issuing_authority, issue_date,
                          expiry_date, status, verification_status, metadata, sha256, created_at
            """),
            {
                "id": str(doc_id),
                "employee_id": str(employee_id),
                "document_type": document_type,
                "document_number": document_number,
                "issuing_authority": issuing_authority,
                "issue_date": issue_date or None,
                "expiry_date": expiry_date or None,
                "metadata": json.dumps(metadata),
                "original_filename": file.filename or f"{document_type}.{ext}",
                "storage_path": storage_path,
                "mime_type": mime,
                "size_bytes": len(content),
                "sha256": sha256,
                "uploaded_by": current_user.id,
            },
        ).mappings().one()
        audit(db,employee_id,current_user,'DOCUMENT_UPLOAD',employee['version'],{'document_id':str(doc_id),'document_type':document_type})
        refresh_compliance(db,employee_id)
        db.commit()
    except Exception:
        db.rollback()
        try:
            _storage_request(
                "DELETE",
                f"object/{settings.EMPLOYEE_DOCUMENT_BUCKET}",
                body=json.dumps({"prefixes": [storage_path]}).encode(),
                content_type="application/json",
            )
        except Exception:
            pass
        raise HTTPException(500, "Document metadata could not be saved after storage upload.")

    return {
        **dict(row),
        "employee_code": employee["employee_code"],
        "integrity": "PASSED",
        "verification": "PENDING_REVIEW",
    }

@router.post("/{employee_id}/documents/{document_id}/sign")
def sign_document(employee_id: UUID, document_id: UUID, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    row = db.execute(
        text("select storage_path from employee_documents where id=:doc and employee_id=:employee"),
        {"doc": str(document_id), "employee": str(employee_id)},
    ).mappings().first()
    if not row or not row["storage_path"]:
        raise HTTPException(404, "Document not found.")
    status, payload = _storage_request(
        "POST",
        f"object/sign/{settings.EMPLOYEE_DOCUMENT_BUCKET}/{urllib.parse.quote(row['storage_path'], safe='/')}",
        body=json.dumps({"expiresIn": 60}).encode(),
        content_type="application/json",
    )
    signed = payload.get("signedURL")
    if not signed:
        raise HTTPException(502, "Storage did not return a signed URL.")
    base, _ = _storage_config()
    return {"url": f"{base}/storage/v1{signed}", "expires_in": 60}

@router.patch("/{employee_id}/documents/{document_id}/verify")
def verify_document(employee_id: UUID, document_id: UUID, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    if not has_permission(db,current_user,'employees.approve'): raise HTTPException(403,'Employee approval permission is required to verify documents.')
    person=joining_employee(db,employee_id,True)
    if person['status'].upper()=='TERMINATED': raise HTTPException(409,'Terminated employee files are locked.')
    if person['status'].upper()=='PENDING_APPROVAL' and current_user.role.value!='OWNER':
        req=db.execute(text("select assigned_to from employee_approval_requests where employee_id=:id and status='PENDING'"),{'id':str(employee_id)}).first()
        if not req or req[0]!=current_user.id: raise HTTPException(403,'Only the assigned approver may review this submitted file.')
    status=str(payload.get('status','')).upper();notes=str(payload.get('notes') or '').strip()
    if status not in {'VERIFIED','REJECTED'}: raise HTTPException(422,'Choose VERIFIED or REJECTED.')
    if status=='REJECTED' and not notes: raise HTTPException(422,'Document rejection remarks are required.')
    doc=db.execute(text('select * from employee_documents where id=:doc and employee_id=:employee for update'),{'doc':str(document_id),'employee':str(employee_id)}).mappings().first()
    if not doc: raise HTTPException(404,'Document not found.')
    if status=='VERIFIED':
        from app.services.employee_workflow import doc_valid
        if not doc_valid({**doc,'verification_status':'PENDING_REVIEW'}): raise HTTPException(422,'The document is expired, incomplete or was rejected. Upload a valid replacement.')
    db.execute(text('update employee_documents set verification_status=:status,verification_notes=:notes,verified_by=:user,verified_at=now(),updated_at=now() where id=:doc'),{'status':status,'notes':notes or None,'user':current_user.id,'doc':str(document_id)})
    audit(db,employee_id,current_user,'DOCUMENT_REVIEW',person['version'],{'document_id':str(document_id),'status':status,'remarks':notes})
    refresh_compliance(db,employee_id);db.commit()
    return {'id':str(document_id),'verification_status':status,'verification_notes':notes}

def employee_code_safe(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum() or ch in "-_")
