import os
import json
import asyncio
import time
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
load_dotenv()

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import FastAPI, Query, HTTPException, Body, Depends, Header, Cookie
from fastapi.responses import StreamingResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dataclasses import asdict

from agents import ResearchPipeline
import llm
import tools
import database
import auth
import payment

app = FastAPI(title="Multi-Agent Research Assistant API with VeritasCore & SQLite History")

# Pydantic Schemas for Authentication & User Profiles
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = "Researcher"
    avatar_url: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None

# Pydantic Schemas for Razorpay Payment Gateway
class CreateOrderRequest(BaseModel):
    amount_in_rupees: Optional[int] = 499

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Production health check endpoint for cloud monitoring and container orchestrators."""
    return {
        "status": "healthy",
        "service": "Research Paper Agent",
        "version": "2.5",
        "engine": "VeritasCore",
        "timestamp": time.time()
    }


@app.get("/robots.txt", response_class=PlainTextResponse)
async def get_robots_txt():
    """Serve robots.txt for Googlebot and search indexers."""
    robots_file = os.path.join(os.path.dirname(__file__), "static", "robots.txt")
    if os.path.exists(robots_file):
        with open(robots_file, "r", encoding="utf-8") as f:
            return f.read()
    return "User-agent: *\nAllow: /\nDisallow: /api/\n"


@app.get("/sitemap.xml", response_class=Response)
async def get_sitemap_xml():
    """Serve sitemap.xml for search engines with application/xml media type."""
    sitemap_file = os.path.join(os.path.dirname(__file__), "static", "sitemap.xml")
    if os.path.exists(sitemap_file):
        with open(sitemap_file, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/xml")
    return Response(content="<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'></urlset>", media_type="application/xml")


@app.get("/api/models")
async def get_models():
    """Fetch available models from the local Ollama instance or return supported models."""
    try:
        response = requests.get(f"{llm.OLLAMA_URL}/api/tags", timeout=1)
        if response.status_code == 200:
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            if models:
                return {"status": "success", "models": models}
    except Exception:
        pass
    return {
        "status": "success",
        "models": ["llama3:latest", "llama3:8b", "mistral:latest"]
    }


@app.get("/api/config")
async def get_config():
    """Get the current running configuration status of the system."""
    return {
        "llm_demo_mode": False,
        "search_demo_mode": False,
        "default_model": llm.DEFAULT_MODEL,
        "ollama_url": llm.OLLAMA_URL,
        "tavily_key_configured": os.environ.get("TAVILY_API_KEY") is not None,
        "database_type": "SQLite (Persistent)",
        "database_path": database.DEFAULT_DB_PATH
    }


# ---------------------------------------------------------------------------
# Authentication, Profile & 7-Day Free Trial Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    """Registers a new user account with an automatic 7-day free trial."""
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    existing = database.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please log in.")

    password_hash = auth.hash_password(req.password)
    user = database.create_user(
        email=email,
        password_hash=password_hash,
        name=req.name or "Researcher",
        avatar_url=req.avatar_url or "",
        trial_days=7
    )
    token = auth.create_access_token(user["id"], user["email"])
    trial_status = database.get_user_trial_status(user)
    return {
        "status": "success",
        "token": token,
        "user": user,
        "trial_status": trial_status
    }


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    """Authenticates user and returns JWT token and 7-day trial status."""
    email = req.email.strip().lower()
    user = database.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not auth.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = auth.create_access_token(user["id"], user["email"])
    trial_status = database.get_user_trial_status(user)
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    safe_user["is_pro"] = bool(safe_user.get("is_pro", False))

    return {
        "status": "success",
        "token": token,
        "user": safe_user,
        "trial_status": trial_status
    }


@app.get("/api/auth/me")
async def get_current_user_profile(user: dict = Depends(auth.get_current_user)):
    """Returns the authenticated user's profile and live trial countdown status."""
    trial_status = database.get_user_trial_status(user)
    return {
        "status": "success",
        "user": user,
        "trial_status": trial_status
    }


@app.put("/api/auth/profile")
async def update_profile(req: ProfileUpdateRequest, user: dict = Depends(auth.get_current_user)):
    """Updates user display name and/or avatar image URL."""
    success = database.update_user_profile(
        user_id=user["id"],
        name=req.name,
        avatar_url=req.avatar_url
    )
    if not success and req.name is None and req.avatar_url is None:
        raise HTTPException(status_code=400, detail="No profile updates were provided.")

    updated_user = database.get_user_by_id(user["id"])
    trial_status = database.get_user_trial_status(updated_user)
    return {
        "status": "success",
        "user": updated_user,
        "trial_status": trial_status
    }


