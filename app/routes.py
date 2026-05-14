from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.auth import signup_user, login_user
from app.database import supabase

router = APIRouter()

APP_STATUS = "ok"
DATABASE_STATUS = "unreachable"


class AuthRequest(BaseModel):
    email: str
    password: str


@router.get("/health")
def health_check():
    global DATABASE_STATUS
    try:
        supabase.auth.get_session()
        DATABASE_STATUS = "connected"
    except Exception:
        DATABASE_STATUS = "unreachable"

    return {
        "status": APP_STATUS,
        "database": DATABASE_STATUS,
    }


@router.post("/auth/signup")
def signup(request: AuthRequest):
    try:
        response = signup_user(request.email, request.password)
        return {
            "message": "Signup successful. Please verify your email.",
            "user_id": response.user.id,
            "email": response.user.email,
            "email_confirmed": response.user.email_confirmed_at is not None,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/login")
def login(request: AuthRequest):
    try:
        response = login_user(request.email, request.password)
        return {
            "message": "Login successful.",
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "user_id": response.user.id,
            "email": response.user.email,
            "email_confirmed": response.user.email_confirmed_at is not None,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auth/confirm", include_in_schema=False)
def confirm_email(confirmed: str = None):
    if confirmed == "true":
        return {"message": "Email confirmed successfully. You can now login."}
    raise HTTPException(
        status_code=400, detail="Invalid confirmation link. Please request a new one."
    )
