# AIHubMix API Key Instructions

## Use a key in the browser demo

1. Complete setup with `python setup_demo.py`.
2. Start the app with `python run_demo.py`.
3. Open the local address printed in the terminal (normally
   <http://localhost:8501>).
4. Select **AIHubMix** under **Generator**.
5. Paste the API key into **AIHubMix API Key** and click
   **Generate answer**.

The browser field is a password input. The key is kept only for the current
local app session and is not written to `.env`, logs, or GitHub. Enter it again
after refreshing or restarting the app.

## Use a key from the command line

Copy the example configuration:

macOS or Linux:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set only your own key:

```env
AIHUBMIX_API_KEY=replace-with-your-key
AIHUBMIX_BASE_URL=https://aihubmix.com/v1
AIHUBMIX_MODEL=nemotron-3-ultra-550b-a55b-free
```

Then run:

```bash
python scripts/query_rag.py "What is the function of TCF7L2?" --provider aihubmix
```

To replace the key later, edit `AIHUBMIX_API_KEY` in `.env`. The `.env` file is
ignored by Git and must never be committed.

## Troubleshooting and security

- A valid key still requires available account/model quota.
- If the free-trial quota is exhausted, use an account with available quota or
  top up the current account.
- Never paste a key into documentation, source code, screenshots, chat, or a
  Git commit.
- Revoke and replace a key immediately if it is exposed.
- Offline mode remains available when no external API should be used.
