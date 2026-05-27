"""Placement Prep Portal — Motorsport Edition
Design inspired by msport-raptor.com: pure black, racing red, Barlow Condensed.
Run:  python week3/portal.py  →  http://localhost:5001
"""

import os, httpx, chromadb, hashlib, json, csv, io
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template_string, Response
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

API_KEY    = os.getenv("GEMINI_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
EMBED_URL  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
TAVILY_URL = "https://api.tavily.com/search"
QA_DB_PATH = "week3/qa_db"
COL_NAME   = "qa_store"
LOW_CONF   = 0.50

app = Flask(__name__)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=API_KEY,
    temperature=0.1,
    max_output_tokens=600,
)

# ── helpers ────────────────────────────────────────────────────────
def get_col():
    Path(QA_DB_PATH).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=QA_DB_PATH)
    try:    return client.get_collection(COL_NAME)
    except: return client.create_collection(COL_NAME)

def embed(text: str, task="RETRIEVAL_DOCUMENT") -> list[float]:
    r = httpx.post(EMBED_URL, json={
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": text}]},
        "taskType": task,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["embedding"]["values"]

def web_search(query: str) -> str:
    if not TAVILY_KEY: return ""
    try:
        r = httpx.post(TAVILY_URL, json={
            "api_key": TAVILY_KEY, "query": query, "max_results": 3
        }, timeout=20)
        r.raise_for_status()
        return "\n\n".join(i.get("content","") for i in r.json().get("results",[]))
    except: return ""

def load_static_ctx() -> str:
    parts = []
    for pattern in ["week1/*.py", "week2/*.py"]:
        for f in sorted(Path(".").glob(pattern)):
            parts.append(f"[{f.name}]\n{f.read_text(errors='ignore')[:800]}")
    return "\n\n---\n\n".join(parts)


# ── API: Records ───────────────────────────────────────────────────
@app.route("/api/records")
def api_records():
    col  = get_col()
    data = col.get(include=["documents","metadatas"])
    rows = []
    for id_, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        rows.append({
            "id": id_, "content": doc,
            "question":  meta.get("question",""),
            "source":    meta.get("source",""),
            "type":      meta.get("type","qa"),
            "company":   meta.get("company",""),
            "timestamp": meta.get("timestamp",""),
        })
    rows.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify({"records": rows, "total": len(rows)})

@app.route("/api/stats")
def api_stats():
    col   = get_col()
    metas = col.get(include=["metadatas"])["metadatas"]
    by_type, by_source, by_company = {}, {}, {}
    for m in metas:
        t = m.get("type","unknown");    by_type[t]    = by_type.get(t,0)+1
        s = m.get("source","unknown");  by_source[s]  = by_source.get(s,0)+1
        c = m.get("company","")
        if c: by_company[c] = by_company.get(c,0)+1
    return jsonify({
        "total": col.count(),
        "by_type": by_type, "by_source": by_source, "by_company": by_company
    })

@app.route("/api/add", methods=["POST"])
def api_add():
    body    = request.json
    mode    = body.get("mode")
    company = body.get("company","")
    col     = get_col()
    if mode == "qa":
        q = body.get("question","").strip()
        a = body.get("answer","").strip()
        if not q or not a: return jsonify({"error": "Question and answer required"}), 400
        uid  = "qa_" + hashlib.md5(q.lower().encode()).hexdigest()[:16]
        meta = {"question": q[:120], "source": "manual", "type": "qa",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "company": company}
        col.upsert(ids=[uid], embeddings=[embed(q)], documents=[a], metadatas=[meta])
    elif mode == "fact":
        stmt = body.get("statement","").strip()
        if not stmt: return jsonify({"error": "Statement required"}), 400
        uid  = "fact_" + hashlib.md5(stmt.lower().encode()).hexdigest()[:16]
        meta = {"question": "", "source": "manual", "type": "fact",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "company": company}
        col.upsert(ids=[uid], embeddings=[embed(stmt)], documents=[stmt], metadatas=[meta])
    else:
        return jsonify({"error": "Invalid mode"}), 400
    return jsonify({"success": True, "total": col.count()})

@app.route("/api/update/<rid>", methods=["PUT"])
def api_update(rid):
    body    = request.json
    content = body.get("content","").strip()
    if not content: return jsonify({"error": "Content required"}), 400
    col    = get_col()
    result = col.get(ids=[rid], include=["metadatas"])
    if not result["ids"]: return jsonify({"error": "Not found"}), 404
    meta = result["metadatas"][0]
    col.upsert(ids=[rid], embeddings=[embed(content)], documents=[content], metadatas=[meta])
    return jsonify({"success": True})

@app.route("/api/delete/<rid>", methods=["DELETE"])
def api_delete(rid):
    col = get_col()
    col.delete(ids=[rid])
    return jsonify({"success": True, "total": col.count()})

@app.route("/api/search")
def api_search():
    q     = request.args.get("q","").strip()
    top_k = int(request.args.get("k", 5))
    if not q: return jsonify({"error": "Query required"}), 400
    col   = get_col()
    if col.count() == 0: return jsonify({"results": []})
    res   = col.query(
        query_embeddings=[embed(q, "RETRIEVAL_QUERY")],
        n_results=min(top_k, col.count()),
        include=["documents","metadatas","distances"],
    )
    rows = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        rows.append({
            "score":    round(1-dist, 4), "content": doc,
            "question": meta.get("question",""),
            "type":     meta.get("type","qa"),
            "source":   meta.get("source",""),
            "company":  meta.get("company",""),
            "timestamp":meta.get("timestamp",""),
        })
    return jsonify({"results": rows, "query": q})

@app.route("/api/ask", methods=["POST"])
def api_ask():
    body     = request.json
    question = body.get("question","").strip()
    if not question: return jsonify({"error": "Question required"}), 400
    col = get_col()
    hits, top_score, web_ctx, source = [], 0, "", "db+static"
    if col.count() > 0:
        n = min(3, col.count())
        r = col.query(
            query_embeddings=[embed(question, "RETRIEVAL_QUERY")],
            n_results=n, include=["documents","metadatas","distances"],
        )
        hits = [{"answer": d, "meta": m, "score": round(1-dist,4)}
                for d,m,dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])]
        top_score = hits[0]["score"] if hits else 0
    if top_score < LOW_CONF and TAVILY_KEY:
        web_ctx = web_search(question)
        source  = "tavily+static"
    static_ctx = load_static_ctx()
    ctx_parts  = []
    if hits:
        ctx_parts.append("PAST ANSWERS:\n" + "\n\n".join(
            f"Q: {h['meta'].get('question','')}\nA: {h['answer']}" for h in hits))
    if web_ctx:
        ctx_parts.append("WEB:\n" + web_ctx[:2000])
    ctx_parts.append("REFERENCE:\n" + static_ctx[:2000])
    context = "\n\n===\n\n".join(ctx_parts)
    prompt  = ChatPromptTemplate.from_messages([
        ("system", "Answer using ONLY the provided context. Be concise.\n\nContext:\n{context}"),
        ("human", "{question}"),
    ])
    answer = (prompt | llm).invoke({"context": context, "question": question}).content
    uid    = "qa_" + hashlib.md5(question.lower().strip().encode()).hexdigest()[:16]
    col.upsert(ids=[uid], embeddings=[embed(question)], documents=[answer],
               metadatas=[{"question": question[:120], "source": source, "type": "qa",
                           "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "company": ""}])
    return jsonify({"answer": answer, "score": top_score, "source": source, "total": col.count()})

@app.route("/api/companies")
def api_companies():
    profiles = []
    profiles_dir = Path("week2/profiles")
    if profiles_dir.exists():
        for f in sorted(profiles_dir.glob("*.json")):
            try:
                d = json.loads(f.read_text())
                profiles.append({
                    "name":       d.get("company_name",""),
                    "role":       d.get("role","Software Engineer"),
                    "difficulty": d.get("difficulty","Medium"),
                    "ctc":        d.get("fresher_ctc",""),
                    "rounds":     d.get("interview_rounds",[]),
                    "topics":     d.get("key_topics",[]),
                    "stack":      d.get("tech_stack",[]),
                    "news":       d.get("recent_news",""),
                    "questions":  d.get("interview_questions",[]),
                })
            except: pass
    return jsonify({"companies": profiles})

@app.route("/api/research", methods=["POST"])
def api_research():
    body    = request.json
    company = body.get("company","").strip()
    role    = body.get("role","Software Engineer").strip()
    if not company: return jsonify({"error": "Company name required"}), 400
    if not TAVILY_KEY: return jsonify({"error": "Tavily API key not set"}), 400
    col     = get_col()
    queries = [
        f"{company} interview process {role} 2025",
        f"{company} technical interview questions {role}",
        f"{company} fresher salary package India 2025",
    ]
    stored = 0
    for q in queries:
        content = web_search(q)
        if content:
            uid  = "research_" + hashlib.md5(q.lower().encode()).hexdigest()[:16]
            meta = {"question": q[:120], "source": "tavily", "type": "research",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "company": company}
            col.upsert(ids=[uid], embeddings=[embed(content[:1000])],
                       documents=[content[:2500]], metadatas=[meta])
            stored += 1
    return jsonify({"success": True, "stored": stored, "company": company, "total": col.count()})

@app.route("/api/export")
def api_export():
    col    = get_col()
    data   = col.get(include=["documents","metadatas"])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Type","Question","Content","Source","Company","Timestamp"])
    for id_, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        writer.writerow([
            id_, meta.get("type",""), meta.get("question",""),
            doc, meta.get("source",""), meta.get("company",""), meta.get("timestamp",""),
        ])
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=placement_kb.csv"}
    )


# ══════════════════════════════════════════════════════════════════
# HTML — MOTORSPORT EDITION
# ══════════════════════════════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Placement Prep — Intelligence System</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,400;0,600;0,700;0,800;0,900;1,700;1,900&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
/* ─── VARIABLES ──────────────────────────────────────────── */
:root{
  --black:#000;--bg:#0a0a0a;--s1:#111;--s2:#1a1a1a;--s3:#222;
  --red:#cc0000;--red-hi:#e60000;--red-lo:rgba(204,0,0,.12);
  --white:#fff;--g1:#f0f0f0;--g2:#aaa;--g3:#555;--g4:#333;
  --border:#1e1e1e;--border2:#2a2a2a;
  --sw:252px;
  --font-head:'Barlow Condensed',sans-serif;
  --font-body:'Barlow',sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--black);color:var(--white);font-family:var(--font-body);overflow-x:hidden;line-height:1.5}

/* ─── SCROLL PROGRESS ───────────────────────────────────── */
#pgbar{position:fixed;top:0;left:var(--sw);right:0;height:3px;
  background:linear-gradient(90deg,var(--red),#ff4444);
  z-index:500;width:0;box-shadow:0 0 10px rgba(204,0,0,.6)}

/* ─── SCROLLBAR ─────────────────────────────────────────── */
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:var(--black)}
::-webkit-scrollbar-thumb{background:var(--g4)}
::-webkit-scrollbar-thumb:hover{background:var(--red)}

