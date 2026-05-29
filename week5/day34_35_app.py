"""
Day 34-35 -- Placement Prep Agent (Full UI)
============================================
Run:  streamlit run week5/day34_35_app.py
"""

import os, re, json, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from dotenv import load_dotenv
load_dotenv()

try:
    import streamlit as st
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit", "-q"])
    import streamlit as st

# ─── Settings persistence ────────────────────────────────────────────────────
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", ".pp_settings.json")
DEFAULTS = {
    "default_focus": "DSA",
    "num_questions": 5,
    "search_depth":  "basic",
    "gemini_model":  "gemini-2.5-flash",
    "show_chips":    True,
    "name":          "",
}

def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE) as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s

def save_settings(s):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(s, f, indent=2)
        return True
    except Exception:
        return False

def get_cfg():
    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()
    return st.session_state.settings

def log_research(company, role, focus, num_q, duration_s):
    if "progress_log" not in st.session_state:
        st.session_state.progress_log = []
    st.session_state.progress_log.append({
        "company":   company, "role": role, "focus": focus,
        "questions": num_q,   "duration": round(duration_s, 1),
        "timestamp": datetime.now().strftime("%d %b, %H:%M"),
        "date":      date.today().isoformat(),
    })


# ════════════════════════════════════════════════════════════════════
#  CSS
# ════════════════════════════════════════════════════════════════════
CSS = """
<style>
/* ── Tokens ── */
:root {
  --border: #e5e5e5; --border-hov: #cccccc;
  --text-hi: #111111; --text-mid: #555555; --text-lo: #999999; --text-lbl: #888888;
  --shadow: 0 1px 3px rgba(0,0,0,.06);
  --green:#16a34a; --green-bg:#f0fdf4; --green-bd:#bbf7d0;
  --orange:#ea580c; --orange-bg:#fff7ed; --orange-bd:#fed7aa;
  --red:#dc2626; --red-bg:#fef2f2; --red-bd:#fecaca;
  --blue:#2563eb; --blue-bg:#eff6ff; --blue-bd:#bfdbfe;
}

/* ── Shell ── */
.stApp { background: #fff; }
.stApp > header { background: #fff !important; border-bottom: 1px solid var(--border); }
.block-container { padding-top: 28px !important; max-width: 920px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: #f7f7f7 !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
[data-testid="stSidebar"] hr { border-color: var(--border) !important; margin: 10px 0 !important; }

/* ── Sidebar nav buttons ── */
[data-testid="stSidebar"] .stButton > button {
  background: transparent !important; border: none !important;
  border-radius: 8px !important; text-align: left !important;
  justify-content: flex-start !important;
  padding: 8px 12px !important; margin: 1px 0 !important;
  font-size: 13px !important; font-weight: 400 !important;
  color: #555 !important; height: 36px !important;
  line-height: 1.2 !important; box-shadow: none !important;
  transform: none !important; transition: background .12s !important;
  letter-spacing: 0 !important; width: 100% !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(0,0,0,.05) !important; color: #111 !important;
  transform: none !important; box-shadow: none !important;
}
/* Active nav item (type="primary") */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: #ececec !important; color: #111 !important; font-weight: 500 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
  background: #e5e5e5 !important;
}
[data-testid="stSidebar"] .stCaption p { color: var(--text-lo) !important; font-size: 11px !important; }

/* ── Main buttons ── */
.stButton > button {
  background: #111 !important; color: #fff !important;
  border: none !important; border-radius: 8px !important;
  font-size: 13px !important; font-weight: 500 !important;
  padding: 8px 20px !important; box-shadow: none !important;
  transition: background .15s, transform .15s !important;
}
.stButton > button:hover {
  background: #333 !important; transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
  background: transparent !important; color: var(--text-mid) !important;
  border: 1px solid var(--border) !important;
}
.stButton > button[kind="secondary"]:hover {
  border-color: var(--border-hov) !important; color: var(--text-hi) !important;
  transform: none !important;
}

/* ── Form submit button (Run Research) ── */
[data-testid="stFormSubmitButton"] button {
  background: #F5A623 !important; color: #1a1100 !important;
  border: none !important; border-radius: 999px !important;
  font-size: 13px !important; font-weight: 700 !important;
  padding: 10px 28px !important; width: 100% !important;
  box-shadow: 0 2px 8px rgba(245,166,35,.35) !important;
  transition: background .15s, box-shadow .15s, transform .15s !important;
  letter-spacing: .01em !important;
}
[data-testid="stFormSubmitButton"] button:hover {
  background: #E8950D !important;
  box-shadow: 0 4px 14px rgba(245,166,35,.45) !important;
  transform: translateY(-1px) !important;
}

/* ── Inputs ── */
.stTextInput input, .stTextArea textarea,
[data-testid="stForm"] .stTextInput input,
[data-testid="stForm"] .stTextArea textarea,
div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea {
  border: 1px solid #e0e0e0 !important; border-radius: 8px !important;
  color: #111 !important; font-size: 13px !important;
  background: #ffffff !important;
  transition: border-color .2s, box-shadow .2s !important;
  -webkit-text-fill-color: #111 !important;
}
/* Input wrapper background (Streamlit wraps input in a div that also gets themed) */
div[data-baseweb="input"], div[data-baseweb="textarea"] {
  background: #ffffff !important; border-radius: 8px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: #111 !important; box-shadow: 0 0 0 2px rgba(0,0,0,.06) !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {
  color: #bbb !important; opacity: 1 !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label {
  font-size: 10px !important; font-weight: 700 !important;
  color: #999 !important; text-transform: uppercase !important;
  letter-spacing: .08em !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div,
div[data-baseweb="select"] > div {
  border: 1px solid #e0e0e0 !important; border-radius: 8px !important;
  background: #ffffff !important; font-size: 13px !important;
}

/* ── Pills (Focus Area) ── */
[data-testid="stPills"] button {
  border: 1px solid var(--border) !important; border-radius: 20px !important;
  background: #fff !important; color: var(--text-mid) !important;
  font-size: 12px !important; padding: 4px 14px !important;
  transition: all .15s !important; box-shadow: none !important;
  transform: none !important;
}
[data-testid="stPills"] button:hover { border-color: #999 !important; color: var(--text-hi) !important; }
[data-testid="stPills"] button[aria-pressed="true"],
[data-testid="stPills"] button[data-selected="true"] {
  background: #111 !important; color: #fff !important;
  border-color: #111 !important;
}
[data-testid="stPills"] label {
  font-size: 10px !important; font-weight: 700 !important;
  color: var(--text-lbl) !important; text-transform: uppercase !important;
  letter-spacing: .08em !important;
}

/* ── Form card ── */
[data-testid="stForm"] {
  background: #fff !important; border: 1px solid var(--border) !important;
  border-radius: 10px !important; padding: 22px !important;
  box-shadow: var(--shadow) !important;
}
[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
  width: 100% !important;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
  background: #fafafa !important; border: 1px solid var(--border) !important;
  border-radius: 8px !important; padding: 14px 16px !important; box-shadow: var(--shadow) !important;
}
[data-testid="stMetricValue"] { color: var(--text-hi) !important; font-size: 22px !important; font-weight: 600 !important; }
[data-testid="stMetricLabel"] { color: var(--text-lo) !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: .05em; }

/* ── Expanders ── */
.stExpander {
  border: 1px solid var(--border) !important; border-radius: 8px !important;
  background: #fff !important; margin-bottom: 6px !important; box-shadow: var(--shadow) !important;
}
.stExpander:hover { border-color: var(--border-hov) !important; }
.stExpander details summary { font-size: 13px !important; color: var(--text-hi) !important; padding: 10px 14px !important; }

/* ── Status box ── */
[data-testid="stStatusWidget"] {
  border: 1px solid var(--border) !important; border-radius: 10px !important; box-shadow: var(--shadow) !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important; border-radius: 10px !important;
  overflow: hidden !important; box-shadow: var(--shadow) !important;
}

/* ── Chat hero ── */
.chat-hero {
  text-align: center;
  padding: 64px 20px 44px;
}
.chat-greeting {
  font-size: 46px; font-weight: 700; letter-spacing: -.04em;
  line-height: 1.1; margin-bottom: 12px;
}
.hello-hi  { color: #111; }
.hello-name { color: #666; }
.chat-sub {
  font-size: 20px; color: #bbb; font-weight: 400; letter-spacing: -.01em;
}

/* ── Suggestion cards ── */
.sug-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin: 0 auto 32px; max-width: 860px; }
.sug-card {
  background: #fafafa; border: 1px solid var(--border);
  border-radius: 14px; padding: 18px 16px 14px;
  min-height: 136px; cursor: pointer;
  display: flex; flex-direction: column; gap: 6px;
  transition: border-color .18s, box-shadow .18s, transform .18s;
}
.sug-card:hover {
  border-color: #bbb; transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,.07);
}
.sug-icon { font-size: 20px; line-height: 1; }
.sug-title { font-size: 13px; font-weight: 600; color: #111; line-height: 1.4; }
.sug-desc  { font-size: 11.5px; color: #999; line-height: 1.55; margin-top: 2px; }

/* ── Hidden card trigger buttons ── */
.sug-btn-row { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; max-width: 860px; margin: -10px auto 0; }
.sug-btn-row .stButton > button {
  background: transparent !important; color: transparent !important;
  border: none !important; box-shadow: none !important;
  height: 136px !important; margin-top: -146px !important;
  border-radius: 14px !important; cursor: pointer !important;
  transform: none !important; position: relative !important;
  z-index: 10 !important; opacity: 0 !important;
}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
  background: #fafafa !important; border: 1px solid var(--border) !important;
  border-radius: 12px !important; margin-bottom: 8px !important;
}

/* ── Chat input bar ── */
[data-testid="stChatInput"] textarea {
  border-radius: 24px !important; border: 1px solid var(--border) !important;
  background: #fafafa !important; font-size: 14px !important;
  padding: 12px 20px !important;
  box-shadow: 0 2px 8px rgba(0,0,0,.05) !important;
}
[data-testid="stChatInput"] textarea:focus {
  border-color: #111 !important; box-shadow: 0 2px 12px rgba(0,0,0,.1) !important;
}
[data-testid="stChatInput"] button {
  border-radius: 50% !important; background: #111 !important;
  color: #fff !important; border: none !important;
}

/* ── Typography ── */
h1 { font-size: 22px !important; font-weight: 600 !important; color: var(--text-hi) !important; letter-spacing: -.02em !important; margin-bottom: 2px !important; }
h2 { font-size: 18px !important; font-weight: 500 !important; color: var(--text-hi) !important; margin: 0 0 12px !important; }
h3 { font-size: 15px !important; font-weight: 600 !important; color: var(--text-hi) !important; }
p  { color: #333; font-size: 14px; }
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 20px 0 !important; }
.stCaption p { color: var(--text-lo) !important; font-size: 12px !important; }
[data-testid="stAlert"] { border-radius: 8px !important; font-size: 13px !important; }

/* ── Custom components ── */
.breadcrumb {
  font-size: 13px; color: var(--text-lo);
  padding-bottom: 16px; margin-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.breadcrumb strong { color: var(--text-hi); font-weight: 500; }
.nav-lbl {
  font-size: 10.5px; font-weight: 600; color: #aaa;
  text-transform: uppercase; letter-spacing: .08em;
  padding: 18px 0 4px; display: block;
}
.chip-row { display: flex; gap: 7px; flex-wrap: wrap; margin: 10px 0 6px; }
.chip {
  padding: 5px 13px; border: 1px solid var(--border); border-radius: 20px;
  font-size: 12px; color: var(--text-mid); background: #fff; line-height: 1.4;
}
.context-chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--blue-bg); border: 1px solid var(--blue-bd);
  border-radius: 20px; font-size: 12px; color: var(--blue); padding: 4px 12px; font-weight: 500;
}
.badge-easy   { font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px; background:var(--green-bg);  color:var(--green);  border:1px solid var(--green-bd); }
.badge-medium { font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px; background:var(--orange-bg); color:var(--orange); border:1px solid var(--orange-bd); }
.badge-hard   { font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px; background:var(--red-bg);    color:var(--red);    border:1px solid var(--red-bd); }
.co-card {
  border: 1px solid var(--border); border-radius: 10px;
  padding: 18px 20px; margin-bottom: 16px; box-shadow: var(--shadow);
}
.co-icon {
  display: inline-flex; width: 34px; height: 34px; border-radius: 8px;
  background: #111; color: #fff; align-items: center; justify-content: center;
  font-size: 15px; font-weight: 700; margin-right: 10px; vertical-align: middle;
}
.sec-lbl {
  font-size: 11px; font-weight: 600; color: var(--text-lbl);
  text-transform: uppercase; letter-spacing: .07em; margin-bottom: 10px; display: block;
}
.prog-row {
  display: flex; align-items: center; gap: 12px; padding: 10px 14px;
  border: 1px solid var(--border); border-radius: 8px; margin-bottom: 7px; font-size: 13px;
}
.prog-done {
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--green-bg); border: 1px solid var(--green-bd); color: var(--green);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; flex-shrink: 0;
}
.api-ok   { color: var(--green);  font-size: 12px; font-weight: 500; }
.api-miss { color: var(--orange); font-size: 12px; font-weight: 500; }
.ai-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); display: inline-block; margin-right: 5px; }
</style>
"""


