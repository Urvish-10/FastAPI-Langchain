from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from fastapi_pagination import add_pagination
from fastapi.responses import RedirectResponse
from app.api.agents.v1.urls import agents_router
from app.api.users.v1.urls import users_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="{0}/openapi.json".format(settings.API_V1_STR),
)

# app.add_middleware(HTTPSRedirectMiddleware)

if settings.BACKEND_CORS_ORIGINS:
    # print(str(origin) for origin in settings.BACKEND_CORS_ORIGINS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000", "http://localhost:8000"
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
# add_pagination(app)

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
# below line will add all endpoints with prefix
app.include_router(agents_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
