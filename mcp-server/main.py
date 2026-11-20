"""Punto de entrada del servidor FastMCP (puerto interno 8000)."""
import inspect
import json
import logging

import uvicorn

from app import server as server_mod
from app.config import settings
from app.server import mcp

log = logging.getLogger("mcp-args")

# Hosts con los que n8n (u otros contenedores) llaman al servicio dentro de la red Docker.
ALLOWED_HOSTS = ["mcp-server", "mcp-server:8000", "localhost", "localhost:8000", "127.0.0.1", "127.0.0.1:8000"]


def _tool_params() -> dict[str, set[str]]:
    """Nombres de parámetros de cada herramienta MCP (según la firma de la función)."""
    out: dict[str, set[str]] = {}
    for name in ("search_documents", "get_student_courses", "ingest_documents", "run_news_scraper",
                 "get_academic_plan", "get_academic_calendar", "get_news", "get_ccd_progress"):
        obj = getattr(server_mod, name, None)
        fn = getattr(obj, "fn", obj)
        if callable(fn):
            out[name] = set(inspect.signature(fn).parameters)
    return out


TOOL_PARAMS = _tool_params()


def _clean(msg: dict) -> bool:
    params = msg.get("params") if isinstance(msg, dict) else None
    if not (isinstance(params, dict) and msg.get("method") == "tools/call"):
        return False
    allowed = TOOL_PARAMS.get(params.get("name"))
    args = params.get("arguments")
    if allowed is None or not isinstance(args, dict):
        return False
    extra = set(args) - allowed
    if extra:
        # El nodo "MCP Client Tool" de n8n agrega toolCallId y los campos del ítem de entrada
        log.info("tools/call %s: se ignoran argumentos extra %s", params.get("name"), sorted(extra))
        params["arguments"] = {k: v for k, v in args.items() if k in allowed}
    return bool(extra)


WRITE_TOOLS = {"ingest_documents", "run_news_scraper"}


def _is_write_call(msg) -> bool:
    return (isinstance(msg, dict) and msg.get("method") == "tools/call"
            and isinstance(msg.get("params"), dict) and msg["params"].get("name") in WRITE_TOOLS)


def strip_unknown_args(asgi_app):
    """Middleware ASGI: elimina de tools/call los argumentos que la herramienta no declara."""
    async def wrapped(scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or not scope["path"].startswith("/mcp"):
            return await asgi_app(scope, receive, send)
        body, more = b"", True
        while more:
            m = await receive()
            body += m.get("body", b"")
            more = m.get("more_body", False)
        external = any(k == b"x-mcp-external" for k, _ in scope["headers"])
        try:
            data = json.loads(body or b"null")
            msgs = data if isinstance(data, list) else [data]
            # Clientes externos (mcp.traumado.top: Claude, OpenAI...) solo pueden usar herramientas de lectura
            blocked = [m for m in msgs if external and _is_write_call(m)]
            if blocked:
                err = {"jsonrpc": "2.0", "id": blocked[0].get("id"),
                       "error": {"code": -32601, "message": "Herramienta no disponible para clientes externos (solo lectura)"}}
                payload = json.dumps(err).encode()
                await send({"type": "http.response.start", "status": 200,
                            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]})
                await send({"type": "http.response.body", "body": payload})
                return
            if any([_clean(m) for m in msgs]):
                body = json.dumps(data).encode()
        except ValueError:
            pass
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        headers = [(k, v) for k, v in scope["headers"] if k != b"content-length"]
        headers.append((b"content-length", str(len(body)).encode()))
        return await asgi_app({**scope, "headers": headers}, replay, send)
    return wrapped


app = strip_unknown_args(mcp.http_app(path="/mcp", allowed_hosts=ALLOWED_HOSTS))
# El ciclo de vida (lifespan) lo maneja la app interna; uvicorn lo propaga por el wrapper.

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
