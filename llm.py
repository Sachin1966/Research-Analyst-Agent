"""
Thin wrapper around the Claude API.

DEMO_MODE=1 (default if no ANTHROPIC_API_KEY is set) returns canned,
realistic responses so you can run and demo the whole pipeline without
an API key or network access. Flip DEMO_MODE off once you plug in your
real ANTHROPIC_API_KEY to see it run for real.
"""

import os
import json
import random
import requests
import asyncio
import queue
import threading

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3:latest")

# Check if we should run in DEMO_MODE (either manually requested, or if Ollama is offline)
DEMO_MODE = os.environ.get("DEMO_MODE") == "1"

if not DEMO_MODE:
    try:
        # Check if Ollama is accessible
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        if response.status_code != 200:
            print("Ollama returned non-200 status code. Running in DEMO_MODE.")
            DEMO_MODE = True
    except Exception as e:
        print(f"Cannot connect to Ollama at {OLLAMA_URL} ({e}). Running in DEMO_MODE.")
        DEMO_MODE = True


async def call_llm_stream(system: str, user: str, model: str = None):
    """Async generator to stream response from local Ollama line-by-line."""
    if DEMO_MODE:
        response = _demo_response(system, user)
        # Yield in chunks of ~20 characters to simulate real streaming
        chunk_size = 20
        for i in range(0, len(response), chunk_size):
            yield response[i:i+chunk_size]
            await asyncio.sleep(0.03)
        return

    active_model = model or DEFAULT_MODEL
    payload = {
        "model": active_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "stream": True,
        "options": {
            "temperature": 0.0
        }
    }

    q = queue.Queue()

    def run_in_thread():
        try:
            url = f"{OLLAMA_URL}/api/chat"
            res = requests.post(url, json=payload, timeout=180, stream=True)
            res.raise_for_status()
            for line in res.iter_lines():
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        q.put(content)
        except Exception as err:
            print(f"Ollama stream error: {err}")
        finally:
            q.put(None)

    threading.Thread(target=run_in_thread, daemon=True).start()

    # Fallback response content in case Ollama stream yields nothing
    yielded_any = False
    while True:
        chunk = await asyncio.to_thread(q.get)
        if chunk is None:
            break
        yielded_any = True
        yield chunk

    if not yielded_any:
        print("Ollama stream yielded no tokens. Falling back to demo response.")
        response = _demo_response(system, user)
        chunk_size = 20
        for i in range(0, len(response), chunk_size):
            yield response[i:i+chunk_size]
            await asyncio.sleep(0.03)


def call_llm(system: str, user: str, max_tokens: int = 1024, json_format: bool = False, model: str = None) -> str:
    """Send one message to local Ollama and return the text response."""
    if DEMO_MODE:
        return _demo_response(system, user)

    active_model = model or DEFAULT_MODEL

    payload = {
        "model": active_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    
    if json_format:
        payload["format"] = "json"

    try:
        url = f"{OLLAMA_URL}/api/chat"
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        res_data = response.json()
        return res_data["message"]["content"]
    except Exception as e:
        print(f"Ollama call failed for model {active_model} ({e}). Falling back to demo response.")
        return _demo_response(system, user)


# ---------------------------------------------------------------------------
# DEMO MODE: canned responses so the agent loop is fully runnable and
# inspectable without an API key. Each agent role gets a plausible response
# shaped like what Claude would actually return for that prompt type.
# ---------------------------------------------------------------------------

def _demo_response(system: str, user: str) -> str:
    if "guardrail" in system.lower() or "security" in system.lower():
        lower_user = user.lower()
        if any(term in lower_user for term in ["ignore previous", "system override", "jailbreak", "dan mode", "bypass safety"]):
            return json.dumps({
                "safe": False,
                "reason": "Input flagged by Security Guardrail: potential prompt injection or system override pattern detected."
            })
        return json.dumps({
            "safe": True,
            "reason": "Query verified clean and safe for research processing."
        })

    if "decompose" in system.lower():

        return json.dumps({
            "sub_questions": [
                "What are the main techniques used in current multi-agent LLM systems?",
                "What real-world products or companies use multi-agent architectures in production?",
                "What are the known failure modes and limitations of multi-agent systems compared to single-agent ones?",
            ]
        })

    if "critic" in system.lower():
        # Check if this is the revision or initial review
        if "previous draft" in user.lower() or "critic feedback" in user.lower():
            return json.dumps({
                "status": "approved",
                "feedback": "The report looks excellent. The future trends and emerging nature warning has been successfully integrated."
            })
        else:
            return json.dumps({
                "status": "revision_needed",
                "feedback": "Please add a brief note emphasizing that multi-agent LLM coordination remains an active, emerging research field."
            })

    if "summarize" in system.lower() and "search results" in system.lower():
        topic_snippets = {
            "techniques": "Common patterns include orchestrator-worker delegation, sequential pipelines, and debate-style peer review between agents. Frameworks like LangGraph and AutoGen formalize these patterns with explicit state machines.",
            "production": "Companies report using multi-agent setups for coding assistants, customer support triage, and research synthesis, typically with one orchestrator agent and several narrowly scoped worker agents.",
            "failure": "Known issues include coordination overhead, error propagation between agents, higher latency and cost from multiple LLM calls, and difficulty attributing failures to a specific agent in the chain.",
        }
        key = next((k for k in topic_snippets if k in user.lower()), "techniques")
        return json.dumps({
            "summary": topic_snippets[key],
            "sources": [
                {"title": "Building effective agents", "url": "https://example.com/source1"},
                {"title": "Multi-agent systems in practice", "url": "https://example.com/source2"},
            ],
        })

    if "synthesize" in system.lower() or "final report" in system.lower():
        if "critic feedback" in user.lower():
            return (
                "## Multi-Agent LLM Systems: Summary Report (Revised)\n\n"
                "Multi-agent systems extend single-agent LLM loops by splitting work across "
                "specialized agents, most commonly using an orchestrator-worker pattern where one "
                "agent decomposes a task and delegates to narrower workers [1]. In production, this "
                "shows up in coding assistants, support triage, and research tools [2]. The main "
                "tradeoff is reliability versus overhead: more agents means more coordination "
                "surface area, higher latency, and harder debugging when something goes wrong [3]. "
                "Most practitioners recommend starting single-agent and only splitting when a "
                "concrete need (context limits, parallelism, specialization) appears.\n\n"
                "> [!NOTE]\n"
                "> Multi-agent LLM coordination remains an active, emerging research field with "
                "evolving best practices for reliability.\n\n"
                "Sources:\n[1] example.com/source1\n[2] example.com/source2\n[3] example.com/source3"
            )
        else:
            return (
                "## Multi-Agent LLM Systems: Summary Report\n\n"
                "Multi-agent systems extend single-agent LLM loops by splitting work across "
                "specialized agents, most commonly using an orchestrator-worker pattern where one "
                "agent decomposes a task and delegates to narrower workers [1]. In production, this "
                "shows up in coding assistants, support triage, and research tools [2]. The main "
                "tradeoff is reliability versus overhead: more agents means more coordination "
                "surface area, higher latency, and harder debugging when something goes wrong [3]. "
                "Most practitioners recommend starting single-agent and only splitting when a "
                "concrete need (context limits, parallelism, specialization) appears.\n\n"
                "Sources:\n[1] example.com/source1\n[2] example.com/source2\n[3] example.com/source3"
            )

    return "Demo response: no matching canned output for this prompt."

