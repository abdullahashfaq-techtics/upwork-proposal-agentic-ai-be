import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from app.auth import signup_user, login_user, get_current_user
from app.database import supabase
from app.agents import proposal_graph

bearer_scheme = HTTPBearer()
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
    stream: Optional[bool] = None


class ResumeRequest(BaseModel):
    decision: str
    feedback: Optional[str] = ""
    stream: Optional[bool] = None


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
def generate_proposal(
    request: ProposalRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    token = credentials.credentials

    try:
        user = get_current_user(token)
        user_id = user["user_id"]

        config = {"configurable": {"thread_id": user_id}}

        if request.stream:

            def event_generator():
                try:
                    for event in proposal_graph.stream(
                        {
                            "job_description": request.job_description,
                            "user_profile": request.user_profile.model_dump(),
                            "proposal_id": user_id,
                        },
                        config=config,
                    ):
                        for node_name, node_data in event.items():
                            sse_data = {
                                "node": node_name,
                                "status": "completed",
                            }
                            yield f"data: {json.dumps(sse_data)}\n\n"

                    current_state = proposal_graph.get_state(config)
                    state_values = current_state.values
                    final_data = {
                        "node": "__end__",
                        "status": "done",
                        "data": {
                            "user_id": user_id,
                            "status": state_values.get("status"),
                            "proposal_draft": state_values.get("proposal_draft"),
                            "draft_version": state_values.get("draft_version"),
                            "retry_count": state_values.get("retry_count"),
                            "quality_report": state_values.get("quality_report"),
                            "draft_history": state_values.get("draft_history"),
                            "message": "Proposal ready for review. Use /proposal/resume to submit decision.",
                        },
                    }
                    yield f"data: {json.dumps(final_data)}\n\n"
                except Exception as e:
                    error_data = {
                        "node": "__error__",
                        "status": "error",
                        "detail": str(e),
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        for event in proposal_graph.stream(
            {
                "job_description": request.job_description,
                "user_profile": request.user_profile.model_dump(),
                "proposal_id": user_id,
            },
            config=config,
        ):
            pass

        current_state = proposal_graph.get_state(config)
        state_values = current_state.values

        return {
            "user_id": user_id,
            "status": state_values.get("status"),
            "proposal_draft": state_values.get("proposal_draft"),
            "draft_version": state_values.get("draft_version"),
            "retry_count": state_values.get("retry_count"),
            "quality_report": state_values.get("quality_report"),
            "draft_history": state_values.get("draft_history"),
            "message": "Proposal ready for review. Use /proposal/resume to submit decision.",
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in str(e) or "resourceexhausted" in error_msg or "quota" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable. Please try again in a minute.",
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposal/resume")
def resume_proposal(
    request: ResumeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    token = credentials.credentials

    valid_decisions = ["approved", "revise", "rejected"]
    if request.decision not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision. Must be one of: {valid_decisions}",
        )

    if request.decision == "revise" and not request.feedback:
        raise HTTPException(
            status_code=400,
            detail="feedback is required when decision is 'revise'",
        )

    try:
        user = get_current_user(token)
        user_id = user["user_id"]

        config = {"configurable": {"thread_id": user_id}}

        current_state = proposal_graph.get_state(config)
        if not current_state.values:
            raise HTTPException(
                status_code=400,
                detail="No active proposal found. Please call /proposal/generate first.",
            )

        if request.decision == "revise":
            draft_history = current_state.values.get("draft_history", [])
            if len(draft_history) >= 3:
                raise HTTPException(
                    status_code=400,
                    detail="Maximum revision limit of 3 reached. Please approve or reject the proposal.",
                )

        proposal_graph.update_state(
            config,
            {
                "human_decision": request.decision,
                "human_feedback": request.feedback,
                "status": request.decision,
            },
            as_node="human_review",
        )

        if request.stream:

            def event_generator():
                try:
                    for event in proposal_graph.stream(
                        None,
                        config=config,
                        stream_mode="values",
                    ):
                        node_name = event.get("status", "processing")
                        sse_data = {
                            "node": node_name,
                            "status": "completed",
                        }
                        yield f"data: {json.dumps(sse_data)}\n\n"

                    final_state = proposal_graph.get_state(config)
                    is_paused = bool(final_state.tasks)
                    final_data = {
                        "node": "__end__",
                        "status": "done",
                        "data": {
                            "user_id": user_id,
                            "status": final_state.values.get("status"),
                            "human_decision": final_state.values.get("human_decision"),
                            "proposal_draft": final_state.values.get("proposal_draft"),
                            "final_proposal": final_state.values.get("final_proposal"),
                            "draft_version": final_state.values.get("draft_version"),
                            "draft_history": final_state.values.get("draft_history"),
                            "waiting_for_review": is_paused,
                            "message": "Proposal revised. Please review again."
                            if is_paused
                            else f"Proposal {request.decision}.",
                        },
                    }
                    yield f"data: {json.dumps(final_data)}\n\n"
                except Exception as e:
                    error_data = {
                        "node": "__error__",
                        "status": "error",
                        "detail": str(e),
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        for event in proposal_graph.stream(
            None,
            config=config,
            stream_mode="values",
        ):
            pass

        final_state = proposal_graph.get_state(config)
        is_paused = bool(final_state.tasks)

        return {
            "user_id": user_id,
            "status": final_state.values.get("status"),
            "human_decision": final_state.values.get("human_decision"),
            "proposal_draft": final_state.values.get("proposal_draft"),
            "final_proposal": final_state.values.get("final_proposal"),
            "draft_version": final_state.values.get("draft_version"),
            "draft_history": final_state.values.get("draft_history"),
            "waiting_for_review": is_paused,
            "message": "Proposal revised. Please review again."
            if is_paused
            else f"Proposal {request.decision}.",
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
