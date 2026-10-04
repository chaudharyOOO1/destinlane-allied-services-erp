from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
import json

from app.api.deps import require_hr_or_admin
from app.core.database import get_db

router = APIRouter()
VERTICALS = {"SECURITY", "HOUSEKEEPING", "NURSING"}
CATEGORIES = {
    "SECURITY": {"GUARD", "GUNMAN", "SUPERVISOR", "FIELD_OFFICER"},
    "HOUSEKEEPING": {"JANITOR", "CLEANER", "FACILITY_ATTENDANT"},
    "NURSING": {"GDA", "NURSE_ASSISTANT", "HOSPITAL_ATTENDANT"},
}

def verhoeff(number: str) -> bool:
    if not number.isdigit() or len(number) != 12:
        return False
    d=[[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,1,6,4,2],[8,7,9,0,6,4,3,5,2,1],[6,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,1,6,4,2],[8,7,9,0,6,4,3,5,2,1],[6,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4]]
    p=[[0,1,2,3,4,5,6,7,8,9],[0,5,7,8,9,4,2,1,3,6],[0,8,1,4,6,3,5,9,7,2],[0,9,4,7,2,6,3,8,5,1],[0,4,8,1,6,2,9,5,7,3],[0,2,9,5,1,7,4,8,6,3],[0,7,3,6,4,5,2,9,8,1],[0,3,5,2,7,9,8,6,1,4]]
    c=0
    for i,n in enumerate(reversed(number)): c=d[c][p[i%8][int(n)]]
    return c==0

def validate(payload):
    v=str(payload.get("vertical","")).upper()
    cat=str(payload.get("category","")).upper()
    if v not in VERTICALS: raise HTTPException(422,"Invalid staff vertical.")
    if cat and cat not in CATEGORIES[v]: raise HTTPException(422,"Invalid category for selected vertical.")
    return v,cat

@router.get("")
def list_candidates(db: Session=Depends(get_db), current_user=Depends(require_hr_or_admin)):
    return [dict(r) for r in db.execute(text("select * from recruitment_candidates order by created_at desc")).mappings().all()]

@router.post("",status_code=201)
def create_candidate(payload: dict, db: Session=Depends(get_db), current_user=Depends(require_hr_or_admin)):
    v,cat=validate(payload)
    if not payload.get("full_name") or not payload.get("phone"): raise HTTPException(422,"Full name and phone are required.")
    cid=payload.get("candidate_id") or f"CND-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:6].upper()}"
    row=db.execute(text("""insert into recruitment_candidates(candidate_id,full_name,phone,vertical,category,documents)
      values(:cid,:name,:phone,:vertical,:category,cast(:docs as jsonb)) returning *"""),
      {"cid":cid,"name":payload["full_name"],"phone":payload["phone"],"vertical":v,"category":cat or None,"docs":json.dumps(payload.get("documents") or {})}).mappings().one()
    db.commit(); return dict(row)

@router.patch("/{candidate_id}")
def update_candidate(candidate_id:str,payload:dict,db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    row=db.execute(text("select * from recruitment_candidates where candidate_id=:id"),{"id":candidate_id}).mappings().first()
    if not row: raise HTTPException(404,"Candidate not found.")
    status=str(payload.get("status",row["status"])).upper()
    if status not in {"APPLIED","VERIFIED","ONBOARDED"}: raise HTTPException(422,"Invalid recruitment status.")
    if status=="ONBOARDED": raise HTTPException(409,"Use the onboarding endpoint to create the staff record.")
    db.execute(text("update recruitment_candidates set status=:status,verified_at=case when :status='VERIFIED' then now() else verified_at end,updated_at=now() where candidate_id=:id"),{"id":candidate_id,"status":status})
    db.commit(); return dict(db.execute(text("select * from recruitment_candidates where candidate_id=:id"),{"id":candidate_id}).mappings().one())

@router.post("/{candidate_id}/onboard",status_code=201)
def onboard_candidate(candidate_id:str,payload:dict|None=None,db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    raise HTTPException(409,"Create the employee intimation in Employee Creation; recruitment cannot bypass joining approval.")