/* ─── SIDEBAR ───────────────────────────────────────────── */
.sidebar{
  position:fixed;top:0;left:0;width:var(--sw);height:100vh;
  background:#000;border-right:1px solid var(--border);
  display:flex;flex-direction:column;z-index:300;overflow-y:auto
}
.sb-brand{
  padding:22px 20px 20px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:14px
}
.sb-emblem{
  width:40px;height:40px;background:var(--red);flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  font-family:var(--font-head);font-weight:900;font-size:16px;letter-spacing:.05em;
  clip-path:polygon(0 0,88% 0,100% 50%,88% 100%,0 100%)
}
.sb-name{font-family:var(--font-head);font-weight:900;font-size:15px;
  letter-spacing:.12em;text-transform:uppercase;line-height:1.1}
.sb-ver{font-size:10px;color:var(--g3);letter-spacing:.15em;text-transform:uppercase;margin-top:2px}

.sb-group{padding:20px 0 4px}
.sb-group-label{
  padding:0 20px 10px;
  font-family:var(--font-head);font-size:10px;font-weight:700;
  letter-spacing:.25em;text-transform:uppercase;color:var(--g4)
}
.sb-link{
  display:flex;align-items:center;gap:10px;padding:10px 20px;
  text-decoration:none;color:var(--g3);cursor:pointer;
  font-family:var(--font-head);font-size:13px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;
  border-left:2px solid transparent;transition:all .15s;
  position:relative
}
.sb-link:hover{color:var(--white);background:rgba(255,255,255,.03);border-left-color:var(--g4)}
.sb-link.active{color:var(--white);border-left-color:var(--red);background:var(--red-lo)}
.sb-link.active .sb-n{color:var(--red)}
.sb-n{font-size:10px;color:var(--g4);min-width:22px;font-family:var(--font-head);font-weight:700}
.sb-badge{
  margin-left:auto;background:var(--red);color:#fff;
  font-size:9px;font-weight:900;padding:1px 6px;font-family:var(--font-head);letter-spacing:.05em
}

.sb-foot{
  margin-top:auto;padding:14px 20px;border-top:1px solid var(--border);
  font-size:10px;color:var(--g4);letter-spacing:.1em;text-transform:uppercase;
  display:flex;align-items:center;gap:8px
}
.live-dot{
  width:6px;height:6px;border-radius:50%;background:var(--red);flex-shrink:0;
  animation:pulse 1.8s ease-in-out infinite
}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(204,0,0,.5)}
  60%{opacity:.7;box-shadow:0 0 0 5px rgba(204,0,0,0)}}

/* ─── MAIN ──────────────────────────────────────────────── */
.main{margin-left:var(--sw);min-height:100vh}

/* ─── TOPBAR ────────────────────────────────────────────── */
.topbar{
  position:sticky;top:0;z-index:200;height:52px;
  background:rgba(0,0,0,.95);backdrop-filter:blur(16px);
  border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;padding:0 36px
}
.topbar-label{
  font-family:var(--font-head);font-weight:900;font-size:12px;
  letter-spacing:.2em;text-transform:uppercase;color:var(--g3)
}
.topbar-actions{display:flex;gap:10px;align-items:center}

/* ─── BUTTONS ───────────────────────────────────────────── */
.btn-red{
  background:var(--red);color:#fff;border:none;cursor:pointer;
  font-family:var(--font-head);font-weight:700;font-size:12px;
  letter-spacing:.12em;text-transform:uppercase;padding:9px 22px;
  transition:all .15s;
  clip-path:polygon(0 0,calc(100% - 10px) 0,100% 50%,calc(100% - 10px) 100%,0 100%)
}
.btn-red:hover{background:var(--red-hi);transform:translateX(2px)}
.btn-red:disabled{opacity:.4;cursor:not-allowed;transform:none}

.btn-ghost{
  background:transparent;color:var(--g2);border:1px solid var(--border2);cursor:pointer;
  font-family:var(--font-head);font-weight:700;font-size:12px;
  letter-spacing:.12em;text-transform:uppercase;padding:8px 18px;transition:all .15s
}
.btn-ghost:hover{border-color:var(--red);color:var(--white)}
.btn-ghost:disabled{opacity:.3;cursor:not-allowed}

.btn-icon{
  background:transparent;border:1px solid var(--border2);color:var(--g3);
  width:32px;height:32px;cursor:pointer;font-size:13px;transition:all .15s;
  display:inline-flex;align-items:center;justify-content:center
}
.btn-icon:hover{border-color:var(--red);color:var(--red)}
.btn-icon.danger:hover{background:rgba(204,0,0,.1)}

/* ─── SECTION LAYOUT ────────────────────────────────────── */
.sec{padding:64px 48px;border-bottom:1px solid var(--border);min-height:100vh}

.sec-tag{
  font-family:var(--font-head);font-size:11px;font-weight:700;
  letter-spacing:.3em;text-transform:uppercase;color:var(--red);
  display:flex;align-items:center;gap:12px;margin-bottom:14px
}
.sec-tag::before{content:'';display:block;width:28px;height:1px;background:var(--red)}

.sec-title{
  font-family:var(--font-head);font-weight:900;font-size:64px;
  text-transform:uppercase;line-height:.92;letter-spacing:-.02em;margin-bottom:10px
}
.sec-title .red{color:var(--red)}
.sec-title .dim{color:var(--g3)}

.sec-sub{
  font-size:15px;font-weight:300;color:var(--g2);margin-bottom:52px;max-width:540px
}

/* ─── STAT STRIP ────────────────────────────────────────── */
.stat-strip{display:grid;grid-template-columns:repeat(4,1fr);background:var(--border);gap:1px;margin-bottom:52px}
.stat-cell{background:var(--bg);padding:28px 24px;position:relative;overflow:hidden}
.stat-cell::after{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:var(--red);transform:scaleX(0);transform-origin:left;transition:transform .5s
}
.stat-cell:hover::after{transform:scaleX(1)}
.stat-num{
  font-family:var(--font-head);font-size:60px;font-weight:900;
  line-height:1;color:var(--white);letter-spacing:-.02em
}
.stat-lbl{
  font-family:var(--font-head);font-size:10px;font-weight:700;
  letter-spacing:.2em;text-transform:uppercase;color:var(--g3);margin-top:6px
}
.stat-hint{font-size:11px;color:var(--g4);margin-top:3px}

/* ─── GRID BLOCKS ───────────────────────────────────────── */
.block-grid{display:grid;gap:1px;background:var(--border)}
.block-2{grid-template-columns:repeat(2,1fr)}
.block-3{grid-template-columns:repeat(3,1fr)}
.block-4{grid-template-columns:repeat(4,1fr)}

.block-item{
  background:var(--bg);padding:24px;cursor:pointer;
  border-top:2px solid transparent;transition:all .15s
}
.block-item:hover{background:var(--s1);border-top-color:var(--red)}
.block-item.no-hover:hover{cursor:default;border-top-color:transparent;background:var(--bg)}

