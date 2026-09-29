from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_hr_or_admin, require_admin, get_current_active_user
from app.api.permissions import has_permission
from app.core.database import get_db
from app.models.user import User

router = APIRouter()

REQUIRED_DOCUMENTS = {"FORM_11", "POLICE_VERIFICATION", "MEDICAL_FITNESS", "BANK_PASSBOOK", "AADHAAR", "PAN"}

def _employee_joining_payload(db: Session, employee_id: str):
    row = db.execute(text("""
        select e.*, i.intimation_id as source_intimation_id, i.name as intimation_name,
               i.status as intimation_status, d.status as joining_status, d.last_saved_at
        from public.employees e
        left join public.employee_joining_drafts d on d.employee_id=e.id
        left join public.employee_intimations i on i.id=d.intimation_id
        where e.id=:id
    """), {"id": employee_id}).mappings().first()
    return dict(row) if row else None

@router.post("/intimations", status_code=201)
def create_intimation(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(require_hr_or_admin)):
    if not payload.get("name"):
        raise HTTPException(422, "Employee name is required for intimation.")
    row = db.execute(text("""
        insert into public.employee_intimations
          (name, phone, designation, category, client_id, notes, created_by)
        values (:name,:phone,:designation,:category,:client_id,:notes,:created_by)
        returning *
    """), {
        "name": payload["name"].strip(),
        "phone": payload.get("phone"),
        "designation": payload.get("designation"),
        "category": payload.get("category"),
        "client_id": payload.get("client_id"),
        "notes": payload.get("notes"),
        "created_by": current_user.id,
    }).mappings().one()
    db.commit()
    return dict(row)

@router.get("/intimations")
def list_intimations(db: Session = Depends(get_db), current_user: User = Depends(require_hr_or_admin)):
    rows = db.execute(text("""
        select i.*, e.id as employee_id, e.employee_code, e.status as employee_status,
               d.status as joining_status
        from public.employee_intimations i
        left join public.employee_joining_drafts d on d.intimation_id=i.id
        left join public.employees e on e.id=d.employee_id
        order by i.created_at desc
    """)).mappings().all()
    return [dict(r) for r in rows]

@router.post("/intimations/{intimation_id}/create", status_code=201)
def create_employee_from_intimation(intimation_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_hr_or_admin)):
    info = db.execute(text("select * from public.employee_intimations where id=:id"), {"id": str(intimation_id)}).mappings().first()
    if not info:
        raise HTTPException(404, "Intimation not found.")
    existing = db.execute(text("select employee_id from public.employee_joining_drafts where intimation_id=:id"), {"id": str(intimation_id)}).first()
    if existing:
        return _employee_joining_payload(db, str(existing.employee_id))

    try:
        row = db.execute(text("""
            insert into public.employees
              (name, phone, designation, category, client_id, intimation_id, status)
            values
              (:name,:phone,:designation,:category,:client_id,:intimation_id,'DRAFT')
            returning *
        """), {
            "name": info["name"],
            "phone": info["phone"],
            "designation": info["designation"],
            "category": info["category"] or "GUARD",
            "client_id": info["client_id"],
            "intimation_id": info["intimation_id"],
        }).mappings().one()

        db.execute(text("""
            insert into public.employee_joining_drafts(intimation_id, employee_id, created_by)
            values (:intimation_id,:employee_id,:created_by)
        """), {"intimation_id": str(intimation_id), "employee_id": str(row["id"]), "created_by": current_user.id})
        db.execute(text("update public.employee_intimations set status='JOINING' where id=:id"), {"id": str(intimation_id)})
        db.commit()
        return _employee_joining_payload(db, str(row["id"]))
    except Exception as exc:
        db.rollback()
        raise HTTPException(409, str(exc).split("\n")[0])

@router.get("/joining")
def list_joining(db: Session = Depends(get_db), current_user: User = Depends(require_hr_or_admin)):
    rows = db.execute(text("""
        select e.id, e.employee_code, e.name, e.phone, e.designation, e.category, e.client_id,
               e.status as employee_status, i.intimation_id, i.created_at as intimation_created_at,
               d.status as joining_status, d.last_saved_at,
               coalesce((select count(*) from public.employee_documents ed where ed.employee_id=e.id),0) as document_count
        from public.employee_joining_drafts d
        join public.employees e on e.id=d.employee_id
        join public.employee_intimations i on i.id=d.intimation_id
        order by d.updated_at desc
    """)).mappings().all()
    return [dict(r) for r in rows]

