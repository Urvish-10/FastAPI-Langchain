from fastapi import APIRouter

from app.api.users.v1.user import user

users_router = APIRouter()

users_router.include_router(user.router, tags=['Users'])