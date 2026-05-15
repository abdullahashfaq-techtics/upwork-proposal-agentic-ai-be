from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.auth import signup_user, login_user
from app.database import supabase
from app.agents import proposal_graph

router = APIRouter()


class AuthRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    bio: str
    skills: List[str]
    past_projects: List[str]
    rate: str


class ProposalRequest(BaseModel):
    job_description: str
    user_profile: UserProfile


@router.get("/health")
def health_check():
    app_status = "ok"
    db_status = "unreachable"

    try:
        supabase.auth.get_session()
        db_status = "connected"
    except Exception:
        db_status = "unreachable"

    return {
        "status": app_status,
        "database": db_status,
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


@router.post("/proposal/generate")
def generate_proposal(request: ProposalRequest):
    try:
        result = proposal_graph.invoke(
            {
                "job_description": request.job_description,
                "user_profile": request.user_profile.model_dump(),
            }
        )
        return {
            "combined_input": result["combined_input"],
            "job_analysis": result["job_analysis"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in str(e) or "resourceexhausted" in error_msg or "quota" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable due to rate limits. Please try again in a minute.",
            )
        raise HTTPException(status_code=500, detail=str(e))