@router.get("/joining/{employee_id}")
def get_joining(employee_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_hr_or_admin)):
    result = _employee_joining_payload(db, str(employee_id))
    if not result:
        raise HTTPException(404, "Joining record not found.")
    return result

@router.patch("/joining/{employee_id}")
def save_joining_draft(employee_id: UUID, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(require_hr_or_admin)):
    exists = db.execute(text("select id from public.employee_joining_drafts where employee_id=:id and status in ('DRAFT','REJECTED')"), {"id": str(employee_id)}).first()
    if not exists:
        raise HTTPException(409, "This employee joining record is no longer editable.")
    allowed = {
        "name","phone","dob","gender","designation","client_id","site_id","joining_date","category",
        "aadhaar_no","pan_no","permanent_address","present_address","emergency_contact","marital_status",
        "status_reason"
    }
    data = {k:v for k,v in payload.items() if k in allowed}
    if not data:
        return _employee_joining_payload(db, str(employee_id))
    data["id"]=str(employee_id)
    sets=", ".join(f"{k}=:{k}" for k in data if k!="id")
    row=db.execute(text(f"update public.employees set {sets} where id=:id returning id"), data).first()
    if not row:
        db.rollback()
        raise HTTPException(404, "Employee not found.")
    bank_keys={"bank_account_no","bank_name","bank_branch","bank_ifsc"}
    bank_present=any(payload.get(k) for k in bank_keys)
    if bank_present:
        if not all(payload.get(k) for k in bank_keys):
            db.rollback()
            raise HTTPException(422, "Complete all bank fields before saving the bank section.")
        db.execute(text("""
            insert into public.employee_bank_accounts
              (employee_id,account_number,bank_name,branch,ifsc_code,ifsc_verified)
            values (:id,:account_number,:bank_name,:branch,:ifsc_code,:verified)
            on conflict (employee_id) do update set
              account_number=excluded.account_number, bank_name=excluded.bank_name,
              branch=excluded.branch, ifsc_code=excluded.ifsc_code,
              ifsc_verified=excluded.ifsc_verified, updated_at=now()
        """), {
            "id": str(employee_id), "account_number": payload["bank_account_no"],
            "bank_name": payload["bank_name"], "branch": payload["bank_branch"],
            "ifsc_code": str(payload["bank_ifsc"]).strip().upper(),
            "verified": bool(payload.get("ifsc_verified", False))
        })
    if payload.get("nominee_name"):
        existing_nominee=db.execute(text("select id from public.employee_nominees where employee_id=:id limit 1"), {"id": str(employee_id)}).first()
        if existing_nominee:
            db.execute(text("""
                update public.employee_nominees
                set nominee_name=:name, relation=:relation, dob=:dob,
                    aadhaar_no=:aadhaar, allocation_percentage=:percentage
                where id=:nominee_id
            """), {
                "nominee_id": existing_nominee[0], "name": payload.get("nominee_name"),
                "relation": payload.get("nominee_relation"), "dob": payload.get("nominee_dob"),
                "aadhaar": payload.get("nominee_aadhaar"), "percentage": payload.get("nominee_percentage") or 100
            })
        else:
            db.execute(text("""
                insert into public.employee_nominees
                  (employee_id,nominee_name,relation,dob,aadhaar_no,allocation_percentage)
                values (:id,:name,:relation,:dob,:aadhaar,:percentage)
            """), {
                "id": str(employee_id), "name": payload.get("nominee_name"),
                "relation": payload.get("nominee_relation"), "dob": payload.get("nominee_dob"),
                "aadhaar": payload.get("nominee_aadhaar"), "percentage": payload.get("nominee_percentage") or 100
            })
    db.execute(text("update public.employee_joining_drafts set status='DRAFT', last_saved_at=now(), updated_at=now() where employee_id=:id"), {"id": str(employee_id)})
    db.execute(text("update public.employee_intimations set status='JOINING', updated_at=now() where id=(select intimation_id from public.employee_joining_drafts where employee_id=:id)"), {"id": str(employee_id)})
    db.commit()
    return _employee_joining_payload(db, str(employee_id))

