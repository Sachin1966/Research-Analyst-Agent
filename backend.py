import os
import json
import asyncio
import time
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
load_dotenv()

from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dataclasses import asdict

from agents import ResearchPipeline
import llm
import tools
import database

app = FastAPI(title="Multi-Agent Research Assistant API with VeritasCore & SQLite History")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/models")
async def get_models():
    """Fetch available models from the local Ollama instance."""
    try:
        response = requests.get(f"{llm.OLLAMA_URL}/api/tags", timeout=3)
        if response.status_code == 200:
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"status": "success", "models": models}
        else:
            return {"status": "error", "message": "Ollama returned error", "models": []}
    except Exception as e:
        return {
            "status": "offline",
            "message": f"Could not connect to Ollama at {llm.OLLAMA_URL} ({str(e)})",
            "models": [llm.DEFAULT_MODEL]  # fallback
        }


@app.get("/api/config")
async def get_config():
    """Get the current running configuration status of the system."""
    return {
        "llm_demo_mode": llm.DEMO_MODE,
        "search_demo_mode": tools.DEMO_MODE,
        "default_model": llm.DEFAULT_MODEL,
        "ollama_url": llm.OLLAMA_URL,
        "tavily_key_configured": os.environ.get("TAVILY_API_KEY") is not None,
        "database_type": "SQLite (Persistent)",
        "database_path": database.DEFAULT_DB_PATH
    }


# ---------------------------------------------------------------------------
# Persistent Chat / Research History Endpoints (SQLite)
# ---------------------------------------------------------------------------

@app.get("/api/history")
async def list_history(limit: int = Query(50, description="Max history items")):
    """Get recent research history sessions from SQLite database."""
    try:
        sessions = database.get_all_sessions(limit=limit)
        return {"status": "success", "history": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")


@app.get("/api/history/{session_id}")
async def get_history_detail(session_id: int):
    """Retrieve full research session by ID with all agent worker results and VeritasCore metrics."""
    session = database.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Research session #{session_id} not found")
    return {"status": "success", "session": session}


@app.post("/api/history")
async def save_history_record(payload: dict = Body(...)):
    """Manually insert or update a research history record in SQLite database."""
    try:
        session_id = database.save_session(
            query=payload.get("query", ""),
            final_report=payload.get("final_report", ""),
            model=payload.get("model", "default"),
            duration=payload.get("duration", "00:00.0"),
            sub_questions=payload.get("sub_questions", []),
            worker_results=payload.get("worker_results", []),
            paper_summaries=payload.get("paper_summaries", []),
            evidence_dna=payload.get("evidence_dna", []),
            audit_report=payload.get("audit_report", {})
        )
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save session: {str(e)}")


@app.delete("/api/history/{session_id}")
async def delete_history_record(session_id: int):
    """Delete a research session by ID from SQLite database."""
    success = database.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or already deleted")
    return {"status": "success", "message": f"Session #{session_id} deleted"}


@app.delete("/api/history")
async def clear_all_history():
    """Clear all research history sessions from SQLite database."""
    database.clear_all_sessions()
    return {"status": "success", "message": "All research history cleared"}


# ---------------------------------------------------------------------------
# Research Execution Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/research/stream")
async def stream_research(
    query: str = Query(..., description="The research question to answer"),
    model: str = Query(None, description="Ollama model to use")
):
    """Run the multi-agent research pipeline, stream progress updates in real-time via SSE,
    and automatically persist completed research runs into SQLite database."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    async def event_generator():
        pipeline = ResearchPipeline(model=model)
        await asyncio.sleep(0.1)
        
        t0 = time.time()
        sub_questions = []

        async for event in pipeline.run_stream(query):
            status = event.get("status")

            if status == "sub_questions":
                sub_questions = event.get("sub_questions", [])

            elif status == "completed":
                # Automatically persist completed session to SQLite database
                try:
                    elapsed_sec = time.time() - t0
                    mins = int(elapsed_sec // 60)
                    secs = int(elapsed_sec % 60)
                    duration_str = f"{mins:02d}:{secs:02d}"

                    veritas_data = event.get("veritas", {})
                    session_id = database.save_session(
                        query=query,
                        final_report=event.get("final_report", ""),
                        model=model,
                        duration=duration_str,
                        sub_questions=sub_questions,
                        worker_results=event.get("worker_results", []),
                        paper_summaries=veritas_data.get("paper_summaries", []),
                        evidence_dna=veritas_data.get("evidence_dna", []),
                        audit_report=veritas_data.get("audit_report", {})
                    )
                    event["session_id"] = session_id
                except Exception as db_err:
                    print(f"Error persisting session to SQLite: {db_err}")

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/research")
async def run_research(payload: dict):
    """Execute research pipeline synchronously, persist to SQLite database, and return full JSON result."""
    query = payload.get("query", "")
    model = payload.get("model", None)
    
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    t0 = time.time()
    try:
        pipeline = ResearchPipeline(model=model)
        result = await pipeline.run(query)

        elapsed_sec = time.time() - t0
        mins = int(elapsed_sec // 60)
        secs = int(elapsed_sec % 60)
        duration_str = f"{mins:02d}:{secs:02d}"

        # Persist to SQLite
        try:
            worker_dicts = [asdict(w) for w in result.worker_results]
            session_id = database.save_session(
                query=query,
                final_report=result.final_report,
                model=model,
                duration=duration_str,
                sub_questions=result.sub_questions,
                worker_results=worker_dicts,
                paper_summaries=result.paper_summaries,
                evidence_dna=result.evidence_dna,
                audit_report=result.audit_report
            )
            data = asdict(result)
            data["session_id"] = session_id
            return data
        except Exception:
            return asdict(result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files directory if it exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting Multi-Agent Research Assistant FastAPI Backend on http://{host}:{port}...")
    uvicorn.run("backend:app", host=host, port=port)
