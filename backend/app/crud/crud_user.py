from typing import Optional
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password

class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        data = obj_in.model_dump(exclude={"password"})
        data["hashed_password"] = get_password_hash(obj_in.password)
        db_obj = User(**data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, *, db_obj: User, obj_in: UserUpdate | dict) -> User:
        data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        if "password" in data:
            db_obj.hashed_password = get_password_hash(data.pop("password"))
        for field, value in data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def authenticate(self, db: Session, *, login_id: str, password: str) -> Optional[User]:
        identifier = login_id.strip()
        user = self.get_by_email(db, email=identifier)
        if not user:
            user = db.query(User).filter(User.phone_number == identifier).first()
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user

user = CRUDUser(User)