@router.post("/joining/{employee_id}/submit")
def submit_joining(employee_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_hr_or_admin)):
    emp = db.execute(text("select * from public.employees where id=:id"), {"id": str(employee_id)}).mappings().first()
    draft = db.execute(text("select * from public.employee_joining_drafts where employee_id=:id"), {"id": str(employee_id)}).mappings().first()
    if not emp or not draft:
        raise HTTPException(404, "Employee joining draft not found.")
    if draft["status"] not in ("DRAFT","REJECTED"):
        raise HTTPException(409, "This joining record is not ready for submission.")
    required = ["name","phone","dob","gender","designation","client_id","joining_date","category","aadhaar_no","pan_no","permanent_address","present_address","emergency_contact"]
    missing=[k for k in required if not emp.get(k)]
    if missing:
        raise HTTPException(422, "Complete required employee details before submission: " + ", ".join(missing))
    docs = {r[0] for r in db.execute(text("select document_type from public.employee_documents where employee_id=:id"), {"id": str(employee_id)}).all()}
    missing_docs = sorted(REQUIRED_DOCUMENTS - docs)
    if missing_docs:
        raise HTTPException(422, "Upload required documents before submission: " + ", ".join(missing_docs))
    category = db.execute(text("""
        select * from public.employee_approval_categories
        where task_type='EMPLOYEE_JOINING' and is_active=true and approver_user_id is not null
        order by sequence_order asc, id asc limit 1
    """)).mappings().first()
    final_category = db.execute(text("""
        select 1 from public.employee_approval_categories
        where task_type='EMPLOYEE_JOINING' and is_active=true
          and is_final_approver=true and approver_user_id is not null
    """)).first()
    if not category:
        raise HTTPException(409, "No approver is assigned for Employee Joining. Set an approver in Approver Setup first.")
    if not final_category:
        raise HTTPException(409, "A final approver must be assigned in Approver Setup before an employee can be submitted.")
    if db.execute(text("select 1 from public.employee_approval_requests where employee_id=:id and status='PENDING'"), {"id": str(employee_id)}).first():
        raise HTTPException(409, "This employee is already pending approval.")
    req = db.execute(text("""
        insert into public.employee_approval_requests
          (employee_id,category_id,assigned_to,submitted_by,status,submitted_at)
        values (:employee_id,:category_id,:assigned_to,:submitted_by,'PENDING',now())
        returning *
    """), {
        "employee_id": str(employee_id), "category_id": category["id"],
        "assigned_to": category["approver_user_id"], "submitted_by": current_user.id
    }).mappings().one()
    db.execute(text("update public.employee_joining_drafts set status='PENDING_APPROVAL',last_saved_at=now(),updated_at=now() where employee_id=:id"), {"id": str(employee_id)})
    db.execute(text("update public.employees set status='PENDING_APPROVAL' where id=:id"), {"id": str(employee_id)})
    db.commit()
    return dict(req)

