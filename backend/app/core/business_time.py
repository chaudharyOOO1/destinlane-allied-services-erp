from datetime import datetime
from zoneinfo import ZoneInfo


def business_date():
    """ERP commercial validity follows the company's Indian business date."""
    return datetime.now(ZoneInfo('Asia/Kolkata')).date()
