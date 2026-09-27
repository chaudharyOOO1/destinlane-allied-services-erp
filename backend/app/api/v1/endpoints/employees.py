from datetime import date\nfrom uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import require_hr_or_admin\nfrom app.api.v1.endpoints.recruitment import verhoeff
from app.core.database import get_db

router = APIRouter()

@router.get("")
def list_employees(db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    return [dict(r) for r in db.execute(text("select * from employees order by created_at desc")).mappings().all()]

@router.get("/ifsc/validate")
def validate_ifsc(ifsc: str = Query(..., min_length=11, max_length=11), db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    code = ifsc.strip().upper()
    if not __import__("re").fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", code):
        return {"valid": False}
    row = db.execute(text("select ifsc_code, bank_name, branch_name, address, city, district, state from ifsc_master where ifsc_code=:ifsc and approved=true"), {"ifsc": code}).mappings().first()
    return {"valid": bool(row), **(dict(row) if row else {})}


@router.post("", status_code=201)
def create_employee(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    required = ["name", "phone"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise HTTPException(422, f"Missing required fields: {', '.join(missing)}")

    category = str(payload.get("category") or "GUARD").upper()
    vertical = {"GUARD":"SECURITY","GUNMAN":"SECURITY","SUPERVISOR":"SECURITY","FIELD_OFFICER":"SECURITY","JANITOR":"HOUSEKEEPING","CLEANER":"HOUSEKEEPING","FACILITY_ATTENDANT":"HOUSEKEEPING","GDA":"NURSING","NURSE_ASSISTANT":"NURSING","HOSPITAL_ATTENDANT":"NURSING"}.get(category)
    if not vertical:
        raise HTTPException(422, "A valid employee category is required.")

    aadhaar = str(payload.get("aadhaar_no") or "").replace(" ", "")
    if aadhaar and not verhoeff(aadhaar):
        raise HTTPException(422, "Aadhaar failed 12-digit Verhoeff checksum validation.")

    bank_fields = ["bank_account_no", "bank_name", "bank_branch", "bank_ifsc"]
    bank_ifsc = str(payload.get("bank_ifsc") or "").strip().upper()
    if any(payload.get(k) for k in bank_fields):
        if not all(payload.get(k) for k in bank_fields):
            raise HTTPException(422, "Account number, bank name, branch and IFSC are all required.")
        if not __import__("re").fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", bank_ifsc):
            raise HTTPException(422, "Invalid IFSC format.")
        ifsc = db.execute(text("select ifsc_code, bank_name, branch_name, address, city, district, state from ifsc_master where ifsc_code=:ifsc and approved=true"), {"ifsc": bank_ifsc}).mappings().first()
        if not ifsc:
            raise HTTPException(422, "IFSC is not present in the approved bank database.")
    else:
        ifsc = None

    employee_code = str(payload.get("employee_code") or "").strip() or f"NL-EMP-{uuid4().hex[:8].upper()}"
    intimation_id = str(payload.get("intimation_id") or "").strip() or f"INT-{uuid4().hex[:8].upper()}"
    master = {
        "employee_code": employee_code, "name": payload["name"], "phone": payload["phone"], "status": str(payload.get("status") or "active").lower(),
        "intimation_id": intimation_id, "dob": payload.get("dob"), "gender": payload.get("gender"), "designation": payload.get("designation"),
        "branch": payload.get("branch"), "site_id": payload.get("site_id"), "joining_date": payload.get("joining_date"), "category": category,
        "aadhaar_no": aadhaar or None, "pan_no": payload.get("pan_no"), "permanent_address": payload.get("permanent_address"),
        "present_address": payload.get("present_address"), "emergency_contact": payload.get("emergency_contact"), "marital_status": payload.get("marital_status"),
        "status_reason": payload.get("status_reason"), "photo_url": payload.get("photo_url"),
    }

    try:
        cols = ", ".join(master); binds = ", ".join(f":{k}" for k in master)
        employee = db.execute(text(f"insert into employees ({cols}) values ({binds}) returning *"), master).mappings().one()
        employee_id = str(employee["id"])

        db.execute(text("""
            insert into staff_profiles(employee_id,intimation_id,vertical,category,status,aadhaar_number,pan_number,bank_account_no,bank_name,bank_ifsc,
              nominee_name,nominee_relation,nominee_aadhaar,arms_license_no,arms_expiry_date,arms_caliber,ammunition_count,
              uniform_total_cost,uniform_monthly_emi,uniform_balance_due,police_verification_expiry,medical_fitness_expiry,psara_cert_no,psara_training_expiry,gun_license_expiry)
            values(:employee_id,:intimation_id,:vertical,:category,:status,:aadhaar,:pan,:account_no,:bank_name,:ifsc,
              :nominee_name,:nominee_relation,:nominee_aadhaar,:arms_license_no,:arms_expiry_date,:arms_caliber,:ammunition_count,
              :uniform_total_cost,:uniform_monthly_emi,:uniform_balance_due,:police_expiry,:medical_expiry,:psara_cert_no,:psara_training_expiry,:gun_license_expiry)
        """), {
            "employee_id": employee_id, "intimation_id": intimation_id, "vertical": vertical, "category": category, "status": str(master["status"]).upper(),
            "aadhaar": aadhaar or None, "pan": payload.get("pan_no"), "account_no": payload.get("bank_account_no"), "bank_name": payload.get("bank_name"), "ifsc": bank_ifsc or None,
            "nominee_name": payload.get("nominee_name"), "nominee_relation": payload.get("nominee_relation"), "nominee_aadhaar": payload.get("nominee_aadhaar"),
            "arms_license_no": payload.get("gun_license_no"), "arms_expiry_date": payload.get("gun_license_expiry"), "arms_caliber": payload.get("arms_caliber"),
            "ammunition_count": payload.get("ammunition_count"), "uniform_total_cost": payload.get("uniform_total_cost") or 0, "uniform_monthly_emi": payload.get("uniform_monthly_emi") or 0,
            "uniform_balance_due": payload.get("uniform_balance_due") or payload.get("uniform_total_cost") or 0, "police_expiry": payload.get("police_verification_expiry"),
            "medical_expiry": payload.get("medical_fitness_expiry"), "psara_cert_no": payload.get("psara_batch_no"), "psara_training_expiry": payload.get("psara_training_expiry"),
            "gun_license_expiry": payload.get("gun_license_expiry"),
        })

        if ifsc:
            db.execute(text("insert into employee_bank_accounts(employee_id,account_number,bank_name,branch,ifsc_code,ifsc_verified) values(:employee_id,:account_number,:bank_name,:branch,:ifsc,true)"),
              {"employee_id": employee_id, "account_number": payload["bank_account_no"], "bank_name": ifsc["bank_name"], "branch": payload["bank_branch"], "ifsc": ifsc["ifsc_code"]})

        if payload.get("nominee_name"):
            percentage = float(payload.get("nominee_percentage") or 100)
            if not 0 < percentage <= 100:
                raise HTTPException(422, "Nominee allocation percentage must be between 0 and 100.")
            db.execute(text("insert into employee_nominees(employee_id,nominee_name,relation,dob,aadhaar_no,allocation_percentage) values(:employee_id,:name,:relation,:dob,:aadhaar,:percentage)"),
              {"employee_id": employee_id, "name": payload["nominee_name"], "relation": payload.get("nominee_relation"), "dob": payload.get("nominee_dob"), "aadhaar": payload.get("nominee_aadhaar"), "percentage": percentage})

        if category == "GUNMAN" and payload.get("gun_license_no"):
            db.execute(text("insert into employee_arms(employee_id,gun_license_number,issuing_authority,expiry_date,caliber,weapon_serial_number,ammunition_count,jurisdiction_limits) values(:employee_id,:license,:authority,:expiry,:caliber,:serial,:ammo,:jurisdiction)"),
              {"employee_id": employee_id, "license": payload.get("gun_license_no"), "authority": payload.get("arms_issuing_authority"), "expiry": payload.get("gun_license_expiry"), "caliber": payload.get("arms_caliber"), "serial": payload.get("weapon_serial_no"), "ammo": payload.get("ammunition_count") or 0, "jurisdiction": payload.get("jurisdiction_limits")})

        if any(payload.get(k) for k in ["uniform_shirt","uniform_trousers","uniform_shoes","uniform_belt","uniform_cap"]) or payload.get("uniform_total_cost") is not None:
            total = float(payload.get("uniform_total_cost") or 0); emi = float(payload.get("uniform_monthly_emi") or 0)
            if total < 0 or emi < 0 or emi > total:
                raise HTTPException(422, "Uniform total cost and EMI values are invalid.")
            db.execute(text("insert into employee_uniforms(employee_id,shirt,trousers,shoes,belt,cap,total_cost,monthly_emi,outstanding_balance,issued_date) values(:employee_id,:shirt,:trousers,:shoes,:belt,:cap,:total,:emi,:balance,:issued_date)"),
              {"employee_id": employee_id, "shirt": bool(payload.get("uniform_shirt")), "trousers": bool(payload.get("uniform_trousers")), "shoes": bool(payload.get("uniform_shoes")),
               "belt": bool(payload.get("uniform_belt")), "cap": bool(payload.get("uniform_cap")), "total": total, "emi": emi, "balance": total, "issued_date": date.today()})

        for doc_type, authority, expiry in [
            ("POLICE_VERIFICATION", payload.get("police_station"), payload.get("police_verification_expiry")),
            ("MEDICAL_FITNESS", None, payload.get("medical_fitness_expiry")),
            ("PSARA_TRAINING", payload.get("psara_batch_no"), payload.get("psara_training_expiry")),
            ("GUN_LICENSE", payload.get("arms_issuing_authority"), payload.get("gun_license_expiry")),
        ]:
            if authority or expiry:
                db.execute(text("insert into employee_documents(employee_id,document_type,issuing_authority,expiry_date,status,metadata) values(:employee_id,:type,:authority,:expiry,'VALID',cast(:metadata as jsonb))"),
                  {"employee_id": employee_id, "type": doc_type, "authority": authority, "expiry": expiry, "metadata": "{}"})

        db.commit()
        return dict(employee)
    except HTTPException:
        db.rollback(); raise
    except Exception as exc:
        db.rollback(); raise HTTPException(409, str(exc).split("\n")[0])


@router.patch("/{employee_id}")
def update_employee(employee_id: UUID, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    allowed={"employee_code","name","phone","status","intimation_id","dob","gender","designation","branch","site_id","joining_date","category","aadhaar_no","pan_no","permanent_address","present_address","emergency_contact","marital_status","status_reason"}
    data={k:v for k,v in payload.items() if k in allowed}
    if not data: raise HTTPException(422,"No editable fields supplied")
    data["id"]=str(employee_id); sets=", ".join(f"{k}=:{k}" for k in data if k!="id")
    row=db.execute(text(f"update employees set {sets} where id=:id returning *"),data).mappings().first()
    if not row: db.rollback(); raise HTTPException(404,"Employee not found")
    db.commit(); return dict(row)
