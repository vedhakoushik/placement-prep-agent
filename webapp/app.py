import os, json, time, uuid, httpx
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ── Gemini config ─────────────────────────────────────────────────────────────
MODEL   = "gemini-2.5-flash"
API_KEY = os.getenv("GEMINI_API_KEY")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

COST_IN  = 0.00015
COST_OUT = 0.00060

# ── In-memory session store (conversation histories, interview state) ──────────
_store: dict = {}

PLACEMENT_SYSTEM = "You are a placement advisor helping engineering students prepare for tech company interviews in India. Be concise and practical."
INTERVIEW_SYSTEM = """You are a strict but encouraging technical interviewer for top tech companies in India.
- Ask ONE question at a time.
- After each answer give brief feedback (2-3 lines): what was good, what was missing.
- Be professional but supportive."""


# ── Gemini helper ─────────────────────────────────────────────────────────────
def gemini(messages: list, system: str = "", max_tokens: int = 600) -> dict:
    payload = {
        "contents": messages,
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}

    for wait in [5, 5, 5]:
        r = httpx.post(API_URL, json=payload, timeout=30)
        if r.status_code == 429:
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()
        text    = data["candidates"][0]["content"]["parts"][0]["text"]
        tok_in  = data["usageMetadata"]["promptTokenCount"]
        tok_out = data["usageMetadata"]["candidatesTokenCount"]
        cost    = (tok_in / 1000 * COST_IN) + (tok_out / 1000 * COST_OUT)
        return {"text": text, "tok_in": tok_in, "tok_out": tok_out, "cost": round(cost, 6)}

    return {"error": "Rate limited. Wait 60s and try again."}


def u(text): return {"role": "user",  "parts": [{"text": text}]}
def m(text): return {"role": "model", "parts": [{"text": text}]}


# ── Page routes ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat")
def chat():
    sid = session.get("sid")
    if not sid or sid not in _store:
        sid = str(uuid.uuid4())
        session["sid"] = sid
        _store[sid] = {"messages": [], "total_cost": 0.0, "turns": 0}
    return render_template("chat.html", sid=sid)

@app.route("/interview")
def interview():
    return render_template("interview.html")

@app.route("/research")
def research():
    return render_template("research.html")


# ── Chat API ──────────────────────────────────────────────────────────────────
@app.route("/api/chat/send", methods=["POST"])
def chat_send():
    data  = request.json
    sid   = session.get("sid")
    if not sid or sid not in _store:
        return jsonify({"error": "No session"}), 400

    store = _store[sid]
    store["messages"].append(u(data["message"]))

    result = gemini(store["messages"], system=PLACEMENT_SYSTEM)
    if "error" in result:
        store["messages"].pop()
        return jsonify(result), 429

    store["messages"].append(m(result["text"]))
    store["total_cost"] += result["cost"]
    store["turns"] += 1

    return jsonify({
        "reply":      result["text"],
        "tok_in":     result["tok_in"],
        "tok_out":    result["tok_out"],
        "cost":       result["cost"],
        "total_cost": round(store["total_cost"], 6),
        "turns":      store["turns"],
    })

@app.route("/api/chat/clear", methods=["POST"])
def chat_clear():
    sid = session.get("sid")
    if sid in _store:
        _store[sid] = {"messages": [], "total_cost": 0.0, "turns": 0}
    return jsonify({"ok": True})


# ── Interview API ─────────────────────────────────────────────────────────────
@app.route("/api/interview/start", methods=["POST"])
def interview_start():
    data    = request.json
    company = data.get("company", "").strip()
    role    = data.get("role", "").strip()
    sid     = str(uuid.uuid4())
    session["isid"] = sid

    opening = f"Start a mock interview for {role} at {company}. Greet the candidate warmly and ask your first question."
    messages = [u(opening)]
    result   = gemini(messages, system=INTERVIEW_SYSTEM, max_tokens=400)
    if "error" in result:
        return jsonify(result), 429

    messages.append(m(result["text"]))
    _store[sid] = {
        "company": company, "role": role,
        "messages": messages,
        "current_q": result["text"],
        "qa_pairs": [], "q_num": 1,
        "total_questions": 5,
    }
    return jsonify({"reply": result["text"], "q_num": 1, "total": 5})

