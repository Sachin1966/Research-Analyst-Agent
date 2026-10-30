"""
CLI entry point with VeritasCore Evidence Verification and SQLite History Logging.
Run with: python main.py "your research question"
"""

import sys
import asyncio
import time

# Ensure Windows terminal can print unicode without charmap errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from agents import ResearchPipeline
import llm
import tools
import database


def banner():
    mode = "DEMO MODE (canned fallback)" if llm.DEMO_MODE else f"LIVE MODE (Model: {llm.DEFAULT_MODEL})"
    print("=" * 80)
    print(f"  [VeritasCore] Research Analyst & Evidence Verification Agent")
    print(f"  Status: {mode} | Database: SQLite (Persistent)")
    print("=" * 80)


async def main():
    query = " ".join(sys.argv[1:]) or "How do multi-agent LLM systems work and where are they used in production?"
    banner()
    print(f"\nQuery: {query}\n")

    pipeline = ResearchPipeline()
    t0 = time.time()
    sub_questions = []

    async for event in pipeline.run_stream(query):
        status = event.get("status")

        if status == "guardrail_checking":
            print("[Security Guardrail] Validating query safety...")
        elif status == "guardrail_result":
            tag = "PASSED" if event.get("safe") else "BLOCKED"
            print(f"[Security Guardrail] {tag}: {event.get('message')}")
        elif status == "decomposing":
            print("[Orchestrator] Decomposing query into sub-questions...")
        elif status == "sub_questions":
            sub_questions = event.get("sub_questions", [])
            print("\nGenerated Sub-questions:")
            for i, sq in enumerate(sub_questions, 1):
                print(f"   {i}. {sq}")
            print("\n[Workers] Launching worker agents concurrently...")
        elif status == "worker_completed":
            print(f"\n   Worker {event['index'] + 1} completed -> {event['sub_question']}")
            print(f"      Summary: {event['summary']}")
            print(f"      Sources: {[s.get('url') for s in event.get('sources', [])]}")
        elif status == "worker_failed":
            print(f"\n   Worker {event['index'] + 1} failed -> {event['sub_question']}")
            print(f"      Error: {event['message']}")

        # VeritasCore Capability 1: Research Paper Summarization
        elif status == "veritas_paper_summarizing":
            print(f"\n[VeritasCore: Paper Intelligence] {event['message']}")
        elif status == "veritas_paper_summaries":
            print("\n[VeritasCore] Summarized Research Papers:")
            for i, p in enumerate(event.get("summaries", []), 1):
                print(f"   Paper {i}: {p.get('title')} ({p.get('authors')}, {p.get('year')})")
                print(f"      Objective: {p.get('objective')}")
                print(f"      Key Findings: {', '.join(p.get('key_findings', []))[:140]}...")

        elif status == "synthesizing":
            print(f"\n[Synthesizer] {event['message']}")

        # VeritasCore Capability 2: Evidence DNA
        elif status == "veritas_linking_dna":
            print(f"\n[VeritasCore: Evidence DNA] {event['message']}")
        elif status == "veritas_evidence_dna":
            print(f"\n[VeritasCore] Traced Evidence DNA Links ({len(event.get('dna', []))} claims mapped):")
            for item in event.get("dna", [])[:3]:
                print(f"   * Claim: \"{item.get('claim_text')[:80]}...\"")
                print(f"     Passage: \"{item.get('verbatim_passage')[:90]}...\"")
                print(f"     Grounding: {item.get('grounding_alignment')} (Confidence: {int(item.get('confidence_score', 0)*100)}%)")

        # VeritasCore Capability 3: Claim-Level Verification
        elif status == "veritas_verifying_claims":
            print(f"\n[VeritasCore: Verification Audit] {event['message']}")
        elif status == "veritas_verification":
            audit = event.get("audit", {})
            print(f"\n[VeritasCore] Claim-Level Verification Audit:")
            print(f"   Evidence Integrity Score: {audit.get('integrity_score')}%")
            print(f"   Supported: {audit.get('supported_claims')} | Unsupported: {audit.get('unsupported_claims')} | Contradictory: {audit.get('contradictory_claims')} | Needs Research: {audit.get('needs_research_claims')}")
            for c in audit.get("claims", []):
                icon = "[OK]" if c.get("verdict") == "SUPPORTED" else ("[ALERT]" if c.get("verdict") == "UNSUPPORTED" else "[REVIEW]")
                print(f"   {icon} [{c.get('verdict')}] {c.get('claim_text')[:75]}...")

        elif status == "critic_reviewing":
            print(f"\n[Critic Agent] {event['message']}")
        elif status == "critic_verdict":
            print(f"   Critic Verdict: {event.get('verdict', '').upper()} -> {event.get('feedback')}")

        elif status == "completed":
            print("\n" + "=" * 80)
            print("  FINAL SYNTHESIZED RESEARCH REPORT")
            print("=" * 80)
            print(event.get("final_report", ""))
            print("=" * 80)

            # Persist CLI run into SQLite Database
            try:
                elapsed = time.time() - t0
                mins, secs = int(elapsed // 60), int(elapsed % 60)
                duration_str = f"{mins:02d}:{secs:02d}"
                veritas_data = event.get("veritas", {})
                sid = database.save_session(
                    query=query,
                    final_report=event.get("final_report", ""),
                    model="cli_default",
                    duration=duration_str,
                    sub_questions=sub_questions,
                    worker_results=event.get("worker_results", []),
                    paper_summaries=veritas_data.get("paper_summaries", []),
                    evidence_dna=veritas_data.get("evidence_dna", []),
                    audit_report=veritas_data.get("audit_report", {})
                )
                print(f"\n[SQLite Database] Successfully saved research run to database as Session #{sid}")
            except Exception as ex:
                print(f"\n[SQLite Database] Note: Failed to save to database: {ex}")

        elif status == "error":
            print(f"\n[Pipeline Error] {event.get('message')}")

    print(f"\nTotal time: {time.time() - t0:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