/* ─── QUICK ACTIONS ─────────────────────────────────────── */
.qa-icon{font-size:22px;margin-bottom:14px;color:var(--red)}
.qa-label{font-family:var(--font-head);font-size:14px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.qa-desc{font-size:12px;color:var(--g3);margin-top:4px}

/* ─── TOPICS ────────────────────────────────────────────── */
.topic-row{
  display:flex;align-items:center;gap:12px;padding:14px 16px;
  background:var(--bg);border-bottom:1px solid var(--border);cursor:pointer;transition:all .15s
}
.topic-row:hover{background:var(--s1)}
.topic-row.done{background:rgba(204,0,0,.06)}
.topic-row.done .tp-name{color:var(--g3);text-decoration:line-through}
.tp-check{
  width:18px;height:18px;border:1px solid var(--border2);flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:10px;transition:all .15s
}
.topic-row.done .tp-check{background:var(--red);border-color:var(--red);color:#fff}
.tp-name{font-size:13px;font-weight:500;flex:1}
.tp-tag{
  font-family:var(--font-head);font-size:9px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;
  color:var(--g4);background:var(--s2);padding:2px 7px
}
.tp-prog-wrap{margin-bottom:6px;display:flex;justify-content:space-between;align-items:baseline}
.tp-prog-num{font-family:var(--font-head);font-size:36px;font-weight:900}
.tp-prog-lbl{font-family:var(--font-head);font-size:10px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--g3)}

/* ─── PROGRESS BAR ──────────────────────────────────────── */
.prog-track{height:2px;background:var(--s2)}
.prog-fill{height:100%;background:var(--red);transition:width .5s}

/* ─── ACTIVITY ──────────────────────────────────────────── */
.act-row{display:flex;gap:14px;padding:13px 0;border-bottom:1px solid rgba(255,255,255,.04)}
.act-dot{width:7px;height:7px;border-radius:50%;background:var(--red);flex-shrink:0;margin-top:5px}
.act-text{font-size:13px;line-height:1.4}
.act-meta{font-size:10px;color:var(--g3);font-family:var(--font-head);letter-spacing:.1em;text-transform:uppercase;margin-top:3px}

/* ─── COMPANY CARDS ─────────────────────────────────────── */
.co-card{
  background:var(--bg);padding:28px;border-top:2px solid var(--border);
  cursor:pointer;transition:all .15s
}
.co-card:hover{background:var(--s1);border-top-color:var(--red)}
.co-name{font-family:var(--font-head);font-size:26px;font-weight:900;text-transform:uppercase;margin-bottom:4px}
.co-role{font-size:12px;color:var(--g3);margin-bottom:18px}
.co-divider{height:1px;background:var(--border);margin:16px 0}
.co-ctc{font-family:var(--font-head);font-size:34px;font-weight:900;color:var(--red)}
.co-ctc-lbl{font-family:var(--font-head);font-size:9px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--g3)}
.co-tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:14px}

