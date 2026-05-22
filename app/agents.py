import json
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END, START
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

# Gemini (quota exceeded, enable later)
# from langchain_google_genai import ChatGoogleGenerativeAI
# if not settings.GEMINI_API_KEY:
#     raise ValueError("GEMINI_API_KEY is missing from .env")
# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.0-flash",
#     google_api_key=settings.GEMINI_API_KEY
# )

# Groq (active for now — switch back to Gemini later)
llm = init_chat_model("groq:llama-3.3-70b-versatile")


class ProposalState(TypedDict):
    job_description: str
    user_profile: dict
    combined_input: dict
    job_analysis: dict
    match_summary: dict
    proposal_draft: str
    draft_version: int
    quality_report: dict
    retry_count: int
    human_decision: str
    human_feedback: str
    draft_history: list
    status: str
    proposal_id: Optional[str]


def input_collection(state: ProposalState) -> ProposalState:
    """
    Node 01 - Input Collection + Combine
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
        "draft_version": 1,
        "retry_count": 0,
        "human_decision": "",
        "human_feedback": "",
        "draft_history": [],
    }


def analyze_job(state: ProposalState) -> ProposalState:
    """
    Node 02 - Job Analysis
    Calls LLM to extract skills, tone, budget, pain_points.
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

    return {
        **state,
        "job_analysis": json.loads(raw),
    }