# ════════════════════════════════════════════════════════════════════
#  AGENT FUNCTIONS
# ════════════════════════════════════════════════════════════════════
def _gemini(prompt: str) -> str:
    import google.generativeai as genai
    cfg = get_cfg()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(cfg.get("gemini_model", "gemini-2.5-flash"))
    return model.generate_content(prompt).text.strip()

def _search(query: str, max_results: int = 5) -> list:
    from tavily import TavilyClient
    cfg = get_cfg()
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    res = tavily.search(query=query, max_results=max_results,
                        search_depth=cfg.get("search_depth", "basic"))
    return [r.get("content", "")[:500] for r in res.get("results", []) if r.get("content")]

def _search_domains(query: str, domains: list, max_results: int = 4) -> list:
    """Tavily search restricted to specific domains (e.g. glassdoor.com)."""
    from tavily import TavilyClient
    cfg = get_cfg()
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    res = tavily.search(query=query, max_results=max_results,
                        search_depth=cfg.get("search_depth", "basic"),
                        include_domains=domains)
    return [r.get("content", "")[:500] for r in res.get("results", []) if r.get("content")]

def _research_all(company: str, role: str, focus: str) -> dict:
    """
    Run three searches in parallel using ThreadPoolExecutor.

    Source 1 — General web (Tavily open search):
        Interview experiences, DSA questions, tips, tech blogs.

    Source 2 — Glassdoor (domain-filtered):
        Company ratings, interview difficulty, culture reviews,
        salary bands. Gives the 'insider' view no blog covers.

    Source 3 — Job portals (Naukri / LinkedIn / Indeed):
        Active JD requirements, must-have skills, CTC ranges.
        Tells you exactly what the company is hiring for right now.

    All three run simultaneously — total time ≈ slowest single search
    instead of 3× sequential time.
    """
    def _safe(future):
        try:
            return future.result(timeout=25)
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_general   = ex.submit(
            _search,
            f"{company} {role} interview experience questions {focus} 2024 2025",
        )
        f_glassdoor = ex.submit(
            _search_domains,
            f"{company} interview difficulty reviews culture rating work life balance",
            ["glassdoor.com"],
        )
        f_jobs = ex.submit(
            _search_domains,
            f"{company} {role} job requirements skills responsibilities",
            ["naukri.com", "linkedin.com", "indeed.com", "instahyre.com"],
        )

        return {
            "general":   _safe(f_general),
            "glassdoor": _safe(f_glassdoor),
            "jobs":      _safe(f_jobs),
        }

