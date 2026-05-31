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
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

:root {
  --bg:#15190f; --surface-low:#1d2216; --surface:#222719; --surface-lowest:#10130b;
  --surface-high:#2d3422; --surface-highest:#3a432c;
  --border:#3c4a2b; --border-hov:#7e8f57;
  --text-hi:#f3f6ec; --text-mid:#cfd8bd; --text-lo:#9aa67a; --text-lbl:#9aa67a;
  --gold:#c5f82a; --gold-soft:#d6ff5c; --on-gold:#101806;
  --shadow:0 4px 20px rgba(0,0,0,.4); --glow:0 0 26px rgba(197,248,42,.14);
  --green:#86efac; --green-bg:#14271a; --green-bd:#2f5236;
  --orange:#fdba74; --orange-bg:#2a1c10; --orange-bd:#5a3d1f;
  --red:#fca5a5; --red-bg:#2a1414; --red-bd:#5a2f2f;
  --blue:#93c5fd; --blue-bg:#14203a; --blue-bd:#2f4373;
}
*:not([class*="material"]):not([class*="icon"]):not([data-testid*="Icon"]) { font-family:'Manrope',sans-serif !important; }
/* Restore Material Symbols / icon ligature fonts (collapse arrow etc.) */
[class*="material-symbols"], [class*="material-icons"], span[data-testid*="Icon"] i,
[data-testid="stIconMaterial"], .material-symbols-outlined, .material-symbols-rounded {
  font-family:'Material Symbols Outlined','Material Symbols Rounded','Material Icons' !important;
}
/* Button labels inherit the button colour (global p rule was hiding them) */
.stButton > button p, .stButton > button div, .stButton > button span,
[data-testid="stFormSubmitButton"] button p, [data-testid="stFormSubmitButton"] button div {
  color:inherit !important; -webkit-text-fill-color:inherit !important;
}

.stApp {
  background:
    radial-gradient(circle at 50% 0%, rgba(197,248,42,.04) 0%, transparent 45%),
    radial-gradient(circle at 90% 90%, rgba(197,248,42,.03) 0%, transparent 35%),
    #0d100a;
}
.stApp > header, [data-testid="stHeader"] { background:transparent !important; height:0 !important; border:none !important; }
[data-testid="stToolbar"] { right:8px !important; }
[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background:#131313 !important; }
[data-testid="stBottomBlockContainer"] { padding-top:8px !important; padding-bottom:14px !important; }
.block-container { padding-top:42px !important; max-width:960px; }

[data-testid="stSidebar"] { background:#1c1b1b !important; border-right:1px solid var(--border) !important; }
[data-testid="stSidebar"] > div:first-child { padding-top:0 !important; }
[data-testid="stSidebar"] hr { border-color:var(--border) !important; margin:10px 0 !important; }

/* Sidebar collapse/expand toggle — always visible (not just on hover) */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] button {
  opacity:1 !important; visibility:visible !important;
}
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapsedControl"] button {
  color:var(--gold) !important; background:var(--surface-high) !important;
  border:1px solid var(--border) !important; border-radius:8px !important;
}
/* Flat nav rows — reset ALL card/border leakage from global button rules */
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
  background:transparent !important; border:none !important; border-radius:8px !important;
  min-height:0 !important; height:38px !important;
  text-align:left !important; justify-content:flex-start !important; white-space:normal !important;
  padding:8px 12px !important; margin:1px 0 !important;
  font-size:13.5px !important; font-weight:500 !important; color:var(--text-mid) !important;
  line-height:1.2 !important; box-shadow:none !important; transform:none !important;
  transition:background .15s,color .15s !important; width:100% !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background:var(--surface-high) !important; color:var(--text-hi) !important;
  border:none !important; transform:none !important; box-shadow:none !important;
}
/* Active row — subtle filled, no box */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background:rgba(197,248,42,.10) !important; color:var(--gold) !important; font-weight:600 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
  background:rgba(197,248,42,.16) !important; color:var(--gold-soft) !important;
}
[data-testid="stSidebar"] .stCaption p { color:var(--text-lo) !important; font-size:11px !important; }

.stButton > button {
  background:var(--gold) !important; color:var(--on-gold) !important; border:none !important; border-radius:10px !important;
  font-size:13px !important; font-weight:700 !important; padding:9px 22px !important; box-shadow:none !important; transition:all .18s !important;
}
.stButton > button:hover { background:var(--gold-soft) !important; transform:translateY(-1px) !important; box-shadow:0 6px 20px rgba(197,248,42,.25) !important; }
.stButton > button[kind="secondary"] { background:transparent !important; color:var(--text-mid) !important; border:1px solid var(--border) !important; }
.stButton > button[kind="secondary"]:hover { border-color:var(--gold) !important; color:var(--gold-soft) !important; background:rgba(197,248,42,.05) !important; transform:none !important; box-shadow:none !important; }

.stButton > button[kind="primary"] {
  background:linear-gradient(160deg,var(--surface) 0%,var(--surface-lowest) 100%) !important; color:var(--text-mid) !important;
  border:1px solid var(--border) !important; border-radius:16px !important;
  min-height:150px !important; height:auto !important; padding:18px 16px !important;
  text-align:left !important; justify-content:flex-start !important; white-space:pre-line !important;
  font-size:13px !important; font-weight:500 !important; line-height:1.55 !important; box-shadow:none !important; transform:none !important;
}
.stButton > button[kind="primary"]:hover {
  border-color:rgba(197,248,42,.4) !important; color:var(--text-hi) !important;
  box-shadow:var(--glow) !important; transform:translateY(-3px) !important;
  background:linear-gradient(160deg,var(--surface-high) 0%,var(--surface-lowest) 100%) !important;
}