def match_profile(state: ProposalState) -> ProposalState:
    """
    Node 03 - Profile Matching
    Scores freelancer skills vs JD requirements.
    """
    job_analysis = state["job_analysis"]
    user_profile = state["combined_input"]["user_profile"]

    prompt = f"""
    You are a proposal writing assistant.
    Compare the freelancer profile against the job requirements.

    Job Requirements:
    - Required Skills: {job_analysis["skills"]}
    - Tone: {job_analysis["tone"]}
    - Pain Points: {job_analysis["pain_points"]}

    Freelancer Profile:
    - Bio: {user_profile["bio"]}
    - Skills: {user_profile["skills"]}
    - Past Projects: {user_profile["past_projects"]}
    - Rate: {user_profile["rate"]}

    Return ONLY a JSON object with exactly these fields:
    {{
        "matched_skills": ["skills from freelancer profile that match job requirements"],
        "top_projects": ["2-3 most relevant past projects to mention in proposal"],
        "match_score": 0,
        "emphasis": ["key points to emphasise in the proposal"]
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

    return {
        **state,
        "match_summary": json.loads(raw),
    }


def draft_proposal(state: ProposalState) -> ProposalState:
    """
    Node 04 - Proposal Draft
    Generates 150-300 word proposal.
    Structure: hook, experience, solution, CTA
    """
    job_analysis = state["job_analysis"]
    match_summary = state["match_summary"]
    user_profile = state["combined_input"]["user_profile"]
    job_description = state["combined_input"]["job_description"]

    prompt = f"""
    You are an expert Upwork proposal writer.
    Write a professional proposal for the following job.

    Job Description:
    {job_description}

    Job Analysis:
    - Required Skills: {job_analysis["skills"]}
    - Tone: {job_analysis["tone"]}
    - Budget: {job_analysis["budget"]}
    - Pain Points: {job_analysis["pain_points"]}

    Freelancer Profile:
    - Bio: {user_profile["bio"]}
    - Matched Skills: {match_summary["matched_skills"]}
    - Relevant Projects: {match_summary["top_projects"]}
    - Key Points to Emphasise: {match_summary["emphasis"]}

    Write a proposal with this exact structure:
    1. Hook - grab attention in first sentence
    2. Experience - mention relevant skills and projects
    3. Solution - explain how you will solve their problem
    4. CTA - clear call to action at the end

    Requirements:
    - 150 to 300 words
    - Match the tone: {job_analysis["tone"]}
    - No markdown, no bullet points
    - Plain text only, ready to paste into Upwork
    - Do not include a subject line or greeting
    """

    response = llm.invoke([HumanMessage(content=prompt)])

    return {
        **state,
        "proposal_draft": response.content.strip(),
    }


def evaluate_quality(state: ProposalState) -> ProposalState:
    """
    Node 05 - Quality Evaluator
    Scores proposal on 5 axes. Max 50.
    Score less than 35 triggers retry. Score 35 or more goes to human review.
    """
    proposal_draft = state["proposal_draft"]
    job_analysis = state["job_analysis"]

    prompt = f"""
    You are a proposal quality evaluator.
    Score the following Upwork proposal on 5 axes.
    Each axis is scored out of 10. Maximum total is 50.

    Proposal:
    {proposal_draft}

    Job Requirements:
    - Skills: {job_analysis["skills"]}
    - Tone: {job_analysis["tone"]}
    - Pain Points: {job_analysis["pain_points"]}

    Score on these 5 axes:
    1. Relevance - does it address job requirements?
    2. Tone - does it match required tone: {job_analysis["tone"]}?
    3. Specificity - does it mention specific skills and projects?
    4. Hook - is the opening sentence attention-grabbing?
    5. CTA - is there a clear call to action?

    Return ONLY a JSON object with exactly these fields:
    {{
        "scores": {{
            "relevance": 0,
            "tone": 0,
            "specificity": 0,
            "hook": 0,
            "cta": 0
        }},
        "total_score": 0,
        "critique": ["list of specific improvements needed"]
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

    quality_report = json.loads(raw)
    total_score = quality_report["total_score"]
    status = "reviewing" if total_score >= 35 else "draft"

    return {
        **state,
        "quality_report": quality_report,
        "status": status,
    }


def route_after_evaluation(state: ProposalState) -> str:
    """
    Routing function after Node 05.
    Score less than 35 AND retry_count less than 2 goes to retry.
    Score 35 or more OR retry_count 2 or more goes to human review.
    """
    total_score = state["quality_report"]["total_score"]
    retry_count = state.get("retry_count", 0)

    if total_score < 35 and retry_count < 2:
        return "retry"
    return "human_review"


def increment_retry(state: ProposalState) -> ProposalState:
    """
    Increments retry_count and draft_version
    before sending back to draft_proposal.
    """
    return {
        **state,
        "retry_count": state.get("retry_count", 0) + 1,
        "draft_version": state.get("draft_version", 1) + 1,
    }


def human_review(state: ProposalState) -> ProposalState:
    """
    Node 06 - Human Review
    Graph pauses here using interrupt().
    Resumes when update_state is called from /proposal/resume.
    human_decision and human_feedback are already in state
    when graph resumes, set by update_state in routes.py.
    """
    interrupt(
        {
            "proposal_draft": state["proposal_draft"],
            "quality_report": state["quality_report"],
            "message": "Please review the proposal. Decision: approved | revise | rejected",
        }
    )

    return state


def revise_draft(state: ProposalState) -> ProposalState:
    """
    Node 07 - Revise Draft
    Rewrites proposal based on human_feedback + critique.
    Saves previous draft to draft_history.
    Increments draft_version.
    Routes back to Node 05 for re-evaluation.
    Max 3 revision cycles.
    """
    history = state.get("draft_history", [])
    history.append(
        {
            "version": state["draft_version"],
            "draft": state["proposal_draft"],
            "quality_report": state["quality_report"],
            "human_feedback": state["human_feedback"],
        }
    )

    prompt = f"""
    You are an expert Upwork proposal writer.
    Rewrite the following proposal based on human feedback.

    Current Proposal:
    {state["proposal_draft"]}

    Human Feedback:
    {state["human_feedback"]}

    Quality Critique:
    {state["quality_report"]["critique"]}

    Requirements:
    - Address ALL feedback points
    - Keep 150 to 300 words
    - No markdown, no bullet points
    - Plain text only
    - Do not include subject line or greeting
    """

    response = llm.invoke([HumanMessage(content=prompt)])

    return {
        **state,
        "proposal_draft": response.content.strip(),
        "draft_version": state["draft_version"] + 1,
        "draft_history": history,
        "human_decision": "",
        "human_feedback": "",
        "status": "draft",
    }


def route_after_revision(state: ProposalState) -> str:
    """
    After revision goes back to evaluate_quality.
    Max 3 revision cycles checked by draft_history length.
    """
    if len(state.get("draft_history", [])) >= 3:
        return "end"
    return "evaluate"


def route_after_human_review(state: ProposalState) -> str:
    """
    Routing function after Node 06.
    approved goes to END.
    revise goes to revise_draft.
    rejected goes to END.
    """
    decision = state.get("human_decision", "")
    if decision == "approved":
        return "end"
    elif decision == "revise":
        return "revise"
    else:
        return "end"


graph = StateGraph(ProposalState)

graph.add_node("input_collection", input_collection)
graph.add_node("analyze_job", analyze_job)
graph.add_node("match_profile", match_profile)
graph.add_node("draft_proposal", draft_proposal)
graph.add_node("evaluate_quality", evaluate_quality)
graph.add_node("increment_retry", increment_retry)
graph.add_node("human_review", human_review)
graph.add_node("revise_draft", revise_draft)

graph.add_edge(START, "input_collection")
graph.add_edge("input_collection", "analyze_job")
graph.add_edge("analyze_job", "match_profile")
graph.add_edge("match_profile", "draft_proposal")
graph.add_edge("draft_proposal", "evaluate_quality")

graph.add_conditional_edges(
    "evaluate_quality",
    route_after_evaluation,
    {
        "retry": "increment_retry",
        "human_review": "human_review",
    },
)

graph.add_edge("increment_retry", "draft_proposal")

graph.add_conditional_edges(
    "human_review",
    route_after_human_review,
    {
        "end": END,
        "revise": "revise_draft",
    },
)

graph.add_conditional_edges(
    "revise_draft",
    route_after_revision,
    {
        "evaluate": "evaluate_quality",
        "end": END,
    },
)

checkpointer = MemorySaver()
proposal_graph = graph.compile(checkpointer=checkpointer)
