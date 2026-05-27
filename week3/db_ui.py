"""DB Manager UI — Professional web interface for the Q&A knowledge base.
Run: python week3/db_ui.py  →  open http://localhost:5000"""

import os, httpx, chromadb, hashlib, json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template_string

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY")
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
QA_DB_PATH = "week3/qa_db"
COL_NAME   = "qa_store"

app = Flask(__name__)

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


# ── API routes ─────────────────────────────────────────────────

@app.route("/api/records")
def api_records():
    col    = get_col()
    data   = col.get(include=["documents","metadatas"])
    rows   = []
    for id_, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        rows.append({
            "id":        id_,
            "content":   doc,
            "question":  meta.get("question",""),
            "source":    meta.get("source",""),
            "type":      meta.get("type",""),
            "company":   meta.get("company",""),
            "timestamp": meta.get("timestamp",""),
        })
    rows.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify({"records": rows, "total": len(rows)})

@app.route("/api/stats")
def api_stats():
    col   = get_col()
    metas = col.get(include=["metadatas"])["metadatas"]
    by_type   = {}
    by_source = {}
    for m in metas:
        t = m.get("type","unknown");   by_type[t]   = by_type.get(t,0)   + 1
        s = m.get("source","unknown"); by_source[s] = by_source.get(s,0) + 1
    return jsonify({
        "total": col.count(),
        "by_type": by_type,
        "by_source": by_source,
    })

@app.route("/api/add", methods=["POST"])
def api_add():
    body    = request.json
    mode    = body.get("mode")       # "qa" or "fact"
    company = body.get("company","")

    if mode == "qa":
        question = body.get("question","").strip()
        answer   = body.get("answer","").strip()
        if not question or not answer:
            return jsonify({"error": "Question and answer required"}), 400
        uid  = "qa_"   + hashlib.md5(question.lower().encode()).hexdigest()[:16]
        text = question
        doc  = answer
        meta = {"question": question[:120], "source": "manual", "type": "qa",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "company": company}
    elif mode == "fact":
        statement = body.get("statement","").strip()
        if not statement:
            return jsonify({"error": "Statement required"}), 400
        uid  = "fact_" + hashlib.md5(statement.lower().encode()).hexdigest()[:16]
        text = statement
        doc  = statement
        meta = {"question": "", "source": "manual", "type": "fact",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "company": company}
    else:
        return jsonify({"error": "Invalid mode"}), 400

    col = get_col()
    col.upsert(ids=[uid], embeddings=[embed(text)], documents=[doc], metadatas=[meta])
    return jsonify({"success": True, "id": uid, "total": col.count()})

@app.route("/api/update/<rid>", methods=["PUT"])
def api_update(rid):
    body    = request.json
    content = body.get("content","").strip()
    if not content:
        return jsonify({"error": "Content required"}), 400
    col    = get_col()
    result = col.get(ids=[rid], include=["metadatas"])
    if not result["ids"]:
        return jsonify({"error": "Not found"}), 404
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
    if not q:
        return jsonify({"error": "Query required"}), 400
    col = get_col()
    if col.count() == 0:
        return jsonify({"results": []})
    results = col.query(
        query_embeddings=[embed(q, "RETRIEVAL_QUERY")],
        n_results=min(top_k, col.count()),
        include=["documents","metadatas","distances"],
    )
    rows = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        rows.append({
            "score":    round(1 - dist, 4),
            "content":  doc,
            "question": meta.get("question",""),
            "type":     meta.get("type",""),
            "source":   meta.get("source",""),
            "company":  meta.get("company",""),
            "timestamp":meta.get("timestamp",""),
        })
    return jsonify({"results": rows, "query": q})


