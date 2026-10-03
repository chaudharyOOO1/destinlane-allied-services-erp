from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models.company import CompanySettings
from app.schemas.company import CompanyProfile


def company_response(db: Session):
    row = db.get(CompanySettings, 1)
    profile = CompanyProfile.model_validate(row.profile if row else {}).model_dump(mode='json')
    year, month = profile['financial_year_start_year'], profile['financial_year_start_month']
    start = date(year, month, 1)
    end = date(year + 1, month, 1) - timedelta(days=1)
    return {
        'profile': profile, 'version': row.version if row else 0,
        'updated_at': row.updated_at.isoformat() if row and row.updated_at else None,
        'financial_year': {'label': f'{start.year}–{end.year}', 'start': start.isoformat(), 'end': end.isoformat()},
        'status': 'SUBMITTED' if row and row.submitted_at else 'DRAFT',
        'submitted_at': row.submitted_at.isoformat() if row and row.submitted_at else None,
    }


def company_document_profile(db: Session):
    profile = company_response(db)['profile']
    profile['address'] = profile['registered_office'] or profile['address']
    return {key: profile[key] for key in ['legal_name', 'display_name', 'address', 'city', 'state', 'pincode', 'contact_email', 'contact_phone', 'website', 'gstin']}
