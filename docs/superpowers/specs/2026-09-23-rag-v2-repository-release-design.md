# CS46 Scientific RAG v2 Repository Release Design

## Objective

Create a new private University of Sydney GitHub repository named
`CS46-Scientific-RAG-Assistant-v2`. Preserve the complete commit history of the
existing project, add the locally completed offline RAG phases, and make the
result reproducible for team members without requiring an external LLM API or
the large dense-retrieval dependencies.

## Repository Strategy

The existing repository `main` branch at commit `5c04755` is the history base.
A release branch will receive the reviewed local additions before it is pushed
to the new private repository. This preserves the original contributors and
development history while keeping the current upstream repository unchanged.

The new repository will contain:

- approved-corpus ingestion and chunking;
- BM25, dense, and hybrid retrieval implementations;
- the authorization-aware retrieval service and diagnostics;
- context augmentation and evidence-status policy;
- the deterministic offline generation provider;
- claim-linked citations and structural validation;
- the end-to-end RAG pipeline and evaluation harness;
- automated tests, stage reports, and reproducibility documentation.

## Tracked and Excluded Content

Tracked content includes source code, configuration, tests, small evaluation
datasets, reproducible evaluation summaries, phase reports, the root README,
and team-facing documentation.

The repository must exclude virtual environments, environment-variable files,
API keys, Python caches, generated package metadata, downloaded model weights,
and locally generated BM25 or dense indexes. Large indexes are rebuilt from the
documented commands rather than committed.

## Dependency Design

Dependencies are separated by purpose:

- `requirements.txt` installs the offline BM25 RAG runtime;
- `requirements-dev.txt` installs automated test and quality tooling;
- `requirements-embed.txt` installs optional Torch, Sentence Transformers,
  Hugging Face, and FAISS dependencies for dense and hybrid retrieval.

All direct dependencies are pinned to tested versions. The root README will
also document the supported Python version and clean-environment setup.

## Documentation Design

The root `README.md` will provide the shortest reproducible path for setup,
BM25 index construction, offline demonstration, testing, and evaluation.

`docs/TEAM_UPDATE_GUIDE.md` will describe what changed relative to the source
repository, where each addition is located, how team members can reproduce the
work, current metrics and their limitations, repository hygiene rules, and a
suggested division of remaining work. Its complete content will also be
delivered in the project chat.

`docs/PROJECT_STATUS_AND_ROADMAP.md` will separate completed baseline work from
remaining scientific validation, retrieval optimisation, LLM integration, API,
demo-interface, containerisation, and final-report tasks.

## Dense and Hybrid Policy

Dense and hybrid retrieval remain supported but optional for the first v2
release. Their historical benchmark artifacts are retained with an explicit
statement that they have not yet been fully reproduced on the current machine.
The release is not blocked by the estimated long local embedding run.

Before final project delivery, the team should build the dense index once in a
controlled environment, rerun dense and hybrid evaluation against the frozen
test set, record hardware and model revision, and compare the results with BM25.

## Validation and Release Gates

Before pushing the release:

1. Install the runtime and development dependencies in a clean virtual
   environment.
2. Run the complete automated test suite.
3. Rebuild the BM25 index from the approved corpus.
4. Reproduce the BM25 benchmark.
5. Run the offline end-to-end RAG evaluation.
6. Confirm that no secret, `.env`, model weight, virtual environment, cache, or
   generated index is tracked.
7. Review the staged diff and repository size.
8. Commit the release and push it to the new private repository.

Dense and hybrid evaluation are documented follow-up gates rather than initial
release blockers.

## Known Quality Boundary

The offline generator is an extractive, deterministic safety baseline. Current
citation scores validate citation structure against supplied context; they do
not prove semantic entailment or scientific correctness. The roadmap therefore
prioritises gold-evidence citation scoring, required-field checks, numerical
fidelity, question-type relevance, blind evaluation questions, and human
scientific review before adopting any hosted LLM result as a final-quality
answer.

## Success Criteria

The release is successful when a team member can clone the new private
repository, install only the base and development dependencies, build BM25,
run the offline demonstration, pass the complete automated test suite, and
reproduce the documented offline evaluation without an external API key.
