from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import UserRepository, get_user_repository
from app.schemas.auth import TokenResponse, UserLogin, UserPublic, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=UserPublic, status_code=201)
def register(payload: UserRegister, users: UserRepository = Depends(get_user_repository)):
    if users.get_by_email(payload.email):
        raise ValidationError("An account with this email already exists.")
    user = users.create(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name)


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), users: UserRepository = Depends(get_user_repository)):
    user = users.get_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password.")
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


@router.post("/login-json", response_model=TokenResponse)
def login_json(payload: UserLogin, users: UserRepository = Depends(get_user_repository)):
    """JSON-friendly login variant for non-form clients (e.g. the Streamlit frontend)."""
    user = users.get_by_email(payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password.")
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
