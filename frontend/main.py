"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.
"""

import os
import uuid

import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
)

try:
    from a2a.types import TransportProtocol
except ImportError:
    try:
        from a2a.client import TransportProtocol
    except ImportError:
        TransportProtocol = None

try:
    from a2a.types import TextPart
except ImportError:
    TextPart = None

try:
    from a2a.types import FilePart
except ImportError:
    FilePart = None

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

RESOURCE = os.environ["AGENT_ENGINE_RESOURCE_NAME"]
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"
_A2UI_MIME = "application/json+a2ui"

_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


_contexts: dict[str, str] = {}
_card: AgentCard | None = None


async def _get_card(client: httpx.AsyncClient) -> AgentCard:
    global _card
    if _card is None:
        resp = await client.get(A2A_CARD_URL)
        resp.raise_for_status()
        try:
            card = AgentCard(**resp.json())
        except Exception:
            from google.protobuf.json_format import ParseDict

            card = AgentCard()
            ParseDict(resp.json(), card, ignore_unknown_fields=True)

        if hasattr(card, "supported_interfaces") and getattr(card, "supported_interfaces", None):
            for interface in card.supported_interfaces:
                interface.url = A2A_BASE
        elif hasattr(card, "url"):
            try:
                card.url = A2A_BASE
            except AttributeError:
                pass
        _card = card
    return _card


def _extract_parts(parts: list) -> list[dict]:
    out: list[dict] = []
    for p in parts:
        root = getattr(p, "root", p)
        text = getattr(root, "text", None)
        if text:
            out.append({"kind": "text", "text": text})
            continue

        data = getattr(root, "data", None)
        if data is not None:
            meta = getattr(root, "metadata", None) or {}
            mime = meta.get("mimeType") if isinstance(meta, dict) else None
            if mime == _A2UI_MIME or getattr(root, "media_type", None) == _A2UI_MIME:
                out.append({"kind": "a2ui", "data": data})
            continue

        file_obj = getattr(root, "file", None)
        uri = getattr(file_obj, "uri", None) if file_obj else None
        if uri:
            out.append({"kind": "text", "text": uri})

    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        card = await _get_card(client)
        transports = (
            [TransportProtocol.jsonrpc, TransportProtocol.http_json]
            if TransportProtocol and hasattr(TransportProtocol, "jsonrpc")
            else None
        )
        config_kwargs = {"httpx_client": client}
        if transports:
            config_kwargs["supported_transports"] = transports

        factory = ClientFactory(ClientConfig(**config_kwargs))
        a2a_client = factory.create(card)

        try:
            role_val = getattr(Role, "user", Role.ROLE_USER)
        except AttributeError:
            role_val = "user"

        try:
            part_obj = Part(root=TextPart(text=message)) if TextPart else Part(text=message)
        except Exception:
            part_obj = Part(text=message)

        ctx_id = _contexts.get(user_id)
        msg = Message(
            message_id=str(uuid.uuid4()),
            role=role_val,
            parts=[part_obj],
            context_id=ctx_id,
        )

        last_task = None
        got_artifact_update = False
        async for event in a2a_client.send_message(msg):
            if not isinstance(event, tuple):
                continue
            task, update = event
            if task is not None:
                last_task = task
                if getattr(task, "context_id", None):
                    _contexts[user_id] = task.context_id
            if isinstance(update, TaskArtifactUpdateEvent):
                got_artifact_update = True
                parts.extend(_extract_parts(update.artifact.parts))

        if not got_artifact_update and last_task is not None:
            for artifact in getattr(last_task, "artifacts", None) or []:
                parts.extend(_extract_parts(artifact.parts))

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
