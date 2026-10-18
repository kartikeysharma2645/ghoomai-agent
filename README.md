# GhoomAI Agent

A separate Python agent service that connects the existing GhoomAI
travel-planning application to Fetch.ai Agentverse and ASI:One for
Fetch-A-Thon 3.0.

This repository is **independent** of the original GhoomAI Next.js
project. No files are copied or modified from that repository.

## Architecture and current status

| Component | Status |
|-----------|--------|
| FastAPI service with `GET /status` health endpoint | Implemented |
| GhoomAI HTTP client (`POST /api/agent`) | Implemented (not yet wired to routes) |
| In-memory session store | Implemented |
| Fetch.ai Agent Chat Protocol integration | Planned (placeholder only) |
| Agent registration on Agentverse | Not implemented |
| ASI:One discoverability / message handling | Not implemented |

### Current implementation

- `app/main.py` — FastAPI application exposing `GET /status`.
- `app/config.py` — Configuration loaded from environment variables via
  `python-dotenv`. Defaults `GHOOMAI_API_BASE_URL` to
  `https://ghoomai.netlify.app`.
- `app/ghoomai_client.py` — Async `httpx` client that calls the GhoomAI
  `/api/agent` endpoint with `{ session, message }`, validates the
  response, and returns updated session state.
- `app/session_store.py` — Thread-safe in-memory session store keyed by
  conversation ID. Sessions are lost when the service restarts.
- `app/agent.py` — Documented integration boundary for the Fetch.ai
  Agent Chat Protocol. Records the verified `uagents-core` imports
  (`chat_protocol_spec` = `AgentChatProtocol 0.3.0`). No agent is
  constructed or registered yet.

### Planned Fetch.ai integration

1. Construct a uAgent using a seed phrase from `AGENT_SEED_PHRASE`.
2. Include the `chat_protocol_spec` from
   `uagents_core.contrib.protocols.chat` (verified:
   `AgentChatProtocol 0.3.0`).
3. Register handlers for `ChatMessage` / `ChatAcknowledgement`.
4. Register on Agentverse (`AGENTVERSE_API_KEY`) and connect to ASI:One.
5. Wire the GhoomAI client into agent message handlers.

Note: the "Agent Chat Protocol" (uAgents/Fetch.ai) is distinct from the
unrelated "Agent Client Protocol" (agentcommunicationprotocol.dev).

## Prerequisites

- Python 3.13 (tested with 3.13.15)
- `pip`

## Windows PowerShell setup

```powershell
# Create the virtual environment (already done)
python -m venv .venv

# Activate it (current PowerShell session only)
.\.venv\Scripts\Activate.ps1

# To run Python / pip without relying on activation, use:
.\.venv\Scripts\python.exe
.\.venv\Scripts\pip.exe
```

## Dependency installation

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Running the FastAPI service

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The service will be available at `http://127.0.0.1:8000`.

## Testing the `/status` endpoint

```powershell
# In another terminal, once the server is running:
.\.venv\Scripts\python.exe -c "import httpx; print(httpx.get('http://127.0.0.1:8000/status').json())"
```

Or use a browser: `http://127.0.0.1:8000/status`

Expected response:

```json
{ "status": "ok", "service": "ghoomai-agent", "version": "0.1.0" }
```

## Running tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests mock all network calls and do not require real API keys, live
external services, or an internet connection.

## Environment variables

| Variable | Example | Required for health? |
|----------|---------|----------------------|
| `GHOOMAI_API_BASE_URL` | `https://ghoomai.netlify.app` | No |
| `GHOOMAI_API_TIMEOUT` | `30.0` | No |
| `AGENT_SEED_PHRASE` | `<seed phrase>` | No (future) |
| `AGENTVERSE_API_KEY` | `<api key>` | No (future) |

See `.env.example` for a template. Copy it to `.env` locally; `.env` is
excluded from Git by `.gitignore`.

## Current limitations

- Sessions are stored in memory only and are lost on service restart.
- No Fetch.ai agent is registered yet; `/status` is the only endpoint.
- The GhoomAI client is implemented but not yet wired to FastAPI routes.
- No agent registration, ACP message handling, or ASI:One discovery.

## Security

Never commit API keys, agent seed phrases, or other secrets. `.env` and
`.env.*` (except `.env.example`) are excluded by `.gitignore`.
