# Runtime data release

Use source code that includes the content-based database fingerprint fix with
`CS46-runtime-data-v1.2.0.zip`. The earlier commit 01c5ad9 does not include this fix.
Extract the ZIP in the source root, allowing it to replace the older artifact
manifests and baseline chunks. Keep `data/raw/` from the repository: source
content is verified before the prebuilt database is reused.

Install the backend dependencies in a fresh Python environment with
`python -m pip install -r requirements/api.txt` and run
`python -m uvicorn server:app --host 127.0.0.1 --port 8000`.
Run the retained API with `python -m uvicorn server:app --host 127.0.0.1 --port 8000`, or use the offline Agent Harness CLI documented in the root README. No Node or web frontend is required.
The default offline BM25 application does not require an API key or Dense model.

The archive contains the active eight-collection chunks, matching manifests,
BM25 index, SQLite database and client example. It excludes Dense indexes,
installed dependencies, credentials and query logs. `runtime-package.json`
records the SHA-256 of every included data file; the adjacent `.zip.sha256`
verifies the ZIP itself. On macOS use `shasum -a 256 -c <archive>.sha256`.

To prepare a release from a project with current data, chunks and indexes:

```sh
python scripts/package_runtime.py --output /path/to/CS46-runtime-data-v1.2.0.zip
```

The packager validates corpus/index consistency, prepares a content-fingerprinted
database, checks SQLite integrity and takes a consistent SQLite backup. Legacy
timestamp fingerprints trigger one rebuild during preparation, not on recipients'
first launch. Changes to raw file content or the raw file list invalidate the cache.

Publish code and runtime data together after a clean-directory smoke test.
Do not mix the old seven-collection Release with this eight-collection runtime.
