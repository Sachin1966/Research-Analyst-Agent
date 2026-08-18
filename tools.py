"""
The actual tool the worker agents call. Real implementation uses Tavily
(https://tavily.com - free tier available, sign up for an API key).

DEMO_MODE returns canned search results so the pipeline runs end-to-end
without any external API keys.
"""

import os

# Manual .env loading to avoid external package dependencies
for env_path in [".env", "../.env", "research_agent_project/.env", "../research_agent_project/.env"]:
    try:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ[k.strip()] = v.strip()
            break
    except Exception:
        pass

# DEMO_MODE is enabled if explicitly requested via environment variable.
# We also run in DEMO_MODE if no API keys are present and ddgs cannot be imported/run.
DEMO_MODE = os.environ.get("DEMO_MODE") == "1"

_tavily_client = None
if not DEMO_MODE and os.environ.get("TAVILY_API_KEY"):
    try:
        from tavily import TavilyClient
        _tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    except Exception as e:
        print(f"Failed to initialize Tavily client: {e}")


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Run a web search and return a list of {title, url, content} dicts."""
    query_str = str(query)
    if DEMO_MODE:
        return _demo_search(query_str)

    # 1. Try Tavily if configured
    if _tavily_client is not None:
        try:
            results = _tavily_client.search(query=query_str, max_results=max_results)
            return [
                {"title": r["title"], "url": r["url"], "content": r["content"]}
                for r in results.get("results", [])
            ]
        except Exception as e:
            print(f"Tavily search failed: {e}. Falling back to DuckDuckGo...")

    # 2. Try DuckDuckGo Search
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query_str, max_results=max_results))
            if results:
                return [
                    {"title": r["title"], "url": r["href"], "content": r["body"]}
                    for r in results
                ]
    except Exception as e:
        print(f"DuckDuckGo search failed: {e}. Falling back to canned demo results...")

    # 3. Fallback to demo results
    return _demo_search(query_str)


def _demo_search(query: str) -> list[dict]:
    query_str = str(query)
    return [
        {
            "title": f"Result A relevant to: {query_str[:50]}",
            "url": "https://example.com/source1",
            "content": "Demo search result content used to feed the worker agent's summarizer step.",
        },
        {
            "title": f"Result B relevant to: {query_str[:50]}",
            "url": "https://example.com/source2",
            "content": "A second demo search result, simulating what Tavily/Serper would return.",
        },
    ]