NODE_INFO = {
    "metadata_node":     ("Fetching company basics…",          "Company basics fetched"),
    "research_parallel": ("Searching 3 sources in parallel…",  "All sources searched"),
    "synthesize_node":   ("Synthesising with AI…",             "Synthesis complete"),
    "question_node":     ("Generating questions…",             "Questions generated"),
}

def stream_research(company, role, focus):
    cfg  = get_cfg()
    nq   = cfg.get("num_questions", 5)
    state = {"company": company, "role": role, "focus": focus,
             "metadata": {}, "research_data": [], "synthesis": "", "questions": []}

    yield "metadata_node", {}
    try:
        raw = _gemini(
            f"From web data about {company}, reply EXACTLY:\n"
            "Founded: <year>\nHQ: <city>\nType: <MNC/Startup/Product/Service>\n\n"
            f"Data: {' '.join(_search(f'{company} founded headquarters industry'))[:1500]}"
        )
        meta = {"founded": "?", "hq": "?", "type": "?"}
        for line in raw.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                if k in meta:
                    meta[k] = v.strip()
        state["metadata"] = meta
    except Exception:
        state["metadata"] = {"founded": "?", "hq": "?", "type": "?"}
    yield "metadata_node", {"metadata": state["metadata"]}

    # ── Parallel research: 3 sources at the same time ────────────
    yield "research_parallel", {}
    sources = {"general": [], "glassdoor": [], "jobs": []}
    try:
        sources = _research_all(company, role, focus)
    except Exception:
        pass
    state["research_data"]    = sources["general"]   # backward-compat
    state["research_sources"] = sources
    yield "research_parallel", {"research_sources": sources}

    # ── Synthesis: structured prompt using all three sources ──────
    yield "synthesize_node", {}
    try:
        meta  = state["metadata"]
        parts = []
        if sources.get("general"):
            parts.append("INTERVIEW EXPERIENCES:\n" +
                         "\n---\n".join(sources["general"]))
        if sources.get("glassdoor"):
            parts.append("GLASSDOOR REVIEWS & RATINGS:\n" +
                         "\n---\n".join(sources["glassdoor"]))
        if sources.get("jobs"):
            parts.append("JOB REQUIREMENTS & SKILLS:\n" +
                         "\n---\n".join(sources["jobs"]))
        block = "\n\n".join(parts) or "(no search results found)"
        state["synthesis"] = _gemini(
            f"Summarise {company} {role} interview prep for {focus}. Keep under 180 words.\n"
            f"Company: {company} | Founded: {meta.get('founded','?')} | HQ: {meta.get('hq','?')}\n\n"
            f"{block[:3500]}"
        )
    except Exception as e:
        state["synthesis"] = f"Could not synthesise: {e}"
    yield "synthesize_node", {"synthesis": state["synthesis"]}

    yield "question_node", {}
    try:
        text = _gemini(
            f"Generate exactly {nq} {focus} interview questions for {company} {role}.\n"
            f"Format each as: Q1. <question> [Easy/Medium/Hard]\n"
            f"Context: {state['synthesis'][:400]}"
        )
        parts = re.split(r"\n(?=Q\d+\.)", text.strip())
        state["questions"] = [p.strip() for p in parts if p.strip()] or [text.strip()]
    except Exception as e:
        state["questions"] = [f"Error: {e}"]
    yield "question_node", {"questions": state["questions"]}

    yield "done", state

