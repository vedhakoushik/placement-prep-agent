# Placement Prep Agent

An AI-powered interview preparation system built with Claude, LangChain, LangGraph, and ChromaDB.

## What it does
- Input a company name + role → researches interview experiences from the web
- Stores knowledge in a vector database (gets smarter over time)
- Generates targeted interview questions
- Lets you have a follow-up conversation about the company
- Tracks all companies across sessions
- Deployed as a live web app

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env        # add your API keys
```

## Project Structure
```
placement-prep-agent/
├── week1/          # Raw API, conversation loops, prompt engineering
├── week2/          # LangChain chains, tools, web search
├── week3/          # Embeddings, ChromaDB, RAG
├── week4/          # LangGraph agents
├── week5/          # Multi-agent + Streamlit UI
├── data/
│   └── sessions/   # Saved conversation JSON files
└── requirements.txt
```

## Progress
- [x] Week 1 — Claude API + Python fundamentals
- [ ] Week 2 — LangChain + Tools + Tavily
- [ ] Week 3 — Embeddings + ChromaDB + RAG
- [ ] Week 4 — LangGraph + State + Human Loop
- [ ] Week 5 — Multi-Agent + Streamlit + LangSmith
- [ ] Week 6 — Integration + Testing + Docs
- [ ] Week 7 — Docker + CI/CD
- [ ] Week 8 — Cloud Deploy + Monitoring
