# Streamlit MVP Demo UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a locally runnable Streamlit interface for the existing evidence-grounded RAG MVP, plus concise customer-facing progress and next-step views.

**Architecture:** A single root-level `app.py` renders three Streamlit tabs and directly reuses the existing retrieval, augmentation, generation, fallback, validation, and pipeline classes. Streamlit caches the loaded BM25 resources; `.env` remains the only location for AIHubMix credentials. No separate API server, database, or frontend build is introduced.

**Tech Stack:** Python 3.10+, Streamlit, existing project RAG modules, pytest, Streamlit AppTest.

**Spec:** `docs/superpowers/specs/2026-10-06-streamlit-demo-ui-design.md`

## Global Constraints

- Keep the offline provider as the default and require no external API for the main demo.
- Never display, log, persist, or commit `AIHUBMIX_API_KEY`.
- Reuse existing RAG components; do not duplicate retrieval or generation logic.
- Add only Streamlit as a UI dependency.
- Defer authentication, persistence, chat history, public hosting, Docker, FastAPI, CI deployment, streaming, and visual redesign.

## Review Focus

- Blank or whitespace-only question must show a warning without invoking the pipeline; Task 1 AppTest covers it.
- Missing AIHubMix key must show setup guidance without exposing environment values; Task 1 AppTest covers it.
- Missing BM25 index or runtime failure must become a readable page error rather than a rendered traceback; Task 1 AppTest covers the failure renderer.
- Long answers and citations must remain readable at desktop and constrained width; Task 2 browser checks cover both viewports.
- Existing CLI and RAG behavior must not regress; Task 2 runs the complete existing test suite and CLI smoke test.

---

### Task 1: Build the tested Streamlit demo

**Files:**
- Create: `app.py`
- Create: `requirements-ui.txt`
- Create: `tests/test_app.py`

**Interfaces:**
- Consumes: `load_retrieval_config(Path)`, `load_corpus_from_config(config)`, `load_bm25_index(index_dir, records)`, `RetrieverService`, `ContextBuilder`, `OfflineEvidenceGenerator`, `AIHubMixGenerator`, `FallbackGenerator`, `RAGPipeline.run(RetrievalRequest)`.
- Produces: `build_pipeline(provider: str) -> RAGPipeline`, `run_question(question: str, provider: str) -> RAGRun`, and the Streamlit page launched by `streamlit run app.py`.

- [ ] **Step 1: Add the UI dependency**

Create `requirements-ui.txt` containing the pinned Streamlit dependency and install it into `.venv` together with existing core and LLM requirements.

- [ ] **Step 2: Write failing Streamlit AppTests**

Create tests that assert the three tab labels and default example are present, blank submission produces a warning, missing-key AIHubMix submission produces safe setup guidance, and a patched offline run renders answer/citation/validation/provider/latency values.

- [ ] **Step 3: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_app.py -q`

Expected: FAIL because `app.py` does not exist or the required UI elements are absent.

- [ ] **Step 4: Implement the minimal page**

Create `app.py` with cached BM25 pipeline construction, provider selection, input validation, spinner/error handling, result rendering, progress metrics, and the next-step list. Load `.env` without overriding shell variables and never render the key.

- [ ] **Step 5: Run tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_app.py -q`

Expected: all UI tests PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add app.py requirements-ui.txt tests/test_app.py
git commit -m "Add Streamlit MVP demo interface"
```

### Task 2: Document and verify the runnable demo

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1 launch command and provider behavior.
- Produces: reproducible UI installation, offline launch, and optional AIHubMix instructions for presenters.

- [ ] **Step 1: Write the documentation expectation test**

Extend `tests/test_app.py` to assert the README contains `requirements-ui.txt`, `streamlit run app.py`, offline-first guidance, and `.env` key-safety guidance.

- [ ] **Step 2: Run the documentation test to verify RED**

Run: `.venv/bin/python -m pytest tests/test_app.py -q`

Expected: FAIL because the README does not yet contain the UI commands.

- [ ] **Step 3: Add concise README instructions**

Document dependency installation, launch command, offline demo flow, optional AIHubMix selection, key replacement, and the intentionally non-production scope.

- [ ] **Step 4: Run automated verification**

Run: `.venv/bin/python -m pytest -q`

Expected: 55 existing tests plus all new UI/documentation tests PASS.

- [ ] **Step 5: Run the real workflow and browser acceptance checks**

Launch `.venv/bin/streamlit run app.py --server.headless true`, open the served page, and verify initial, blank, normal offline answer, missing-key/error, long content, loading, desktop, and constrained-width states. Also rerun the existing offline CLI smoke query.

Expected: the offline query produces a cited, validated natural-language answer in both UI and CLI; all applicable states remain understandable; no secret is visible.

- [ ] **Step 6: Commit Task 2**

```bash
git add README.md tests/test_app.py
git commit -m "Document and verify Streamlit demo"
```
