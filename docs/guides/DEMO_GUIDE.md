# Scientific RAG Customer Demo Guide

## What this demonstration does

The application retrieves passages from an approved scientific corpus, builds a controlled evidence package, and generates an answer with source citations. The default offline generator is deterministic and requires no external service. AIHubMix is optional and automatically falls back to offline generation if its response is unavailable or invalid.

The current implementation and reported evaluation results use the previous data release. They have not yet been adjusted for the documents added this month.

## Requirements

- Windows 10/11 or a recent macOS version
- Python 3.10 or newer from <https://www.python.org/downloads/>
- Internet access during the first setup so Python packages can be downloaded
- About 1 GB of free disk space

Docker is not required.

## Install automatically

Download or clone the repository, open Terminal (macOS) or PowerShell (Windows), and change into the downloaded folder.

Run the same command on either operating system:

```text
python setup_demo.py
```

On Windows, use `py setup_demo.py` if the `python` command is unavailable. The script creates an isolated `.venv`, installs the required packages, and builds the local BM25 search index. Initial setup may take several minutes.

## Start the demonstration

```text
python run_demo.py
```

On Windows, `py run_demo.py` also works. A browser should open automatically. If it does not, open <http://localhost:8501>.

Leave the terminal window open while presenting. Press `Ctrl+C` in that terminal to stop the application.

## Recommended questions

- `What is the function of TCF7L2?`
- `What gene function of INS explains its effect on blood glucose concentration?`
- `For ADCY5 and 2-hour glucose, what common-variant evidence is available?`
- `Is LPCAT2 significantly associated with 2-hour glucose in the rare-variant gene-based test?`
- `What p-value is reported for the LDSC correlation between 2hrI and 2hrG?`
- `For ADCY5, what is its gene function and what common-variant evidence is reported for 2-hour glucose?`
- `What is the LDSC genetic correlation between 2-hour insulin and TCF7L2?` (expected refusal/qualification)

## Optional AIHubMix mode

Offline mode is recommended for a reliable demonstration. To try AIHubMix in
the browser, select **AIHubMix**, paste the key into the password field, and
click **Generate answer**. The key stays only in the current local app session;
it is not written to `.env` or GitHub. See [`API_KEY_GUIDE.md`](API_KEY_GUIDE.md)
for browser and command-line instructions.

AIHubMix is an external service. Availability, free-model behaviour, latency,
and quotas are outside this project's control. The UI reports API, format, and
quota errors directly. A valid key cannot generate an online answer after its
account quota is exhausted.

## How the pipeline works

1. The query router selects relevant approved collections.
2. BM25 retrieves the most relevant chunks.
3. The context builder packages evidence and a citation registry.
4. The selected generator creates the answer using only that evidence.
5. The validator checks claim-linked citations; invalid hosted output falls back to the offline generator.

## Current status and limitations

- 41,103 indexed chunks
- 60 automated tests passing
- BM25 TargetHit@10: 96.67% on the current evaluation set
- Offline and optional AIHubMix generation
- Claim-linked citations, refusal handling, validation, fallback, and latency reporting

These figures measure the current corpus and test set. They do not prove perfect scientific correctness. Production delivery still requires evaluation against the new monthly documents, a blind held-out question set, and domain-expert scoring of correctness, evidence support, citation relevance, completeness, clarity, and refusal quality.

## Troubleshooting

- **`python` not found:** install Python 3.10+ and select the installer option that adds Python to PATH. On Windows, try `py` instead.
- **Page does not open:** keep `run_demo.py` running and visit <http://localhost:8501>.
- **Index or dependency error:** rerun `python setup_demo.py --rebuild`.
- **AIHubMix fails:** check the key, model access, account quota, and network. Use Offline mode if the external service is unavailable.
- **Port 8501 is already in use:** close the older Streamlit terminal, then run `python run_demo.py` again.
