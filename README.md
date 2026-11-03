# Research Analyst Agent with VeritasCore 🚀🔬

[![Deploy to Netlify](https://www.netlify.com/img/deploy/button.svg)](https://app.netlify.com/start/deploy?repository=https://github.com/Sachin1966/Research-Analyst-Agent)

An autonomous, multi-agent AI research assistant built on an **Orchestrator-Worker-Synthesizer-Critic** architecture with real-time SSE web streaming, automatic fallbacks, built-in **Agentic AI Security Guardrails**, and **VeritasCore: Research Paper Intelligence & Evidence Verification**.

---

## 🔬 VeritasCore — Core Verification Engine

**VeritasCore** adds automated scholarly intelligence and evidence grounding to the research pipeline through three capabilities:

1. **📚 Research Paper Summarization**:
   - Automatically inspects retrieved scholarly literature and technical sources (integrating live web engines and open **ArXiv API**).
   - Extracts structured intelligence: **Core Objective & Hypothesis**, **Methodology & Experimental Architecture**, **Key Quantitative Findings & Benchmark Metrics**, and **Identified Constraints & Limitations**.

2. **🧬 Evidence DNA**:
   - Traces every individual factual claim in the final synthesized report directly back to its **verbatim or high-fidelity grounding passage** in the original research papers.
   - Computes grounding alignment tags (`Direct Corroboration`, `Contextual Inference`, `Partial Support`) and confidence scores (e.g., `96% Match`).

3. **⚖️ Claim-Level Verification**:
   - Comprehensive factual integrity audit classifying every claim into:
     - **✅ SUPPORTED**: Directly backed by retrieved paper passages.
     - **❌ UNSUPPORTED**: Assertions without empirical source backing (flags potential hallucinations).
     - **⚠️ CONTRADICTORY**: Conflicting statistics, benchmarks, or conclusions across competing literature.
     - **🔍 NEEDS FURTHER RESEARCH**: Speculative hypotheses or open research questions requiring more empirical study.
   - Computes an overall **Evidence Integrity Score** and enables interactive filtering in the web dashboard.

---

## 🌟 Full Feature Overview

- **🛡️ AI Security Guardrails**: Built-in `GuardrailAgent` that inspects queries for prompt injection attacks, system prompt overrides, and roleplay jailbreaks before pipeline execution.
- **🧠 Orchestrator Agent**: Intelligently decomposes complex research topics into 2–4 focused, non-overlapping sub-questions.
- **⚡ Parallel Worker Agents**: Executes web and academic searches concurrently (`asyncio`), retrieving real-time information via Tavily, DuckDuckGo, and ArXiv.
- **🔬 VeritasCore Engine**: Paper intelligence, Evidence DNA, and multi-tier claim verification audit.
- **📝 Synthesizer Agent**: Compiles worker summaries and paper intelligence into a polished Markdown report with inline `[1] [2]` citations.
- **🔍 Critic Agent**: Reviews draft reports against the VeritasCore evidence audit, initiating self-correction revision loops when ungrounded claims or contradictions are detected.
- **💻 Modern Web Dashboard**: Responsive glassmorphism UI with real-time SSE progress steppers, Evidence DNA matrix cards, interactive audit filter tabs, timers, markdown rendering, copy-to-clipboard, and report downloads.
- **🗄️ Persistent SQLite Database**: Zero-configuration, serverless SQLite database (`research_history.db`) that automatically records full research sessions, including query prompts, worker results, paper summaries, Evidence DNA mappings, and claim audits with instant reload and delete capabilities.
- **📊 MLflow Experiment Tracking & LLMOps**: Logs query parameters, pipeline latency, worker counts, critic approval, VeritasCore Evidence Integrity scores, supported/unsupported claim counts, and artifacts (`final_report.md`, `evidence_dna.json`, `veritas_audit.json`, `paper_summaries.json`).
- **☁️ 100% Free Perpetual Cloud Deployment**: Dockerized and configured with automatic Demo Mode fallback, ready for zero-cost hosting on **Hugging Face Spaces** or **Render.com**.

---

## 🏗️ Architecture Pipeline

```
[ User Input Query ]
         │
         ▼
[ 🛡️ Guardrail Agent ] ──(Flagged Injection)──► [ ❌ Error / Block ]
         │ (Clean)
         ▼
[ 🧠 Orchestrator Agent ] ──► (Decomposes into Sub-questions)
         │
   ┌──────┴──────┬─────────────┐
   ▼             ▼             ▼
[ Worker 1 ] [ Worker 2 ] [ Worker 3 ]  (Parallel Web + ArXiv Search)
   └──────┬──────┴─────────────┘
          │
          ▼
[ 🔬 VeritasCore: Paper Summarizer ] ──► (Extracts Objectives, Methods, Findings, Constraints)
          │
          ▼
[ 📝 Synthesizer Agent ] ──► (Drafts Initial Cited Report)
          │
          ▼
[ 🧬 VeritasCore: Evidence DNA ] ──► (Links Claims to Verbatim Paper Passages)
          │
          ▼
[ ⚖️ VeritasCore: Claim Verifier ] ──► (Audits Supported, Unsupported, Contradictory)
          │
          ▼
[ 🔍 Critic Agent ] ──(Revision Needed?)──► [ Re-Synthesize Report ]
          │ (Approved)
          ▼
[ 📄 Final Cited Markdown Report + Evidence DNA Matrix + Verification Audit ]
```

---

## 🚀 Quick Start (Local Setup)

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/Sachin1966/Research-Analyst-Agent.git
cd Research-Analyst-Agent
pip install -r requirements.txt
```

### 2. Run the Web Interface (FastAPI)
```bash
python backend.py
```
Open your browser and visit `http://localhost:8000`.

### 3. Run via CLI
```bash
python main.py "How do multi-agent LLM systems work in production?"
```

---

## 🔑 Environment Variables & Configuration

Copy `.env.example` to `.env`:

```env
# Local Ollama URL & Model (Default)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3:latest

# API Keys (Optional - live web search & cloud LLMs)
TAVILY_API_KEY=tvly-...
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...

# Force Demo Mode (0 = Auto-detect, 1 = Force canned responses)
DEMO_MODE=0
```

*Note: If Ollama or Tavily API keys are absent, the system automatically falls back to **Demo Mode** with DuckDuckGo & ArXiv search so the application never crashes.*

---

## 📊 MLflow LLMOps & Experiment Tracking

Every pipeline execution automatically logs runs into an MLflow experiment named `Research_Analyst_Agent`:

- **Logged Parameters**: Query text, LLM model choice, guardrail status.
- **Logged Metrics**: Execution duration, sub-question count, worker count, retrieved source count, critic approval score, **VeritasCore Evidence Integrity score**, supported claims count, unsupported claims count, contradictory claims count, and needs-further-research count.
- **Logged Artifacts**: Complete synthesized Markdown research report (`final_report.md`), Evidence DNA mapping (`evidence_dna.json`), Claim verification audit (`veritas_audit.json`), and Paper summaries (`paper_summaries.json`).

To launch the MLflow web UI locally:
```bash
mlflow ui
```
Open `http://localhost:5000` in your browser.

---

---

## 🌐 Netlify Deployment

The web frontend is pre-configured for continuous deployment on **Netlify**:

1. **Push your repository** to GitHub (`https://github.com/Sachin1966/Research-Analyst-Agent`).
2. **Log into Netlify** ([app.netlify.com](https://app.netlify.com)) and click **"Add new site" > "Import an existing project"**.
3. Select your repository: Netlify will automatically detect [`netlify.toml`](netlify.toml) and set:
   - **Publish directory**: `static`
   - **Build command**: *(leave blank)*
4. Click **Deploy Site**.
5. *(Optional)* If your Python backend is hosted on Render, Railway, or Hugging Face Spaces, enter its URL in the web UI under **Configuration > Backend API URL** or uncomment the API proxy rule in `netlify.toml`.

## 📁 Repository Structure

```
├── database.py        # SQLite persistent database manager (CRUD, session history & schema)
├── veritas.py         # VeritasCore Engine: Paper Summaries, Evidence DNA & Claim Verifier
├── agents.py          # Guardrail, Orchestrator, Worker, Synthesizer, and Critic agents
├── backend.py         # FastAPI server with SSE streaming endpoint (/api/research/stream) & history REST API
├── llm.py             # LLM provider wrapper (Ollama / Gemini / Cloud LLM / Demo fallbacks)
├── tools.py           # Tavily, DuckDuckGo & ArXiv academic search integration
├── main.py            # CLI entry point with VeritasCore terminal reporting & DB persistence
├── app.py             # Alternative Streamlit UI
├── data/              # SQLite database storage (research_history.db)
├── static/            # Frontend assets (index.html, app.js, app.css)
├── netlify.toml       # Netlify frontend & CDN routing configuration
├── Dockerfile         # Hugging Face Spaces / Container deployment manifest
├── Procfile           # Render deployment manifest
├── requirements.txt   # Python dependencies
└── README.md          # Documentation
```

---

## 📄 License

MIT License. Free for open source research and commercial adaptation.
