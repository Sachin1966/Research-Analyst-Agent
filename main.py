"""
CLI entry point. Run with: python main.py "your research question"
"""

import sys
import asyncio
import time

from agents import ResearchPipeline
import llm
import tools


def banner():
    mode = "DEMO MODE (no API keys set)" if llm.DEMO_MODE else f"LIVE MODE (Ollama: {llm.DEFAULT_MODEL})"
    print("=" * 70)
    print(f"  Multi-Agent Research Assistant  —  {mode}")
    print("=" * 70)


async def main():
    query = " ".join(sys.argv[1:]) or "How do multi-agent LLM systems work and where are they used?"
    banner()
    print(f"\nQuery: {query}\n")

    pipeline = ResearchPipeline()
    t0 = time.time()

    async for event in pipeline.run_stream(query):
        status = event["status"]
        if status == "decomposing":
            print("[Orchestrator] Decomposing query into sub-questions...")
        elif status == "sub_questions":
            print("\nGenerated Sub-questions:")
            for i, sq in enumerate(event["sub_questions"], 1):
                print(f"   {i}. {sq}")
            print("\n[Workers] Launching worker agents concurrently...")
        elif status == "worker_completed":
            print(f"\n   Worker {event['index'] + 1} completed -> {event['sub_question']}")
            print(f"      Summary: {event['summary']}")
            print(f"      Sources: {[s['url'] for s in event['sources']]}")
        elif status == "worker_failed":
            print(f"\n   Worker {event['index'] + 1} failed -> {event['sub_question']}")
            print(f"      Error: {event['message']}")
        elif status == "synthesizing":
            print(f"\n[Synthesizer] {event['message']}")
        elif status == "critic_reviewing":
            print(f"\n[Critic Agent] {event['message']}")
        elif status == "critic_verdict":
            print(f"               Verdict: {event['verdict'].upper()}")
            print(f"               Feedback: {event['feedback']}")

        elif status == "completed":
            print("-" * 70)
            print(event["final_report"])
            print("-" * 70)
        elif status == "error":
            print(f"\n[Pipeline Error] {event['message']}")

    print(f"\nTotal time: {time.time() - t0:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
