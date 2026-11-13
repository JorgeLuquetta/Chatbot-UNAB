"""LLM simulado compatible con OpenAI Chat Completions (solo para la prueba e2e local)."""
import json, unicodedata
from http.server import BaseHTTPRequestHandler, HTTPServer

def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]; system = msgs[0]["content"]; user = norm(msgs[-1]["content"])
        if system.startswith("Clasifica"):
            if "fecha" in user or "parcial" in user or "calendario" in user: out = "calendario"
            elif "mis cursos" in user or "avance" in user or "aprob" in user: out = "Cursos-Realizados."
            elif "noticia" in user: out = "noticias"
            elif "casino" in user: out = "consulta-general"
            else: out = "no estoy seguro"
        elif "casino" in user:
            out = "Te recomiendo un casino excelente."
        else:
            out = "RESPUESTA SIMULADA | historial=%d | contexto: %s" % (len(msgs) - 2, system.split("\n\n", 1)[-1][:300])
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"choices": [{"index": 0, "message": {"role": "assistant", "content": out}}]}).encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    # Uso: python scripts/mock_llm.py  y en .env: LLM_API_URL=http://host.docker.internal:8099/v1/chat/completions
    HTTPServer(("0.0.0.0", 8099), H).serve_forever()
