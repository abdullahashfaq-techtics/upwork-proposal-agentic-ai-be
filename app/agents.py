from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END, START


class ProposalState(TypedDict):
    job_description: str
    user_profile: dict
    combined_input: dict
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


graph = StateGraph(ProposalState)

graph.add_node("input_collection", input_collection)

graph.add_edge(START, "input_collection")
graph.add_edge("input_collection", END)

proposal_graph = graph.compile()
