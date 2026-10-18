# GhoomAI Agent

A separate Python agent service that connects the existing GhoomAI
travel-planning application to Fetch.ai Agentverse and ASI:One for
Fetch-A-Thon 3.0.

This repository is **independent** of the original GhoomAI Next.js
project. No files are copied or modified from that repository.

## Architecture and current status

| Component | Status |
|-----------|--------|
| FastAPI service with `GET /status` health endpoint | Implemented and tested |
| GhoomAI HTTP client (`POST /api/agent`) | Implemented and tested (not yet wired to FastAPI routes) |
| In-memory session store | Implemented and tested |
| Fetch.ai Agent Chat Protocol integration | Implemented and tested (agent not yet registered) |
| Agent registration on Agentverse | Not implemented |
| ASI:One discoverability / message handling | Not implemented |

### Current implementation

- `app/main.py` — FastAPI application exposing `GET /status`.
- `app/config.py` — Configuration loaded from environment variables via
  `python-dotenv`. Defaults `GHOOMAI_API_BASE_URL` to
  `https://ghoomai.netlify.app`. Includes agent port, network, and
  credential validation.
- `app/ghoomai_client.py` — Async `httpx` client that calls the GhoomAI
  `/api/agent` endpoint with `{ session, message }`, validates the
  response, and returns updated session state.
- `app/session_store.py` — Thread-safe in-memory session store keyed by
  conversation ID. Sessions are lost when the service restarts.
- `app/chat_protocol.py` — Fetch.ai Agent Chat Protocol (ACP)
  integration. Defines `ChatHandler` (receives `ChatMessage`, extracts
  text, maps `ctx.session` to a GhoomAI conversation, calls
  `GhoomAIClient`, persists the returned session, sends a
  `ChatAcknowledgement` to acknowledge the incoming message, and sends
  the actual GhoomAI response as a separate `ChatMessage` with
  `TextContent`) and builds a `uagents` `Protocol` from the verified
  `chat_protocol_spec` (AgentChatProtocol 0.3.0). The acknowledgement
  is never confused with the response content.
- `app/agent.py` — Constructs a `uagents` `Agent` with a deterministic
  identity from `AGENT_SEED_PHRASE`, includes the chat protocol, and
  requires `AGENT_SEED_PHRASE` at construction time.

### Mailbox-enabled Fetch.ai agent

The `uagents` Agent runs in mailbox mode (`mailbox=True`) and connects to
Agentverse via a secure mailbox channel. This avoids the need for a
publicly reachable HTTP endpoint. The agent must remain running locally to
process live messages.

1. Set `AGENT_SEED_PHRASE` in `.env` and call `create_agent()` to obtain
   the `Agent` instance.
2. Run `agent.run()` (or `run_agent.py`) to start the agent runtime.
   The agent connects outbound to Agentverse's mailbox service.
3. Register on Agentverse (`AGENTVERSE_API_KEY`) and connect to ASI:One
   when ready for production. Registration is a separate workflow from
   running the mailbox-enabled agent locally.

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

## Running the FastAPI service (health endpoint only)

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The service will be available at `http://127.0.0.1:8000`.

## Running the Fetch.ai agent (requires `AGENT_SEED_PHRASE`)

The `uagents` Agent runs in **mailbox mode** (`mailbox=True`) and connects to
Agentverse via a secure mailbox channel. It is **not** part of the FastAPI
app and runs on its own port. No publicly reachable HTTP endpoint is needed.

Set `AGENT_SEED_PHRASE` in `.env`, then run the dedicated entry point:

```powershell
# Example: create and run the mailbox-enabled agent (requires AGENT_SEED_PHRASE)
.\.venv\Scripts\python.exe run_agent.py
```

The agent runs on port `AGENT_PORT` (default `8001`) and connects outbound
to Agentverse's mailbox service at `https://Agentverse.ai`.

When the agent receives a `ChatMessage` from another agent or ASI:One:
1. It extracts the user text and identifies the conversation from the
   envelope session UUID (`ctx.session`).
2. It calls the GhoomAI backend at `POST /api/agent` with the message
   and current session state.
3. It persists the updated session returned by GhoomAI.
4. It sends a `ChatAcknowledgement` to acknowledge the incoming message.
5. It sends the actual GhoomAI response as a separate `ChatMessage`
   containing `TextContent` back to the originating agent.

Do not register, deploy, or claim ASI:One discoverability in this phase.

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

| Variable | Example | Required for health? | Required for agent? |
|----------|---------|----------------------|---------------------|
| `GHOOMAI_API_BASE_URL` | `https://ghoomai.netlify.app` | No | No |
| `GHOOMAI_API_TIMEOUT` | `30.0` | No | No |
| `AGENT_SEED_PHRASE` | `<seed phrase>` | No | **Yes** |
| `AGENT_PORT` | `8001` | No | No (default 8001) |
| `AGENT_NETWORK` | `mainnet` | No | No (default mainnet) |
| `AGENT_MAILBOX` | `true` | No | No (default true; enables mailbox mode) |
| `AGENTVERSE_API_KEY` | `<api key>` | No | No (future) |

See `.env.example` for a template. Copy it to `.env` locally; `.env` is
excluded from Git by `.gitignore`.

## Current limitations

- Sessions are stored in memory only and are lost on service restart.
- No Fetch.ai agent is registered on Agentverse.
- The agent runs in mailbox mode but is not yet registered on Agentverse.
- The agent runtime is not started by default; `create_agent()` requires
  `AGENT_SEED_PHRASE`.
- The GhoomAI client is implemented but not yet wired to FastAPI routes.
- No agent registration, production deployment, or ASI:One discovery.

## Security

Never commit API keys, agent seed phrases, or other secrets. `.env` and
`.env.*` (except `.env.example`) are excluded by `.gitignore`.
