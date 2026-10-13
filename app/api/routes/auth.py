
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services.audit_service import record_audit_event
from app.services.auth_service import (
    InvalidCredentialsError,
    authenticate_user,
    issue_access_token,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])

DatabaseSession = Annotated[Session, Depends(get_db)]


def _record_login_audit(
    db: Session,
    request: Request,
    *,
    action: str,
    username: str,
    user: User | None = None,
) -> None:
    """Persist a login audit event independently of authentication outcome."""
    try:
        record_audit_event(
            db,
            action=action,
            resource_type="user",
            actor_user_id=user.id if user else None,
            actor_username=user.username if user else username[:100],
            details={"outcome": action},
            ip_address=(
                request.client.host if request.client else None
            ),
            request_id=getattr(request.state, "request_id", None),
        )
        db.commit()
    except Exception:
        db.rollback()
        # Do not turn a login result into a 500 solely because auditing failed.
        # Production deployments should alert on audit persistence failures.


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and obtain an access token",
)
def login(
    payload: LoginRequest,
    request: Request,
    db: DatabaseSession,
) -> TokenResponse:
    try:
        user = authenticate_user(
            db,
            payload.username,
            payload.password,
        )
        token = issue_access_token(user)
    except InvalidCredentialsError as exc:
        _record_login_audit(
            db,
            request,
            action="login_failed",
            username=payload.username,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    _record_login_audit(
        db,
        request,
        action="login_success",
        username=user.username,
        user=user,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the currently authenticated user",
)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(current_user)
