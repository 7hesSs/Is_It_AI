import os
import re

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from app.services import auth as auth_service
from app.services import email as email_service

router = APIRouter()

# Simple email-shape check - avoids pulling in the email-validator dependency
# that pydantic's EmailStr would require, for a check this basic.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8

# Used to build the link inside the reset email. Set this to your deployed
# frontend's URL in production (e.g. https://your-app.vercel.app).
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")


class SignupRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    email: str


class UserResponse(BaseModel):
    email: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=MIN_PASSWORD_LENGTH)


def _validate_email(email: str) -> None:
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")


def _extract_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization[len("Bearer "):]


def get_current_user(authorization: str = Header(default=None)) -> dict:
    """
    FastAPI dependency - add `user: dict = Depends(get_current_user)` to any
    route to require a logged-in user. Raises 401 automatically if missing
    or invalid, which is what makes the /analyze/* endpoints refuse
    unauthenticated requests at the API level (not just hidden in the UI).
    """
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Log in to use this feature.")

    user = auth_service.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    return user


@router.post("/signup", response_model=AuthResponse)
def signup(request: SignupRequest):
    _validate_email(request.email)

    if auth_service.get_user_by_email(request.email):
        raise HTTPException(
            status_code=409, detail="An account with this email already exists."
        )

    user_id = auth_service.create_user(request.email, request.password)
    token = auth_service.create_session(user_id)
    return AuthResponse(token=token, email=request.email.lower().strip())


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest):
    user = auth_service.verify_password(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = auth_service.create_session(user["id"])
    return AuthResponse(token=token, email=user["email"])


@router.post("/logout")
def logout(authorization: str = Header(default=None)):
    token = _extract_token(authorization)
    if token:
        auth_service.delete_session(token)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(email=user["email"])


@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    user = auth_service.get_user_by_email(request.email)

    # Only actually send an email if the account exists, but ALWAYS return
    # the same response either way - returning a different message for
    # unregistered emails would let anyone check which emails have accounts.
    if user:
        token = auth_service.create_password_reset(user["id"])
        reset_link = f"{FRONTEND_URL}/?resetToken={token}"
        email_service.send_email(
            user["email"],
            "Reset your password — Is it AI?",
            "Click the link below to reset your password. "
            "This link expires in 30 minutes.\n\n"
            f"{reset_link}\n\n"
            "If you didn't request this, you can safely ignore this email.",
        )

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    user_id = auth_service.get_user_id_by_reset_token(request.token)
    if not user_id:
        raise HTTPException(
            status_code=400, detail="This reset link is invalid or has expired."
        )

    auth_service.update_password(user_id, request.new_password)
    auth_service.consume_reset_token(request.token)
    return {"message": "Password updated. You can log in with your new password."}
