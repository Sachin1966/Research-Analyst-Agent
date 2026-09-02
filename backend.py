import os
import json
import asyncio
import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dataclasses import asdict

from agents import ResearchPipeline
import llm
import tools

app = FastAPI(title="Multi-Agent Research Assistant API")

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
        "tavily_key_configured": os.environ.get("TAVILY_API_KEY") is not None
    }

@app.get("/api/research/stream")
async def stream_research(
    query: str = Query(..., description="The research question to answer"),
    model: str = Query(None, description="Ollama model to use")
):
    """Run the multi-agent research pipeline and stream progress updates in real-time via SSE."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    async def event_generator():
        pipeline = ResearchPipeline(model=model)
        # Add a tiny delay to ensure the connection is fully initialized before sending data
        await asyncio.sleep(0.1)
        async for event in pipeline.run_stream(query):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/research")
async def run_research(
    payload: dict
):
    """Execute research pipeline synchronously and return the full JSON result."""
    query = payload.get("query", "")
    model = payload.get("model", None)
    
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        pipeline = ResearchPipeline(model=model)
        result = await pipeline.run(query)
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


