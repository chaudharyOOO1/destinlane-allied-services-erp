from datetime import date
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import require_ops_or_admin
from app.core.database import get_db

router=APIRouter()

@router.get("")
def list_rosters(db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    q="""select r.*,s.site_name,s.site_code,e.id employee_id,e.employee_code,e.name,
      coalesce(sp.is_bench_locked,false) as is_bench_locked,
      sp.bench_lock_reason
      from shift_rosters r
      join sites s on s.id=r.site_id
      join guard_profiles g on g.id=r.guard_id
      left join employees e on e.id=g.employee_id
      left join staff_profiles sp on sp.employee_id=g.employee_id
      order by r.date desc,r.created_at desc"""
    return [dict(r) for r in db.execute(text(q)).mappings().all()]

@router.get("/employees")
def roster_employees(db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    q="""select g.id guard_id,g.employee_id,g.badge_number,e.employee_code,e.name,e.status,
      sp.vertical,sp.category,coalesce(sp.is_bench_locked,false) as is_bench_locked
      from guard_profiles g join employees e on e.id=g.employee_id
      left join staff_profiles sp on sp.employee_id=g.employee_id
      where g.status::text='ACTIVE' and lower(coalesce(e.status,''))='active' and exists(select 1 from employee_joining_drafts jd where jd.employee_id=e.id and jd.status='APPROVED') and exists(select 1 from employee_documents cd where cd.employee_id=e.id and cd.document_type='POLICE_VERIFICATION' and cd.verification_status='VERIFIED' and cd.expiry_date>=current_date) and exists(select 1 from employee_documents cd where cd.employee_id=e.id and cd.document_type='MEDICAL_FITNESS' and cd.verification_status='VERIFIED' and cd.expiry_date>=current_date)
        and coalesce(sp.is_bench_locked,false)=false
      order by e.name"""
    return [dict(r) for r in db.execute(text(q)).mappings().all()]

@router.get("/shortfall-analysis")
def shortfall_analysis(
    analysis_date:date|None=Query(default=None),
    db:Session=Depends(get_db),
    current_user=Depends(require_ops_or_admin)
):
    target=analysis_date or date.today()
    sites=db.execute(text("""select id,site_name,site_code,shift_requirements from sites where is_active=true order by site_name""")).mappings().all()
    result=[]
    for site in sites:
        req=site["shift_requirements"] or {}
        for shift in ("DAY","NIGHT"):
            key="day_shift_guards" if shift=="DAY" else "night_shift_guards"
            required=int(req.get(key) or 0)
            active=int(db.execute(text("""select count(*) from shift_rosters r
              join guard_profiles g on g.id=r.guard_id
              left join staff_profiles sp on sp.employee_id=g.employee_id
              where r.site_id=:site_id and r.date=:d and r.shift_type=:shift
                and r.status in ('SCHEDULED','COMPLETED')
                and g.status::text='ACTIVE' and coalesce(sp.is_bench_locked,false)=false"""),
              {"site_id":site["id"],"d":target,"shift":shift}).scalar() or 0)
            gs=(1-(active/required)) if required else 0
            candidates=db.execute(text("""select g.id guard_id,e.id employee_id,e.name,e.employee_code,
              sp.vertical,sp.category
              from guard_profiles g join employees e on e.id=g.employee_id
              left join staff_profiles sp on sp.employee_id=g.employee_id
              where g.status::text='ACTIVE' and lower(coalesce(e.status,''))='active' and exists(select 1 from employee_joining_drafts jd where jd.employee_id=e.id and jd.status='APPROVED') and exists(select 1 from employee_documents cd where cd.employee_id=e.id and cd.document_type='POLICE_VERIFICATION' and cd.verification_status='VERIFIED' and cd.expiry_date>=current_date) and exists(select 1 from employee_documents cd where cd.employee_id=e.id and cd.document_type='MEDICAL_FITNESS' and cd.verification_status='VERIFIED' and cd.expiry_date>=current_date)
                and coalesce(sp.is_bench_locked,false)=false
                and not exists(select 1 from shift_rosters x
                  where x.guard_id=g.id and x.date=:d and x.status in ('SCHEDULED','COMPLETED'))
              order by e.name limit 5"""),{"d":target}).mappings().all() if gs>0 else []
            result.append({"site_id":site["id"],"site_name":site["site_name"],"site_code":site["site_code"],
              "date":target.isoformat(),"shift_type":shift,"required":required,"active":active,
              "shortfall_index":round(gs,4),"vacancy":max(required-active,0),"replacement_suggestions":[dict(x) for x in candidates]})
    return result

def _assert_deployable(db,guard_id:int,roster_id:int|None=None):
    row=db.execute(text("""select g.id,g.employee_id,e.name,coalesce(sp.is_bench_locked,false) is_bench_locked,
      sp.bench_lock_reason,g.status::text guard_status
      from guard_profiles g join employees e on e.id=g.employee_id
      left join staff_profiles sp on sp.employee_id=g.employee_id
      where g.id=:guard_id"""),{"guard_id":guard_id}).mappings().first()
    if not row: raise HTTPException(404,"Staff member not found")
    if row["guard_status"]!="ACTIVE" or str(row.get("is_bench_locked")).lower()=="true":
        reason=row.get("bench_lock_reason") or "Staff member is not active for deployment."
        raise HTTPException(400,f"Staff member is locked to Bench due to compliance: {reason}")
    from app.services.employee_workflow import compliance_reasons, employee
    person=employee(db,row["employee_id"])
    if person["status"].upper()!="ACTIVE" or compliance_reasons(db,row["employee_id"]): raise HTTPException(409,"Employee joining or mandatory compliance is incomplete.")
    return row

@router.post("",status_code=201)
def create_roster(payload:dict,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    for k in ("site_id","guard_id","date","shift_type"):
        if not payload.get(k): raise HTTPException(422,f"Missing required field: {k}")
    _assert_deployable(db,int(payload["guard_id"]))
    conflict=db.execute(text("""select r.id,s.site_name,r.shift_type from shift_rosters r
      join sites s on s.id=r.site_id
      where r.guard_id=:guard_id and r.date=:d and r.status in ('SCHEDULED','COMPLETED')"""),
      {"guard_id":int(payload["guard_id"]),"d":payload["date"]}).mappings().first()
    if conflict:
        raise HTTPException(409,f"Shift collision detected for guard across sites (existing: {conflict['site_name']} / {conflict['shift_type']}).")
    allowed=["site_id","guard_id","date","shift_type","status","notes"]
    data={k:payload[k] for k in allowed if k in payload};data.setdefault("status","SCHEDULED")
    try:
        row=db.execute(text("""insert into shift_rosters(site_id,guard_id,date,shift_type,status,notes)
          values(:site_id,:guard_id,:date,:shift_type,:status,:notes) returning *"""),data).mappings().one()
        db.commit();return dict(row)
    except Exception as exc:
        db.rollback();raise HTTPException(409,str(exc).split("\n")[0])

@router.patch("/{roster_id}")
def update_roster(roster_id:int,payload:dict,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    allowed={"site_id","guard_id","date","shift_type","status","notes"}
    data={k:v for k,v in payload.items() if k in allowed}
    if not data: raise HTTPException(422,"No editable fields supplied")
    existing=db.execute(text("select * from shift_rosters where id=:id"),{"id":roster_id}).mappings().first()
    if not existing: raise HTTPException(404,"Roster not found")
    guard_id=int(data.get("guard_id",existing["guard_id"])); roster_date=data.get("date",existing["date"])
    _assert_deployable(db,guard_id,roster_id)
    conflict=db.execute(text("""select r.id,s.site_name,r.shift_type from shift_rosters r
      join sites s on s.id=r.site_id
      where r.guard_id=:guard_id and r.date=:d and r.id<>:id and r.status in ('SCHEDULED','COMPLETED')"""),
      {"guard_id":guard_id,"d":roster_date,"id":roster_id}).mappings().first()
    if conflict: raise HTTPException(409,f"Shift collision detected for guard across sites (existing: {conflict['site_name']} / {conflict['shift_type']}).")
    data["id"]=roster_id;sets=", ".join(f"{k}=:{k}" for k in data if k!="id")
    try:
        row=db.execute(text(f"update shift_rosters set {sets},updated_at=now() where id=:id returning *"),data).mappings().first()
        db.commit();return dict(row)
    except Exception as exc:
        db.rollback();raise HTTPException(409,str(exc).split("\n")[0])
