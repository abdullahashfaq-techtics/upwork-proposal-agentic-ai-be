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
    final_proposal: str


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
        "proposal_id": state.get("proposal_id"),
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
    You are a top-rated Upwork freelancer writing a winning proposal.
    You have a 98% job success score and have won over 200 contracts.

    Job Description:
    {job_description}

    Job Analysis:
    - Required Skills: {job_analysis["skills"]}
    - Tone: {job_analysis["tone"]}
    - Budget: {job_analysis["budget"]}
    - Client Pain Points: {job_analysis["pain_points"]}

    Freelancer Profile:
    - Bio: {user_profile["bio"]}
    - Matched Skills: {match_summary["matched_skills"]}
    - Relevant Projects: {match_summary["top_projects"]}
    - Key Points to Emphasise: {match_summary["emphasis"]}

    Write a proposal following these STRICT rules:

    STRUCTURE:
    1. Hook — Open with the client's specific problem or goal from the job description.
       Do NOT start with "I am excited" or "I would love".
       Start with THEIR situation, not yours.
       Example: "Your AI backend needs to handle real-time data processing at scale —"

    2. Experience — Mention 1-2 specific past projects that directly relate.
       Include a concrete result if possible (increased speed by 40%, reduced cost by 30%).
       Do NOT list skills generically.

    3. Solution — Explain your specific approach to THEIR project.
       Show you understood their requirements.
       Give 2-3 concrete steps you would take.

    4. CTA — End with one clear, low-friction question or next step.
       Example: "Want to jump on a 15-minute call to map out the architecture?"

    STRICT REQUIREMENTS:
    - 150 to 250 words maximum
    - Match the tone: {job_analysis["tone"]}
    - No markdown, no bullet points, no bold, no headers
    - Plain text only, ready to paste into Upwork
    - No generic phrases: "I am excited", "I would love to", "I am a fast learner"
    - No self-introduction at the start
    - Correct grammar and spelling
    - Sound like a confident expert, not an eager applicant
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
    You are a senior Upwork recruiter evaluating proposals.
    You have reviewed 10,000+ proposals and know exactly what wins contracts.

    Proposal:
    {proposal_draft}

    Job Requirements:
    - Skills: {job_analysis["skills"]}
    - Tone: {job_analysis["tone"]}
    - Pain Points: {job_analysis["pain_points"]}

    Score on these 5 axes. Be STRICT — average proposals get 5-6 not 8-9:

    1. Relevance (0-10) — Does it directly address the client's specific pain points?
       10 = addresses every pain point specifically
       5 = mentions the job but stays generic
       0 = could be sent to any job

    2. Tone (0-10) — Does it match required tone: {job_analysis["tone"]}?
       10 = perfect match, sounds natural
       5 = mostly right but some mismatches
       0 = completely wrong tone

    3. Specificity (0-10) — Does it mention specific skills, projects, and results?
       10 = concrete examples with measurable results
       5 = mentions skills but no specific examples
       0 = completely generic

    4. Hook (0-10) — Is the opening sentence attention-grabbing and client-focused?
       10 = opens with client's problem, immediately compelling
       5 = decent but starts with "I" or generic statement
       0 = starts with "I am excited" or similar

    5. CTA (0-10) — Is there a clear, specific, low-friction call to action?
       10 = specific question that invites response
       5 = vague "let me know" or "contact me"
       0 = no clear next step

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
        "critique": ["specific actionable improvement for each weakness"]
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

    if total_score < 40 and retry_count < 2:
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
    You are a top-rated Upwork freelancer rewriting a proposal.
    You have a 98% job success score and have won over 200 contracts.

    Current Proposal:
    {state["proposal_draft"]}

    Human Feedback:
    {state["human_feedback"]}

    Quality Critique:
    {state["quality_report"]["critique"]}

    Rewrite the proposal following these STRICT rules:

    MUST DO:
    - Address EVERY point in the human feedback
    - Fix EVERY issue mentioned in the quality critique
    - Keep the hook focused on the CLIENT's problem, not your excitement
    - Make it sound more human and confident
    - Use specific details, not generic claims

    MUST AVOID:
    - Generic openers: "I am excited", "I would love to"
    - Vague claims: "I am a quick learner", "I work hard"
    - Listing skills without context
    - Sounding like an AI wrote it

    STRICT REQUIREMENTS:
    - 150 to 250 words maximum
    - No markdown, no bullet points, no bold, no headers
    - Plain text only
    - Correct grammar and spelling
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


def finalize_proposal(state: ProposalState) -> ProposalState:
    """
    Node 08 - Finalize and Save
    Saves approved proposal to Supabase.
    Sets final_proposal and status = complete.
    """
    from app.database import supabase

    final_proposal = state["proposal_draft"]

    user_id = state.get("proposal_id")

    try:
        supabase.table("proposals").insert(
            {
                "user_id": user_id,
                "job_description": state["job_description"],
                "proposal_draft": state["proposal_draft"],
                "draft_version": state["draft_version"],
                "quality_report": state["quality_report"],
                "human_feedback": state.get("human_feedback", ""),
                "final_proposal": final_proposal,
                "status": "complete",
            }
        ).execute()
    except Exception as e:
        print(f"Supabase save error: {e}")

    return {
        **state,
        "final_proposal": final_proposal,
        "status": "complete",
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
        return "finalize"
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
graph.add_node("finalize_proposal", finalize_proposal)

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
        "finalize": "finalize_proposal",
        "end": END,
        "revise": "revise_draft",
    },
)

graph.add_edge("finalize_proposal", END)

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
