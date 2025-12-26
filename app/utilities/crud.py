from sqlmodel import Session, select

from app.core.security import verify_password, get_password_hash
from app.models.users.user import UserCreate, Users


def create_user(*, session: Session, user_create: UserCreate) -> Users:
    db_obj = Users.model_validate(
        user_create, update={"password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_user_by_email(*, session: Session, email: str) -> Users | None:
    statement = select(Users).where(Users.email == email)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> Users | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.password):
        return None
    return db_user