def rag_answer(question, company):
    context = ""
    if "research_results" in st.session_state:
        r    = st.session_state.research_results
        meta = r.get("metadata", {})
        context = (f"Company: {r.get('company')} | Role: {r.get('role')} | "
                   f"Founded: {meta.get('founded','?')} | HQ: {meta.get('hq','?')}\n\n"
                   f"Summary:\n{r.get('synthesis','')}")
    try:
        return _gemini(
            f"You are a placement prep coach. Answer clearly and concisely.\n\n"
            f"Context about {company}:\n{context[:2000]}\n\nStudent: {question}"
        )
    except Exception as e:
        return f"Error: {e}"


# ════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════
def _breadcrumb(page: str):
    st.markdown(
        f'<div class="breadcrumb">Placement Prep '
        f'<span style="color:#ccc">/</span> <strong>{page}</strong></div>',
        unsafe_allow_html=True,
    )

def _company_card(company, role, meta):
    st.markdown(
        f'<div class="co-card">'
        f'<span class="co-icon">{company[0].upper()}</span>'
        f'<strong style="font-size:16px;vertical-align:middle">{company}</strong>'
        f'&nbsp;<span style="color:#999;font-size:13px;vertical-align:middle">— {role}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Founded", meta.get("founded", "?"))
    c2.metric("HQ",      meta.get("hq",      "?"))
    c3.metric("Type",    meta.get("type",     "?"))

def _questions(questions, focus):
    if not questions:
        st.info("No questions generated.")
        return
    st.markdown(f'<span class="sec-lbl">{focus} Interview Questions</span>',
                unsafe_allow_html=True)
    diff_map = {"easy": "badge-easy", "medium": "badge-medium", "hard": "badge-hard"}
    for i, q in enumerate(questions, 1):
        m     = re.search(r"\[(Easy|Medium|Hard)\]", q, re.IGNORECASE)
        badge = (f'<span class="{diff_map.get(m.group(1).lower())}">{m.group(1)}</span> '
                 if m else "")
        clean = re.sub(r"\[(Easy|Medium|Hard)\]", "", q, flags=re.IGNORECASE).strip()
        with st.expander(f"Q{i}. {clean[:90]}{'...' if len(clean)>90 else ''}"):
            st.markdown(badge + q, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  PAGE 1 — RESEARCH
# ════════════════════════════════════════════════════════════════════
SUGGESTIONS = [
    ("Google",    "SDE-2",            "DSA"),
    ("Flipkart",  "Backend Engineer", "Behavioral"),
    ("Microsoft", "PM",               "System Design"),
    ("Razorpay",  "Full Stack SDE",   "DSA"),
]
FOCUS_OPTS = ["DSA", "System Design", "Behavioral", "SQL", "Low-Level Design"]

def page_research():
    _breadcrumb("Research")
    st.title("Research")
    st.caption("Analyse any company in seconds — interview patterns, culture, and custom questions.")

    cfg = get_cfg()

    # ── Generate bar ──────────────────────────────────────────────
    st.markdown("## Start a new research session")
    gc1, gc2 = st.columns([6, 1])
    with gc1:
        gen = st.text_input("gen", label_visibility="collapsed",
                             placeholder="e.g. Research Google SDE-2 with focus on System Design",
                             key="gen_input")
    with gc2:
        if st.button("Go →", key="go_btn"):
            low = gen.lower()
            for c, r, f in SUGGESTIONS:
                if c.lower() in low:
                    st.session_state["_pf"] = (c, r, f)
                    st.rerun()

    # Static suggestion chips
    if cfg.get("show_chips", True):
        st.markdown(
            '<div class="chip-row">' +
            "".join(f'<span class="chip">🔍 {c} · {r} · {f}</span>'
                    for c, r, f in SUGGESTIONS) +
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Form card ─────────────────────────────────────────────────
    pf = st.session_state.get("_pf", ("", "", cfg.get("default_focus", "DSA")))

    with st.form("research_form"):
        fc1, fc2 = st.columns(2)
        with fc1:
            company = st.text_input("Company", value=pf[0],
                                    placeholder="e.g. Google, Flipkart")
        with fc2:
            role = st.text_input("Role", value=pf[1],
                                  placeholder="e.g. SDE-2, PM, Data Analyst")

        # Focus area pills
        try:
            focus = st.pills(
                "Focus Area", FOCUS_OPTS,
                default=pf[2] if pf[2] in FOCUS_OPTS else "DSA",
            )
        except AttributeError:
            # Streamlit < 1.40 fallback
            focus = st.radio("Focus Area", FOCUS_OPTS,
                             index=FOCUS_OPTS.index(pf[2]) if pf[2] in FOCUS_OPTS else 0,
                             horizontal=True)

        fb1, fb2 = st.columns([3, 1])
        with fb1:
            st.caption("Powered by Tavily + Gemini")
        with fb2:
            run = st.form_submit_button("+ Run Research", use_container_width=True)

    if not run:
        return
    if not company or not role:
        st.warning("Please enter both Company and Role.")
        return
    if not focus:
        st.warning("Please select a Focus Area.")
        return

    # ── Stream ────────────────────────────────────────────────────
    t0          = time.time()
    final       = {}
    cur_node    = None

    with st.status("Starting research…", expanded=True) as status:
        slot = st.empty()
        for ev, data in stream_research(company, role, focus):
            if ev == "done":
                final = data
                status.update(label="✓ Research complete", state="complete", expanded=False)

            elif data:
                # ── Node completed — show result summary ──────────
                if ev == "research_parallel":
                    src = data.get("research_sources", {})
                    ng  = len(src.get("general",   []))
                    ngd = len(src.get("glassdoor", []))
                    nj  = len(src.get("jobs",      []))
                    slot.markdown(
                        f"✅ Sources searched — "
                        f"🔍 Web: **{ng}** &nbsp;|&nbsp; "
                        f"⭐ Glassdoor: **{ngd}** &nbsp;|&nbsp; "
                        f"💼 Jobs: **{nj}**"
                    )
                    slot = st.empty()
                elif cur_node in NODE_INFO:
                    slot.markdown(f"✅ {NODE_INFO[cur_node][1]}")
                    slot = st.empty()

            else:
                # ── Node starting — show spinner label ────────────
                cur_node = ev
                lbl = NODE_INFO.get(ev, (ev,))[0]
                status.update(label=lbl)
                if ev == "research_parallel":
                    slot.markdown(
                        "⏳ Searching 3 sources simultaneously…\n\n"
                        "> 🔍 **Web** — interview experiences &nbsp;&nbsp;"
                        "⭐ **Glassdoor** — ratings & reviews &nbsp;&nbsp;"
                        "💼 **Job portals** — requirements & skills"
                    )
                else:
                    slot.markdown(f"⏳ {lbl}")

    if not final:
        st.error("Research failed. Check your API keys in Settings.")
        return

    final.update({"company": company, "role": role, "focus": focus})
    st.session_state.research_results = final
    if "companies" not in st.session_state:
        st.session_state.companies = {}
    st.session_state.companies[company] = final
    log_research(company, role, focus, len(final.get("questions", [])), time.time() - t0)

    # ── Results ───────────────────────────────────────────────────
    st.markdown("---")
    _company_card(company, role, final.get("metadata", {}))
    st.markdown(
        f'<div style="margin:8px 0 16px">'
        f'<span class="context-chip">📌 Context: '
        f'<strong style="margin-left:4px">{company} · {focus}</strong></span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Interview Summary")
    st.markdown(final.get("synthesis", ""))

    # ── Source pill row ───────────────────────────────────────────
    src = final.get("research_sources", {})
    if src:
        ng  = len(src.get("general",   []))
        ngd = len(src.get("glassdoor", []))
        nj  = len(src.get("jobs",      []))
        st.markdown(
            f'<div class="chip-row">'
            f'<span class="chip">🔍 Web: {ng} result{"s" if ng != 1 else ""}</span>'
            f'<span class="chip">⭐ Glassdoor: {ngd} review{"s" if ngd != 1 else ""}</span>'
            f'<span class="chip">💼 Job portals: {nj} listing{"s" if nj != 1 else ""}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    _questions(final.get("questions", []), focus)


# ════════════════════════════════════════════════════════════════════
#  PAGE 2 — CHAT
# ════════════════════════════════════════════════════════════════════
def page_chat():
    cfg  = get_cfg()
    name = cfg.get("name", "") or "there"

    companies = st.session_state.get("companies", {})
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    chat_history = st.session_state.chat_history

    # ── Context bar — always visible ──────────────────────────────
    selected = None
    company  = "general prep"
    focus    = cfg.get("default_focus", "DSA")
    role     = "Software Engineer"
    r        = {}

    ctx_col, clr_col = st.columns([5, 1])
    with ctx_col:
        if companies:
            selected = st.selectbox(
                "", list(companies.keys()),
                label_visibility="collapsed", key="chat_ctx",
            )
            r       = companies[selected]
            company = selected
            focus   = r.get("focus", "DSA")
            role    = r.get("role",  "Software Engineer")
        else:
            typed = st.text_input(
                "", placeholder="Type a company name to give context (optional)…",
                label_visibility="collapsed", key="chat_co_input",
            )
            if typed.strip():
                company = typed.strip()
    with clr_col:
        if st.button("New chat", type="secondary", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()

    # ══════════════════════════════════════════════════════════════
    #  HERO STATE — no messages yet
    # ══════════════════════════════════════════════════════════════
    if not chat_history:
        # Large greeting
        st.markdown(
            f'<div class="chat-hero">'
            f'  <div class="chat-greeting">'
            f'    <span class="hello-hi">Hello, </span>'
            f'    <span class="hello-name">{name}</span>'
            f'  </div>'
            f'  <div class="chat-sub">How can I help you prep today?</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # 4 suggestion cards — HTML visual layer
        CARDS = [
            ("🔍",
             f"Walk me through the {company} research",
             "Key interview patterns, culture notes, and what rounds to expect.",
             f"Walk me through the {company} research — what are the interview patterns and key focus areas?"),
            ("💡",
             f"Give me a hard {focus} question",
             f"A challenging practice problem for your {company} {role} interview.",
             f"Give me a challenging {focus} interview question for {company} {role} — include hints"),
            ("📋",
             "Structure 'Tell me about yourself'",
             "Build a compelling 90-second intro for tech interviews.",
             "Help me write a compelling 'tell me about yourself' answer for a tech interview"),
            ("📊",
             "Which company should I target first?",
             "Data-driven recommendation based on your researched companies.",
             "Based on my research sessions, which company should I prioritise and why?"),
        ]

        # Visual cards row (HTML only — clickable overlay via buttons below)
        st.markdown(
            '<div class="sug-grid">' +
            "".join(
                f'<div class="sug-card">'
                f'  <div class="sug-icon">{ic}</div>'
                f'  <div class="sug-title">{ttl}</div>'
                f'  <div class="sug-desc">{dsc}</div>'
                f'</div>'
                for ic, ttl, dsc, _ in CARDS
            ) +
            "</div>",
            unsafe_allow_html=True,
        )

        # Invisible trigger buttons aligned to cards
        st.markdown('<div class="sug-btn-row">', unsafe_allow_html=True)
        triggered = None
        btn_cols = st.columns(4)
        for i, ((_, ttl, _, prompt), col) in enumerate(zip(CARDS, btn_cols)):
            with col:
                if st.button(ttl, key=f"sug_{i}", use_container_width=True):
                    triggered = prompt
        st.markdown("</div>", unsafe_allow_html=True)

        if triggered:
            st.session_state.chat_history.append({"role": "user", "content": triggered})
            with st.spinner("Thinking…"):
                ans = rag_answer(triggered, selected or company)
            st.session_state.chat_history.append({"role": "assistant", "content": ans})
            st.rerun()

    # ══════════════════════════════════════════════════════════════
    #  CHAT STATE — conversation in progress
    # ══════════════════════════════════════════════════════════════
    else:
        if selected:
            st.markdown(
                f'<div style="margin-bottom:14px">'
                f'<span class="context-chip">📌 {selected} '
                f'· {r.get("role","?")} · {r.get("focus","?")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        for msg in chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ══════════════════════════════════════════════════════════════
    #  Input bar — always visible
    # ══════════════════════════════════════════════════════════════
    if prompt := st.chat_input(f"Ask anything about {company} prep…"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                ans = rag_answer(prompt, selected or company)
            st.markdown(ans)
            if selected:
                st.caption(f"Based on {selected} research · {focus}")
            elif company != "general prep":
                st.caption(f"Answering about {company} · no research context loaded")
        st.session_state.chat_history.append({"role": "assistant", "content": ans})


# ════════════════════════════════════════════════════════════════════
#  PAGE 3 — MY COMPANIES
# ════════════════════════════════════════════════════════════════════
def page_companies():
    _breadcrumb("My Companies")
    st.title("My Companies")
    st.caption("All companies researched this session.")

    companies = st.session_state.get("companies", {})
    if not companies:
        st.info("No companies yet. Go to Research to get started.")
        return

    import pandas as pd
    rows = [{"Company": co, "Role": d.get("role","?"), "Focus": d.get("focus","?"),
             "Founded": d.get("metadata",{}).get("founded","?"),
             "HQ": d.get("metadata",{}).get("hq","?"),
             "Questions": len(d.get("questions",[]))}
            for co, d in companies.items()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    sel = st.selectbox("View details", list(companies.keys()))
    d   = companies[sel]
    _company_card(sel, d.get("role","?"), d.get("metadata",{}))
    st.markdown("**Interview Summary**")
    st.markdown(d.get("synthesis", "No summary."))
    _questions(d.get("questions",[]), d.get("focus","DSA"))

    st.markdown("---")
    if st.button("Which company should I target first?", type="secondary"):
        with st.spinner("Analysing…"):
            summaries = "\n\n".join(
                f"{c}: {v.get('synthesis','')[:200]}" for c, v in companies.items()
            )
            try:
                st.success(_gemini(
                    f"Recommend which company a fresher SWE should target first and why "
                    f"(3 sentences):\n\n{summaries}"
                ))
            except Exception as e:
                st.error(f"Error: {e}")


# ════════════════════════════════════════════════════════════════════
#  PAGE 4 — PROGRESS
# ════════════════════════════════════════════════════════════════════
def page_progress():
    _breadcrumb("Progress")
    st.title("Progress")
    st.caption("Your interview prep activity this session.")

    log   = st.session_state.get("progress_log", [])
    comps = st.session_state.get("companies", {})

    total_co = len(comps)
    total_q  = sum(len(d.get("questions",[])) for d in comps.values())
    total_s  = len(log)
    avg_dur  = round(sum(e.get("duration",0) for e in log) / total_s, 0) if log else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Companies",       total_co)
    c2.metric("Questions",       total_q)
    c3.metric("Sessions Run",    total_s)
    c4.metric("Avg Duration",    f"{avg_dur:.0f}s" if log else "—")

    if not log:
        st.markdown("---")
        st.info("Run a research session to start tracking progress.")
        return

    import pandas as pd
    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<span class="sec-lbl">Focus Area Breakdown</span>', unsafe_allow_html=True)
        fc: dict = {}
        for e in log:
            fc[e.get("focus","DSA")] = fc.get(e.get("focus","DSA"), 0) + 1
        st.bar_chart(pd.DataFrame({"Focus": list(fc.keys()), "Sessions": list(fc.values())})
                     .set_index("Focus"), height=200)
    with col_b:
        st.markdown('<span class="sec-lbl">Questions per Session</span>', unsafe_allow_html=True)
        st.bar_chart(pd.DataFrame({
            "Session":   [f"{e['company']}" for e in log],
            "Questions": [e.get("questions", 0) for e in log],
        }).set_index("Session"), height=200)

    # Readiness score
    st.markdown("---")
    st.markdown("### Readiness Score")
    score = int(min(
        (len(fc) / 5 * 0.3 + min(total_co/5,1) * 0.4 + min(total_q/25,1) * 0.3) * 100, 100
    ))
    color = "#16a34a" if score >= 60 else "#ea580c" if score >= 30 else "#dc2626"
    st.markdown(
        f'<div style="font-size:42px;font-weight:700;color:{color};line-height:1">'
        f'{score}<span style="font-size:20px;font-weight:400;color:#999">/100</span></div>',
        unsafe_allow_html=True,
    )
    st.progress(score / 100)
    tips = []
    if len(fc) < 3:  tips.append("Try different focus areas — DSA, System Design, and Behavioral.")
    if total_co < 3: tips.append("Research at least 3 companies for a broader perspective.")
    if total_q < 15: tips.append("Aim for 5+ questions per company to build question familiarity.")
    for t in tips:
        st.markdown(f"- {t}")

    # Recent sessions
    st.markdown("---")
    st.markdown('<span class="sec-lbl">Recent Sessions</span>', unsafe_allow_html=True)
    for e in reversed(log):
        st.markdown(
            f'<div class="prog-row">'
            f'<div class="prog-done">✓</div>'
            f'<div style="flex:1"><strong>{e["company"]}</strong>'
            f'<span style="color:#999;font-size:12px;margin-left:8px">{e["timestamp"]}</span></div>'
            f'<span style="font-size:12px;color:#555">{e["focus"]} · {e["questions"]}Q · {e["duration"]}s</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    if st.button("Export session data", type="secondary"):
        st.download_button(
            "Download JSON",
            data=json.dumps({"log": log, "companies": {
                k: {"role": v.get("role"), "focus": v.get("focus"),
                    "metadata": v.get("metadata"),
                    "question_count": len(v.get("questions",[]))}
                for k, v in comps.items()
            }}, indent=2),
            file_name=f"placement_prep_{date.today()}.json",
            mime="application/json",
        )


# ════════════════════════════════════════════════════════════════════
#  PAGE 5 — SETTINGS
# ════════════════════════════════════════════════════════════════════
def page_settings():
    _breadcrumb("Settings")
    st.title("Settings")
    st.caption("Configure keys, model preferences, and defaults.")

    cfg = get_cfg()

    # API key status
    st.markdown("### API Keys")
    st.caption("Keys are read from your `.env` file. Restart the app after editing it.")

    def _key_status(val, name, link):
        if val:
            masked = val[:6] + "••••••" + val[-4:] if len(val) > 12 else "••••"
            st.markdown(f'<span class="api-ok">✓ {name} connected</span> '
                        f'<span style="color:#999;font-size:11px">({masked})</span>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="api-miss">✗ {name} missing — '
                        f'<a href="{link}" target="_blank">get a free key ↗</a></span>',
                        unsafe_allow_html=True)

    _key_status(os.getenv("GEMINI_API_KEY"),    "Gemini",    "https://aistudio.google.com/app/apikey")
    _key_status(os.getenv("TAVILY_API_KEY"),    "Tavily",    "https://tavily.com")
    _key_status(os.getenv("LANGSMITH_API_KEY"), "LangSmith", "https://smith.langchain.com")

    st.markdown("---")
    st.markdown("### Preferences")

    with st.form("settings_form"):
        c1, c2 = st.columns(2)
        with c1:
            name   = st.text_input("Your name (optional)", value=cfg.get("name",""),
                                   placeholder="e.g. Bella")
            d_foc  = st.selectbox("Default focus area", FOCUS_OPTS,
                                  index=FOCUS_OPTS.index(cfg.get("default_focus","DSA")))
            num_q  = st.number_input("Questions per session", 3, 15,
                                     value=cfg.get("num_questions", 5), step=1)
        with c2:
            model  = st.selectbox(
                "Gemini model",
                ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
                index=["gemini-2.5-flash","gemini-1.5-flash","gemini-1.5-pro"]
                      .index(cfg.get("gemini_model","gemini-2.5-flash")),
                help="Flash = faster & cheaper. Pro = higher quality.",
            )
            depth  = st.selectbox("Tavily search depth", ["basic","advanced"],
                                  index=["basic","advanced"].index(cfg.get("search_depth","basic")))
            chips  = st.toggle("Show suggestion chips", value=cfg.get("show_chips", True))

        saved = st.form_submit_button("Save Settings", use_container_width=True)

    if saved:
        new = {"name": name, "default_focus": d_foc, "num_questions": int(num_q),
               "gemini_model": model, "search_depth": depth, "show_chips": chips}
        st.session_state.settings = new
        if save_settings(new):
            st.success("Settings saved — will persist across sessions.")
        else:
            st.warning("Saved for this session only (could not write to disk).")

    st.markdown("---")
    st.markdown("### Session Data")
    ca, cb = st.columns(2)
    with ca:
        if st.button("Clear all data", type="secondary"):
            for k in ("research_results","companies","chat_history","progress_log","_pf"):
                st.session_state.pop(k, None)
            st.success("Session cleared.")
            st.rerun()
    with cb:
        if st.button("Reset to defaults", type="secondary"):
            st.session_state.settings = dict(DEFAULTS)
            save_settings(dict(DEFAULTS))
            st.success("Settings reset.")
            st.rerun()


# ════════════════════════════════════════════════════════════════════
#  NAVIGATION
# ════════════════════════════════════════════════════════════════════
NAV_SECTIONS = {
    "PREPARE": [("🔍  Research",     page_research),
                ("💬  Chat",         page_chat)],
    "MANAGE":  [("🏢  My Companies", page_companies)],
    "MORE":    [("📊  Progress",     page_progress),
                ("⚙️  Settings",     page_settings)],
}


def main():
    st.set_page_config(
        page_title="Placement Prep",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Default page ──────────────────────────────────────────────
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = "🔍  Research"

    # ── Sidebar logo ──────────────────────────────────────────────
    st.sidebar.markdown(
        '<div style="display:flex;align-items:center;gap:10px;padding:22px 16px 16px">'
        '<div style="width:34px;height:34px;border-radius:9px;background:#0d0d0d;'
        'display:flex;align-items:center;justify-content:center;flex-shrink:0">'
        '<svg width="18" height="18" viewBox="0 0 20 20" fill="none">'
        '<circle cx="10" cy="10" r="8" stroke="#60a5fa" stroke-width="1.6"/>'
        '<path d="M10 4.5L14.5 10L10 15.5L5.5 10Z" fill="#f87171" opacity="0.95"/>'
        '<circle cx="10" cy="10" r="2.2" fill="white"/>'
        '</svg></div>'
        '<span style="font-size:15px;font-weight:700;color:#111;letter-spacing:-.02em">'
        'Placement Prep</span></div>',
        unsafe_allow_html=True,
    )

    # ── Navigation — buttons interleaved with section labels ──────
    all_page_fns = {}
    for section, items in NAV_SECTIONS.items():
        st.sidebar.markdown(
            f'<span class="nav-lbl">{section}</span>', unsafe_allow_html=True
        )
        for label, fn in items:
            all_page_fns[label] = fn
            is_active = st.session_state.nav_page == label
            if st.sidebar.button(
                label, key=f"nav_{label}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.nav_page = label
                st.rerun()

    st.sidebar.divider()

    # ── Context chip (after research) ─────────────────────────────
    if "research_results" in st.session_state:
        r = st.session_state.research_results
        st.sidebar.markdown(
            f'<div style="padding:2px 2px 5px">'
            f'<span class="context-chip">📌 {r.get("company","?")} · {r.get("focus","?")}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    log = st.session_state.get("progress_log", [])
    if log:
        total_q = sum(e.get("questions", 0) for e in log)
        st.sidebar.markdown(
            f'<div style="font-size:11px;color:#aaa;padding:2px 2px 4px">'
            f'{len(log)} session{"s" if len(log)>1 else ""} · {total_q} questions</div>',
            unsafe_allow_html=True,
        )

    # ── AI status + week tag (bottom) ─────────────────────────────
    gem_ok = bool(os.getenv("GEMINI_API_KEY"))
    tav_ok = bool(os.getenv("TAVILY_API_KEY"))
    if gem_ok and tav_ok:
        st.sidebar.markdown(
            '<div style="margin-top:12px">'
            '<span style="font-size:12px;color:#16a34a;font-weight:600">'
            '<span class="ai-dot"></span>AI Ready</span>'
            '<div style="font-size:11px;color:#aaa;margin-top:3px">Week 5 · Day 36–37</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        missing = [n for n, ok in [("Gemini", gem_ok), ("Tavily", tav_ok)] if not ok]
        st.sidebar.markdown(
            f'<div style="margin-top:12px;font-size:12px;color:#ea580c;font-weight:500">'
            f'⚠ {", ".join(missing)} key missing</div>'
            f'<div style="font-size:11px;color:#aaa;margin-top:2px">Check ⚙️ Settings</div>',
            unsafe_allow_html=True,
        )

    # ── Render active page ────────────────────────────────────────
    all_page_fns[st.session_state.nav_page]()


if __name__ == "__main__":
    main()
