"""
Day 34-35 -- Streamlit UI (3 pages)
======================================
ONE concept: a real, usable web interface for the placement prep agent.

Pages:
  Research   -- enter company + role, watch nodes run in real time, see results
  Chat       -- ask follow-up questions, get RAG-backed answers
  Companies  -- comparison table of all companies researched this session

Run:
  streamlit run week5/day34_35_app.py

What is NEW today:
  st.status()         -- real-time progress box while graph streams
  st.session_state    -- persist results between Streamlit reruns
  st.chat_input()     -- chat UI with message history
  st.dataframe()      -- comparison table
  st.spinner()        -- spinner during API calls
  Page navigation     -- st.sidebar.radio()
"""

import os, re, json
from dotenv import load_dotenv

load_dotenv()

try:
    import streamlit as st
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit", "-q"])
    import streamlit as st


# ══════════════════════════════════════════════════════════════════
#  AGENT FUNCTIONS (standalone -- no imports from other week5 files)
# ══════════════════════════════════════════════════════════════════

def _gemini(prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.5-flash")
    return model.generate_content(prompt).text.strip()


def _search(query: str) -> list:
    from tavily import TavilyClient
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    res = tavily.search(query=query, max_results=5, search_depth="basic")
    return [r.get("content", "")[:500] for r in res.get("results", []) if r.get("content")]


# ── Research pipeline (matches Day 23 linear graph, streamed manually) ─────────
def stream_research(company: str, role: str, focus: str):
    """
    Generator that yields (node_name, partial_state) tuples.
    Streamlit consumes these one at a time and updates st.status().
    """
    state = {"company": company, "role": role, "focus": focus,
             "metadata": {}, "research_data": [], "synthesis": "", "questions": []}

    # Node 1: metadata
    yield "metadata_node", {}
    try:
        snippets = _search(f"{company} company founded headquarters size")
        content  = " ".join(snippets)
        raw = _gemini(
            f"From text about {company}, reply EXACTLY:\n"
            "Founded: <>\nHQ: <>\nType: <>\n\n"
            f"Text: {content[:1500]}"
        )
        meta = {"founded": "?", "hq": "?", "type": "?"}
        for line in raw.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                if k in meta:
                    meta[k] = v.strip()
        state["metadata"] = meta
    except Exception as e:
        state["metadata"] = {"founded": "?", "hq": "?", "type": "?"}
    yield "metadata_node", {"metadata": state["metadata"]}

    # Node 2: research
    yield "research_node", {}
    try:
        snippets = _search(f"{company} {role} interview experience questions 2024 2025")
        state["research_data"] = snippets
    except Exception as e:
        state["research_data"] = []
    yield "research_node", {"research_data": state["research_data"]}

    # Node 3: synthesize
    yield "synthesize_node", {}
    try:
        block = "\n---\n".join(state["research_data"])
        meta  = state["metadata"]
        synthesis = _gemini(
            f"Summarize {company} {role} interview for {focus} focus. 150 words.\n"
            f"Company: Founded {meta.get('founded','?')}, HQ {meta.get('hq','?')}.\n\n{block[:3000]}"
        )
        state["synthesis"] = synthesis
    except Exception as e:
        state["synthesis"] = f"Error: {e}"
    yield "synthesize_node", {"synthesis": state["synthesis"]}

    # Node 4: questions
    yield "question_node", {}
    try:
        text  = _gemini(
            f"5 {focus} interview questions for {company} {role}. "
            f"Q1-Q5 with [Easy/Medium/Hard]. Context:\n{state['synthesis'][:400]}"
        )
        parts = re.split(r"\n(?=Q\d+\.)", text.strip())
        qs    = [p.strip() for p in parts if p.strip()] or [text.strip()]
        state["questions"] = qs
    except Exception as e:
        state["questions"] = [f"Error: {e}"]
    yield "question_node", {"questions": state["questions"]}

    yield "done", state


def rag_answer(question: str, company: str) -> str:
    """Answer a question using Gemini with session research as context."""
    context = ""
    if "research_results" in st.session_state:
        r = st.session_state.research_results
        synthesis = r.get("synthesis", "")
        metadata  = r.get("metadata", {})
        context   = f"Company: {r.get('company')}\nRole: {r.get('role')}\n"
        context  += f"Founded: {metadata.get('founded','?')} | HQ: {metadata.get('hq','?')}\n\n"
        context  += f"Research summary:\n{synthesis}"
    try:
        return _gemini(
            f"You are a placement prep assistant. Answer the student's question.\n\n"
            f"Context about {company}:\n{context[:2000]}\n\n"
            f"Student question: {question}\n\n"
            f"Give a concise, actionable answer."
        )
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════════
#  SHARED UI HELPERS
#  Called from multiple pages -- keeps page functions short.
# ══════════════════════════════════════════════════════════════════

def _render_company_card(company: str, role: str, meta: dict):
    """Three metric chips: Founded | HQ | Type."""
    st.subheader(f"{company} -- {role}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Founded", meta.get("founded", "?"))
    col2.metric("HQ",      meta.get("hq",      "?"))
    col3.metric("Type",    meta.get("type",     "?"))


def _render_questions(questions: list, focus: str):
    """Expandable list of interview questions."""
    if not questions:
        st.info("No questions generated.")
        return
    st.markdown(f"### {focus} Interview Questions")
    for i, q in enumerate(questions, 1):
        with st.expander(f"Q{i}. {q[:80]}..."):
            st.markdown(q)


# ══════════════════════════════════════════════════════════════════
#  PAGE 1: RESEARCH
# ══════════════════════════════════════════════════════════════════
def page_research():
    st.header("Company Research")
    st.caption("Enter a company and role to generate a full interview prep guide.")

    col1, col2 = st.columns(2)
    with col1:
        company = st.text_input("Company", placeholder="e.g. Google, Flipkart, Razorpay")
        role    = st.text_input("Role",    placeholder="e.g. Software Engineer, SDE-2")
    with col2:
        focus   = st.selectbox("Focus Area", ["DSA", "System Design", "Behavioral"])
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("Research", type="primary", use_container_width=True)

    if not run_btn:
        return

    if not company or not role:
        st.warning("Please enter both company and role.")
        return

    # ── Stream the agent, update status in real time ──
    final_state = {}

    # Single dict: node_name -> (running label, done label)
    NODE_INFO = {
        "metadata_node":   ("Fetching company basics...",        "Company basics fetched"),
        "research_node":   ("Searching interview experiences...", "Interview data collected"),
        "synthesize_node": ("Synthesizing with AI...",           "Synthesis complete"),
        "question_node":   ("Generating questions...",           "Questions generated"),
    }

    with st.status("Starting research...", expanded=True) as status:
        step_placeholder = st.empty()
        current_node = None

        for event_type, data in stream_research(company, role, focus):
            if event_type == "done":
                final_state = data
                status.update(label="Research complete!", state="complete", expanded=False)
            elif data:  # node completed (has output data)
                if current_node in NODE_INFO:
                    step_placeholder.markdown(f"✅ {NODE_INFO[current_node][1]}")
                    step_placeholder = st.empty()
            else:  # node started (empty data dict)
                current_node = event_type
                running_label = NODE_INFO.get(event_type, (event_type, event_type))[0]
                status.update(label=running_label)
                step_placeholder.markdown(f"⏳ {running_label}")

    # ── Display results ──
    if not final_state:
        st.error("Research failed. Check your API keys.")
        return

    # Store in session for Chat page
    final_state["company"] = company
    final_state["role"]    = role
    st.session_state.research_results = final_state

    # Store in companies list for comparison
    if "companies" not in st.session_state:
        st.session_state.companies = {}
    st.session_state.companies[company] = final_state

    # Show company card + summary + questions
    meta = final_state.get("metadata", {})
    st.markdown("---")
    _render_company_card(company, role, meta)
    st.markdown("### Interview Summary")
    st.markdown(final_state.get("synthesis", "No summary available."))
    _render_questions(final_state.get("questions", []), focus)


# ══════════════════════════════════════════════════════════════════
#  PAGE 2: CHAT
# ══════════════════════════════════════════════════════════════════
def page_chat():
    st.header("Ask Questions")
    st.caption("Ask follow-up questions about your research. Answers use your session's research context.")

    # Which company context to use
    if "companies" in st.session_state and st.session_state.companies:
        selected = st.selectbox(
            "Context company",
            list(st.session_state.companies.keys()),
        )
    else:
        selected = ""
        st.info("Research a company first (Research page) to enable contextual answers.")

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask anything about your interview prep..."):
        # Show user message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get answer
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = rag_answer(prompt, selected or "the company")
            st.markdown(answer)
            # Show context note
            if selected:
                st.caption(f"Using research context for {selected}")

        st.session_state.chat_history.append({"role": "assistant", "content": answer})

    if st.session_state.chat_history:
        if st.button("Clear chat"):
            st.session_state.chat_history = []
            st.rerun()


# ══════════════════════════════════════════════════════════════════
#  PAGE 3: MY COMPANIES
# ══════════════════════════════════════════════════════════════════
def page_companies():
    st.header("My Companies")
    st.caption("All companies researched this session.")

    if "companies" not in st.session_state or not st.session_state.companies:
        st.info("No companies researched yet. Go to the Research page to get started.")
        return

    companies = st.session_state.companies

    # ── Comparison table ──
    st.subheader("Comparison Table")
    import pandas as pd

    rows = []
    for company, data in companies.items():
        meta = data.get("metadata", {})
        rows.append({
            "Company":   company,
            "Role":      data.get("role", "?"),
            "Founded":   meta.get("founded", "?"),
            "HQ":        meta.get("hq", "?"),
            "Type":      meta.get("type", "?"),
            "Questions": len(data.get("questions", [])),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Per-company detail ──
    st.subheader("Details")
    selected = st.selectbox("Select company", list(companies.keys()))
    data = companies[selected]

    st.markdown("**Interview Summary**")
    st.markdown(data.get("synthesis", "No summary."))
    _render_questions(data.get("questions", []), data.get("focus", "DSA"))

    # ── Recommendation ──
    st.markdown("---")
    if st.button("Which company should I target first?", type="secondary"):
        with st.spinner("Analyzing..."):
            summaries = "\n\n".join(
                f"{c}: {d.get('synthesis','')[:200]}"
                for c, d in companies.items()
            )
            try:
                rec = _gemini(
                    f"Based on these company summaries, recommend which one a "
                    f"fresher SWE should target first and why (3 sentences max):\n\n{summaries}"
                )
                st.success(rec)
            except Exception as e:
                st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════
#  APP SHELL
# ══════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title="Placement Prep Agent",
        page_icon="🎯",
        layout="wide",
    )

    st.sidebar.title("Placement Prep")
    st.sidebar.markdown("*AI-powered interview preparation*")
    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["Research", "Chat", "My Companies"],
        label_visibility="collapsed",
    )

    st.sidebar.divider()
    st.sidebar.caption("Week 5 — Day 34-35")

    if page == "Research":
        page_research()
    elif page == "Chat":
        page_chat()
    else:
        page_companies()


if __name__ == "__main__":
    main()