/* ─── BADGE ─────────────────────────────────────────────── */
.badge{
  font-family:var(--font-head);font-size:9px;font-weight:700;
  letter-spacing:.15em;text-transform:uppercase;padding:2px 8px;display:inline-block
}
.b-red{background:rgba(204,0,0,.18);color:#ff7777;border:1px solid rgba(204,0,0,.3)}
.b-gray{background:rgba(255,255,255,.06);color:var(--g2);border:1px solid var(--border2)}
.b-green{background:rgba(16,185,129,.15);color:#34d399;border:1px solid rgba(16,185,129,.3)}
.b-amber{background:rgba(245,158,11,.15);color:#fbbf24;border:1px solid rgba(245,158,11,.3)}
.b-blue{background:rgba(59,130,246,.15);color:#93c5fd;border:1px solid rgba(59,130,246,.3)}

/* ─── RESEARCH PANEL ────────────────────────────────────── */
.res-panel{
  background:var(--s1);border-top:2px solid var(--red);border-bottom:1px solid var(--border);
  padding:28px 32px;margin-bottom:32px
}

/* ─── FLASHCARD ─────────────────────────────────────────── */
.flash-scene{display:flex;flex-direction:column;align-items:center;padding:48px 0}
.flash-card-wrap{width:640px;max-width:90vw;height:340px;perspective:1400px;cursor:pointer}
.flash-inner{
  width:100%;height:100%;transform-style:preserve-3d;
  transition:transform .55s cubic-bezier(.4,0,.2,1);position:relative
}
.flash-inner.flipped{transform:rotateY(180deg)}
.flash-face{
  position:absolute;inset:0;backface-visibility:hidden;
  background:var(--s1);border:1px solid var(--border);border-top:3px solid var(--red);
  display:flex;align-items:center;justify-content:center;padding:44px;text-align:center;
  flex-direction:column
}
.flash-face.back{background:var(--s2);border-top-color:#10b981;transform:rotateY(180deg)}
.flash-face-tag{
  position:absolute;top:16px;left:20px;
  font-family:var(--font-head);font-size:10px;font-weight:700;letter-spacing:.25em;
  text-transform:uppercase;color:var(--red)
}
.flash-face.back .flash-face-tag{color:#10b981}
.flash-q{font-family:var(--font-head);font-size:20px;font-weight:700;line-height:1.35}
.flash-a{font-size:14px;color:var(--g2);line-height:1.6}
.flash-controls{display:flex;gap:1px;background:var(--border);margin-top:28px}
.flash-controls .btn-ghost{border:none;background:var(--s1);min-width:120px}
.flash-filters{display:flex;gap:1px;background:var(--border);margin-top:16px}

/* ─── FILTER CHIPS ──────────────────────────────────────── */
.chip-bar{display:flex;gap:1px;background:var(--border)}
.chip{
  background:var(--bg);padding:9px 18px;border:none;cursor:pointer;
  font-family:var(--font-head);font-size:11px;font-weight:700;letter-spacing:.15em;
  text-transform:uppercase;color:var(--g3);transition:all .15s
}
.chip:hover{background:var(--s1);color:var(--white)}
.chip.on{background:var(--red);color:#fff}

/* ─── TABLE ─────────────────────────────────────────────── */
.tbl{width:100%;border-collapse:collapse}
.tbl th{
  font-family:var(--font-head);font-size:10px;font-weight:700;letter-spacing:.2em;
  text-transform:uppercase;color:var(--g3);padding:12px 16px;text-align:left;
  border-bottom:1px solid var(--border);background:var(--bg);white-space:nowrap
}
.tbl td{padding:13px 16px;font-size:13px;border-bottom:1px solid rgba(255,255,255,.04)}
.tbl tr:hover td{background:var(--s1)}
.tbl td.muted{color:var(--g3);font-size:12px}
.tbl td.num{font-family:var(--font-head);font-weight:700;color:var(--g3)}

/* ─── FORM ──────────────────────────────────────────────── */
.f-label{
  display:block;font-family:var(--font-head);font-size:10px;font-weight:700;
  letter-spacing:.18em;text-transform:uppercase;color:var(--g3);margin-bottom:8px
}
.f-input{
  width:100%;background:var(--s1);border:1px solid var(--border2);
  color:var(--white);padding:11px 14px;font-family:var(--font-body);font-size:14px;
  outline:none;transition:border-color .15s
}
.f-input:focus{border-color:var(--red)}
.f-group{margin-bottom:20px}
.f-err{font-size:12px;color:#ff6666;margin-top:6px;display:none}

/* ─── CHAT ──────────────────────────────────────────────── */
.chat-wrap{display:flex;flex-direction:column;height:56vh;min-height:360px}
.chat-msgs{
  flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:14px;padding:20px 0;
  border-top:1px solid var(--border);border-bottom:1px solid var(--border)
}
.c-msg{max-width:72%}
.c-msg.user{margin-left:auto}
.c-role{font-family:var(--font-head);font-size:9px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--g3);margin-bottom:5px}
.c-bubble{padding:12px 16px;font-size:13px;line-height:1.6;background:var(--s1);border:1px solid var(--border)}
.c-msg.user .c-bubble{background:var(--red-lo);border-color:rgba(204,0,0,.3);border-left:3px solid var(--red)}
.chat-bar{display:flex;margin-top:16px;gap:0}
.chat-in{
  flex:1;background:var(--s1);border:1px solid var(--border2);border-right:none;
  color:var(--white);padding:12px 16px;font-family:var(--font-body);font-size:14px;outline:none
}
.chat-in:focus{border-color:var(--red)}
.chat-send{clip-path:none;padding:12px 28px}

/* ─── SEARCH ────────────────────────────────────────────── */
.search-bar{display:flex;margin-bottom:32px}
.search-in{
  flex:1;background:var(--s1);border:1px solid var(--border2);border-right:none;
  color:var(--white);padding:14px 20px;font-family:var(--font-body);font-size:15px;outline:none
}
.search-in:focus{border-color:var(--red)}
.s-num{
  background:var(--s1);border:1px solid var(--border2);border-right:none;
  color:var(--white);padding:14px;text-align:center;font-size:14px;width:72px;outline:none
}
.s-num:focus{border-color:var(--red)}
.s-result{
  background:var(--s1);border:1px solid var(--border);border-left:3px solid var(--red);
  padding:20px 24px;margin-bottom:1px;transition:background .15s
}
.s-result:hover{background:var(--s2)}
.s-score{font-family:var(--font-head);font-size:11px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:var(--red)}
.s-rank{font-family:var(--font-head);font-size:28px;font-weight:900;color:var(--red);min-width:40px}

/* ─── ANALYTICS BARS ────────────────────────────────────── */
.a-row{display:flex;align-items:center;gap:16px;margin-bottom:12px}
.a-lbl{
  font-family:var(--font-head);font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--g3);min-width:110px;text-align:right
}
.a-track{flex:1;height:3px;background:var(--s2);position:relative}
.a-fill{height:100%;background:var(--red);transition:width .8s cubic-bezier(.4,0,.2,1)}
.a-val{font-family:var(--font-head);font-size:16px;font-weight:900;min-width:28px}
.a-panel{background:var(--bg);border:1px solid var(--border);border-top:2px solid var(--red);padding:28px}
.a-panel-title{font-family:var(--font-head);font-size:10px;font-weight:700;letter-spacing:.25em;text-transform:uppercase;color:var(--red);margin-bottom:20px}

/* ─── MODAL ─────────────────────────────────────────────── */
.m-overlay{
  position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:600;
  display:flex;align-items:center;justify-content:center;
  opacity:0;pointer-events:none;transition:opacity .18s
}
.m-overlay.open{opacity:1;pointer-events:all}
.m-box{
  background:var(--s1);border:1px solid var(--border2);border-top:2px solid var(--red);
  width:560px;max-width:94vw;max-height:88vh;overflow-y:auto;padding:32px
}
.m-box.wide{width:680px}
.m-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}
.m-title{font-family:var(--font-head);font-size:26px;font-weight:900;text-transform:uppercase}
.m-close{
  background:none;border:1px solid var(--border2);color:var(--g3);
  width:30px;height:30px;cursor:pointer;font-size:14px;transition:all .15s;
  display:flex;align-items:center;justify-content:center
}
.m-close:hover{border-color:var(--red);color:var(--red)}

/* ─── TABS ──────────────────────────────────────────────── */
.tab-bar{display:flex;border-bottom:1px solid var(--border);margin-bottom:22px}
.tab-btn{
  background:none;border:none;border-bottom:2px solid transparent;
  color:var(--g3);cursor:pointer;padding:10px 22px;margin-bottom:-1px;
  font-family:var(--font-head);font-size:12px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;transition:all .15s
}
.tab-btn:hover{color:var(--white)}
.tab-btn.on{color:var(--white);border-bottom-color:var(--red)}

/* ─── COMMAND PALETTE ───────────────────────────────────── */
.cmd-bg{
  position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:900;
  display:none;align-items:flex-start;justify-content:center;padding-top:110px
}
.cmd-bg.open{display:flex}
.cmd-box{background:var(--s1);border:1px solid var(--border2);border-top:2px solid var(--red);width:580px;max-width:94vw}
.cmd-in{
  width:100%;background:transparent;border:none;border-bottom:1px solid var(--border);
  color:var(--white);padding:16px 20px;font-family:var(--font-body);font-size:15px;outline:none
}
.cmd-row{
  display:flex;align-items:center;gap:14px;padding:12px 20px;cursor:pointer;
  border-left:2px solid transparent;transition:all .1s;font-size:14px
}
.cmd-row:hover,.cmd-row.on{background:var(--s2);border-left-color:var(--red)}
.cmd-rn{font-family:var(--font-head);font-size:10px;font-weight:700;color:var(--red);min-width:22px}
.cmd-hint{
  display:flex;justify-content:space-between;
  padding:10px 20px;border-top:1px solid var(--border);
  font-family:var(--font-head);font-size:10px;font-weight:700;letter-spacing:.15em;
  text-transform:uppercase;color:var(--g4)
}

/* ─── TOAST ─────────────────────────────────────────────── */
#toast-rack{position:fixed;bottom:24px;right:24px;z-index:999;display:flex;flex-direction:column;gap:8px}
.toast{
  background:var(--s1);border:1px solid var(--border2);border-left:3px solid var(--red);
  padding:12px 20px;font-family:var(--font-head);font-size:13px;font-weight:700;letter-spacing:.05em;
  min-width:260px;animation:tin .3s ease
}
.toast.ok{border-left-color:#10b981}
.toast.err{border-left-color:var(--red)}
.toast.inf{border-left-color:#3b82f6}
@keyframes tin{from{transform:translateX(110%);opacity:0}to{transform:none;opacity:1}}
@keyframes tout{from{transform:none;opacity:1}to{transform:translateX(110%);opacity:0}}

/* ─── SECTION DIVIDERS ──────────────────────────────────── */
.sec-sep{height:1px;background:var(--border);margin:40px 0}
.red-rule{height:2px;background:var(--red);width:48px;margin:28px 0}

/* ─── RESPONSIVE ────────────────────────────────────────── */
@media(max-width:900px){
  :root{--sw:0px}
  .sidebar{display:none}
  .stat-strip{grid-template-columns:repeat(2,1fr)}
  .block-4,.block-3{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:560px){
  .sec{padding:40px 20px}
  .sec-title{font-size:42px}
  .stat-strip,.block-2,.block-3,.block-4{grid-template-columns:1fr}
}
</style>
</head>
<body>

<div id="pgbar"></div>

<!-- ═══════════ SIDEBAR ═══════════ -->
<aside class="sidebar">
  <div class="sb-brand">
    <div class="sb-emblem">PP</div>
    <div>
      <div class="sb-name">Placement Prep</div>
      <div class="sb-ver">Intelligence · v2.0</div>
    </div>
  </div>

  <div class="sb-group">
    <div class="sb-group-label">Main</div>
    <a class="sb-link active" data-sec="dashboard" onclick="gotoSec('dashboard')">
      <span class="sb-n">01</span>Dashboard
    </a>
    <a class="sb-link" data-sec="companies" onclick="gotoSec('companies')">
      <span class="sb-n">02</span>Company Hub
    </a>
    <a class="sb-link" data-sec="flashcards" onclick="gotoSec('flashcards')">
      <span class="sb-n">03</span>Flashcards
    </a>
  </div>

  <div class="sb-group">
    <div class="sb-group-label">Tools</div>
    <a class="sb-link" data-sec="browse" onclick="gotoSec('browse')">
      <span class="sb-n">04</span>Browse Records
    </a>
    <a class="sb-link" data-sec="ask" onclick="gotoSec('ask')">
      <span class="sb-n">05</span>Ask AI
    </a>
    <a class="sb-link" data-sec="search" onclick="gotoSec('search')">
      <span class="sb-n">06</span>Semantic Search
    </a>
    <a class="sb-link" data-sec="analytics" onclick="gotoSec('analytics')">
      <span class="sb-n">07</span>Analytics
    </a>
  </div>

  <div class="sb-foot">
    <div class="live-dot"></div>
    <span id="sb-count">0</span>&nbsp;records · live
  </div>
</aside>

<!-- ═══════════ MAIN ═══════════ -->
<div class="main">

  <!-- TOPBAR -->
  <div class="topbar">
    <div class="topbar-label" id="tb-label">01 — DASHBOARD</div>
    <div class="topbar-actions">
      <button class="btn-ghost" onclick="openCmd()">
        &#8984;&nbsp;Command&nbsp;<span style="opacity:.4;font-size:10px">Ctrl+K</span>
      </button>
      <button class="btn-red" onclick="openM('addM')">+ Add Record</button>
    </div>
  </div>

  <!-- ════════════════ 01 DASHBOARD ════════════════ -->
  <section class="sec" id="dashboard">
    <div class="sec-tag">01 — System Overview</div>
    <div class="sec-title">Every Answer<br><span class="red">Matters.</span></div>
    <div class="sec-sub">Your personal placement intelligence hub — questions answered, companies researched, patterns learned.</div>

    <!-- STATS -->
    <div class="stat-strip">
      <div class="stat-cell">
        <div class="stat-num" id="st-total">0</div>
        <div class="stat-lbl">Total Records</div>
        <div class="stat-hint">Knowledge base entries</div>
      </div>
      <div class="stat-cell">
        <div class="stat-num" id="st-qa">0</div>
        <div class="stat-lbl">Q&amp;A Pairs</div>
        <div class="stat-hint">Answered questions</div>
      </div>
      <div class="stat-cell">
        <div class="stat-num" id="st-research">0</div>
        <div class="stat-lbl">Research Items</div>
        <div class="stat-hint">Company intelligence</div>
      </div>
      <div class="stat-cell">
        <div class="stat-num" id="st-co">0</div>
        <div class="stat-lbl">Companies</div>
        <div class="stat-hint">Tracked profiles</div>
      </div>
    </div>

    <!-- QUICK ACTIONS -->
    <div class="sec-tag" style="margin-bottom:16px">Quick Actions</div>
    <div class="block-grid block-4" style="margin-bottom:52px">
      <div class="block-item" onclick="openM('addM')">
        <div class="qa-icon">＋</div>
        <div class="qa-label">Add Q&amp;A</div>
        <div class="qa-desc">Store a new answer</div>
      </div>
      <div class="block-item" onclick="gotoSec('ask')">
        <div class="qa-icon">◎</div>
        <div class="qa-label">Ask AI</div>
        <div class="qa-desc">Gemini-powered answers</div>
      </div>
      <div class="block-item" onclick="gotoSec('companies')">
        <div class="qa-icon">◈</div>
        <div class="qa-label">Research</div>
        <div class="qa-desc">Company intelligence</div>
      </div>
      <div class="block-item" onclick="exportCSV()">
        <div class="qa-icon">&#8595;</div>
        <div class="qa-label">Export CSV</div>
        <div class="qa-desc">Download all records</div>
      </div>
    </div>

    <!-- TOPICS + ACTIVITY -->
    <div class="block-grid block-2" style="gap:32px;background:transparent">
      <div>
        <div class="sec-tag" style="margin-bottom:14px">Study Tracker</div>
        <div class="tp-prog-wrap">
          <div class="tp-prog-num" id="tp-done">0 / 12</div>
          <div class="tp-prog-lbl">Completed</div>
        </div>
        <div class="prog-track" style="margin-bottom:18px">
          <div class="prog-fill" id="tp-bar" style="width:0%"></div>
        </div>
        <div id="topics-list"></div>
      </div>
      <div>
        <div class="sec-tag" style="margin-bottom:14px">Recent Activity</div>
        <div id="activity"></div>
      </div>
    </div>
  </section>

  <!-- ════════════════ 02 COMPANY HUB ════════════════ -->
  <section class="sec" id="companies">
    <div class="sec-tag">02 — Target Companies</div>
    <div class="sec-title">Company<br><span class="red">Intelligence.</span></div>
    <div class="sec-sub">Live web research via Tavily. Intelligence stored in your knowledge base.</div>

    <!-- RESEARCH PANEL -->
    <div class="res-panel" style="margin-bottom:32px">
      <div class="sec-tag" style="margin-bottom:16px">Live Research</div>
      <div style="display:flex;gap:0">
        <input class="f-input" id="res-co" placeholder="Company name  (e.g. Google, Infosys, Wipro)" style="flex:1;border-right:none">
        <input class="f-input" id="res-role" placeholder="Role  (e.g. SDE, Data Analyst)" style="width:220px;border-right:none">
        <button class="btn-red" id="res-btn" onclick="doResearch()" style="clip-path:none;white-space:nowrap">Research →</button>
      </div>
      <div id="res-status" style="margin-top:10px;font-size:12px;color:var(--g3);display:none;font-family:var(--font-head);letter-spacing:.08em;text-transform:uppercase"></div>
    </div>

    <!-- COMPANY GRID -->
    <div class="block-grid block-3" id="co-grid">
      <div style="grid-column:1/-1;padding:70px;text-align:center;background:var(--bg)">
        <div style="font-family:var(--font-head);font-size:28px;font-weight:900;text-transform:uppercase;color:var(--g3)">Loading Profiles...</div>
      </div>
    </div>
  </section>

  <!-- ════════════════ 03 FLASHCARDS ════════════════ -->
  <section class="sec" id="flashcards">
    <div class="sec-tag">03 — Practice Mode</div>
    <div class="sec-title">Flashcard<br><span class="red">Training.</span></div>
    <div class="sec-sub">Click the card to flip. Shuffle and drill your knowledge base.</div>

    <div class="flash-scene">
      <!-- progress -->
      <div style="width:640px;max-width:90vw;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center">
        <span style="font-family:var(--font-head);font-size:10px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--g3)">Progress</span>
        <span id="fl-counter" style="font-family:var(--font-head);font-weight:700;font-size:14px">0 / 0</span>
      </div>
      <div style="width:640px;max-width:90vw;margin-bottom:30px">
        <div class="prog-track"><div class="prog-fill" id="fl-prog" style="width:0%"></div></div>
      </div>

      <!-- card -->
      <div class="flash-card-wrap" onclick="flipCard()">
        <div class="flash-inner" id="fl-inner">
          <div class="flash-face">
            <div class="flash-face-tag">Question</div>
            <div class="flash-q" id="fl-q">Loading cards...</div>
          </div>
          <div class="flash-face back">
            <div class="flash-face-tag">Answer</div>
            <div class="flash-a" id="fl-a">Flip to reveal</div>
          </div>
        </div>
      </div>

      <!-- controls -->
      <div class="flash-controls">
        <button class="btn-ghost" onclick="flashNav(-1)">&#8592; Prev</button>
        <button class="btn-ghost" onclick="shuffleFlash()">&#8644; Shuffle</button>
        <button class="btn-ghost" onclick="flashNav(1)">Next &#8594;</button>
      </div>

      <!-- filter -->
      <div class="chip-bar flash-filters" style="margin-top:16px">
        <button class="chip on" onclick="setFlashType('all',this)">All</button>
        <button class="chip" onclick="setFlashType('qa',this)">Q&amp;A</button>
        <button class="chip" onclick="setFlashType('fact',this)">Facts</button>
        <button class="chip" onclick="setFlashType('research',this)">Research</button>
      </div>
    </div>
  </section>

  <!-- ════════════════ 04 BROWSE ════════════════ -->
  <section class="sec" id="browse">
    <div class="sec-tag">04 — Knowledge Base</div>
    <div class="sec-title">Browse<br><span class="red">Records.</span></div>
    <div class="sec-sub">View, edit, and manage all stored knowledge.</div>

    <!-- toolbar -->
    <div style="display:flex;gap:0;margin-bottom:22px;flex-wrap:wrap">
      <input class="f-input" id="br-search" placeholder="Filter records..." style="flex:1;min-width:200px;border-right:none" oninput="filterBrowse()">
      <div class="chip-bar" style="border:1px solid var(--border2);border-left:none;flex-wrap:nowrap">
        <button class="chip on" onclick="setBrType('all',this)">All</button>
        <button class="chip" onclick="setBrType('qa',this)">Q&amp;A</button>
        <button class="chip" onclick="setBrType('fact',this)">Facts</button>
        <button class="chip" onclick="setBrType('research',this)">Research</button>
      </div>
      <button class="btn-ghost" onclick="exportCSV()" style="border-left:none;white-space:nowrap">&#8595; Export</button>
    </div>

    <div style="overflow-x:auto">
      <table class="tbl" id="br-table">
        <thead>
          <tr>
            <th>#</th><th>Type</th><th>Question / Content</th>
            <th>Source</th><th>Company</th><th>Time</th><th>Actions</th>
          </tr>
        </thead>
        <tbody id="br-body">
          <tr><td colspan="7" style="text-align:center;padding:60px;color:var(--g3)">Loading...</td></tr>
        </tbody>
      </table>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px">
      <span id="br-info" style="font-family:var(--font-head);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--g3)"></span>
      <div style="display:flex;gap:1px;background:var(--border)">
        <button class="btn-ghost" id="br-prev" onclick="changeBrPage(-1)" style="border:none;background:var(--s1)">&#8592; Prev</button>
        <button class="btn-ghost" id="br-next" onclick="changeBrPage(1)" style="border:none;background:var(--s1)">Next &#8594;</button>
      </div>
    </div>
  </section>

  <!-- ════════════════ 05 ASK AI ════════════════ -->
  <section class="sec" id="ask">
    <div class="sec-tag">05 — AI Interface</div>
    <div class="sec-title">Ask<br><span class="red">Intelligence.</span></div>
    <div class="sec-sub">Powered by Gemini 2.5 Flash — searches knowledge base first, Tavily web fallback if needed.</div>

    <!-- suggestion chips -->
    <div class="chip-bar" style="margin-bottom:22px;flex-wrap:wrap">
      <button class="chip" onclick="askChip(this)">What is Dynamic Programming?</button>
      <button class="chip" onclick="askChip(this)">Explain System Design basics</button>
      <button class="chip" onclick="askChip(this)">TCS NQT preparation tips</button>
      <button class="chip" onclick="askChip(this)">OOP concepts in Python</button>
    </div>

    <div class="chat-wrap">
      <div class="chat-msgs" id="chat-msgs">
        <div class="c-msg">
          <div class="c-role">System</div>
          <div class="c-bubble">Ready. Ask me anything about your placement preparation — DSA, company processes, HR rounds, or any technical topic.</div>
        </div>
      </div>
      <div class="chat-bar">
        <input class="chat-in" id="ask-in" placeholder="Type your question and press Enter..." onkeydown="if(event.key==='Enter')sendAsk()">
        <button class="btn-red chat-send" onclick="sendAsk()">Send &#8594;</button>
      </div>
    </div>
    <div id="ask-src" style="margin-top:8px;font-family:var(--font-head);font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--g4)"></div>
  </section>

  <!-- ════════════════ 06 SEMANTIC SEARCH ════════════════ -->
  <section class="sec" id="search">
    <div class="sec-tag">06 — Vector Search</div>
    <div class="sec-title">Semantic<br><span class="red">Search.</span></div>
    <div class="sec-sub">Find semantically similar content using Gemini embedding vectors.</div>

    <div class="search-bar">
      <input class="search-in" id="s-in" placeholder="Search by meaning, not just keywords..." onkeydown="if(event.key==='Enter')doSearch()">
      <input type="number" class="s-num" id="s-k" value="5" min="1" max="20">
      <button class="btn-red" onclick="doSearch()" style="clip-path:none;padding:14px 28px">Search</button>
    </div>
    <div id="s-results"></div>
  </section>

  <!-- ════════════════ 07 ANALYTICS ════════════════ -->
  <section class="sec" id="analytics">
    <div class="sec-tag">07 — Performance Data</div>
    <div class="sec-title">Knowledge<br><span class="red">Analytics.</span></div>
    <div class="sec-sub">Real-time breakdown of your knowledge base — type, source, company coverage, and growth.</div>

    <div class="block-grid block-2" style="gap:24px;background:transparent">
      <div class="a-panel">
        <div class="a-panel-title">By Record Type</div>
        <div id="ch-type"></div>
      </div>
      <div class="a-panel">
        <div class="a-panel-title">By Source</div>
        <div id="ch-src"></div>
      </div>
      <div class="a-panel">
        <div class="a-panel-title">Companies Researched</div>
        <div id="ch-co"></div>
      </div>
      <div class="a-panel">
        <div class="a-panel-title">Growth — Last 7 Days</div>
        <div id="ch-growth"></div>
      </div>
    </div>
  </section>

</div><!-- /main -->

<!-- ═══════════ MODALS ═══════════ -->

<!-- ADD -->
<div class="m-overlay" id="addM">
  <div class="m-box">
    <div class="m-head">
      <div class="m-title">Add Record</div>
      <button class="m-close" onclick="closeM('addM')">&#10005;</button>
    </div>
    <div class="tab-bar">
      <button class="tab-btn on" id="tab-qa" onclick="switchTab('qa')">Q&amp;A Pair</button>
      <button class="tab-btn" id="tab-fact" onclick="switchTab('fact')">Fact / Statement</button>
    </div>
    <div id="qa-fields">
      <div class="f-group"><label class="f-label">Question</label><input class="f-input" id="add-q" placeholder="Interview question..."></div>
      <div class="f-group"><label class="f-label">Answer</label><textarea class="f-input" id="add-a" rows="4" placeholder="Answer..."></textarea></div>
    </div>
    <div id="fact-fields" style="display:none">
      <div class="f-group"><label class="f-label">Statement / Fact</label><textarea class="f-input" id="add-stmt" rows="5" placeholder="Any fact or statement to remember..."></textarea></div>
    </div>
    <div class="f-group"><label class="f-label">Company (optional)</label><input class="f-input" id="add-co" placeholder="e.g. Google, TCS..."></div>
    <div class="f-err" id="add-err"></div>
    <div style="display:flex;gap:1px;margin-top:4px">
      <button class="btn-ghost" onclick="closeM('addM')" style="flex:1">Cancel</button>
      <button class="btn-red" onclick="submitAdd()" style="flex:1;clip-path:none">Save Record</button>
    </div>
  </div>
</div>

<!-- EDIT -->
<div class="m-overlay" id="editM">
  <div class="m-box">
    <div class="m-head">
      <div class="m-title">Edit Record</div>
      <button class="m-close" onclick="closeM('editM')">&#10005;</button>
    </div>
    <input type="hidden" id="edit-id">
    <div class="f-group"><label class="f-label">Content</label><textarea class="f-input" id="edit-content" rows="7"></textarea></div>
    <div style="display:flex;gap:1px">
      <button class="btn-ghost" onclick="closeM('editM')" style="flex:1">Cancel</button>
      <button class="btn-red" onclick="submitEdit()" style="flex:1;clip-path:none">Update</button>
    </div>
  </div>
</div>

<!-- DELETE -->
<div class="m-overlay" id="delM">
  <div class="m-box" style="max-width:420px">
    <div class="m-head">
      <div class="m-title">Delete Record</div>
      <button class="m-close" onclick="closeM('delM')">&#10005;</button>
    </div>
    <input type="hidden" id="del-id">
    <p style="color:var(--g2);font-size:14px;margin-bottom:24px;line-height:1.6">This record will be permanently removed from the knowledge base. This action cannot be undone.</p>
    <div style="display:flex;gap:1px">
      <button class="btn-ghost" onclick="closeM('delM')" style="flex:1">Cancel</button>
      <button class="btn-red" onclick="submitDel()" style="flex:1;clip-path:none">Delete</button>
    </div>
  </div>
</div>

<!-- COMPANY DETAIL -->
<div class="m-overlay" id="coM">
  <div class="m-box wide">
    <div class="m-head">
      <div class="m-title" id="co-m-name"></div>
      <button class="m-close" onclick="closeM('coM')">&#10005;</button>
    </div>
    <div id="co-m-body"></div>
  </div>
</div>

<!-- COMMAND PALETTE -->
<div class="cmd-bg" id="cmdBg">
  <div class="cmd-box">
    <input class="cmd-in" id="cmd-in" placeholder="Go to section, add record, export..." oninput="renderCmd()" onkeydown="cmdKey(event)">
    <div id="cmd-list"></div>
    <div class="cmd-hint">
      <span>&#8593;&#8595; Navigate</span>
      <span>Enter — Select</span>
      <span>Esc — Close</span>
    </div>
  </div>
</div>

<div id="toast-rack"></div>

<!-- ═══════════ JS ═══════════ -->
<script>
'use strict';
// ── State ──────────────────────────────────────────────────────
let records=[],flashAll=[],flashList=[],flashIdx=0,flashFlipped=false,flashType='all';
let brFilter='all',brSearch='',brCurPage=0;
const PG=15;

const TOPICS=[
  {id:'dsa', name:'Data Structures',  tag:'Core'},
  {id:'algo',name:'Algorithms',       tag:'Core'},
  {id:'dp',  name:'Dynamic Programming',tag:'Core'},
  {id:'oop', name:'OOP Concepts',     tag:'Core'},
  {id:'dbms',name:'DBMS & SQL',       tag:'DB'},
  {id:'os',  name:'Operating Systems',tag:'Systems'},
  {id:'cn',  name:'Computer Networks',tag:'Systems'},
  {id:'sd',  name:'System Design',    tag:'Advanced'},
  {id:'sql', name:'SQL Queries',      tag:'DB'},
  {id:'py',  name:'Python / Java',    tag:'Lang'},
  {id:'git', name:'Git & Linux',      tag:'Tools'},
  {id:'hr',  name:'HR Interview',     tag:'Soft'},
];

// ── Scroll progress + spy ──────────────────────────────────────
window.addEventListener('scroll',()=>{
  const s=document.documentElement;
  document.getElementById('pgbar').style.width=
    (s.scrollTop/(s.scrollHeight-s.clientHeight)*100)+'%';
});

const SECS=['dashboard','companies','flashcards','browse','ask','search','analytics'];
const SEC_LABELS={
  dashboard:'01 — Dashboard',companies:'02 — Company Hub',flashcards:'03 — Flashcards',
  browse:'04 — Browse Records',ask:'05 — Ask Intelligence',search:'06 — Semantic Search',analytics:'07 — Analytics'
};
let ioSeen={};
const spy=new IntersectionObserver(es=>{
  es.forEach(e=>{
    if(!e.isIntersecting) return;
    const id=e.target.id;
    document.querySelectorAll('.sb-link').forEach(a=>a.classList.toggle('active',a.dataset.sec===id));
    document.getElementById('tb-label').textContent=SEC_LABELS[id].toUpperCase();
    if(!ioSeen[id]){ioSeen[id]=true; lazyLoad(id);}
  });
},{threshold:.1});
SECS.forEach(id=>{const el=document.getElementById(id);if(el)spy.observe(el);});

function lazyLoad(id){
  if(id==='dashboard'){loadAll();}
  if(id==='companies'){loadCompanies();}
  if(id==='analytics'){loadStats();}
  if(id==='flashcards'){rebuildFlash();}
  if(id==='browse'){renderBrowse();}
}

// ── Navigation ─────────────────────────────────────────────────
function gotoSec(id){
  document.getElementById(id).scrollIntoView({behavior:'smooth'});
}

// ── Boot ───────────────────────────────────────────────────────
async function loadAll(){
  await fetchRecords();
  renderTopics();
  renderActivity();
}

async function fetchRecords(){
  const r=await fetch('/api/records');
  const d=await r.json();
  records=d.records||[];
  updateStats();
  document.getElementById('sb-count').textContent=records.length;
  return records;
}

// ── Stats ──────────────────────────────────────────────────────
function updateStats(){
  const qa=records.filter(r=>r.type==='qa').length;
  const res=records.filter(r=>r.type==='research').length;
  const cos=new Set(records.map(r=>r.company).filter(Boolean)).size;
  countUp('st-total',records.length);
  countUp('st-qa',qa);
  countUp('st-research',res);
  countUp('st-co',cos);
}
function countUp(id,target){
  const el=document.getElementById(id);
  let n=0; const step=Math.max(1,Math.ceil(target/28));
  const t=setInterval(()=>{n=Math.min(n+step,target);el.textContent=n;if(n>=target)clearInterval(t);},30);
}

// ── Topics ─────────────────────────────────────────────────────
function renderTopics(){
  const done=JSON.parse(localStorage.getItem('pp-topics')||'[]');
  const pct=Math.round(done.length/TOPICS.length*100);
  document.getElementById('tp-done').textContent=`${done.length} / ${TOPICS.length}`;
  document.getElementById('tp-bar').style.width=pct+'%';
  document.getElementById('topics-list').innerHTML=TOPICS.map(t=>{
    const ok=done.includes(t.id);
    return `<div class="topic-row${ok?' done':''}" onclick="toggleTopic('${t.id}')">
      <div class="tp-check">${ok?'&#10003;':''}</div>
      <span class="tp-name">${t.name}</span>
      <span class="tp-tag">${t.tag}</span>
    </div>`;
  }).join('');
}
function toggleTopic(id){
  let done=JSON.parse(localStorage.getItem('pp-topics')||'[]');
  done=done.includes(id)?done.filter(x=>x!==id):[...done,id];
  localStorage.setItem('pp-topics',JSON.stringify(done));
  renderTopics();
}

// ── Activity ───────────────────────────────────────────────────
function renderActivity(){
  const el=document.getElementById('activity');
  const rows=records.slice(0,8);
  if(!rows.length){el.innerHTML='<div style="color:var(--g3);font-size:13px">No activity yet.</div>';return;}
  el.innerHTML=rows.map(r=>`
    <div class="act-row">
      <div class="act-dot"></div>
      <div>
        <div class="act-text">${(r.question||r.content||'Record added').substring(0,64)}...</div>
        <div class="act-meta">${(r.type||'').toUpperCase()} &middot; ${r.timestamp||''}</div>
      </div>
    </div>`).join('');
}

// ── Companies ──────────────────────────────────────────────────
let _companies=[];
async function loadCompanies(){
  const r=await fetch('/api/companies');
  const d=await r.json();
  _companies=d.companies||[];
  const grid=document.getElementById('co-grid');
  if(!_companies.length){
    grid.innerHTML='<div style="grid-column:1/-1;padding:70px;text-align:center;background:var(--bg)"><div style="font-family:var(--font-head);font-size:24px;font-weight:900;text-transform:uppercase;color:var(--g3)">No profiles found</div><div style="font-size:12px;color:var(--g4);margin-top:8px">Add JSON files to week2/profiles/</div></div>';
    return;
  }
  const DIFF_COLOR={Easy:'#10b981',Medium:'#f59e0b',Hard:'#cc0000'};
  grid.innerHTML=_companies.map((c,i)=>{
    const dc=DIFF_COLOR[c.difficulty]||'#888';
    return `<div class="co-card" onclick="showCo(${i})">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
        <span class="badge" style="background:rgba(${hexRgb(dc)},.18);color:${dc};border:1px solid rgba(${hexRgb(dc)},.35)">${c.difficulty||'Medium'}</span>
        <span style="font-family:var(--font-head);font-size:10px;color:var(--g4);letter-spacing:.1em">&#8594;</span>
      </div>
      <div class="co-name">${c.name}</div>
      <div class="co-role">${c.role||'Software Engineer'}</div>
      <div class="co-divider"></div>
      <div class="co-ctc">${c.ctc||'—'}</div>
      <div class="co-ctc-lbl">Fresher CTC</div>
      <div class="co-tags">${(c.topics||[]).slice(0,3).map(t=>`<span class="badge b-gray">${t}</span>`).join('')}</div>
    </div>`;
  }).join('');
}

function hexRgb(hex){
  const h=hex.replace('#','');
  return `${parseInt(h.slice(0,2),16)},${parseInt(h.slice(2,4),16)},${parseInt(h.slice(4,6),16)}`;
}

function showCo(i){
  const c=_companies[i];
  const DIFF_COLOR={Easy:'#10b981',Medium:'#f59e0b',Hard:'#cc0000'};
  const dc=DIFF_COLOR[c.difficulty]||'#888';
  document.getElementById('co-m-name').textContent=c.name.toUpperCase();
  document.getElementById('co-m-body').innerHTML=`
    <div class="block-grid block-2" style="gap:24px;background:transparent;margin-bottom:24px">
      <div>
        <div class="sec-tag" style="font-size:10px;margin-bottom:6px">CTC Package</div>
        <div style="font-family:var(--font-head);font-size:40px;font-weight:900;color:var(--red)">${c.ctc||'—'}</div>
      </div>
      <div>
        <div class="sec-tag" style="font-size:10px;margin-bottom:6px">Difficulty</div>
        <div style="font-family:var(--font-head);font-size:28px;font-weight:900;color:${dc}">${c.difficulty||'—'}</div>
      </div>
    </div>
    <div class="sec-tag" style="font-size:10px;margin-bottom:8px">Interview Rounds</div>
    <div style="display:flex;flex-wrap:wrap;gap:1px;background:var(--border);margin-bottom:22px">
      ${(c.rounds||[]).map((r,j)=>`<div style="background:var(--s1);padding:10px 18px;font-family:var(--font-head);font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase">
        <span style="color:var(--red);margin-right:8px">${String(j+1).padStart(2,'0')}</span>${r}
      </div>`).join('')}
    </div>
    <div class="sec-tag" style="font-size:10px;margin-bottom:8px">Key Topics</div>
    <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:22px">
      ${(c.topics||[]).map(t=>`<span class="badge b-gray">${t}</span>`).join('')}
    </div>
    ${c.stack&&c.stack.length?`
    <div class="sec-tag" style="font-size:10px;margin-bottom:8px">Tech Stack</div>
    <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:22px">
      ${c.stack.map(s=>`<span class="badge b-blue">${s}</span>`).join('')}
    </div>`:''}
    ${c.questions&&c.questions.length?`
    <div class="sec-tag" style="font-size:10px;margin-bottom:8px">Sample Questions</div>
    ${c.questions.map(q=>`<div class="act-row"><div class="act-dot"></div><div class="act-text">${q}</div></div>`).join('')}`:''}
  `;
  openM('coM');
}

// ── Research ───────────────────────────────────────────────────
async function doResearch(){
  const co=document.getElementById('res-co').value.trim();
  const role=document.getElementById('res-role').value.trim()||'Software Engineer';
  if(!co){toast('Enter a company name','err');return;}
  const btn=document.getElementById('res-btn');
  const st=document.getElementById('res-status');
  btn.textContent='Researching...'; btn.disabled=true;
  st.style.display='block';
  st.textContent='Running 3 Tavily queries — interview process, questions, salary...';
  try{
    const r=await fetch('/api/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company:co,role})});
    const d=await r.json();
    if(d.error){toast(d.error,'err');st.textContent='';}
    else{
      toast(`${d.stored} items saved for ${d.company}`,'ok');
      st.textContent=`✓ ${d.stored} research items stored. Total: ${d.total} records.`;
      await fetchRecords();
    }
  }catch{toast('Research failed — check Tavily key','err');}
  btn.textContent='Research →'; btn.disabled=false;
}

// ── Flashcards ─────────────────────────────────────────────────
function rebuildFlash(){
  flashList=records.filter(r=>flashType==='all'||r.type===flashType);
  flashIdx=0; flashFlipped=false;
  document.getElementById('fl-inner').classList.remove('flipped');
  showFlash();
}
function showFlash(){
  const tot=flashList.length;
  document.getElementById('fl-counter').textContent=`${tot?flashIdx+1:0} / ${tot}`;
  document.getElementById('fl-prog').style.width=tot?`${((flashIdx+1)/tot)*100}%`:'0%';
  if(!tot){
    document.getElementById('fl-q').textContent='No cards. Add Q&A records first.';
    document.getElementById('fl-a').textContent='—';
    return;
  }
  const c=flashList[flashIdx];
  document.getElementById('fl-q').textContent=c.question||c.content.substring(0,120)+'...';
  document.getElementById('fl-a').textContent=c.content;
  flashFlipped=false;
  document.getElementById('fl-inner').classList.remove('flipped');
}
function flipCard(){
  flashFlipped=!flashFlipped;
  document.getElementById('fl-inner').classList.toggle('flipped',flashFlipped);
}
function flashNav(d){
  const tot=flashList.length; if(!tot) return;
  flashIdx=(flashIdx+d+tot)%tot; showFlash();
}
function shuffleFlash(){
  flashList.sort(()=>Math.random()-.5); flashIdx=0; showFlash(); toast('Cards shuffled','ok');
}
function setFlashType(t,el){
  flashType=t;
  document.querySelectorAll('.flash-filters .chip').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
  rebuildFlash();
}

// ── Browse ─────────────────────────────────────────────────────
function filterBrowse(){brSearch=document.getElementById('br-search').value.toLowerCase();brCurPage=0;renderBrowse();}
function setBrType(t,el){
  brFilter=t; brCurPage=0;
  el.closest('.chip-bar').querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
  renderBrowse();
}
function changeBrPage(d){
  const filtered=getFiltered();
  const maxP=Math.max(0,Math.ceil(filtered.length/PG)-1);
  brCurPage=Math.max(0,Math.min(brCurPage+d,maxP));
  renderBrowse();
}
function getFiltered(){
  return records.filter(r=>{
    if(brFilter!=='all'&&r.type!==brFilter) return false;
    if(brSearch&&!(r.question+r.content).toLowerCase().includes(brSearch)) return false;
    return true;
  });
}
function renderBrowse(){
  const filtered=getFiltered();
  const tot=filtered.length;
  const page=filtered.slice(brCurPage*PG,(brCurPage+1)*PG);
  const TB={qa:'b-red',fact:'b-gray',research:'b-green',unknown:'b-gray'};
  const tbody=document.getElementById('br-body');
  if(!page.length){
    tbody.innerHTML='<tr><td colspan="7" style="text-align:center;padding:60px;color:var(--g3);font-family:var(--font-head);font-size:14px;letter-spacing:.1em;text-transform:uppercase">No records match</td></tr>';
  } else {
    tbody.innerHTML=page.map((r,i)=>{
      const prev=(r.question||r.content||'').substring(0,56);
      return `<tr>
        <td class="num">${brCurPage*PG+i+1}</td>
        <td><span class="badge ${TB[r.type]||'b-gray'}">${r.type||'?'}</span></td>
        <td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${prev}">${prev}...</td>
        <td class="muted">${r.source||'—'}</td>
        <td class="muted">${r.company||'—'}</td>
        <td class="muted" style="white-space:nowrap">${r.timestamp||'—'}</td>
        <td>
          <span style="display:flex;gap:6px">
            <button class="btn-icon" onclick="openEdit('${r.id}',\`${(r.content||'').replace(/`/g,"'")}\`)">&#9998;</button>
            <button class="btn-icon danger" onclick="openDel('${r.id}')">&#10005;</button>
          </span>
        </td>
      </tr>`;
    }).join('');
  }
  document.getElementById('br-info').textContent=tot?`Showing ${brCurPage*PG+1}–${Math.min((brCurPage+1)*PG,tot)} of ${tot} records`:'No records';
  document.getElementById('br-prev').disabled=brCurPage===0;
  document.getElementById('br-next').disabled=(brCurPage+1)*PG>=tot;
}

// ── Ask AI ─────────────────────────────────────────────────────
function askChip(el){document.getElementById('ask-in').value=el.textContent.trim();sendAsk();}
async function sendAsk(){
  const q=document.getElementById('ask-in').value.trim(); if(!q) return;
  addMsg(q,'user');
  document.getElementById('ask-in').value='';
  const thinking=addMsg('Thinking...','ai',true);
  try{
    const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});
    const d=await r.json();
    thinking.remove(); addMsg(d.answer,'ai');
    document.getElementById('ask-src').textContent=`Source: ${d.source}  ·  Score: ${d.score}  ·  DB: ${d.total} records`;
    await fetchRecords();
  }catch{thinking.remove(); addMsg('Error contacting the AI. Please check server logs.','ai');}
}
function addMsg(text,role,dim=false){
  const wrap=document.getElementById('chat-msgs');
  const div=document.createElement('div');
  div.className='c-msg'+(role==='user'?' user':'');
  div.innerHTML=`<div class="c-role">${role==='user'?'You':'Gemini 2.5 Flash'}</div>
    <div class="c-bubble" style="${dim?'color:var(--g3);font-style:italic':''}">${text}</div>`;
  wrap.appendChild(div);
  wrap.scrollTop=wrap.scrollHeight;
  return div;
}

// ── Semantic Search ────────────────────────────────────────────
async function doSearch(){
  const q=document.getElementById('s-in').value.trim(); if(!q) return;
  const k=parseInt(document.getElementById('s-k').value)||5;
  const el=document.getElementById('s-results');
  el.innerHTML='<div style="font-family:var(--font-head);font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--g3);padding:20px 0">Searching...</div>';
  try{
    const r=await fetch(`/api/search?q=${encodeURIComponent(q)}&k=${k}`);
    const d=await r.json();
    if(!d.results||!d.results.length){el.innerHTML='<div style="color:var(--g3);padding:20px 0;font-size:13px">No results found.</div>';return;}
    const TB={qa:'b-red',fact:'b-gray',research:'b-green'};
    el.innerHTML=d.results.map((r,i)=>`
      <div class="s-result">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
          <div style="display:flex;align-items:center;gap:14px">
            <span class="s-rank">${String(i+1).padStart(2,'0')}</span>
            <span class="badge ${TB[r.type]||'b-gray'}">${r.type}</span>
            ${r.company?`<span class="badge b-gray">${r.company}</span>`:''}
          </div>
          <div style="text-align:right">
            <div class="s-score">${(r.score*100).toFixed(1)}% match</div>
            <div style="width:88px;height:2px;background:var(--s2);margin-top:4px">
              <div style="height:100%;width:${r.score*100}%;background:var(--red)"></div>
            </div>
          </div>
        </div>
        ${r.question?`<div style="font-family:var(--font-head);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--g3);margin-bottom:8px">Q: ${r.question.substring(0,80)}</div>`:''}
        <div style="font-size:13px;line-height:1.6;color:var(--g1)">${r.content.substring(0,220)}...</div>
      </div>`).join('');
  }catch{el.innerHTML='<div style="color:var(--red)">Search failed.</div>';}
}

// ── Analytics ──────────────────────────────────────────────────
async function loadStats(){
  const r=await fetch('/api/stats');
  const d=await r.json();
  renderBars('ch-type',d.by_type||{});
  renderBars('ch-src',d.by_source||{});
  renderBars('ch-co',d.by_company||{});
  growthChart();
}
function renderBars(id,data){
  const el=document.getElementById(id);
  const entries=Object.entries(data).sort((a,b)=>b[1]-a[1]);
  const max=entries[0]?entries[0][1]:1;
  if(!entries.length){
    el.innerHTML='<div style="color:var(--g4);font-family:var(--font-head);font-size:11px;letter-spacing:.15em;text-transform:uppercase">No data yet</div>';
    return;
  }
  el.innerHTML=entries.map(([k,v])=>`
    <div class="a-row">
      <div class="a-lbl">${k}</div>
      <div class="a-track"><div class="a-fill" style="width:${(v/max)*100}%"></div></div>
      <div class="a-val">${v}</div>
    </div>`).join('');
}
function growthChart(){
  const el=document.getElementById('ch-growth');
  const counts={};
  const now=new Date();
  for(let i=6;i>=0;i--){
    const d=new Date(now); d.setDate(d.getDate()-i);
    const key=d.toISOString().slice(5,10);
    counts[key]=0;
  }
  records.forEach(r=>{
    const k=(r.timestamp||'').slice(5,10);
    if(k in counts) counts[k]++;
  });
  const entries=Object.entries(counts);
  const max=Math.max(...entries.map(e=>e[1]),1);
  el.innerHTML=entries.map(([k,v])=>`
    <div class="a-row">
      <div class="a-lbl">${k}</div>
      <div class="a-track"><div class="a-fill" style="width:${(v/max)*100}%"></div></div>
      <div class="a-val">${v}</div>
    </div>`).join('');
}

// ── Export ─────────────────────────────────────────────────────
function exportCSV(){window.open('/api/export','_blank');toast('Downloading CSV...','ok');}

// ── Modals ─────────────────────────────────────────────────────
function openM(id){document.getElementById(id).classList.add('open');}
function closeM(id){document.getElementById(id).classList.remove('open');}
document.addEventListener('keydown',e=>{
  if(e.key==='Escape') document.querySelectorAll('.m-overlay.open').forEach(m=>m.classList.remove('open'));
});
document.querySelectorAll('.m-overlay').forEach(el=>{
  el.addEventListener('click',e=>{if(e.target===el)el.classList.remove('open');});
});

let addMode='qa';
function switchTab(m){
  addMode=m;
  document.getElementById('qa-fields').style.display=m==='qa'?'block':'none';
  document.getElementById('fact-fields').style.display=m==='fact'?'block':'none';
  document.getElementById('tab-qa').classList.toggle('on',m==='qa');
  document.getElementById('tab-fact').classList.toggle('on',m==='fact');
}
async function submitAdd(){
  const err=document.getElementById('add-err');
  err.style.display='none';
  const body={mode:addMode,company:document.getElementById('add-co').value.trim()};
  if(addMode==='qa'){
    body.question=document.getElementById('add-q').value.trim();
    body.answer=document.getElementById('add-a').value.trim();
    if(!body.question||!body.answer){err.textContent='Both question and answer are required.';err.style.display='block';return;}
  } else {
    body.statement=document.getElementById('add-stmt').value.trim();
    if(!body.statement){err.textContent='Statement is required.';err.style.display='block';return;}
  }
  const r=await fetch('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(d.error){err.textContent=d.error;err.style.display='block';return;}
  closeM('addM');
  toast('Record saved successfully','ok');
  await fetchRecords();
  renderBrowse();
}

function openEdit(id,content){
  document.getElementById('edit-id').value=id;
  document.getElementById('edit-content').value=content;
  openM('editM');
}
async function submitEdit(){
  const id=document.getElementById('edit-id').value;
  const content=document.getElementById('edit-content').value.trim();
  await fetch(`/api/update/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({content})});
  closeM('editM'); toast('Record updated','ok');
  await fetchRecords(); renderBrowse();
}

function openDel(id){document.getElementById('del-id').value=id;openM('delM');}
async function submitDel(){
  const id=document.getElementById('del-id').value;
  await fetch(`/api/delete/${id}`,{method:'DELETE'});
  closeM('delM'); toast('Record deleted','err');
  await fetchRecords(); renderBrowse();
}

// ── Command Palette ────────────────────────────────────────────
const CMD=[
  {n:'01',label:'Dashboard',   sec:'dashboard'},
  {n:'02',label:'Company Hub', sec:'companies'},
  {n:'03',label:'Flashcards',  sec:'flashcards'},
  {n:'04',label:'Browse Records',sec:'browse'},
  {n:'05',label:'Ask AI',      sec:'ask'},
  {n:'06',label:'Semantic Search',sec:'search'},
  {n:'07',label:'Analytics',   sec:'analytics'},
  {n:'→', label:'Add Record',  action:()=>openM('addM')},
  {n:'↓', label:'Export CSV',  action:exportCSV},
];
let cmdIdx=0;
function openCmd(){
  document.getElementById('cmdBg').classList.add('open');
  document.getElementById('cmd-in').value='';
  renderCmd();
  setTimeout(()=>document.getElementById('cmd-in').focus(),50);
}
function closeCmd(){document.getElementById('cmdBg').classList.remove('open');}
function renderCmd(){
  const q=document.getElementById('cmd-in').value.toLowerCase();
  const items=CMD.filter(c=>c.label.toLowerCase().includes(q));
  cmdIdx=0;
  document.getElementById('cmd-list').innerHTML=items.map((c,i)=>`
    <div class="cmd-row${i===0?' on':''}" onclick="execCmd('${c.label}')">
      <span class="cmd-rn">${c.n}</span>
      <span>${c.label}</span>
    </div>`).join('');
}
function execCmd(label){
  const c=CMD.find(x=>x.label===label);
  closeCmd();
  if(c.sec) gotoSec(c.sec);
  if(c.action) c.action();
}
function cmdKey(e){
  const rows=document.querySelectorAll('.cmd-row');
  if(e.key==='ArrowDown'){cmdIdx=Math.min(cmdIdx+1,rows.length-1);}
  else if(e.key==='ArrowUp'){cmdIdx=Math.max(cmdIdx-1,0);}
  else if(e.key==='Enter'){const a=document.querySelector('.cmd-row.on');if(a)a.click();return;}
  else if(e.key==='Escape'){closeCmd();return;}
  rows.forEach((r,i)=>r.classList.toggle('on',i===cmdIdx));
}
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();openCmd();}
});
document.getElementById('cmdBg').addEventListener('click',e=>{
  if(e.target===document.getElementById('cmdBg')) closeCmd();
});

// ── Toast ──────────────────────────────────────────────────────
function toast(msg,type='ok'){
  const el=document.createElement('div');
  el.className=`toast ${type}`;
  el.textContent=msg;
  document.getElementById('toast-rack').appendChild(el);
  setTimeout(()=>{
    el.style.animation='tout .3s ease forwards';
    setTimeout(()=>el.remove(),300);
  },3500);
}

// ── Boot ───────────────────────────────────────────────────────
loadAll();
loadCompanies();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    print("\n  ================================================")
    print("  Placement Prep Intelligence  v2.0")
    print("  Design: Motorsport Edition")
    print("  Open  ->  http://localhost:5001")
    print("  Ctrl+K -> Command Palette")
    print("  ================================================\n")
    app.run(debug=False, port=5001)
