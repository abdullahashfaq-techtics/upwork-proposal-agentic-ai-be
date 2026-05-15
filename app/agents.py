import json
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END, START
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from app.config import settings

# Gemini (commented out — quota exceeded, enable later)
# from langchain_google_genai import ChatGoogleGenerativeAI
# if not settings.GEMINI_API_KEY:
#     raise ValueError("GEMINI_API_KEY is missing from .env")
# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.0-flash",
#     google_api_key=settings.GEMINI_API_KEY
# )


llm = init_chat_model("groq:llama-3.3-70b-versatile")


class ProposalState(TypedDict):
    job_description: str
    user_profile: dict
    combined_input: dict
    job_analysis: dict
    status: str
    proposal_id: Optional[str]


def input_collection(state: ProposalState) -> ProposalState:
    """
    Node 01 — Input Collection + Combine
    Validates job_description and user_profile.
    Combines both into combined_input.
    """
    if not state.get("job_description"):
        raise ValueError("job_description is required.")

    if len(state["job_description"].strip()) < 20:
        raise ValueError("job_description is too short.")

    if not state.get("user_profile"):
        raise ValueError("user_profile is required.")

    required_fields = ["bio", "skills", "past_projects", "rate"]
    for field in required_fields:
        if field not in state["user_profile"]:
            raise ValueError(f"user_profile missing field: '{field}'")

    combined_input = {
        "job_description": state["job_description"],
        "user_profile": state["user_profile"],
    }

    return {
        **state,
        "combined_input": combined_input,
        "status": "draft",
        "proposal_id": None,
    }


def analyze_job(state: ProposalState) -> ProposalState:
    """
    Node 02 — Job Analysis
    Calls LLM to extract skills, tone, budget, pain_points.
    Currently using Groq — switch to Gemini when quota available.
    """
    job_description = state["combined_input"]["job_description"]

    prompt = f"""
    Analyze the following job description and extract key information.

    Job Description:
    {job_description}

    Return ONLY a JSON object with exactly these fields:
    {{
        "skills": ["list of required technical skills mentioned"],
        "tone": "one of: formal | casual | technical | neutral",
        "budget": "budget if mentioned, otherwise not mentioned",
        "pain_points": ["list of problems or challenges the client mentioned"]
    }}

    Return only the JSON. No explanation. No markdown. No extra text.
    """

    response = llm.invoke([HumanMessage(content=prompt)])

    raw = response.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    job_analysis_result = json.loads(raw)

    return {
        **state,
        "job_analysis": job_analysis_result,
    }


graph = StateGraph(ProposalState)

graph.add_node("input_collection", input_collection)
graph.add_node("analyze_job", analyze_job)

graph.add_edge(START, "input_collection")
graph.add_edge("input_collection", "analyze_job")
graph.add_edge("analyze_job", END)

proposal_graph = graph.compile()