[data-testid="stFormSubmitButton"] button {
  background:var(--gold) !important; color:var(--on-gold) !important; border:none !important; border-radius:999px !important;
  font-size:13px !important; font-weight:700 !important; padding:11px 28px !important; width:100% !important;
  box-shadow:0 2px 12px rgba(197,248,42,.25) !important; transition:all .18s !important;
}
[data-testid="stFormSubmitButton"] button:hover { background:var(--gold-soft) !important; box-shadow:0 6px 22px rgba(197,248,42,.4) !important; transform:translateY(-1px) !important; }

.stTextInput input, .stTextArea textarea, div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {
  border:1px solid var(--border) !important; border-radius:10px !important; color:var(--text-hi) !important; font-size:13px !important;
  background:var(--surface-low) !important; -webkit-text-fill-color:var(--text-hi) !important; transition:border-color .2s,box-shadow .2s !important;
}
div[data-baseweb="input"], div[data-baseweb="textarea"] { background:var(--surface-low) !important; border-radius:10px !important; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color:var(--gold) !important; box-shadow:0 0 0 2px rgba(197,248,42,.15) !important; }
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color:var(--text-lo) !important; opacity:1 !important; }
.stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label { font-size:10px !important; font-weight:700 !important; color:var(--text-lo) !important; text-transform:uppercase !important; letter-spacing:.08em !important; }

.stSelectbox > div > div, div[data-baseweb="select"] > div { border:1px solid var(--border) !important; border-radius:10px !important; background:var(--surface-low) !important; font-size:13px !important; color:var(--text-hi) !important; }
div[data-baseweb="popover"] li { background:var(--surface) !important; color:var(--text-hi) !important; }

[data-testid="stPills"] button { border:1px solid var(--border) !important; border-radius:20px !important; background:var(--surface-low) !important; color:var(--text-mid) !important; font-size:12px !important; padding:5px 14px !important; transition:all .15s !important; box-shadow:none !important; transform:none !important; }
[data-testid="stPills"] button:hover { border-color:var(--gold) !important; color:var(--gold-soft) !important; }
[data-testid="stPills"] button[aria-pressed="true"], [data-testid="stPills"] button[data-selected="true"] { background:var(--gold) !important; color:var(--on-gold) !important; border-color:var(--gold) !important; }
[data-testid="stPills"] label { font-size:10px !important; font-weight:700 !important; color:var(--text-lbl) !important; text-transform:uppercase !important; letter-spacing:.08em !important; }

[data-testid="stForm"] { background:linear-gradient(160deg,var(--surface) 0%,var(--surface-lowest) 100%) !important; border:1px solid var(--border) !important; border-radius:16px !important; padding:24px !important; box-shadow:var(--shadow) !important; }

[data-testid="stMetric"], [data-testid="metric-container"] { background:var(--surface) !important; border:1px solid var(--border) !important; border-radius:12px !important; padding:14px 16px !important; }
[data-testid="stMetricValue"] { color:var(--text-hi) !important; font-size:22px !important; font-weight:700 !important; }
[data-testid="stMetricLabel"] { color:var(--text-lo) !important; font-size:11px !important; text-transform:uppercase; letter-spacing:.05em; }

.stExpander { border:1px solid var(--border) !important; border-radius:12px !important; background:var(--surface-low) !important; margin-bottom:6px !important; }
.stExpander:hover { border-color:rgba(197,248,42,.3) !important; }
.stExpander details summary { font-size:13px !important; color:var(--text-hi) !important; padding:11px 15px !important; }
.stExpander p, .stExpander li { color:var(--text-mid) !important; }

[data-testid="stStatusWidget"] { border:1px solid var(--border) !important; border-radius:12px !important; background:var(--surface-low) !important; }
[data-testid="stDataFrame"] { border:1px solid var(--border) !important; border-radius:12px !important; overflow:hidden !important; }