@app.route("/api/interview/answer", methods=["POST"])
def interview_answer():
    sid   = session.get("isid")
    store = _store.get(sid)
    if not store:
        return jsonify({"error": "No interview session"}), 400

    answer  = request.json.get("answer", "(skipped)").strip() or "(skipped)"
    q_num   = store["q_num"]
    total   = store["total_questions"]
    company = store["company"]
    role    = store["role"]

    if q_num < total:
        prompt = f'Candidate answered: "{answer}". Give brief feedback, then ask question {q_num+1} of {total}.'
    else:
        prompt = f'Candidate answered: "{answer}". Give brief feedback on this final answer, then wrap up professionally.'

    store["messages"].append(u(prompt))
    result = gemini(store["messages"], system=INTERVIEW_SYSTEM, max_tokens=500)
    if "error" in result:
        store["messages"].pop()
        return jsonify(result), 429

    store["messages"].append(m(result["text"]))
    store["qa_pairs"].append({"question": f"Q{q_num}", "answer": answer, "feedback": result["text"]})
    store["current_q"] = result["text"]
    store["q_num"] += 1

    if q_num >= total:
        summary = _make_summary(company, role, store["qa_pairs"])
        return jsonify({"reply": result["text"], "done": True, "summary": summary})

    return jsonify({"reply": result["text"], "done": False, "q_num": store["q_num"]})

@app.route("/api/interview/ideal", methods=["POST"])
def interview_ideal():
    sid   = session.get("isid")
    store = _store.get(sid)
    if not store:
        return jsonify({"error": "No session"}), 400

    prompt = (f'For a {store["role"]} interview at {store["company"]}, '
              f'the question was: "{store["current_q"]}". '
              f'Give a strong model answer in 8-10 lines with key points.')
    result = gemini([u(prompt)], max_tokens=500)
    if "error" in result:
        return jsonify(result), 429
    return jsonify({"ideal": result["text"]})

def _make_summary(company, role, qa_pairs):
    qa_text = "\n\n".join(
        f"Q{i+1}: {qa['question']}\nA: {qa['answer']}\nFeedback: {qa['feedback']}"
        for i, qa in enumerate(qa_pairs)
    )
    prompt = f"""Evaluated mock interview for {role} at {company}:
{qa_text}

Return ONLY valid JSON:
{{"overall_score": <1-10>, "strengths": ["a","b"], "improvements": ["a","b"],
  "topic_scores": {{"DSA": <1-10>, "OOP": <1-10>, "HR": <1-10>}},
  "recommendation": "Ready|Needs more prep|Not ready"}}"""

    result = gemini([u(prompt)], max_tokens=400)
    if "error" in result:
        return {}
    raw = result["text"].strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except:
        return {}


# ── Research API ──────────────────────────────────────────────────────────────
@app.route("/api/research/profile", methods=["POST"])
def research_profile():
    company = request.json.get("company", "").strip()
    prompt  = f"""Return ONLY a JSON object for {company}:
{{"company":"","founded":"","hq":"","tech_stack":[],"known_for":"","typical_roles":[],"interview_difficulty":"easy|medium|hard"}}"""
    result = gemini([u(prompt)],
                    system="You are a JSON API. Return only valid JSON, no markdown.",
                    max_tokens=400)
    if "error" in result:
        return jsonify(result), 429
    raw = result["text"].strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return jsonify({"profile": json.loads(raw)})
    except:
        return jsonify({"error": "Could not parse JSON", "raw": result["text"]}), 500

@app.route("/api/research/compare", methods=["POST"])
def research_compare():
    company = request.json.get("company", "").strip()
    results = {}
    prompts = {
        "zero_shot": f"What is the interview process at {company} for a fresher software engineer? Answer in 5 bullet points.",
        "few_shot":  f"Company: TCS — 3 rounds: online test, technical, HR.\nCompany: Infosys — 3 rounds: InfyTQ test, technical, HR.\nNow same format for:\nCompany: {company} —",
        "cot":       f"Think step by step:\n1. What kind of company is {company}?\n2. What does that tell us about interviews?\n3. What should a fresher focus on?\n4. Final preparation plan.",
    }
    for key, prompt in prompts.items():
        r = gemini([u(prompt)], max_tokens=400)
        results[key] = r.get("text", r.get("error", ""))
        time.sleep(6)
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
