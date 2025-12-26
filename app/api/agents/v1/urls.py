from fastapi import APIRouter

from app.api.agents.v1.test_agents import sample_1

agents_router = APIRouter()

agents_router.include_router(sample_1.router, tags=['Sample Agents'])