.chat-hero { text-align:center; padding:54px 20px 40px; }
.chat-greeting {
  font-size:46px; font-weight:800; letter-spacing:-.03em; line-height:1.1; margin-bottom:12px;
  background:linear-gradient(90deg,#eef2e6 0%,#d6ff5c 50%,#eef2e6 100%); background-size:200% auto;
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
}
.hello-hi { color:transparent; } .hello-name { color:transparent; }
.chat-sub { font-size:18px; color:var(--text-lo); font-weight:400; letter-spacing:-.01em; }

[data-testid="stChatMessage"] { background:var(--surface-low) !important; border:1px solid var(--border) !important; border-radius:14px !important; margin-bottom:8px !important; }
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li { color:var(--text-hi) !important; }

[data-testid="stChatInput"] { background:var(--surface) !important; border:1px solid var(--border) !important; border-radius:18px !important; }
[data-testid="stChatInput"] textarea { background:transparent !important; color:var(--text-hi) !important; font-size:14px !important; padding:12px 20px !important; border:none !important; }
[data-testid="stChatInput"] textarea::placeholder { color:var(--text-lo) !important; }
[data-testid="stChatInput"] button { border-radius:50% !important; background:var(--gold) !important; color:var(--on-gold) !important; border:none !important; }

h1 { font-size:24px !important; font-weight:700 !important; color:var(--text-hi) !important; letter-spacing:-.02em !important; margin-bottom:2px !important; }
h2 { font-size:18px !important; font-weight:600 !important; color:var(--text-hi) !important; margin:0 0 12px !important; }
h3 { font-size:15px !important; font-weight:600 !important; color:var(--text-hi) !important; }
p  { color:var(--text-mid); font-size:14px; }
hr { border:none !important; border-top:1px solid var(--border) !important; margin:20px 0 !important; }
.stCaption p { color:var(--text-lo) !important; font-size:12px !important; }
[data-testid="stAlert"] { border-radius:10px !important; font-size:13px !important; }
.stMarkdown a { color:var(--gold-soft) !important; }

.breadcrumb { font-size:13px; color:var(--text-lo); padding-bottom:16px; margin-bottom:16px; border-bottom:1px solid var(--border); }
.breadcrumb strong { color:var(--text-hi); font-weight:600; }
.nav-lbl { font-size:10.5px; font-weight:700; color:var(--text-lo); text-transform:uppercase; letter-spacing:.08em; padding:18px 0 4px; display:block; }

/* Bottom user chip */
[data-testid="stSidebar"] > div:first-child { display:flex !important; flex-direction:column !important; }
.user-chip {
  margin-top:auto; display:flex; align-items:center; gap:11px;
  padding:12px 14px; border-top:1px solid var(--border);
}
.user-avatar {
  width:34px; height:34px; border-radius:9px; flex-shrink:0;
  background:var(--gold); color:var(--on-gold);
  display:flex; align-items:center; justify-content:center;
  font-size:14px; font-weight:700;
}
.user-meta { line-height:1.3; overflow:hidden; }
.user-name { font-size:13px; font-weight:600; color:var(--text-hi); white-space:nowrap; text-overflow:ellipsis; overflow:hidden; }
.user-status { font-size:11px; color:var(--text-lo); display:flex; align-items:center; gap:5px; }
.user-dot { width:6px; height:6px; border-radius:50%; display:inline-block; }
.chip-row { display:flex; gap:7px; flex-wrap:wrap; margin:10px 0 6px; }
.chip { padding:5px 13px; border:1px solid var(--border); border-radius:20px; font-size:12px; color:var(--text-mid); background:var(--surface-low); line-height:1.4; }
div[data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"] { border-radius:20px !important; font-size:12px !important; font-weight:500 !important; padding:6px 13px !important; height:auto !important; line-height:1.4 !important; color:var(--text-mid) !important; border-color:var(--border) !important; }
.context-chip { display:inline-flex; align-items:center; gap:6px; background:rgba(197,248,42,.12); border:1px solid rgba(197,248,42,.3); border-radius:20px; font-size:12px; color:var(--gold-soft); padding:4px 12px; font-weight:600; }
.badge-easy { font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px; background:var(--green-bg); color:var(--green); border:1px solid var(--green-bd); }
.badge-medium { font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px; background:var(--orange-bg); color:var(--orange); border:1px solid var(--orange-bd); }
.badge-hard { font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px; background:var(--red-bg); color:var(--red); border:1px solid var(--red-bd); }
.co-card { border:1px solid var(--border); border-radius:14px; padding:18px 20px; margin-bottom:16px; background:var(--surface); box-shadow:var(--shadow); }
.co-icon { display:inline-flex; width:34px; height:34px; border-radius:8px; background:var(--gold); color:var(--on-gold); align-items:center; justify-content:center; font-size:15px; font-weight:700; margin-right:10px; vertical-align:middle; }
.sec-lbl { font-size:11px; font-weight:700; color:var(--text-lbl); text-transform:uppercase; letter-spacing:.07em; margin-bottom:10px; display:block; }
.prog-row { display:flex; align-items:center; gap:12px; padding:10px 14px; border:1px solid var(--border); border-radius:10px; margin-bottom:7px; font-size:13px; background:var(--surface-low); color:var(--text-mid); }
.prog-done { width:22px; height:22px; border-radius:50%; background:var(--green-bg); border:1px solid var(--green-bd); color:var(--green); display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700; flex-shrink:0; }
.api-ok { color:var(--green); font-size:12px; font-weight:500; }
.api-miss { color:var(--orange); font-size:12px; font-weight:500; }
.ai-dot { width:6px; height:6px; border-radius:50%; background:var(--green); display:inline-block; margin-right:5px; }

@media (max-width:640px) {
  .block-container { padding:14px 12px 90px !important; max-width:100% !important; }
  [data-testid="stHorizontalBlock"] { flex-direction:column !important; gap:8px !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { width:100% !important; flex:1 1 100% !important; min-width:100% !important; }
  .chat-hero { padding:28px 8px 22px !important; }
  .chat-greeting { font-size:30px !important; margin-bottom:8px !important; }
  .chat-sub { font-size:15px !important; }
  .stButton > button[kind="primary"] { min-height:auto !important; padding:14px !important; }
  h1 { font-size:20px !important; } h2 { font-size:16px !important; }
  [data-testid="stForm"] { padding:16px !important; }
  [data-testid="stChatInput"] textarea { font-size:16px !important; }
  .breadcrumb { padding-bottom:10px; margin-bottom:10px; }
  [data-testid="stDataFrame"] { overflow-x:auto !important; }
}
@media (min-width:641px) and (max-width:920px) { .chat-greeting { font-size:38px !important; } }
</style>
"""


# ════════════════════════════════════════════════════════════════════
#  AGENT FUNCTIONS
# ════════════════════════════════════════════════════════════════════
def _gemini(prompt: str) -> str:
    import google.generativeai as genai
    cfg   = get_cfg()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(cfg.get("gemini_model", "gemini-2.5-flash"))

    # Retry once on transient errors; raise a readable message on quota errors
    for attempt in range(2):
        try:
            return model.generate_content(prompt).text.strip()
        except Exception as exc:
            msg = str(exc)
            if "429" in msg:
                raise RuntimeError(
                    "⚠️ Gemini API rate limit reached.\n\n"
                    "**gemini-2.5-flash** free tier allows only 20 requests / day.\n"
                    "Fix options:\n"
                    "- Switch to **gemini-1.5-flash** in ⚙️ Settings (higher free quota).\n"
                    "- Wait ~24 hours for the quota to reset.\n"
                    "- Add a paid API key."
                ) from exc
            if attempt == 0:
                time.sleep(3)   # wait 3 s before one retry for transient errors
            else:
                raise

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
    """Answer a chat question, using 3-source research context if available."""
    context_parts = []

    # Use research from the chat thread (most recent research message)
    companies = st.session_state.get("companies", {})
    if company in companies:
        d   = companies[company]
        src = d.get("research_sources", {})
        if src.get("general"):
            context_parts.append("WEB:\n" + "\n".join(src["general"][:3]))
        if src.get("glassdoor"):
            context_parts.append("GLASSDOOR:\n" + "\n".join(src["glassdoor"][:2]))
        if src.get("jobs"):
            context_parts.append("JOBS:\n" + "\n".join(src["jobs"][:2]))
        if d.get("synthesis"):
            context_parts.append("SUMMARY:\n" + d["synthesis"])

    context = "\n\n".join(context_parts)
    try:
        return _gemini(
            f"You are a placement prep coach. Answer clearly and concisely.\n\n"
            f"Research context for {company}:\n{context[:2500]}\n\n"
            f"Student: {question}"
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

_FILLERS = {
    "research", "tell", "me", "about", "how", "what", "is", "the", "a", "an",
    "interview", "company", "prepare", "for", "i", "want", "to", "know", "show",
    "get", "find", "with", "focus", "on", "and", "or", "of", "in", "at", "do",
    "can", "will", "should", "give", "search", "look", "up",
}
_ROLE_MAP = {
    "sde": "SDE", "engineer": "SDE", "developer": "SDE",
    "backend": "Backend Engineer", "frontend": "Frontend Engineer",
    "fullstack": "Full Stack SDE", "full": "Full Stack SDE",
    "pm": "PM", "manager": "PM", "product": "PM",
    "analyst": "Data Analyst", "data": "Data Analyst",
    "intern": "Intern", "fresher": "Fresher", "qa": "QA Engineer",
    "devops": "DevOps Engineer",
}
_FOCUS_MAP = {
    "system": "System Design", "design": "System Design",
    "behavioral": "Behavioral", "hr": "Behavioral", "culture": "Behavioral",
    "sql": "SQL", "database": "SQL", "db": "SQL",
    "lld": "Low-Level Design", "low-level": "Low-Level Design",
}

def _parse_gen_query(text: str):
    """
    Parse a plain-English query into (company, role, focus).
    Works for inputs like:
      "Google"  |  "Flipkart SDE"  |  "Research Infosys fresher"
      "Wipro backend engineer system design"  |  "TCS interview"
    Returns ("", "SDE", "DSA") if no company can be detected.
    """
    words = text.strip().split()
    significant = [
        w.strip("?.,!") for w in words
        if w.lower().strip("?.,!") not in _FILLERS and len(w.strip("?.,!")) > 1
    ]
    if not significant:
        return "", "SDE", "DSA"

    company = significant[0].title()

    role = "SDE"
    for word in words:
        w = word.lower().strip("?.,!")
        for kw, rv in _ROLE_MAP.items():
            if kw in w:
                role = rv
                break

    focus = "DSA"
    for word in words:
        w = word.lower().strip("?.,!")
        for kw, fv in _FOCUS_MAP.items():
            if kw in w:
                focus = fv
                break

    return company, role, focus

def _src_header(icon: str, title: str, subtitle: str, count: int, color: str):
    """Render a coloured section header for one search source."""
    badge = f"{count} result{'s' if count != 1 else ''}"
    st.markdown(
        f'<div style="border-left:4px solid {color};padding:10px 16px;'
        f'background:linear-gradient(90deg,{color}18,transparent);'
        f'border-radius:0 8px 8px 0;margin:24px 0 10px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<span style="font-size:18px">{icon}</span>'
        f'<span style="font-size:14px;font-weight:700;color:#e5e2e1">{title}</span>'
        f'</div>'
        f'<span style="font-size:11px;font-weight:600;color:{color};'
        f'background:{color}22;padding:3px 10px;border-radius:20px">{badge}</span>'
        f'</div>'
        f'<div style="font-size:11.5px;color:#999077;margin-top:3px;padding-left:26px">'
        f'{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def _show_research_results(final: dict):
    """
    Render research results with 3 clearly separated source sections
    plus AI-generated questions. Called after search AND on navigation back.
    """
    company = final.get("company", "")
    role    = final.get("role",    "")
    focus   = final.get("focus",   "DSA")

    st.markdown("---")
    _company_card(company, role, final.get("metadata", {}))
    st.markdown(
        f'<div style="margin:8px 0 20px">'
        f'<span class="context-chip">📌 {company} · {role} · {focus}</span></div>',
        unsafe_allow_html=True,
    )

    src            = final.get("research_sources", {})
    general_data   = src.get("general",   [])
    glassdoor_data = src.get("glassdoor", [])
    jobs_data      = src.get("jobs",      [])

    # ── Section 1: Web search ─────────────────────────────────────
    _src_header("🔍", "Web Search",
                "Interview experiences, DSA tips, forum discussions",
                len(general_data), "#2563eb")
    if general_data:
        for i, s in enumerate(general_data, 1):
            with st.expander(f"Result {i} — {s[:68].rstrip()}…"):
                st.markdown(s)
    else:
        st.info("No web results found for this search.")

    # ── Section 2: Glassdoor ──────────────────────────────────────
    _src_header("⭐", "Glassdoor",
                "Company ratings, interview difficulty, culture & work-life reviews",
                len(glassdoor_data), "#d97706")
    if glassdoor_data:
        for i, s in enumerate(glassdoor_data, 1):
            with st.expander(f"Review {i} — {s[:68].rstrip()}…"):
                st.markdown(s)
    else:
        st.info("No Glassdoor reviews found for this company.")

    # ── Section 3: Job portals ────────────────────────────────────
    _src_header("💼", "Job Portals",
                "Active JDs from Naukri, LinkedIn & Indeed — required skills & CTC",
                len(jobs_data), "#16a34a")
    if jobs_data:
        for i, s in enumerate(jobs_data, 1):
            with st.expander(f"Listing {i} — {s[:68].rstrip()}…"):
                st.markdown(s)
    else:
        st.info("No job listings found. Try a more specific role.")

    # ── Section 4: AI interview questions ─────────────────────────
    _src_header("🤖", "AI-Generated Interview Questions",
                f"Based on the 3 sources above — {focus} focus",
                len(final.get("questions", [])), "#7c3aed")
    st.markdown(final.get("synthesis", ""))
    st.markdown("---")
    _questions(final.get("questions", []), focus)


def page_questions():
    """
    Interview Questions page — fast, Gemini-only, no web searches.
    For deep 3-source research use the Chat page Research expander.
    """
    _breadcrumb("Interview Questions")
    st.title("Interview Questions")
    st.caption("Enter company and role — Gemini generates targeted questions instantly.")

    cfg = get_cfg()
    nq  = cfg.get("num_questions", 5)

    # ── Quick-fill chips ──────────────────────────────────────────
    if cfg.get("show_chips", True):
        chip_cols = st.columns(len(SUGGESTIONS))
        for col, (c, r, f) in zip(chip_cols, SUGGESTIONS):
            with col:
                if st.button(f"🔍 {c} · {r} · {f}",
                             key=f"chip_{c}",
                             use_container_width=True,
                             type="secondary"):
                    st.session_state["_pf"] = (c, r, f)
                    st.rerun()

    # ── Form ──────────────────────────────────────────────────────
    pf = st.session_state.get("_pf", ("", "", cfg.get("default_focus", "DSA")))

    with st.form("questions_form"):
        fc1, fc2 = st.columns(2)
        with fc1:
            company = st.text_input("Company", value=pf[0],
                                    placeholder="e.g. Google, Infosys, TCS")
        with fc2:
            role = st.text_input("Role", value=pf[1],
                                 placeholder="e.g. SDE-2, PM, Data Analyst, Fresher")
        try:
            focus = st.pills("Focus Area", FOCUS_OPTS,
                             default=pf[2] if pf[2] in FOCUS_OPTS else "DSA")
        except AttributeError:
            focus = st.radio("Focus Area", FOCUS_OPTS,
                             index=FOCUS_OPTS.index(pf[2]) if pf[2] in FOCUS_OPTS else 0,
                             horizontal=True)
        fb1, fb2 = st.columns([3, 1])
        with fb1:
            st.caption("Powered by Gemini  ·  For deep research go to 💬 Chat")
        with fb2:
            run = st.form_submit_button("Get Questions →", use_container_width=True)

    # ── Generate directly with Gemini — no web searches ───────────
    if run:
        if not company or not role:
            st.warning("Please enter both Company and Role.")
        elif not focus:
            st.warning("Please select a Focus Area.")
        else:
            with st.spinner(f"Generating {nq} {focus} questions for {company} {role}…"):
                try:
                    text = _gemini(
                        f"Generate exactly {nq} {focus} interview questions for a "
                        f"{role} position at {company}.\n"
                        f"Format each as: Q1. <question> [Easy/Medium/Hard]\n"
                        f"Mix difficulty levels. Be specific to {company}'s known interview style."
                    )
                    parts = re.split(r"\n(?=Q\d+\.)", text.strip())
                    questions = [p.strip() for p in parts if p.strip()] or [text.strip()]
                    result = {
                        "company": company, "role": role,
                        "focus": focus, "questions": questions,
                        "metadata": {}, "synthesis": "", "research_sources": {},
                    }
                    st.session_state["_qs_result"] = result
                    # Also save to companies so My Companies page shows it
                    if "companies" not in st.session_state:
                        st.session_state.companies = {}
                    st.session_state.companies[company] = result
                except Exception as e:
                    st.error(f"Could not generate questions: {e}")

    # ── Show questions — persists across navigation ───────────────
    if "_qs_result" in st.session_state:
        res = st.session_state["_qs_result"]
        st.markdown("---")
        _src_header("🤖", f"{res['focus']} Questions",
                    f"{res['company']} · {res['role']}",
                    len(res["questions"]), "#7c3aed")
        _questions(res["questions"], res["focus"])


# ════════════════════════════════════════════════════════════════════
#  PAGE 2 — CHAT
# ════════════════════════════════════════════════════════════════════
def _render_research_chat(msg: dict):
    """Render a research message in the chat thread (3 coloured sections)."""
    co   = msg.get("company", "")
    role = msg.get("role",    "")
    src  = msg.get("sources", {})

    st.markdown(
        f'<div style="margin:4px 0 12px">'
        f'<span class="context-chip">🔍 Research — {co} · {role}</span></div>',
        unsafe_allow_html=True,
    )
    _src_header("🔍", "Web Search",
                "Interview forums, DSA tips, tech blogs",
                len(src.get("general", [])), "#2563eb")
    for i, s in enumerate(src.get("general", []), 1):
        with st.expander(f"Result {i} — {s[:65]}…"):
            st.markdown(s)

    _src_header("⭐", "Glassdoor",
                "Ratings, interview difficulty, culture reviews",
                len(src.get("glassdoor", [])), "#d97706")
    for i, s in enumerate(src.get("glassdoor", []), 1):
        with st.expander(f"Review {i} — {s[:65]}…"):
            st.markdown(s)

    _src_header("💼", "Job Portals",
                "Current JDs, required skills & CTC from Naukri, LinkedIn & Indeed",
                len(src.get("jobs", [])), "#16a34a")
    for i, s in enumerate(src.get("jobs", []), 1):
        with st.expander(f"Listing {i} — {s[:65]}…"):
            st.markdown(s)

    if msg.get("synthesis"):
        st.markdown("---")
        st.markdown("**AI Summary**")
        st.markdown(msg["synthesis"])


def _chat_process(prompt: str):
    """
    Core handler for every chat message.

    Searches all 3 sources with the EXACT question as the query —
    no fragile company-name extraction. Tavily finds what's relevant,
    Gemini synthesises using those real results.

    Sources used: Web (general) + Glassdoor + Job portals.
    All 3 run in parallel via ThreadPoolExecutor.
    """
    def _safe(future):
        try:
            return future.result(timeout=25)
        except Exception:
            return []

    # ── Build focused, source-specific queries from the question ──────
    # Detect a company (capitalised word) and the core topic of the question
    _stop = {"what","which","how","why","when","where","is","are","the","a","an",
             "to","of","in","on","for","do","does","did","can","should","tell","me",
             "about","give","explain","at","with","and","or","i","you","your","it"}
    words   = [w.strip("?.,!") for w in prompt.split()]
    company = next((w for w in words if len(w) > 1 and w[0].isupper()), "")
    topic   = " ".join(w for w in words if w.lower() not in _stop and len(w) > 1)
    anchor  = (f"{company} {topic}".strip() or prompt)

    # Each source gets a query tuned to what that site is good for
    web_q  = f"{prompt} interview preparation tips"
    gd_q   = f"{company or anchor} interview experience difficulty rating review"
    jobs_q = f"{company or anchor} job requirements skills eligibility"

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_web  = ex.submit(_search, web_q, 5)
        f_gd   = ex.submit(_search_domains, gd_q, ["glassdoor.com"], 3)
        f_jobs = ex.submit(_search_domains, jobs_q,
                           ["naukri.com", "linkedin.com", "indeed.com", "ambitionbox.com"], 3)
        sources = {
            "general":   _safe(f_web),
            "glassdoor": _safe(f_gd),
            "jobs":      _safe(f_jobs),
        }

    # Build raw context for Gemini
    ctx_parts = []
    if sources.get("general"):
        ctx_parts.append("WEB SEARCH:\n" + "\n".join(sources["general"][:3]))
    if sources.get("glassdoor"):
        ctx_parts.append("GLASSDOOR:\n" + "\n".join(sources["glassdoor"][:2]))
    if sources.get("jobs"):
        ctx_parts.append("JOB PORTALS:\n" + "\n".join(sources["jobs"][:2]))
    context = "\n\n".join(ctx_parts)

    # ONE structured Gemini call — returns per-source summaries + full answer
    structured_prompt = (
        "You are a sharp, professional placement-prep coach. Be concise and scannable.\n"
        "CRITICAL: Answer the EXACT question asked. Do NOT give a generic company overview.\n"
        "If the search results don't cover the question, say so briefly and answer from "
        "your own knowledge — never pad with unrelated facts.\n\n"
        "Respond EXACTLY in this format:\n\n"
        "WEB: [max 2 sentences — only facts relevant to THE QUESTION]\n"
        "GLASSDOOR: [max 2 sentences — rating, interview difficulty, culture]\n"
        "JOBS: [max 2 sentences — required skills, eligibility, CTC if known]\n"
        "ANSWER:\n"
        "[Answer THE SPECIFIC QUESTION like Claude would:\n"
        " - Open with ONE bold sentence that directly answers it.\n"
        " - Then 3-5 markdown bullets ('- ', **bold** key terms) with concrete specifics.\n"
        " - Stay strictly on-topic to the question — no filler company description.\n"
        " - Under 120 words unless depth is requested. Numbered list for rounds/steps.\n"
        " - No preamble like 'Based on the results'.]\n\n"
        f"Search results:\n{context[:3000]}\n\n"
        f"THE QUESTION (answer this exactly): {prompt}"
    )

    summaries = {"general": "", "glassdoor": "", "jobs": ""}
    try:
        raw = _gemini(structured_prompt)

        def _section(tag: str) -> str:
            m = re.search(
                rf'(?:^|\n){tag}:\s*(.*?)(?=\n(?:WEB|GLASSDOOR|JOBS|ANSWER):|$)',
                raw, re.DOTALL | re.IGNORECASE,
            )
            return m.group(1).strip() if m else ""

        summaries = {
            "general":   _section("WEB"),
            "glassdoor": _section("GLASSDOOR"),
            "jobs":      _section("JOBS"),
        }
        answer = _section("ANSWER") or raw  # fallback to full response if parsing fails

    except RuntimeError as exc:   # friendly rate-limit message from _gemini()
        answer = str(exc)
    except Exception as exc:
        answer = f"Error: {exc}"

    # ── Detect company + role + focus from the question ─────────────
    # Use capitalised words as company name (user types "Apple" → saved as Apple)
    words     = prompt.split()
    cap_words = [w.strip("?.,!") for w in words
                 if len(w) > 1 and w.strip("?.,!")[0].isupper()]
    company   = cap_words[0] if cap_words else ""

    # Detect role from question keywords
    role = "SDE"
    for w in words:
        w_lower = w.lower().strip("?.,!")
        if w_lower in {"pm", "manager"}:              role = "PM";                  break
        if w_lower in {"analyst", "data"}:            role = "Data Analyst";        break
        if "backend" in w_lower:                      role = "Backend Engineer";    break
        if "frontend" in w_lower:                     role = "Frontend Engineer";   break
        if "fullstack" in w_lower or "full" in w_lower: role = "Full Stack SDE";   break
        if "fresher" in w_lower or "intern" in w_lower: role = "Fresher";          break
        if w_lower.startswith("sde"):                 role = w.strip("?.,!").upper(); break

    # Detect focus from question keywords
    focus = "DSA"
    low = prompt.lower()
    if "system design" in low:            focus = "System Design"
    elif "behavioral" in low or "hr" in low: focus = "Behavioral"
    elif "sql" in low or "database" in low:  focus = "SQL"
    elif "lld" in low or "low-level" in low: focus = "Low-Level Design"

    # ── Save to My Companies + Progress ─────────────────────────────
    if company and sources and any(sources.values()):
        if "companies" not in st.session_state:
            st.session_state.companies = {}

        # Merge with any existing entry for the same company
        existing = st.session_state.companies.get(company, {})
        st.session_state.companies[company] = {
            "role":             role,
            "focus":            focus,
            "metadata":         existing.get("metadata", {}),
            "synthesis":        answer[:500],
            "research_sources": sources,
            "questions":        existing.get("questions", []),
        }

        # Log to Progress — same format as page_questions()
        log_research(company, role, focus,
                     len(existing.get("questions", [])), 0)

    return answer, sources, summaries


def _clean_snippet(text: str) -> str:
    """Strip markdown links, bare URLs, and HTML tags from a Tavily snippet."""
    # [link text](url) → link text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # bare URLs
    text = re.sub(r'https?://\S+', '', text)
    # any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def _render_sources_columns(summaries: dict):
    """
    Render the 3 source summaries inside one collapsible 'Sources' block —
    clean line-separated sections, no boxes. The main answer stays the
    focus (Claude-style); sources are supporting evidence below it.
    """
    sections = [
        ("🔍", "Web",       "#93c5fd", summaries.get("general",   "")),
        ("⭐", "Glassdoor", "#d6ff5c", summaries.get("glassdoor", "")),
        ("💼", "Jobs",      "#86efac", summaries.get("jobs",      "")),
    ]
    if not any(t for _, _, _, t in sections):
        return

    rows = ""
    for i, (ic, title, color, text) in enumerate(sections):
        if not text:
            continue
        divider = "border-top:1px solid var(--border);" if i and rows else ""
        rows += (
            f'<div style="padding:12px 0;{divider}">'
            f'<div style="font-size:12px;font-weight:700;color:{color};'
            f'letter-spacing:.02em;margin-bottom:5px">{ic} {title}</div>'
            f'<div style="font-size:13.5px;color:var(--text-mid);line-height:1.6">{text}</div>'
            f'</div>'
        )

    with st.expander("Sources  ·  Web · Glassdoor · Jobs", expanded=True):
        st.markdown(rows, unsafe_allow_html=True)


def page_chat():
    _breadcrumb("Chat")
    st.title("Chat")
    st.caption(
        "Ask anything — when you mention a company, "
        "we automatically search Web + Glassdoor + Job Portals to back the answer."
    )

    cfg  = get_cfg()
    name = cfg.get("name", "") or "there"

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    chat_history = st.session_state.chat_history

    # ── Single "New chat" button — top right ──────────────────────
    if st.button("New chat", type="secondary", key="clear_chat"):
        st.session_state.chat_history = []
        st.rerun()

    # ══════════════════════════════════════════════════════════════
    #  HERO STATE — no messages yet, show greeting + suggestion cards
    # ══════════════════════════════════════════════════════════════
    if not chat_history:
        st.markdown(
            f'<div class="chat-hero">'
            f'  <div class="chat-greeting">'
            f'    <span class="hello-hi">Hello, </span>'
            f'    <span class="hello-name">{name}</span>'
            f'  </div>'
            f'  <div class="chat-sub">Ask anything — I\'ll search the web for you.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        CARDS = [
            ("🔍",
             "Research Google SDE-2",
             "Web + Glassdoor + Jobs searched automatically.",
             "Research Google SDE-2 interview — include web experiences, Glassdoor ratings, and current job requirements."),
            ("💡",
             "Give me a hard DSA question",
             "Challenging problem with hints and approach.",
             "Give me a challenging DSA interview question with hints and a step-by-step approach."),
            ("📋",
             "Structure 'Tell me about yourself'",
             "Build a compelling 90-second intro.",
             "Help me write a compelling 'tell me about yourself' answer for a tech interview."),
            ("📊",
             "Best companies for freshers 2025",
             "Ranked picks based on hiring patterns.",
             "Which companies are best for fresh engineers in India in 2025 and why?"),
        ]

        triggered = None
        card_cols = st.columns(4)
        for i, ((ic, ttl, dsc, card_prompt), col) in enumerate(zip(CARDS, card_cols)):
            with col:
                if st.button(f"{ic}\n{ttl}\n{dsc}",
                             key=f"sug_{i}",
                             use_container_width=True,
                             type="primary"):
                    triggered = card_prompt

        if triggered:
            with st.spinner("🔍 Searching 3 sources…"):
                ans, srcs, sums = _chat_process(triggered)
            chat_history.append({"role": "user",      "content": triggered})
            chat_history.append({"role": "assistant", "content": ans,
                                  "sources": srcs, "summaries": sums})
            st.rerun()

    # ══════════════════════════════════════════════════════════════
    #  CHAT STATE — render conversation
    #  Structure per exchange:
    #    [User bubble]
    #    [3-column: Web | Glassdoor | Jobs]   ← outside bubble, full width
    #    [Assistant bubble with AI answer]
    # ══════════════════════════════════════════════════════════════
    else:
        for msg in chat_history:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                # Answer first (the main reply), sources collapsed below
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])
                    sums = msg.get("summaries", {})
                    if sums and any(sums.values()):
                        _render_sources_columns(sums)

    # ══════════════════════════════════════════════════════════════
    #  Chat input — always visible
    # ══════════════════════════════════════════════════════════════
    if prompt := st.chat_input("Ask anything — mention a company to get real-time research…"):
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("🔍 Searching Web · Glassdoor · Job Portals…"):
            ans, srcs, sums = _chat_process(prompt)

        # Answer first, sources collapsed below
        with st.chat_message("assistant"):
            st.markdown(ans)
            if sums and any(sums.values()):
                _render_sources_columns(sums)

        chat_history.append({"role": "user",      "content": prompt})
        chat_history.append({"role": "assistant", "content": ans,
                              "sources": srcs, "summaries": sums})


# ════════════════════════════════════════════════════════════════════
#  PAGE 3 — MY COMPANIES
# ════════════════════════════════════════════════════════════════════
def page_companies():
    _breadcrumb("My Companies")
    st.title("My Companies")
    st.caption("All companies researched this session.")

    companies = st.session_state.get("companies", {})
    if not companies:
        st.info("No companies yet. Go to ❓ Questions or 💬 Chat and search for a company first.")
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
    "PREPARE": [("Chat",         page_chat),
                ("Questions",    page_questions)],
    "MANAGE":  [("My Companies", page_companies)],
    "MORE":    [("Progress",     page_progress),
                ("Settings",     page_settings)],
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
        st.session_state.nav_page = "Chat"

    # ── Sidebar logo ──────────────────────────────────────────────
    st.sidebar.markdown(
        '<div style="display:flex;align-items:center;gap:10px;padding:22px 16px 16px">'
        '<div style="width:34px;height:34px;border-radius:9px;background:#c5f82a;'
        'display:flex;align-items:center;justify-content:center;flex-shrink:0;'
        'box-shadow:0 0 16px rgba(197,248,42,.35)">'
        '<svg width="18" height="18" viewBox="0 0 20 20" fill="none">'
        '<circle cx="10" cy="10" r="8" stroke="#15200a" stroke-width="1.6"/>'
        '<path d="M10 4.5L14.5 10L10 15.5L5.5 10Z" fill="#15200a" opacity="0.9"/>'
        '<circle cx="10" cy="10" r="2.2" fill="#eaffc0"/>'
        '</svg></div>'
        '<span style="font-size:15px;font-weight:700;color:#eef2e6;letter-spacing:-.02em">'
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

    # ── Bottom user chip (fixed to sidebar bottom) ────────────────
    cfg     = get_cfg()
    name    = (cfg.get("name") or "Guest").strip()
    initial = name[0].upper() if name else "G"
    gem_ok  = bool(os.getenv("GEMINI_API_KEY"))
    tav_ok  = bool(os.getenv("TAVILY_API_KEY"))
    online  = gem_ok and tav_ok
    status_dot = "#86efac" if online else "#fca5a5"
    status_txt = "AI Ready" if online else "Keys missing"

    st.sidebar.markdown(
        f'<div class="user-chip">'
        f'  <div class="user-avatar">{initial}</div>'
        f'  <div class="user-meta">'
        f'    <div class="user-name">{name}</div>'
        f'    <div class="user-status"><span class="user-dot" style="background:{status_dot}"></span>{status_txt}</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Render active page ────────────────────────────────────────
    all_page_fns[st.session_state.nav_page]()


if __name__ == "__main__":
    main()
