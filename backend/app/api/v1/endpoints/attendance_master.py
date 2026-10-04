import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_staff, require_ops_or_admin
from app.core.database import get_db
from app.core.geofence import validate_geofence

router = APIRouter()


@router.get("")
def list_attendance(db: Session = Depends(get_db), current_user=Depends(require_ops_or_admin)):
    q = """select a.*,e.employee_code,e.name,s.site_name from attendance a
    join employees e on e.id=a.employee_id left join shift_rosters r on r.id=a.roster_id
    left join sites s on s.id=r.site_id order by a.attendance_date desc,a.created_at desc"""
    return [dict(r) for r in db.execute(text(q)).mappings().all()]



@router.get("/my-rosters")
def my_rosters(db: Session = Depends(get_db), current_user=Depends(require_admin_or_staff)):
    q = """select r.*,s.site_name,s.site_code,s.latitude,s.longitude,
      coalesce(s.geofence_radius_meters,100) geofence_radius_meters,
      a.id attendance_id,a.check_in_time,a.check_out_time,a.verification_status
      from shift_rosters r join guard_profiles g on g.id=r.guard_id
      join sites s on s.id=r.site_id left join attendance a on a.roster_id=r.id
      where g.user_id=:user_id and r.date >= current_date and r.status='SCHEDULED'
      order by r.date asc,r.id asc limit 7"""
    return [dict(r) for r in db.execute(text(q), {"user_id": current_user.id}).mappings().all()]


@router.post("/punch")
def punch_attendance(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_admin_or_staff)):
    for key in ("roster_id", "latitude", "longitude", "device_id"):
        if payload.get(key) in (None, ""):
            raise HTTPException(422, f"{key} is required")
    roster_id = int(payload["roster_id"])
    roster = db.execute(text("""select r.*,g.user_id,g.employee_id,s.site_name,s.latitude site_lat,
      s.longitude site_lng,coalesce(s.geofence_radius_meters,100) radius_m
      from shift_rosters r join guard_profiles g on g.id=r.guard_id
      join sites s on s.id=r.site_id where r.id=:id for update of r"""), {"id": roster_id}).mappings().first()
    if not roster:
        raise HTTPException(404, "Roster not found")
    if roster["status"] != "SCHEDULED": raise HTTPException(409,"This deployment is no longer scheduled.")
    if current_user.role.value == "STAFF" and roster["user_id"] != current_user.id:
        raise HTTPException(403, "Staff may only punch their own assigned roster")
    from app.api.v1.endpoints.roster_master import _assert_deployable
    _assert_deployable(db,roster["guard_id"])
    if roster["site_lat"] is None or roster["site_lng"] is None:
        raise HTTPException(409, "Site GPS coordinates are not configured")

    try:
        staff_lat, staff_lng = float(payload["latitude"]), float(payload["longitude"])
    except (TypeError, ValueError):
        raise HTTPException(422, "latitude and longitude must be numeric")
    within, distance = validate_geofence(float(roster["site_lat"]), float(roster["site_lng"]), staff_lat, staff_lng, float(roster["radius_m"] or 100))
    device_hash = hashlib.sha256(str(payload["device_id"]).encode("utf-8")).hexdigest()
    existing = db.execute(text("select * from attendance where roster_id=:roster_id limit 1"), {"roster_id": roster_id}).mappings().first()
    if existing and existing.get("device_id_hash") and existing["device_id_hash"] != device_hash:
        raise HTTPException(409, "Device binding mismatch for this roster")
    if not within:
        raise HTTPException(400, f"OUT_OF_GEOFENCE: {distance}m from site; allowed radius is {roster['radius_m']}m")

    now = datetime.now(timezone.utc)
    if not existing:
        row = db.execute(text("""insert into attendance
          (roster_id,employee_id,attendance_date,status,check_in_time,check_in_lat,check_in_lng,
           check_in_distance_m,device_id_hash,is_geofence_verified,verification_status,is_late_punch)
          values (:roster_id,:employee_id,current_date,'present',:now,:lat,:lng,:distance,:device_hash,true,'VERIFIED',false)
          returning *"""), {"roster_id": roster_id, "employee_id": roster["employee_id"], "now": now,
          "lat": staff_lat, "lng": staff_lng, "distance": distance, "device_hash": device_hash}).mappings().one()
        db.commit()
        return {**dict(row), "action": "CHECK_IN", "distance_m": distance, "verification_status": "VERIFIED"}

    if existing.get("check_out_time"):
        raise HTTPException(409, "Attendance is already checked out")
    check_in = existing.get("check_in_time")
    elapsed = max(0.0, (now - check_in).total_seconds() / 3600) if check_in else 0.0
    regular_hours = min(elapsed, 8.0)
    overtime_hours = max(0.0, elapsed - 8.0)
    row = db.execute(text("""update attendance set check_out_time=:now,check_out_lat=:lat,check_out_lng=:lng,
      check_out_distance_m=:distance,overtime_hours=:ot,shift_hours=:regular_hours,
      is_geofence_verified=true,verification_status='VERIFIED' where id=:id returning *"""),
      {"now": now, "lat": staff_lat, "lng": staff_lng, "distance": distance, "ot": round(overtime_hours,2),
       "regular_hours": round(regular_hours,2), "id": existing["id"]}).mappings().one()
    db.commit()
    return {**dict(row), "action": "CHECK_OUT", "distance_m": distance, "regular_hours": round(regular_hours,2), "overtime_hours": round(overtime_hours,2)}


@router.patch("/{attendance_id}")
def update_attendance(attendance_id: str, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_ops_or_admin)):
    allowed={"status","shift_hours","overtime_hours","late_minutes","violation_type","client_verified","verification_status","verified_at"}
    data={k:v for k,v in payload.items() if k in allowed}
    if not data: raise HTTPException(422,"No editable fields supplied")
    data["id"]=attendance_id
    sets=", ".join(f"{k}=:{k}" for k in data if k!="id")
    row=db.execute(text(f"update attendance set {sets} where id=cast(:id as uuid) returning *"),data).mappings().first()
    if not row: db.rollback(); raise HTTPException(404,"Attendance not found")
    db.commit(); return dict(row)
