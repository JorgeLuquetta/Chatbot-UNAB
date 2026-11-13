"""Punto de entrada del servidor FastMCP (puerto interno 8000)."""
import uvicorn

from app.config import settings
from app.server import mcp

# Hosts con los que n8n (u otros contenedores) llaman al servicio dentro de la red Docker.
ALLOWED_HOSTS = ["mcp-server", "mcp-server:8000", "localhost", "localhost:8000", "127.0.0.1", "127.0.0.1:8000"]

app = mcp.http_app(path="/mcp", allowed_hosts=ALLOWED_HOSTS)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