@router.get("/approvals")
def list_approvals(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = db.execute(text("""
        select ar.*, e.employee_code, e.name, e.phone, e.designation, e.category,
               c.category_name, u.full_name as assigned_to_name
        from public.employee_approval_requests ar
        join public.employees e on e.id=ar.employee_id
        left join public.employee_approval_categories c on c.id=ar.category_id
        left join public.users u on u.id=ar.assigned_to
        where ar.status='PENDING'
        order by ar.submitted_at asc
    """)).mappings().all()
    return [dict(r) for r in rows if current_user.role.value in {"OWNER","SUPER_ADMIN","ADMIN"} or r["assigned_to"] == current_user.id]

@router.post("/approvals/{approval_id}/decision")
def decide_approval(approval_id: UUID, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if not has_permission(db, current_user, "employees.approve"):
        raise HTTPException(403, "Approval permission is required.")
    request = db.execute(text("select * from public.employee_approval_requests where id=:id"), {"id": str(approval_id)}).mappings().first()
    if not request:
        raise HTTPException(404, "Approval request not found.")
    if request["status"] != "PENDING":
        raise HTTPException(409, "This approval request is already decided.")
    if request["assigned_to"] != current_user.id and current_user.role.value not in {"OWNER","SUPER_ADMIN","ADMIN"}:
        raise HTTPException(403, "This approval is assigned to another approver.")
    decision = str(payload.get("decision","")).upper()
    if decision not in {"APPROVE","REJECT"}:
        raise HTTPException(422, "Decision must be APPROVE or REJECT.")
    remarks = (payload.get("remarks") or "").strip() or None
    category = db.execute(text("select * from public.employee_approval_categories where id=:id"), {"id": request["category_id"]}).mappings().first()
    if decision == "REJECT":
        db.execute(text("""
            update public.employee_approval_requests
            set status='REJECT', remarks=:remarks, decided_by=:decided_by, decided_at=now()
            where id=:id
        """), {"remarks": remarks, "decided_by": current_user.id, "id": str(approval_id)})
        db.execute(text("update public.employees set status='REJECTED' where id=:id"), {"id": str(request["employee_id"])})
        db.execute(text("update public.employee_joining_drafts set status='REJECTED',updated_at=now() where employee_id=:id"), {"id": str(request["employee_id"])})
        db.commit()
        return {"status":"REJECT","employee_id":str(request["employee_id"]),"remarks":remarks}

    db.execute(text("""
        update public.employee_approval_requests
        set status='APPROVED', remarks=:remarks, decided_by=:decided_by, decided_at=now()
        where id=:id
    """), {"remarks": remarks, "decided_by": current_user.id, "id": str(approval_id)})

    if category and category["is_final_approver"]:
        db.execute(text("update public.employees set status='ACTIVE' where id=:id"), {"id": str(request["employee_id"])})
        db.execute(text("update public.employee_joining_drafts set status='APPROVED',updated_at=now() where employee_id=:id"), {"id": str(request["employee_id"])})
        db.execute(text("update public.employee_intimations set status='APPROVED',updated_at=now() where id=(select intimation_id from public.employee_joining_drafts where employee_id=:id)"), {"id": str(request["employee_id"])})
        db.commit()
        return {"status":"APPROVED","employee_id":str(request["employee_id"]),"remarks":remarks,"final":True}

    next_category = db.execute(text("""
        select * from public.employee_approval_categories
        where task_type='EMPLOYEE_JOINING' and is_active=true
          and approver_user_id is not null
          and sequence_order > :current_order
        order by sequence_order asc, id asc limit 1
    """), {"current_order": category["sequence_order"] if category else 0}).mappings().first()
    if not next_category:
        db.rollback()
        raise HTTPException(409, "This approval is not marked final and no next approver is configured.")

    db.execute(text("""
        insert into public.employee_approval_requests
          (employee_id,category_id,assigned_to,submitted_by,status,submitted_at)
        values (:employee_id,:category_id,:assigned_to,:submitted_by,'PENDING',now())
    """), {
        "employee_id":str(request["employee_id"]), "category_id":next_category["id"],
        "assigned_to":next_category["approver_user_id"], "submitted_by":current_user.id
    })
    db.commit()
    return {"status":"APPROVED","employee_id":str(request["employee_id"]),"remarks":remarks,"next_approver":next_category["approver_user_id"],"final":False}eturn {"status": decision, "employee_id": str(request["employee_id"]), "remarks": remarks}

@router.get("/approval-categories")
def list_approval_categories(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    rows=db.execute(text("""
        select c.*, u.full_name as approver_name, u.email as approver_email
        from public.employee_approval_categories c
        left join public.users u on u.id=c.approver_user_id
        order by c.id
    """)).mappings().all()
    return [dict(r) for r in rows]

@router.put("/approval-categories/{category_id}")
def update_approval_category(category_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    approver_id = payload.get("approver_user_id")
    if approver_id in ("", None):
        approver_id = None
    else:
        approver_id = int(approver_id)
        user=db.execute(text("select id,is_active from public.users where id=:id"), {"id":approver_id}).mappings().first()
        if not user or not user["is_active"]:
            raise HTTPException(422, "Approver must be an active user.")
    is_final = bool(payload.get("is_final_approver", False))
    if is_final:
        db.execute(text("update public.employee_approval_categories set is_final_approver=false where id<>:id"), {"id": category_id})
    row=db.execute(text("""
        update public.employee_approval_categories
        set approver_user_id=:approver,is_final_approver=:is_final,updated_at=now()
        where id=:id returning *
    """), {"approver":approver_id,"is_final":is_final,"id":category_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Approval category not found.")
    db.commit()
    return dict(row)
