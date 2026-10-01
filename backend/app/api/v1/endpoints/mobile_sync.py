from datetime import datetime, timedelta, timezone
import hashlib
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.geofence import validate_geofence
from app.core.supabase_auth import create_supabase_signed_url, upload_supabase_storage

router = APIRouter()
mobile_oauth = OAuth2PasswordBearer(tokenUrl="/api/v1/mobile/login")


class MobileLoginRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=20)


class MobilePunchRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0, le=10000)
    device_id: str = Field(min_length=8, max_length=255)
    check_in_selfie_path: str | None = None
    check_out_selfie_path: str | None = None


def _clean_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else digits


def _mobile_token(employee_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=12)
    payload = {"sub": f"employee:{employee_id}", "mobile": True, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _mobile_employee_id(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("mobile") is not True:
            raise ValueError
        subject = payload.get("sub", "")
        if not subject.startswith("employee:"):
            raise ValueError
        return subject.split(":", 1)[1]
    except (JWTError, ValueError, TypeError):
        raise HTTPException(401, "Mobile session is invalid or expired.")


def get_mobile_employee(token: str = Depends(mobile_oauth), db: Session = Depends(get_db)):
    employee_id = _mobile_employee_id(token)
    row = db.execute(
        text(
            """
            select e.*, s.site_name, s.address site_address,
                   s.latitude site_latitude, s.longitude site_longitude,
                   coalesce(s.geofence_radius_meters,100) geofence_radius
            from employees e
            left join sites s on s.id=e.site_id
            where e.id=cast(:employee_id as uuid)
              and lower(coalesce(e.status,'')) not in ('inactive','terminated')
            """
        ),
        {"employee_id": employee_id},
    ).mappings().first()
    if not row:
        raise HTTPException(401, "Employee account is inactive or no longer exists.")
    return row


@router.post("/mobile/login")
def mobile_login(payload: MobileLoginRequest, db: Session = Depends(get_db)):
    phone = _clean_phone(payload.phone)
    if len(phone) != 10:
        raise HTTPException(422, "Enter a valid 10-digit phone number.")

    row = db.execute(
        text(
            """
            select e.id,e.employee_code,e.name,e.phone,e.status,e.designation,e.site_id,
                   s.site_name,s.address site_address,s.latitude site_latitude,
                   s.longitude site_longitude,coalesce(s.geofence_radius_meters,100) geofence_radius
            from employees e
            left join sites s on s.id=e.site_id
            where right(regexp_replace(coalesce(e.phone,''),'\D','','g'),10)=:phone
              and lower(coalesce(e.status,'')) not in ('inactive','terminated')
            order by e.created_at desc
            limit 1
            """
        ),
        {"phone": phone},
    ).mappings().first()

    if not row:
        raise HTTPException(401, "Phone number is not registered with DestinLane ERP.")

    return {
        "access_token": _mobile_token(str(row["id"])),
        "token_type": "bearer",
        "employee": dict(row),
    }


@router.post("/mobile/selfie")
async def mobile_selfie(
    employee=Depends(get_mobile_employee),
    file: UploadFile = File(...),
    kind: str = "check-in",
):
    if kind not in {"check-in", "check-out"}:
        raise HTTPException(422, "Invalid selfie type.")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Selfie must be a JPEG, PNG, or WebP image.")

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Selfie image is too large. Maximum size is 5 MB.")

    path = f"{employee['id']}/{datetime.now(timezone.utc).date().isoformat()}/{kind}-{uuid.uuid4().hex}.jpg"
    stored = upload_supabase_storage(
        bucket="employee-selfies",
        path=path,
        data=data,
        content_type=file.content_type,
    )
    if not stored:
        raise HTTPException(502, "Could not store the selfie securely.")

    return {
        "path": stored,
        "url": create_supabase_signed_url(bucket="employee-selfies", path=stored),
    }


@router.get("/mobile/me")
def mobile_me(employee=Depends(get_mobile_employee)):
    return dict(employee)


@router.get("/mobile/me/attendance")
def mobile_attendance(employee=Depends(get_mobile_employee), db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            select a.*,r.shift_type,r.date roster_date,s.site_name
            from attendance a
            left join shift_rosters r on r.id=a.roster_id
            left join sites s on s.id=r.site_id
            where a.employee_id=cast(:employee_id as uuid)
            order by a.attendance_date desc
            limit 100
            """
        ),
        {"employee_id": str(employee["id"])},
    ).mappings().all()

    result = []
    for row in rows:
        item = dict(row)
        for field in ("check_in_selfie_url", "check_out_selfie_url"):
            value = item.get(field)
            if value and not str(value).startswith("http"):
                item[field] = create_supabase_signed_url(bucket="employee-selfies", path=str(value))
        result.append(item)
    return result


@router.get("/mobile/me/salary")
def mobile_salary(employee=Depends(get_mobile_employee), db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            select id,employee_id,month,status,credited_date
            from salary_records
            where employee_id=cast(:employee_id as uuid)
            order by month desc
            limit 24
            """
        ),
        {"employee_id": str(employee["id"])},
    ).mappings().all()
    return [dict(row) for row in rows]


@router.post("/mobile/punch")
def mobile_punch(
    payload: MobilePunchRequest,
    employee=Depends(get_mobile_employee),
    db: Session = Depends(get_db),
):
    roster = db.execute(
        text(
            """
            select r.id,r.date,r.status,r.shift_type,
                   s.site_name,s.latitude site_lat,s.longitude site_lng,
                   coalesce(s.geofence_radius_meters,100) radius_m
            from shift_rosters r
            join guard_profiles g on g.id=r.guard_id
            join sites s on s.id=r.site_id
            where g.employee_id=cast(:employee_id as uuid)
              and r.date=current_date
              and r.status='SCHEDULED'
            order by r.id
            limit 1
            """
        ),
        {"employee_id": str(employee["id"])},
    ).mappings().first()

    if not roster:
        raise HTTPException(409, "No scheduled roster was found for you today.")
    if roster["site_lat"] is None or roster["site_lng"] is None:
        raise HTTPException(409, "Your assigned site does not have GPS coordinates configured.")

    within, distance = validate_geofence(
        float(roster["site_lat"]),
        float(roster["site_lng"]),
        payload.latitude,
        payload.longitude,
        float(roster["radius_m"] or 100),
    )
    if not within:
        raise HTTPException(
            400,
            f"OUT_OF_GEOFENCE: {round(distance)}m from site; allowed radius is {roster['radius_m']}m",
        )

    device_hash = hashlib.sha256(payload.device_id.encode("utf-8")).hexdigest()
    existing = db.execute(
        text(
            "select * from attendance "
            "where employee_id=cast(:employee_id as uuid) and attendance_date=current_date limit 1"
        ),
        {"employee_id": str(employee["id"])},
    ).mappings().first()

    if existing and existing.get("device_id_hash") and existing["device_id_hash"] != device_hash:
        raise HTTPException(409, "This attendance is bound to another device.")

    now = datetime.now(timezone.utc)

    if not existing:
        row = db.execute(
            text(
                """
                insert into attendance
                  (roster_id,employee_id,attendance_date,status,check_in_time,
                   check_in_selfie_url,check_in_latitude,check_in_longitude,check_in_accuracy,
                   check_in_lat,check_in_lng,check_in_distance_m,device_id_hash,
                   is_geofence_verified,verification_status,is_late_punch)
                values
                  (:roster_id,cast(:employee_id as uuid),current_date,'present',:now,
                   :selfie,:lat,:lng,:accuracy,:lat,:lng,:distance,:device_hash,
                   true,'VERIFIED',false)
                returning *
                """
            ),
            {
                "roster_id": roster["id"],
                "employee_id": str(employee["id"]),
                "now": now,
                "selfie": payload.check_in_selfie_path,
                "lat": payload.latitude,
                "lng": payload.longitude,
                "accuracy": payload.accuracy,
                "distance": distance,
                "device_hash": device_hash,
            },
        ).mappings().one()
        db.commit()
        return {**dict(row), "action": "CHECK_IN", "distance_m": distance}

    if existing.get("check_out_time"):
        raise HTTPException(409, "Today's attendance is already checked out.")

    check_in = existing.get("check_in_time")
    elapsed = max(0.0, (now - check_in).total_seconds() / 3600) if check_in else 0.0
    regular_hours = min(elapsed, 8.0)
    overtime_hours = max(0.0, elapsed - 8.0)

    row = db.execute(
        text(
            """
            update attendance set
              check_out_time=:now,
              check_out_selfie_url=:selfie,
              check_out_latitude=:lat,
              check_out_longitude=:lng,
              check_out_accuracy=:accuracy,
              check_out_lat=:lat,
              check_out_lng=:lng,
              check_out_distance_m=:distance,
              overtime_hours=:ot,
              shift_hours=:regular_hours,
              is_geofence_verified=true,
              verification_status='VERIFIED'
            where id=:id
            returning *
            """
        ),
        {
            "now": now,
            "selfie": payload.check_out_selfie_path,
            "lat": payload.latitude,
            "lng": payload.longitude,
            "accuracy": payload.accuracy,
            "distance": distance,
            "ot": round(overtime_hours, 2),
            "regular_hours": round(regular_hours, 2),
            "id": existing["id"],
        },
    ).mappings().one()
    db.commit()
    return {**dict(row), "action": "CHECK_OUT", "distance_m": distance}
