from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from augmentation.builder import ContextBuilder
from generation.llm_provider import PROVIDER_PRESETS, build_llm_generator
from generation.offline import OfflineEvidenceGenerator
from rag.pipeline import RAGPipeline
from retrieval.bm25_retriever import load_bm25_index
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.router import SUPPORTED_COLLECTIONS as ALL_COLLECTIONS
from retrieval.service import RetrievalRequest, RetrieverService


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)


@st.cache_resource(show_spinner=False)
def load_retriever() -> RetrieverService:
    config = load_retrieval_config(PROJECT_ROOT)
    corpus = load_corpus_from_config(config)
    backend = load_bm25_index(config.index_dir, corpus.records, expected_chunk_hashes=corpus.chunk_hashes)
    return RetrieverService(backend, "bm25")


def generator_for(provider: str, api_key: str, llm_provider: str | None = None,
                  model: str | None = None, base_url: str | None = None):
    if provider == "Offline":
        return OfflineEvidenceGenerator()
    preset = PROVIDER_PRESETS.get(llm_provider or os.environ.get("LLM_PROVIDER", "openai"))
    if preset is not None and preset.requires_key and not api_key.strip():
        raise ValueError("Please enter an API key for the selected LLM provider.")
    return build_llm_generator(provider=llm_provider, api_key=api_key.strip(), model=model or None,
                               base_url=base_url or None)


def build_pipeline(provider: str, api_key: str = "", **llm_settings) -> RAGPipeline:
    return RAGPipeline(
        load_retriever(),
        ContextBuilder(),
        generator_for(provider, api_key, **llm_settings),
    )


def show_result(run) -> None:
    answer = run.answer
    if answer.status == "refuse":
        st.warning(answer.answer)
    elif answer.status == "error":
        st.error(answer.answer)
    else:
        st.success(answer.answer)

    model = answer.diagnostics.get("model")
    columns = st.columns(4 if model else 3)
    left, middle, right = columns[:3]
    left.metric("Status", answer.status)
    middle.metric("Provider", answer.provider)
    right.metric("Latency", f"{run.latency_s['total']:.2f}s")
    if model:
        columns[3].metric("Model", model)

    st.subheader("Citations")
    if not answer.citations:
        st.caption("No citation returned.")
    for citation in answer.citations:
        chunk_id = citation.get("chunk_id", "unknown")
        source = citation.get("source_name") or "Source"
        url = citation.get("source_url")
        label = f"[{source}]({url})" if url else source
        st.markdown(f"- `{chunk_id}` — {label}")

    if answer.limitations:
        with st.expander("Limitations"):
            for limitation in answer.limitations:
                st.write(f"- {limitation}")

    with st.expander("Run details"):
        st.write(f"Validation: {'PASS' if run.validation.valid else 'FAIL'}")
        st.write(f"Retrieved chunks: {len(run.retrieval.results)}")
        st.write(f"Collections: {', '.join(run.retrieval.effective_collections)}")
        st.json(run.latency_s)


load_environment()
st.set_page_config(page_title="Scientific RAG Demo", page_icon="🧬", layout="wide")
st.title("🧬 Evidence-Grounded Scientific RAG")
st.caption("Local MVP demo · answers are limited to the approved project corpus")

ask_tab, progress_tab, next_tab = st.tabs(["Ask", "Current Progress", "Next Steps"])

with ask_tab:
    provider = st.radio("Generator", ["Offline", "Hosted LLM"], horizontal=True)
    api_key = ""
    llm_settings = {}
    if provider == "Hosted LLM":
        names = list(PROVIDER_PRESETS)
        default = os.environ.get("LLM_PROVIDER", "openai")
        llm_provider = st.selectbox("LLM provider", names, index=names.index(default) if default in names else 0,
                                    format_func=lambda n: PROVIDER_PRESETS[n].label or n)
        preset = PROVIDER_PRESETS[llm_provider]
        llm_settings = {
            "llm_provider": llm_provider,
            "model": st.text_input("Model", value=preset.default_model),
            "base_url": st.text_input("Base URL (OpenAI-compatible)", value=preset.base_url or ""),
        }
        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-...",
            help="Kept only in this local app session and never written to disk.",
        )
        st.caption("The key is used only for this request and is not saved to .env or GitHub.")
    question = st.text_area(
        "Question",
        value="What is the function of TCF7L2?",
        height=100,
    )
    if st.button("Generate answer", type="primary"):
        if not question.strip():
            st.warning("Please enter a question.")
        elif provider == "Hosted LLM" and PROVIDER_PRESETS[llm_settings["llm_provider"]].requires_key and not api_key.strip():
            st.warning("Please enter an API key for the selected LLM provider.")
        else:
            try:
                with st.spinner("Retrieving evidence and generating the answer..."):
                    run = build_pipeline(provider, api_key, **llm_settings).run(
                        RetrievalRequest(
                            question.strip(),
                            authorized_collections=tuple(ALL_COLLECTIONS),
                            top_k=10,
                        )
                    )
                if provider == "Hosted LLM" and not run.answer.diagnostics.get("fallback_from"):
                    st.success(f"{llm_settings['llm_provider']} connected successfully and generated this answer.")
                show_result(run)
            except Exception as exc:
                prefix = "Hosted LLM connection failed" if provider == "Hosted LLM" else "Unable to run the demo"
                st.error(f"{prefix}: {exc}")

with progress_tab:
    st.subheader("Current MVP progress")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Corpus chunks", "41,103")
    c2.metric("Automated tests", "60")
    c3.metric("BM25 TargetHit@10", "96.67%")
    c4.metric("Live LLM smoke test", "Passed")
    st.markdown(
        """
        - BM25 retrieval and query routing are implemented.
        - Retrieved evidence is assembled into a controlled context package.
        - Offline and any OpenAI-compatible hosted LLM (OpenAI, AIHubMix, DeepSeek, OpenRouter, Anthropic, Ollama, custom) are available.
        - Claim-level citations, refusal, fallback, validation and latency reporting are implemented.

        **Important:** citation structure has been validated, but this is not yet a claim of
        perfect scientific or semantic answer accuracy.
        """
    )

with next_tab:
    st.subheader("Before production delivery")
    st.markdown(
        """
        1. Create a blind held-out test set and review answers with domain experts.
        2. Add stricter factual-faithfulness and citation-quality evaluation.
        3. Reproduce Dense and Hybrid retrieval results and compare them with BM25.
        4. Expand question types, refusal cases and failure testing.
        5. Add production packaging only when the deployment target is agreed (API, Docker and CI).
        """
    )
