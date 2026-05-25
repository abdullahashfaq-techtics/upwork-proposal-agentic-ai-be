import streamlit as st
import requests
import json
import time

# ─── Config ───────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"

AGENT_STEPS = [
    {
        "key": "input_collection",
        "label": "Input Collection",
        "icon": "📋",
        "desc": "Validating inputs and combining data",
    },
    {
        "key": "analyze_job",
        "label": "Job Analysis",
        "icon": "🔍",
        "desc": "Extracting skills, tone, budget, and pain points",
    },
    {
        "key": "match_profile",
        "label": "Profile Matching",
        "icon": "🎯",
        "desc": "Scoring your profile against job requirements",
    },
    {
        "key": "draft_proposal",
        "label": "Drafting Proposal",
        "icon": "✍️",
        "desc": "Writing your personalized proposal",
    },
    {
        "key": "evaluate_quality",
        "label": "Quality Evaluation",
        "icon": "📊",
        "desc": "Scoring the proposal on 5 quality axes",
    },
    {
        "key": "increment_retry",
        "label": "Retry (Low Score)",
        "icon": "🔄",
        "desc": "Score too low, retrying draft",
    },
    {
        "key": "human_review",
        "label": "Human Review",
        "icon": "👤",
        "desc": "Waiting for your review",
    },
    {
        "key": "revise_draft",
        "label": "Revising Draft",
        "icon": "📝",
        "desc": "Rewriting based on your feedback",
    },
    {
        "key": "finalize_proposal",
        "label": "Finalizing",
        "icon": "✅",
        "desc": "Saving final proposal",
    },
]

STEP_KEY_MAP = {s["key"]: s for s in AGENT_STEPS}


# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Upwork Proposal AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, #0a0f1c 0%, #1a1f3c 50%, #0f1629 100%);
        border: 1px solid rgba(79, 140, 255, 0.15);
        border-radius: 16px;
        padding: 2rem 2.5rem;
        margin-bottom: 2rem;
        text-align: center;
    }
    .main-header h1 {
        background: linear-gradient(135deg, #4f8cff, #7c5cff, #4f8cff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
    }
    .main-header p {
        color: #8892b0;
        font-size: 1rem;
        margin-top: 0.5rem;
    }

    /* Step cards */
    .step-card {
        background: rgba(15, 22, 41, 0.6);
        border: 1px solid rgba(79, 140, 255, 0.1);
        border-radius: 12px;
        padding: 0.8rem 1.2rem;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.8rem;
        transition: all 0.3s ease;
    }
    .step-card.active {
        border-color: #4f8cff;
        background: rgba(79, 140, 255, 0.08);
        box-shadow: 0 0 20px rgba(79, 140, 255, 0.1);
    }
    .step-card.completed {
        border-color: #22c55e;
        background: rgba(34, 197, 94, 0.05);
    }
    .step-card.pending {
        opacity: 0.4;
    }
    .step-label {
        font-weight: 500;
        font-size: 0.95rem;
    }
    .step-desc {
        color: #8892b0;
        font-size: 0.8rem;
    }

    /* Proposal card */
    .proposal-card {
        background: linear-gradient(135deg, rgba(15, 22, 41, 0.8), rgba(26, 31, 60, 0.6));
        border: 1px solid rgba(79, 140, 255, 0.2);
        border-radius: 16px;
        padding: 2rem;
        margin: 1rem 0;
        backdrop-filter: blur(10px);
    }
    .proposal-text {
        color: #e2e8f0;
        font-size: 1rem;
        line-height: 1.8;
        white-space: pre-wrap;
    }

    /* Score bar */
    .score-container {
        margin: 0.4rem 0;
    }
    .score-label {
        display: flex;
        justify-content: space-between;
        font-size: 0.85rem;
        margin-bottom: 0.3rem;
        color: #cbd5e1;
    }
    .score-bar-bg {
        background: rgba(255,255,255,0.08);
        border-radius: 8px;
        height: 8px;
        overflow: hidden;
    }
    .score-bar-fill {
        height: 100%;
        border-radius: 8px;
        transition: width 0.5s ease;
    }

    /* History timeline */
    .history-item {
        border-left: 3px solid #4f8cff;
        padding: 1rem 1.5rem;
        margin-left: 1rem;
        margin-bottom: 1rem;
        background: rgba(15, 22, 41, 0.4);
        border-radius: 0 12px 12px 0;
    }
    .history-version {
        color: #4f8cff;
        font-weight: 600;
        font-size: 0.9rem;
    }

    /* Auth card */
    .auth-card {
        background: linear-gradient(135deg, #0f1629, #1a1f3c);
        border: 1px solid rgba(79, 140, 255, 0.2);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }

    /* Badge */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-complete { background: rgba(34,197,94,0.15); color: #22c55e; }
    .badge-reviewing { background: rgba(79,140,255,0.15); color: #4f8cff; }
    .badge-draft { background: rgba(234,179,8,0.15); color: #eab308; }
    .badge-error { background: rgba(239,68,68,0.15); color: #ef4444; }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True,
)


# ─── Session State Init ──────────────────────────────────────────────────────
defaults = {
    "token": None,
    "user_id": None,
    "user_email": None,
    "completed_steps": [],
    "active_step": None,
    "proposal_result": None,
    "is_generating": False,
    "show_history": False,
    "bio": "",
    "skills": "",
    "past_projects": "",
    "rate": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─── Helper Functions ─────────────────────────────────────────────────────────
def api_request(method, endpoint, data=None, stream=False):
    """Make authenticated API request."""
    headers = {}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"

    url = f"{API_BASE}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=120, stream=stream)
        else:
            resp = requests.post(
                url, json=data, headers=headers, timeout=120, stream=stream
            )

        if not stream:
            if resp.status_code >= 400:
                error = resp.json().get("detail", "Unknown error")
                return {"error": error}
            return resp.json()
        return resp
    except requests.exceptions.ConnectionError:
        return {
            "error": "Cannot connect to backend. Make sure the FastAPI server is running on port 8000."
        }
    except Exception as e:
        return {"error": str(e)}


def render_step_progress(completed_steps, active_step=None, relevant_steps=None):
    """Render the step-by-step progress tracker."""
    if relevant_steps is None:
        relevant_steps = [
            "input_collection",
            "analyze_job",
            "match_profile",
            "draft_proposal",
            "evaluate_quality",
            "human_review",
        ]

    for step_key in relevant_steps:
        step = STEP_KEY_MAP.get(step_key)
        if not step:
            continue

        if step_key in completed_steps:
            css_class = "completed"
            icon = "✅"
        elif step_key == active_step:
            css_class = "active"
            icon = "⏳"
        else:
            css_class = "pending"
            icon = "⬜"

        st.markdown(
            f"""
        <div class="step-card {css_class}">
            <span style="font-size: 1.3rem;">{icon}</span>
            <div>
                <div class="step-label">{step["label"]}</div>
                <div class="step-desc">{step["desc"]}</div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )


def render_quality_scores(quality_report):
    """Render quality score bars."""
    if not quality_report:
        return

    scores = quality_report.get("scores", {})
    total = quality_report.get("total_score", 0)
    colors = {
        "relevance": "#4f8cff",
        "tone": "#7c5cff",
        "specificity": "#22c55e",
        "hook": "#eab308",
        "cta": "#f97316",
    }

    st.markdown(f"**Total Score: {total}/50**")
    progress_val = min(total / 50, 1.0)
    st.progress(progress_val)

    for axis, score in scores.items():
        color = colors.get(axis, "#4f8cff")
        pct = score * 10
        st.markdown(
            f"""
        <div class="score-container">
            <div class="score-label">
                <span>{axis.capitalize()}</span>
                <span>{score}/10</span>
            </div>
            <div class="score-bar-bg">
                <div class="score-bar-fill" style="width: {pct}%; background: {color};"></div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    critique = quality_report.get("critique", [])
    if critique:
        with st.expander("📋 Improvement Suggestions"):
            for item in critique:
                st.markdown(f"- {item}")


def render_proposal_card(proposal_text, draft_version=None):
    """Render the proposal in a styled card."""
    version_badge = f" — Draft v{draft_version}" if draft_version else ""
    st.markdown(
        f"""
    <div class="proposal-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <span style="color: #4f8cff; font-weight: 600; font-size: 1.1rem;">📄 Generated Proposal{version_badge}</span>
        </div>
        <div class="proposal-text">{proposal_text}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_status_badge(status):
    """Render a status badge."""
    badge_class = {
        "complete": "badge-complete",
        "reviewing": "badge-reviewing",
        "draft": "badge-draft",
        "approved": "badge-complete",
        "revise": "badge-reviewing",
        "rejected": "badge-error",
    }.get(status, "badge-draft")

    st.markdown(
        f'<span class="status-badge {badge_class}">{status}</span>',
        unsafe_allow_html=True,
    )


def stream_proposal_generation(job_description, user_profile):
    """Call /proposal/generate with stream=true and parse SSE events."""
    data = {
        "job_description": job_description,
        "user_profile": user_profile,
        "stream": True,
    }
    st.session_state.completed_steps = []
    st.session_state.active_step = None
    st.session_state.proposal_result = None

    progress_container = st.container()
    proposal_container = st.container()

    resp = api_request("POST", "/proposal/generate", data=data, stream=True)

    if isinstance(resp, dict) and "error" in resp:
        st.error(f"❌ {resp['error']}")
        return

    if resp.status_code >= 400:
        try:
            error = resp.json().get("detail", "Unknown error")
        except Exception:
            error = resp.text
        st.error(f"❌ {error}")
        return

    completed = []
    main_steps = [
        "input_collection",
        "analyze_job",
        "match_profile",
        "draft_proposal",
        "evaluate_quality",
        "human_review",
    ]

    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data: "):
            raw = line[6:]
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            node = event.get("node", "")
            status = event.get("status", "")

            if status == "error":
                st.error(f"❌ {event.get('detail', 'Unknown error')}")
                return

            if node == "__end__" and status == "done":
                st.session_state.proposal_result = event.get("data", {})
                st.session_state.active_step = None
                st.session_state.completed_steps = list(completed)
                with progress_container:
                    render_step_progress(completed, None, main_steps)
                break

            if node in STEP_KEY_MAP:
                completed.append(node)
                step_info = STEP_KEY_MAP[node]

                # Find next pending step
                next_step = None
                for s in main_steps:
                    if s not in completed:
                        next_step = s
                        break

                st.session_state.completed_steps = list(completed)
                st.session_state.active_step = next_step

                with progress_container:
                    progress_container.empty()
                with progress_container:
                    render_step_progress(completed, next_step, main_steps)

    # Show the result
    result = st.session_state.proposal_result
    if result:
        with proposal_container:
            st.markdown("---")
            render_status_badge(result.get("status", "unknown"))
            render_proposal_card(
                result.get("proposal_draft", "No proposal generated."),
                result.get("draft_version"),
            )
            render_quality_scores(result.get("quality_report"))


def stream_resume_action(decision, feedback=""):
    """Call /proposal/resume with stream=true."""
    data = {
        "decision": decision,
        "feedback": feedback,
        "stream": True,
    }

    progress_container = st.container()
    result_container = st.container()

    resp = api_request("POST", "/proposal/resume", data=data, stream=True)

    if isinstance(resp, dict) and "error" in resp:
        st.error(f"❌ {resp['error']}")
        return

    if resp.status_code >= 400:
        try:
            error = resp.json().get("detail", "Unknown error")
        except Exception:
            error = resp.text
        st.error(f"❌ {error}")
        return

    completed = []
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data: "):
            raw = line[6:]
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            node = event.get("node", "")
            status = event.get("status", "")

            if status == "error":
                st.error(f"❌ {event.get('detail', 'Unknown error')}")
                return

            if node == "__end__" and status == "done":
                st.session_state.proposal_result = event.get("data", {})
                with progress_container:
                    st.success("✅ Action completed!")
                break

            if node in STEP_KEY_MAP:
                completed.append(node)
                with progress_container:
                    progress_container.empty()
                with progress_container:
                    for c in completed:
                        step = STEP_KEY_MAP[c]
                        st.markdown(f"✅ {step['icon']} {step['label']}")

    result = st.session_state.proposal_result
    if result:
        with result_container:
            render_status_badge(result.get("status", "unknown"))
            render_proposal_card(
                result.get("proposal_draft") or result.get("final_proposal", ""),
                result.get("draft_version"),
            )


# ─── Sidebar: Authentication ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🚀 Upwork Proposal AI")
    st.markdown("---")

    if st.session_state.token:
        st.markdown(f"**Logged in as:**")
        st.markdown(f"📧 `{st.session_state.user_email}`")
        if st.button("🚪 Logout", use_container_width=True):
            for key in defaults:
                st.session_state[key] = defaults[key]
            st.rerun()
        st.markdown("---")

        # Profile section in sidebar
        st.markdown("### 👤 Your Profile")
        st.session_state.bio = st.text_area(
            "Bio",
            value=st.session_state.bio,
            placeholder="Brief description of your expertise...",
            height=80,
        )
        st.session_state.skills = st.text_input(
            "Skills (comma-separated)",
            value=st.session_state.skills,
            placeholder="Python, React, AWS...",
        )
        st.session_state.past_projects = st.text_input(
            "Past Projects (comma-separated)",
            value=st.session_state.past_projects,
            placeholder="E-commerce app, API platform...",
        )
        st.session_state.rate = st.text_input(
            "Hourly Rate",
            value=st.session_state.rate,
            placeholder="$50/hr",
        )
    else:
        auth_tab = st.radio(
            "", ["Login", "Sign Up"], horizontal=True, label_visibility="collapsed"
        )

        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")

        if auth_tab == "Login":
            if st.button("🔐 Login", use_container_width=True):
                if email and password:
                    with st.spinner("Authenticating..."):
                        result = api_request(
                            "POST",
                            "/auth/login",
                            {
                                "email": email,
                                "password": password,
                            },
                        )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.token = result["access_token"]
                        st.session_state.user_id = result["user_id"]
                        st.session_state.user_email = result["email"]
                        st.success("✅ Logged in!")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.warning("Please enter email and password.")
        else:
            if st.button("📝 Sign Up", use_container_width=True):
                if email and password:
                    with st.spinner("Creating account..."):
                        result = api_request(
                            "POST",
                            "/auth/signup",
                            {
                                "email": email,
                                "password": password,
                            },
                        )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(
                            "✅ Account created! Please check your email to verify, then login."
                        )
                else:
                    st.warning("Please enter email and password.")


# ─── Main Content ────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="main-header">
    <h1>🚀 Upwork Proposal AI</h1>
    <p>Generate winning proposals with AI-powered analysis and real-time feedback</p>
</div>
""",
    unsafe_allow_html=True,
)

if not st.session_state.token:
    st.info("👈 Please login or sign up using the sidebar to get started.")
    st.stop()


# ─── Tab Layout ───────────────────────────────────────────────────────────────
tab_proposal, tab_review, tab_history = st.tabs(
    [
        "📝 Generate Proposal",
        "👤 Human Review",
        "📜 Step History",
    ]
)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: Generate Proposal
# ═══════════════════════════════════════════════════════════════════════════════
with tab_proposal:
    st.markdown("### 📋 Job Description")
    job_description = st.text_area(
        "Paste the Upwork job description here",
        height=200,
        placeholder="Looking for an experienced developer to build a full-stack web application...",
        label_visibility="collapsed",
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        generate_btn = st.button(
            "🚀 Generate Proposal",
            use_container_width=True,
            disabled=st.session_state.is_generating,
        )

    if generate_btn:
        # Validate inputs
        if not job_description or len(job_description.strip()) < 20:
            st.error("❌ Job description must be at least 20 characters.")
        elif not st.session_state.bio:
            st.error("❌ Please fill in your Bio in the sidebar.")
        elif not st.session_state.skills:
            st.error("❌ Please fill in your Skills in the sidebar.")
        else:
            st.session_state.is_generating = True

            user_profile = {
                "bio": st.session_state.bio,
                "skills": [
                    s.strip() for s in st.session_state.skills.split(",") if s.strip()
                ],
                "past_projects": [
                    p.strip()
                    for p in st.session_state.past_projects.split(",")
                    if p.strip()
                ]
                or ["General projects"],
                "rate": st.session_state.rate or "Negotiable",
            }

            st.markdown("### ⚡ Progress")
            stream_proposal_generation(job_description, user_profile)
            st.session_state.is_generating = False

    # Show previous result if exists
    elif st.session_state.proposal_result and not st.session_state.is_generating:
        result = st.session_state.proposal_result
        st.markdown("### 📄 Last Generated Proposal")
        render_status_badge(result.get("status", "unknown"))
        render_proposal_card(
            result.get("proposal_draft", ""),
            result.get("draft_version"),
        )
        render_quality_scores(result.get("quality_report"))


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: Human Review
# ═══════════════════════════════════════════════════════════════════════════════
with tab_review:
    result = st.session_state.proposal_result

    if not result:
        st.info("📝 Generate a proposal first to review it here.")
    elif result.get("status") == "complete":
        st.success("✅ This proposal has been finalized.")
        render_proposal_card(
            result.get("final_proposal") or result.get("proposal_draft", ""),
            result.get("draft_version"),
        )
    else:
        st.markdown("### 📄 Proposal Under Review")
        render_status_badge(result.get("status", "unknown"))
        render_proposal_card(
            result.get("proposal_draft", ""),
            result.get("draft_version"),
        )

        if result.get("quality_report"):
            render_quality_scores(result["quality_report"])

        st.markdown("---")
        st.markdown("### 🎯 Your Decision")

        col_approve, col_revise, col_reject = st.columns(3)

        with col_approve:
            if st.button("✅ Approve", use_container_width=True, type="primary"):
                st.markdown("### ⚡ Finalizing...")
                stream_resume_action("approved")

        with col_reject:
            if st.button("❌ Reject", use_container_width=True):
                st.markdown("### ⚡ Processing...")
                stream_resume_action("rejected")

        with col_revise:
            revise_clicked = st.button("✏️ Revise", use_container_width=True)

        if revise_clicked:
            feedback = st.text_area(
                "What should be changed?",
                placeholder="Make the tone more professional, emphasize Python experience...",
                height=100,
            )
            if st.button("📤 Submit Revision", use_container_width=True):
                if not feedback:
                    st.error("❌ Feedback is required for revision.")
                else:
                    st.markdown("### ⚡ Revising...")
                    stream_resume_action("revise", feedback)

        # Show revision feedback area if waiting
        if result.get("waiting_for_review"):
            st.info("🔄 A revised draft is ready. Review the updated proposal above.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: Step History
# ═══════════════════════════════════════════════════════════════════════════════
with tab_history:
    result = st.session_state.proposal_result

    if not result:
        st.info("📝 Generate a proposal first to see the step history.")
    else:
        draft_history = result.get("draft_history", [])

        st.markdown("### 📜 Draft History")

        if not draft_history:
            st.markdown("*This is the first draft — no revision history yet.*")
        else:
            for entry in draft_history:
                version = entry.get("version", "?")
                draft = entry.get("draft", "")
                qr = entry.get("quality_report", {})
                feedback = entry.get("human_feedback", "")

                st.markdown(
                    f"""
                <div class="history-item">
                    <div class="history-version">Draft v{version}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                with st.expander(
                    f"📄 Draft v{version} — Score: {qr.get('total_score', '?')}/50"
                ):
                    st.markdown(f"**Proposal Text:**")
                    st.text(draft)

                    if qr:
                        st.markdown("**Quality Scores:**")
                        scores = qr.get("scores", {})
                        score_cols = st.columns(len(scores))
                        for i, (axis, score) in enumerate(scores.items()):
                            with score_cols[i]:
                                st.metric(axis.capitalize(), f"{score}/10")

                        critique = qr.get("critique", [])
                        if critique:
                            st.markdown("**Critique:**")
                            for c in critique:
                                st.markdown(f"- {c}")

                    if feedback:
                        st.markdown(f"**Human Feedback:** {feedback}")

        # Current draft
        st.markdown("---")
        st.markdown("### 📄 Current Draft")
        render_status_badge(result.get("status", "unknown"))
        render_proposal_card(
            result.get("proposal_draft") or result.get("final_proposal", ""),
            result.get("draft_version"),
        )

        # Completed steps log
        if st.session_state.completed_steps:
            st.markdown("---")
            st.markdown("### 🔗 Completed Agent Steps")
            for step_key in st.session_state.completed_steps:
                step = STEP_KEY_MAP.get(step_key)
                if step:
                    st.markdown(
                        f"✅ {step['icon']} **{step['label']}** — {step['desc']}"
                    )