# ── HTML UI ────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Placement Prep — DB Manager</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<style>
  :root {
    --sidebar-w: 240px;
    --topbar-h: 56px;
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #22263a;
    --border: #2e3250;
    --accent: #6c63ff;
    --accent2: #4ade80;
    --text: #e2e8f0;
    --muted: #8892a4;
    --danger: #f87171;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

  /* topbar */
  .topbar { height: var(--topbar-h); background: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 20px; gap: 16px; flex-shrink: 0; }
  .topbar .logo { font-weight: 700; font-size: 16px; color: var(--accent); letter-spacing: .5px; }
  .topbar .db-badge { background: var(--surface2); border: 1px solid var(--border); padding: 4px 12px; border-radius: 20px; font-size: 12px; color: var(--muted); }
  .topbar .total-badge { background: var(--accent); color: #fff; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
  .topbar .ms-auto { margin-left: auto; display: flex; gap: 8px; }

  /* body layout */
  .app-body { display: flex; flex: 1; overflow: hidden; }

  /* sidebar */
  .sidebar { width: var(--sidebar-w); background: var(--surface); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; padding: 16px 0; overflow-y: auto; }
  .sidebar-section { padding: 8px 16px; font-size: 10px; font-weight: 700; color: var(--muted); letter-spacing: 1px; text-transform: uppercase; margin-top: 8px; }
  .sidebar-item { padding: 9px 20px; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 10px; color: var(--muted); border-left: 3px solid transparent; transition: all .15s; }
  .sidebar-item:hover { background: var(--surface2); color: var(--text); }
  .sidebar-item.active { background: var(--surface2); color: var(--accent); border-left-color: var(--accent); }
  .sidebar-item .bi { font-size: 15px; }
  .stat-pill { margin-left: auto; background: var(--surface2); padding: 1px 8px; border-radius: 10px; font-size: 11px; color: var(--muted); }
  .sidebar-divider { border: none; border-top: 1px solid var(--border); margin: 8px 0; }

  /* main */
  .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

  /* toolbar */
  .toolbar { padding: 12px 20px; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
  .search-box { flex: 1; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 7px 14px; color: var(--text); font-size: 13px; outline: none; }
  .search-box:focus { border-color: var(--accent); }
  .search-box::placeholder { color: var(--muted); }
  .btn-primary-custom { background: var(--accent); border: none; color: #fff; padding: 7px 16px; border-radius: 8px; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 6px; font-weight: 500; transition: opacity .15s; }
  .btn-primary-custom:hover { opacity: .85; }
  .btn-ghost { background: transparent; border: 1px solid var(--border); color: var(--muted); padding: 7px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; transition: all .15s; }
  .btn-ghost:hover { border-color: var(--accent); color: var(--accent); }

  /* views */
  .view { display: none; flex: 1; overflow: hidden; flex-direction: column; }
  .view.active { display: flex; }

  /* table view */
  .table-wrap { flex: 1; overflow-y: auto; padding: 0; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  thead th { background: var(--surface); padding: 10px 16px; color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; border-bottom: 1px solid var(--border); position: sticky; top: 0; white-space: nowrap; }
  tbody tr { border-bottom: 1px solid var(--border); transition: background .1s; }
  tbody tr:hover { background: var(--surface2); }
  tbody td { padding: 10px 16px; vertical-align: middle; }
  .type-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .3px; }
  .type-qa     { background: #1e3a5f; color: #60a5fa; }
  .type-fact   { background: #14532d; color: #4ade80; }
  .type-research { background: #3b1f6b; color: #c084fc; }
  .source-tag { font-size: 11px; color: var(--muted); }
  .content-preview { max-width: 380px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--text); }
  .question-preview { font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 380px; }
  .action-btn { background: none; border: none; color: var(--muted); cursor: pointer; padding: 4px 7px; border-radius: 4px; font-size: 14px; transition: all .15s; }
  .action-btn:hover.edit  { color: var(--accent); background: rgba(108,99,255,.15); }
  .action-btn:hover.del   { color: var(--danger); background: rgba(248,113,113,.1); }
  .statusbar { padding: 6px 20px; background: var(--surface); border-top: 1px solid var(--border); font-size: 11px; color: var(--muted); display: flex; gap: 20px; flex-shrink: 0; }

  /* search view */
  .search-view-wrap { flex: 1; overflow-y: auto; padding: 20px; }
  .search-bar-big { display: flex; gap: 10px; margin-bottom: 20px; }
  .search-input-big { flex: 1; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; color: var(--text); font-size: 15px; outline: none; }
  .search-input-big:focus { border-color: var(--accent); }
  .search-input-big::placeholder { color: var(--muted); }
  .result-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 12px; }
  .result-card .score { font-size: 28px; font-weight: 700; color: var(--accent); }
  .result-card .score-label { font-size: 11px; color: var(--muted); }
  .score-bar { height: 4px; border-radius: 2px; background: var(--surface2); margin: 8px 0; }
  .score-fill { height: 4px; border-radius: 2px; background: linear-gradient(90deg, var(--accent), var(--accent2)); }
  .result-content { font-size: 13px; color: var(--text); margin-top: 10px; line-height: 1.6; }
  .result-meta { display: flex; gap: 12px; margin-top: 10px; font-size: 11px; color: var(--muted); }

  /* stats view */
  .stats-wrap { flex: 1; overflow-y: auto; padding: 24px; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px 24px; }
  .stat-card .num { font-size: 36px; font-weight: 700; color: var(--accent); }
  .stat-card .label { font-size: 12px; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: .5px; }
  .bar-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
  .bar-label { font-size: 12px; color: var(--muted); width: 90px; flex-shrink: 0; text-align: right; }
  .bar-track { flex: 1; height: 8px; background: var(--surface2); border-radius: 4px; }
  .bar-fill  { height: 8px; border-radius: 4px; }
  .bar-count { font-size: 12px; color: var(--text); width: 30px; text-align: right; }

  /* modal */
  .modal-dark .modal-content { background: var(--surface); border: 1px solid var(--border); color: var(--text); }
  .modal-dark .modal-header { border-bottom: 1px solid var(--border); }
  .modal-dark .modal-footer { border-top: 1px solid var(--border); }
  .modal-dark .form-control, .modal-dark .form-select { background: var(--surface2); border: 1px solid var(--border); color: var(--text); }
  .modal-dark .form-control:focus, .modal-dark .form-select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(108,99,255,.2); background: var(--surface2); color: var(--text); }
  .modal-dark .form-label { font-size: 12px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
  .modal-dark .btn-close { filter: invert(1); }
  .tab-mode { display: flex; gap: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 20px; }
  .tab-mode button { flex: 1; background: var(--surface2); border: none; color: var(--muted); padding: 9px; font-size: 13px; cursor: pointer; transition: all .15s; }
  .tab-mode button.active { background: var(--accent); color: #fff; font-weight: 600; }
  .empty-state { text-align: center; padding: 60px 20px; color: var(--muted); }
  .empty-state .bi { font-size: 48px; display: block; margin-bottom: 12px; }

  /* scrollbar */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
</head>
<body>

<!-- TOPBAR -->
<div class="topbar">
  <span class="logo"><i class="bi bi-database-fill-gear"></i> Placement Prep DB</span>
  <span class="db-badge"><i class="bi bi-folder2"></i> qa_store &middot; ChromaDB</span>
  <span class="total-badge" id="top-total">0 records</span>
  <div class="ms-auto">
    <button class="btn-primary-custom" onclick="openAddModal()"><i class="bi bi-plus-lg"></i> Add Record</button>
  </div>
</div>

<div class="app-body">

<!-- SIDEBAR -->
<div class="sidebar">
  <div class="sidebar-section">Views</div>
  <div class="sidebar-item active" id="nav-browse" onclick="showView('browse')">
    <i class="bi bi-table"></i> Browse <span class="stat-pill" id="sbar-total">0</span>
  </div>
  <div class="sidebar-item" id="nav-search" onclick="showView('search')">
    <i class="bi bi-search"></i> Semantic Search
  </div>
  <div class="sidebar-item" id="nav-stats" onclick="showView('stats')">
    <i class="bi bi-bar-chart-line"></i> Statistics
  </div>

  <hr class="sidebar-divider">
  <div class="sidebar-section">Filter by Type</div>
  <div class="sidebar-item" onclick="filterType('')" id="filt-all">
    <i class="bi bi-stack"></i> All <span class="stat-pill" id="sbar-all">0</span>
  </div>
  <div class="sidebar-item" onclick="filterType('qa')" id="filt-qa">
    <i class="bi bi-chat-left-text"></i> Q&A <span class="stat-pill" id="sbar-qa">0</span>
  </div>
  <div class="sidebar-item" onclick="filterType('fact')" id="filt-fact">
    <i class="bi bi-lightbulb"></i> Facts <span class="stat-pill" id="sbar-fact">0</span>
  </div>
  <div class="sidebar-item" onclick="filterType('research')" id="filt-research">
    <i class="bi bi-globe2"></i> Research <span class="stat-pill" id="sbar-research">0</span>
  </div>

  <hr class="sidebar-divider">
  <div class="sidebar-section">Collection</div>
  <div class="sidebar-item" style="cursor:default">
    <i class="bi bi-hdd"></i> <span style="font-size:11px">week3/qa_db</span>
  </div>
</div>

<!-- MAIN -->
<div class="main">

  <!-- BROWSE VIEW -->
  <div class="view active" id="view-browse">
    <div class="toolbar">
      <input class="search-box" id="filter-box" placeholder="Filter records..." oninput="applyFilter()" />
      <button class="btn-ghost" onclick="loadRecords()"><i class="bi bi-arrow-clockwise"></i> Refresh</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Type</th>
            <th>Question / Statement</th>
            <th>Content Preview</th>
            <th>Source</th>
            <th>Company</th>
            <th>Timestamp</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="records-body">
          <tr><td colspan="8" style="text-align:center;padding:40px;color:var(--muted)">Loading...</td></tr>
        </tbody>
      </table>
    </div>
    <div class="statusbar">
      <span id="status-count">0 records</span>
      <span id="status-filter"></span>
    </div>
  </div>

  <!-- SEARCH VIEW -->
  <div class="view" id="view-search">
    <div class="search-view-wrap">
      <h6 style="color:var(--muted);margin-bottom:16px;font-size:12px;text-transform:uppercase;letter-spacing:1px">Semantic Search</h6>
      <div class="search-bar-big">
        <input class="search-input-big" id="sem-query" placeholder="Ask anything — searches by meaning..." onkeydown="if(event.key==='Enter')runSearch()">
        <select id="sem-k" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:12px 14px;border-radius:8px;font-size:13px;outline:none">
          <option value="3">Top 3</option>
          <option value="5" selected>Top 5</option>
          <option value="10">Top 10</option>
        </select>
        <button class="btn-primary-custom" onclick="runSearch()"><i class="bi bi-search"></i> Search</button>
      </div>
      <div id="search-results"></div>
    </div>
  </div>

  <!-- STATS VIEW -->
  <div class="view" id="view-stats">
    <div class="stats-wrap">
      <h6 style="color:var(--muted);margin-bottom:20px;font-size:12px;text-transform:uppercase;letter-spacing:1px">Database Statistics</h6>
      <div class="row g-3 mb-4">
        <div class="col-md-3">
          <div class="stat-card">
            <div class="num" id="s-total">0</div>
            <div class="label">Total Records</div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="stat-card">
            <div class="num" id="s-qa" style="color:#60a5fa">0</div>
            <div class="label">Q&A Pairs</div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="stat-card">
            <div class="num" id="s-fact" style="color:#4ade80">0</div>
            <div class="label">Facts</div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="stat-card">
            <div class="num" id="s-research" style="color:#c084fc">0</div>
            <div class="label">Research</div>
          </div>
        </div>
      </div>
      <div class="row g-3">
        <div class="col-md-6">
          <div class="stat-card">
            <div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:16px">By Type</div>
            <div id="chart-type"></div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="stat-card">
            <div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:16px">By Source</div>
            <div id="chart-source"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

</div><!-- end main -->
</div><!-- end app-body -->


<!-- ADD MODAL -->
<div class="modal fade modal-dark" id="addModal" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-plus-circle"></i> Add New Record</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="tab-mode">
          <button class="active" id="mode-qa-btn" onclick="setMode('qa')"><i class="bi bi-chat-left-text"></i> Q&A Pair</button>
          <button id="mode-fact-btn" onclick="setMode('fact')"><i class="bi bi-lightbulb"></i> Fact / Statement</button>
        </div>
        <div id="form-qa">
          <div class="mb-3">
            <label class="form-label">Question</label>
            <input type="text" class="form-control" id="add-question" placeholder="e.g. What is the Wipro fresher salary?">
          </div>
          <div class="mb-3">
            <label class="form-label">Answer</label>
            <textarea class="form-control" id="add-answer" rows="4" placeholder="e.g. Wipro offers 3.5 LPA to freshers..."></textarea>
          </div>
        </div>
        <div id="form-fact" style="display:none">
          <div class="mb-3">
            <label class="form-label">Statement</label>
            <textarea class="form-control" id="add-statement" rows="5" placeholder="e.g. Intern salary at Google is about $30 per hour..."></textarea>
          </div>
        </div>
        <div class="mb-3">
          <label class="form-label">Company <span style="color:var(--muted);font-weight:400">(optional)</span></label>
          <input type="text" class="form-control" id="add-company" placeholder="e.g. Amazon">
        </div>
        <div id="add-error" style="color:var(--danger);font-size:13px;display:none"></div>
      </div>
      <div class="modal-footer">
        <button class="btn-ghost" data-bs-dismiss="modal">Cancel</button>
        <button class="btn-primary-custom" onclick="submitAdd()"><i class="bi bi-check-lg"></i> Save Record</button>
      </div>
    </div>
  </div>
</div>

<!-- EDIT MODAL -->
<div class="modal fade modal-dark" id="editModal" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-pencil"></i> Edit Record</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <input type="hidden" id="edit-id">
        <div class="mb-3">
          <label class="form-label">Content</label>
          <textarea class="form-control" id="edit-content" rows="7"></textarea>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-ghost" data-bs-dismiss="modal">Cancel</button>
        <button class="btn-primary-custom" onclick="submitEdit()"><i class="bi bi-check-lg"></i> Update</button>
      </div>
    </div>
  </div>
</div>

<!-- DELETE MODAL -->
<div class="modal fade modal-dark" id="delModal" tabindex="-1">
  <div class="modal-dialog modal-sm">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" style="color:var(--danger)"><i class="bi bi-trash3"></i> Delete Record</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body" style="font-size:13px;color:var(--muted)">
        Are you sure? This cannot be undone.
        <input type="hidden" id="del-id">
      </div>
      <div class="modal-footer">
        <button class="btn-ghost" data-bs-dismiss="modal">Cancel</button>
        <button class="btn-primary-custom" style="background:var(--danger)" onclick="submitDelete()"><i class="bi bi-trash3"></i> Delete</button>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
let allRecords = [];
let currentFilter = '';
let currentType = '';
let addMode = 'qa';

// ── load records ───────────────────────────────────────────────
async function loadRecords() {
  const res  = await fetch('/api/records');
  const data = await res.json();
  allRecords = data.records;
  renderTable(allRecords);
  updateSidebar(data.total);
}

function updateSidebar(total) {
  document.getElementById('top-total').textContent = total + ' records';
  document.getElementById('sbar-total').textContent = total;
  document.getElementById('sbar-all').textContent  = total;
  const counts = {};
  allRecords.forEach(r => counts[r.type] = (counts[r.type]||0)+1);
  ['qa','fact','research'].forEach(t => {
    const el = document.getElementById('sbar-'+t);
    if(el) el.textContent = counts[t]||0;
  });
}

function renderTable(records) {
  const tbody = document.getElementById('records-body');
  if (!records.length) {
    tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state"><i class="bi bi-inbox"></i>No records found</div></td></tr>';
    document.getElementById('status-count').textContent = '0 records';
    return;
  }
  tbody.innerHTML = records.map((r,i) => `
    <tr>
      <td style="color:var(--muted);font-size:11px">${i+1}</td>
      <td><span class="type-badge type-${r.type||'qa'}">${r.type||'qa'}</span></td>
      <td><div class="question-preview">${esc(r.question||r.content)}</div></td>
      <td><div class="content-preview">${esc(r.content)}</div></td>
      <td><span class="source-tag">${r.source||'—'}</span></td>
      <td style="font-size:12px;color:var(--muted)">${r.company||'—'}</td>
      <td style="font-size:11px;color:var(--muted);white-space:nowrap">${r.timestamp||'—'}</td>
      <td style="white-space:nowrap">
        <button class="action-btn edit" onclick="openEdit('${esc(r.id)}','${esc(r.content.replace(/'/g,"\\'"))}')" title="Edit"><i class="bi bi-pencil"></i></button>
        <button class="action-btn del"  onclick="openDelete('${esc(r.id)}')" title="Delete"><i class="bi bi-trash3"></i></button>
      </td>
    </tr>`).join('');
  document.getElementById('status-count').textContent = records.length + ' record' + (records.length!==1?'s':'');
}

function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function applyFilter() {
  const q = document.getElementById('filter-box').value.toLowerCase();
  currentFilter = q;
  const filtered = allRecords.filter(r => {
    const matchType = !currentType || r.type === currentType;
    const matchText = !q || (r.content+r.question+r.company).toLowerCase().includes(q);
    return matchType && matchText;
  });
  renderTable(filtered);
  document.getElementById('status-filter').textContent = currentType ? `Type: ${currentType}` : '';
}

function filterType(t) {
  currentType = t;
  ['all','qa','fact','research'].forEach(x => {
    document.getElementById('filt-'+x)?.classList.toggle('active', x === (t||'all'));
  });
  applyFilter();
}


// ── views ──────────────────────────────────────────────────────
function showView(name) {
  ['browse','search','stats'].forEach(v => {
    document.getElementById('view-'+v).classList.toggle('active', v===name);
    document.getElementById('nav-'+v)?.classList.toggle('active', v===name);
  });
  if (name==='stats') loadStats();
}


// ── stats ──────────────────────────────────────────────────────
async function loadStats() {
  const res  = await fetch('/api/stats');
  const data = await res.json();
  document.getElementById('s-total').textContent    = data.total;
  document.getElementById('s-qa').textContent       = data.by_type.qa||0;
  document.getElementById('s-fact').textContent     = data.by_type.fact||0;
  document.getElementById('s-research').textContent = data.by_type.research||0;
  renderBars('chart-type',   data.by_type,   data.total, ['#6c63ff','#4ade80','#c084fc','#f87171']);
  renderBars('chart-source', data.by_source, data.total, ['#60a5fa','#fb923c','#34d399','#a78bfa']);
}

function renderBars(elId, data, total, colors) {
  const el = document.getElementById(elId);
  el.innerHTML = Object.entries(data).sort((a,b)=>b[1]-a[1]).map(([k,v],i) => `
    <div class="bar-row">
      <div class="bar-label">${k}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.round(v/total*100)}%;background:${colors[i%colors.length]}"></div></div>
      <div class="bar-count">${v}</div>
    </div>`).join('');
}


// ── semantic search ────────────────────────────────────────────
async function runSearch() {
  const q = document.getElementById('sem-query').value.trim();
  const k = document.getElementById('sem-k').value;
  if (!q) return;
  document.getElementById('search-results').innerHTML = '<div style="color:var(--muted);text-align:center;padding:40px">Searching...</div>';
  const res  = await fetch(`/api/search?q=${encodeURIComponent(q)}&k=${k}`);
  const data = await res.json();
  if (!data.results?.length) {
    document.getElementById('search-results').innerHTML = '<div class="empty-state"><i class="bi bi-search"></i>No results found</div>';
    return;
  }
  document.getElementById('search-results').innerHTML = data.results.map((r,i) => `
    <div class="result-card">
      <div style="display:flex;align-items:center;gap:16px">
        <div><div class="score">${(r.score*100).toFixed(1)}<span style="font-size:16px;color:var(--muted)">%</span></div><div class="score-label">Similarity</div></div>
        <div style="flex:1">
          <div class="score-bar"><div class="score-fill" style="width:${r.score*100}%"></div></div>
          <span class="type-badge type-${r.type||'qa'}">${r.type||'qa'}</span>
          ${r.company ? `<span style="margin-left:6px;font-size:11px;color:var(--muted)">${r.company}</span>` : ''}
        </div>
        <div style="font-size:22px;font-weight:700;color:var(--muted)">#${i+1}</div>
      </div>
      ${r.question ? `<div style="font-size:12px;color:var(--muted);margin-top:10px">Q: ${esc(r.question)}</div>` : ''}
      <div class="result-content">${esc(r.content)}</div>
      <div class="result-meta">
        <span><i class="bi bi-box-arrow-up-right"></i> ${r.source||'—'}</span>
        <span><i class="bi bi-clock"></i> ${r.timestamp||'—'}</span>
      </div>
    </div>`).join('');
}


// ── add modal ──────────────────────────────────────────────────
function openAddModal() {
  document.getElementById('add-question').value='';
  document.getElementById('add-answer').value='';
  document.getElementById('add-statement').value='';
  document.getElementById('add-company').value='';
  document.getElementById('add-error').style.display='none';
  setMode('qa');
  new bootstrap.Modal(document.getElementById('addModal')).show();
}

function setMode(m) {
  addMode = m;
  document.getElementById('form-qa').style.display   = m==='qa'   ? '' : 'none';
  document.getElementById('form-fact').style.display  = m==='fact' ? '' : 'none';
  document.getElementById('mode-qa-btn').classList.toggle('active', m==='qa');
  document.getElementById('mode-fact-btn').classList.toggle('active', m==='fact');
}

async function submitAdd() {
  const err = document.getElementById('add-error');
  err.style.display = 'none';
  const body = { mode: addMode, company: document.getElementById('add-company').value.trim() };
  if (addMode==='qa') {
    body.question  = document.getElementById('add-question').value.trim();
    body.answer    = document.getElementById('add-answer').value.trim();
  } else {
    body.statement = document.getElementById('add-statement').value.trim();
  }
  const res  = await fetch('/api/add', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await res.json();
  if (data.error) { err.textContent=data.error; err.style.display='block'; return; }
  bootstrap.Modal.getInstance(document.getElementById('addModal')).hide();
  loadRecords();
}


// ── edit modal ─────────────────────────────────────────────────
function openEdit(id, content) {
  document.getElementById('edit-id').value = id;
  document.getElementById('edit-content').value = content;
  new bootstrap.Modal(document.getElementById('editModal')).show();
}

async function submitEdit() {
  const id      = document.getElementById('edit-id').value;
  const content = document.getElementById('edit-content').value.trim();
  await fetch(`/api/update/${id}`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({content})});
  bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
  loadRecords();
}


// ── delete modal ───────────────────────────────────────────────
function openDelete(id) {
  document.getElementById('del-id').value = id;
  new bootstrap.Modal(document.getElementById('delModal')).show();
}

async function submitDelete() {
  const id = document.getElementById('del-id').value;
  await fetch(`/api/delete/${id}`, {method:'DELETE'});
  bootstrap.Modal.getInstance(document.getElementById('delModal')).hide();
  loadRecords();
}


// ── init ───────────────────────────────────────────────────────
loadRecords();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    print("\n  Placement Prep DB Manager")
    print("  Open → http://localhost:5000\n")
    app.run(debug=False, port=5000)
