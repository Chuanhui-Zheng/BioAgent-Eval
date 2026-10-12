# React frontend and RAG API

Run both processes from the same checkout. Python 3.10+ and Node.js 20+ are required. Prepare the chunks and BM25 index using the root README first.

From the repository root:

```sh
python -m pip install -r requirements-api.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite forwards `/api` requests to the local Python server. The assistant uses retrieved evidence offline by default; entering an AIHubMix key enables hosted generation. Hosted failures fall back to offline evidence and include a limitation message. Keys must not be committed. Some charts and MoA workflows still contain prototype data; live API connectivity does not imply every panel is backed by real data.

`npm run build` checks TypeScript and builds the frontend. Production serving requires routing `/api` to the Python server separately.
