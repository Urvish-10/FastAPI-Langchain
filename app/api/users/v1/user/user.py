from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm


from app.api.deps import SessionDep, CurrentUser
from app.core import security
from app.core.config import settings
from app.models.users.user import Token, UserCreate, UserPublic

from app.utilities import crud

router = APIRouter()


@router.post("/login/")
def user_login(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        user_id=user.id,
        user_email=user.email,
        user_name=user.name,
    )


@router.post("/create/user/", response_model=UserPublic)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    # if settings.emails_enabled and user_in.email:
    #     pass
    # email_data = generate_new_account_email(
    #     email_to=user_in.email, username=user_in.email, password=user_in.password
    # )
    # send_email(
    #     email_to=user_in.email,
    #     subject=email_data.subject,
    #     html_content=email_data.html_content,
    # )
    return user


@router.get("/logout")
def logout(current_user: CurrentUser) -> dict:
    """
    Inform the client to discard token. Stateless logout.
    """
    return {"msg": "Successfully logged out."}
