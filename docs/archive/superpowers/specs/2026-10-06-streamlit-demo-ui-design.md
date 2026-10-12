# Streamlit MVP Demo UI Design

## Goal

Add the smallest practical user interface for demonstrating the existing RAG MVP to a customer. The UI must let a presenter ask a scientific question, run either the deterministic offline generator or the configured AIHubMix model, and clearly show the grounded answer, citations, validation result, and latency. It must also summarize current progress and planned work without changing the existing retrieval or generation behavior.

## Chosen approach

Use a single Streamlit application at the repository root. Streamlit is preferred over a custom frontend plus API because this is a local demonstration, not a production web service. It provides forms, loading states, tabs, and readable result panels with very little new code.

The alternatives considered were Gradio and a custom FastAPI/HTML application. Gradio is similarly quick but offers less convenient report-style content. FastAPI plus HTML would provide more control but introduces unnecessary routing, templates, and frontend maintenance for this demo.

## User interface

The page will have three tabs:

1. **Ask the Assistant**
   - A question text area prefilled with a safe example such as `What is the function of TCF7L2?`.
   - A provider selector with `Offline` as the default and `AIHubMix` as the optional live model.
   - A single `Generate answer` button.
   - Results showing status, answer, citations, limitations when present, validation result, provider, fallback information, and latency.
2. **Current Progress**
   - A concise customer-facing summary of the completed retrieval, augmentation, grounded generation, citation, validation, and evaluation work.
   - The current verified project figures: 41,103 chunks, 55 automated tests, BM25 TargetHit@10 of 96.67%, and a completed AIHubMix smoke test.
3. **Next Steps**
   - Blind held-out evaluation, stricter scientific quality checks, reproducible Dense/Hybrid evaluation, wider question-type coverage, and later delivery work such as FastAPI, Docker, and CI.

The page will use Streamlit's built-in components and modest CSS only if needed for readability. It will not add branding assets, accounts, persistence, chat history, analytics, or a production deployment layer.

## Architecture and data flow

The application will import and reuse the existing BM25 retriever, prompt builder, generators, validators, and `RAGPipeline` rather than reproduce RAG logic in the UI.

On startup, Streamlit will load the existing BM25 index once using its resource cache. When the user submits a question:

1. Validate that the question is not blank.
2. Build the selected generator.
3. Run the existing `RAGPipeline` with the question.
4. Render the returned answer and metadata.

The offline provider uses `OfflineEvidenceGenerator`. The AIHubMix provider reads `AIHUBMIX_API_KEY`, base URL, and model from the existing environment configuration, then uses `AIHubMixGenerator` with the existing offline fallback. The interface must never display, log, or save the API key.

## Error handling

- A blank question produces an inline warning and does not run the pipeline.
- Selecting AIHubMix without an API key produces a clear setup message.
- Retrieval or generation failures are shown as a readable error without a raw stack trace in the page.
- If the existing AIHubMix fallback is used, the UI identifies the effective provider and fallback reason returned by the pipeline.
- Missing local index artifacts produce a message pointing the user to the existing index-building instructions.

## Files and dependencies

- `app.py`: the complete demo interface.
- `requirements-ui.txt`: only the additional Streamlit dependency, while retaining the project's existing requirement files as the source of core and LLM dependencies.
- `README.md`: short installation and launch instructions.
- A small UI-focused test file for deterministic configuration and rendering behavior that is practical to test without making a paid network request.

The launch command will be:

```bash
streamlit run app.py
```

## Acceptance criteria

- The app launches from the repository root with the documented command.
- An offline TCF7L2 query produces a natural-language answer with at least one citation and visible validation/latency metadata.
- AIHubMix mode either returns a live answer or clearly reports missing configuration; it does not expose the key.
- Empty, normal, long-answer, loading, error, and constrained-width states remain understandable.
- Existing automated tests continue to pass and the new UI test passes.
- The README commands are reproducible in the project virtual environment.

## Explicitly deferred

Production authentication, persistent user sessions, a database, conversational memory, streaming tokens, public hosting, Docker packaging, FastAPI endpoints, CI deployment, and visual redesign are outside this demonstration scope. They should be added only when the project moves from customer demonstration to an agreed delivery environment.