# ---------------------------------------------------------------------------
# Razorpay Payment Gateway & Pro Upgrade Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/payment/config")
async def get_payment_configuration():
    """Returns public Razorpay configuration for frontend checkout initialization."""
    return {
        "status": "success",
        "config": payment.get_public_config()
    }


@app.post("/api/payment/create-order")
async def create_payment_order(
    req: Optional[CreateOrderRequest] = None,
    user: dict = Depends(auth.get_current_user)
):
    """Creates a Razorpay order for purchasing the Pro subscription."""
    amount_rupees = req.amount_in_rupees if req and req.amount_in_rupees else payment.PRO_PLAN_PRICE_INR
    amount_paise = amount_rupees * 100
    try:
        order = payment.create_order(
            user_id=user["id"],
            user_email=user["email"],
            amount_paise=amount_paise
        )
        return {
            "status": "success",
            "order": order,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Razorpay order: {str(e)}")


@app.post("/api/payment/verify")
async def verify_payment_transaction(
    req: VerifyPaymentRequest,
    user: dict = Depends(auth.get_current_user)
):
    """Verifies Razorpay HMAC signature and upgrades the researcher to Pro Member."""
    if not req.razorpay_payment_id:
        raise HTTPException(status_code=400, detail="Missing payment ID.")

    is_valid = payment.verify_signature(
        order_id=req.razorpay_order_id,
        payment_id=req.razorpay_payment_id,
        signature=req.razorpay_signature
    )
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Payment verification failed: cryptographic signature mismatch."
        )

    try:
        upgrade_res = payment.upgrade_user_membership(
            user_id=user["id"],
            payment_id=req.razorpay_payment_id
        )
        return {
            "status": "success",
            "message": "Payment verified successfully. Welcome to Pro Membership!",
            "user": upgrade_res["user"],
            "trial_status": upgrade_res["trial_status"],
            "payment_id": req.razorpay_payment_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upgrade user in database: {str(e)}")


# ---------------------------------------------------------------------------
# Persistent Chat / Research History Endpoints (SQLite)
# ---------------------------------------------------------------------------

@app.get("/api/history")
async def list_history(
    limit: int = Query(50, description="Max history items"),
    user: Optional[dict] = Depends(auth.get_optional_user)
):
    """Get recent research history sessions from SQLite database.
    If authenticated, returns the user's private sessions."""
    try:
        user_id = user["id"] if user else None
        sessions = database.get_all_sessions(limit=limit, user_id=user_id)
        return {"status": "success", "history": sessions, "user": user["email"] if user else None}
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
    model: str = Query(None, description="Ollama model to use"),
    token: Optional[str] = Query(None, description="JWT auth token for EventSource SSE"),
    user: Optional[dict] = Depends(auth.get_optional_user)
):
    """Run the multi-agent research pipeline, stream progress updates in real-time via SSE,
    and automatically persist completed research runs into SQLite database linked to the user account."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # If user was not resolved via header or cookie, check token query parameter (standard for EventSource)
    if not user and token:
        payload = auth.decode_access_token(token)
        if payload and "sub" in payload:
            try:
                user = database.get_user_by_id(int(payload["sub"]))
            except Exception:
                user = None

    # Check 7-day free trial status if user is registered
    if user:
        trial_status = database.get_user_trial_status(user)
        if not trial_status.get("is_active", True):
            async def expired_generator():
                yield f"data: {json.dumps({'status': 'error', 'error': 'TRIAL_EXPIRED', 'message': 'Your 7-day free trial has expired. Upgrade to Pro for unlimited AI model access.'})}\n\n"
            return StreamingResponse(expired_generator(), media_type="text/event-stream")

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
                # Automatically persist completed session to SQLite database linked to user
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
                        audit_report=veritas_data.get("audit_report", {}),
                        user_id=user["id"] if user else None
                    )
                    event["session_id"] = session_id
                except Exception as db_err:
                    print(f"Error persisting session to SQLite: {db_err}")

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/research")
async def run_research(payload: dict, user: Optional[dict] = Depends(auth.get_optional_user)):
    """Execute research pipeline synchronously, persist to SQLite database, and return full JSON result."""
    query = payload.get("query", "")
    model = payload.get("model", None)
    
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if user:
        trial_status = database.get_user_trial_status(user)
        if not trial_status.get("is_active", True):
            raise HTTPException(
                status_code=402,
                detail="Your 7-day free trial has expired. Upgrade to Pro for unlimited AI model access."
            )

    t0 = time.time()
    try:
        pipeline = ResearchPipeline(model=model)
        result = await pipeline.run(query)

        elapsed_sec = time.time() - t0
        mins = int(elapsed_sec // 60)
        secs = int(elapsed_sec % 60)
        duration_str = f"{mins:02d}:{secs:02d}"

        # Persist to SQLite linked to user
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
                audit_report=result.audit_report,
                user_id=user["id"] if user else None
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
