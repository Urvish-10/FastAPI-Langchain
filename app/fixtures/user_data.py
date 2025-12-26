import uuid
from datetime import datetime

from sqlmodel import Session

from app.core.db import engine
from app.core.security import get_password_hash
from app.models import Users


def seed_users():
    """Seed dummy users into the database."""
    users_data = [
        {"name": "Urvish", "email": "urvish@yopmail.com"},
        {"name": "admin", "email": "admin@yopmail.com"},
        {"name": "Nirav", "email": "nirav@yopmail.com"},
        {"name": "prince", "email": "prince@yopmail.com"},
        {"name": "prafull", "email": "prafull@yopmail.com"},
    ]

    default_password = "Test105*"

    with Session(engine) as session:
        for data in users_data:
            user = Users(
                id=uuid.uuid4(),
                name=data["name"],
                email=data["email"],
                password=get_password_hash(default_password),
                is_active=True,
                created_ts=datetime.now()
            )
            session.add(user)

        session.commit()
        print("✅ Dummy users seeded successfully!")


if __name__ == "__main__":
    seed_users()
