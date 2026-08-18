"""
Streamlit dashboard for the multi-agent research assistant.

Run with: streamlit run app.py

Shows the orchestrator's sub-questions, each worker agent's progress and
findings live, and the final synthesized report — so you can actually watch
the multi-agent loop happen instead of reading it from a terminal log.
"""

import asyncio
import time

import streamlit as st

from agents import OrchestratorAgent, WorkerAgent, SynthesizerAgent
import llm


st.set_page_config(page_title="Multi-Agent Research Assistant", layout="wide")

st.title("Multi-agent research assistant")
mode_label = "DEMO MODE — using canned data" if llm.DEMO_MODE else f"LIVE MODE — calling Ollama ({llm.DEFAULT_MODEL}) + Tavily"
st.caption(mode_label)

query = st.text_input(
    "Research question",
    value="How do multi-agent LLM systems work and where are they used in production?",
)
run_clicked = st.button("Run research pipeline", type="primary")

if run_clicked and query.strip():
    t0 = time.time()

    # --- Step 1: Orchestrator -------------------------------------------------
    st.subheader("1. Orchestrator — decomposing the query")
    with st.spinner("Breaking query into sub-questions..."):
        orchestrator = OrchestratorAgent()
        sub_questions = orchestrator.decompose(query)

    for i, sq in enumerate(sub_questions, 1):
        st.markdown(f"**{i}.** {sq}")

    # --- Step 2: Workers (run concurrently, render as they complete) ---------
    st.subheader("2. Worker agents — researching in parallel")
    worker_cols = st.columns(len(sub_questions))
    placeholders = [col.empty() for col in worker_cols]
    for ph, sq in zip(placeholders, sub_questions):
        ph.info(f"**Worker**\n\n{sq}\n\n_Searching..._")

    async def run_workers():
        workers = [WorkerAgent() for _ in sub_questions]
        tasks = [w.research(sq) for w, sq in zip(workers, sub_questions)]
        results = []
        for coro in asyncio.as_completed(tasks):
            result = await coro
            idx = sub_questions.index(result.sub_question)
            placeholders[idx].success(
                f"**{result.sub_question}**\n\n{result.summary}\n\n"
                f"Sources: {', '.join(s['url'] for s in result.sources)}"
            )
            results.append(result)
        # preserve original sub_question order for the synthesizer
        results.sort(key=lambda r: sub_questions.index(r.sub_question))
        return results

    worker_results = asyncio.run(run_workers())

    # --- Step 3: Synthesizer ---------------------------------------------------
    st.subheader("3. Synthesizer — merging into final report")
    with st.spinner("Writing final report..."):
        synthesizer = SynthesizerAgent()
        report = synthesizer.synthesize(query, worker_results)

    st.markdown(report)

    st.caption(f"Total pipeline time: {time.time() - t0:.2f}s "
               f"({len(sub_questions)} sub-questions, {len(sub_questions)} workers run concurrently)")

elif run_clicked:
    st.warning("Enter a research question first.")

with st.sidebar:
    st.header("How this works")
    st.markdown(
        "- **Orchestrator** splits your question into 2-4 sub-questions\n"
        "- **Worker agents** search and summarize each one, concurrently\n"
        "- **Synthesizer** merges findings into one cited report\n\n"
        "Ensure Ollama is running locally with the `llama3` model. "
        "Set `TAVILY_API_KEY` to enable live web search, otherwise the "
        "assistant runs in demo mode with mock web search data."
    )
