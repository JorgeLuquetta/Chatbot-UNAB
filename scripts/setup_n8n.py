#!/usr/bin/env python3
"""Configura n8n: crea las credenciales (cifradas por n8n) e importa los workflows.

Uso (en el EC2, desde la carpeta del proyecto, con los contenedores arriba):
    python3 scripts/setup_n8n.py            # credenciales + workflows
    python3 scripts/setup_n8n.py --activate # además activa todos los workflows y reinicia n8n

Lee los valores de .env. Las credenciales quedan cifradas con N8N_ENCRYPTION_KEY
dentro de n8n (Requirement 15.4); el archivo temporal se borra al terminar.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def build_credentials(env: dict[str, str]) -> list[dict]:
    db = urlparse(env["SUPABASE_DB_URL"])
    creds = [
        {
            "id": "unabSupabasePg01", "name": "Supabase Postgres", "type": "postgres",
            "data": {
                "host": db.hostname, "port": db.port or 5432, "database": (db.path or "/postgres").lstrip("/"),
                "user": unquote(db.username or "postgres"), "password": unquote(db.password or ""),
                "ssl": "disable" if env.get("DB_SSL") == "disable" else "require",
                # El certificado de Supabase no está en el almacén de Node; solo aplica con SSL
                "allowUnauthorizedCerts": env.get("DB_SSL") != "disable", "maxConnections": 10,
            },
        },
        # Credencial "OpenAI API" para cualquier endpoint compatible. Ollama ignora la clave, pero n8n exige una.
        {"id": "unabOpenAiApi001", "name": "OpenAI API", "type": "openAiApi",
         "data": {"apiKey": env.get("OPENAI_API_KEY") or "ollama-local"}},
    ]
    sa_raw = env.get("GOOGLE_SA_JSON", "")
    if sa_raw.startswith("{") and "private_key" in sa_raw:
        sa = json.loads(sa_raw)
        creds.append({
            "id": "unabGoogleSa0001", "name": "Google Service Account", "type": "googleApi",
            "data": {
                "email": sa["client_email"], "privateKey": sa["private_key"], "httpNode": True,
                "scopes": "https://www.googleapis.com/auth/spreadsheets.readonly "
                          "https://www.googleapis.com/auth/firebase.messaging",
            },
        })
    else:
        print("AVISO: GOOGLE_SA_JSON vacío o inválido; crea la credencial 'Google Service Account' en la UI.")
    return creds


def sh(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, check=True, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=str(ROOT / ".env"))
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--n8n-url", default="http://localhost:9000")
    args = parser.parse_args()

    env = load_env(Path(args.env))
    for key in ("N8N_ENCRYPTION_KEY", "SUPABASE_DB_URL"):
        if not env.get(key):
            sys.exit(f"Falta {key} en {args.env}")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(build_credentials(env), fh)
        tmp = Path(fh.name)
    try:
        sh("docker", "compose", "cp", str(tmp), "n8n:/tmp/unab-creds.json")
        sh("docker", "compose", "exec", "-T", "n8n", "n8n", "import:credentials", "--input=/tmp/unab-creds.json")
    finally:
        tmp.unlink(missing_ok=True)
        subprocess.run(["docker", "compose", "exec", "-T", "n8n", "rm", "-f", "/tmp/unab-creds.json"], cwd=ROOT)

    sh("docker", "compose", "exec", "-T", "n8n", "n8n", "import:workflow", "--separate", "--input=/workflows")
    if args.activate:
        # En n8n 1.123 "update:workflow --active=true" falla (FOREIGN KEY: el import por CLI no crea la versión
        # en workflow_history). Se activa por la API REST: guardar (crea la versión) y luego activar.
        sh("docker", "compose", "restart", "n8n")
        email = env.get("N8N_OWNER_EMAIL", "")
        password = env.get("N8N_OWNER_PASSWORD", "")
        if not (email and password):
            sys.exit("Para --activate define N8N_OWNER_EMAIL y N8N_OWNER_PASSWORD en .env (se crea el usuario dueño si no existe).")
        activate_via_rest(args.n8n_url, email, password)
    print("\nListo. Abre http://<host>:9000 y revisa que los 6 workflows estén activos.")


def activate_via_rest(base: str, email: str, password: str) -> None:
    import http.cookiejar
    import time
    import urllib.error
    import urllib.request

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(base.rstrip("/") + "/rest" + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"content-type": "application/json", "browser-id": "setup-n8n"})
        try:
            with opener.open(req, timeout=120) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, {"error": e.read().decode(errors="replace")[:300]}
        except OSError as e:
            return 0, {"error": str(e)}

    for _ in range(60):  # n8n tarda en arrancar después del restart
        if call("GET", "/settings")[0] == 200:
            break
        time.sleep(3)
    call("POST", "/owner/setup", {"email": email, "firstName": "Admin", "lastName": "UNAB", "password": password})
    status, _ = call("POST", "/login", {"emailOrLdapLoginId": email, "password": password})
    if status != 200:
        sys.exit("No se pudo iniciar sesión en n8n con N8N_OWNER_EMAIL / N8N_OWNER_PASSWORD.")
    _, wfs = call("GET", "/workflows")
    for w in wfs.get("data", []):
        _, full = call("GET", f"/workflows/{w['id']}")
        d = full["data"]
        _, saved = call("PATCH", f"/workflows/{w['id']}", {
            "name": d["name"], "nodes": d["nodes"], "connections": d["connections"],
            "settings": d.get("settings", {}), "versionId": d["versionId"]})
        vid = saved.get("data", {}).get("versionId", d["versionId"])
        status, res = call("PATCH", f"/workflows/{w['id']}", {"active": True, "versionId": vid})
        if status >= 300:
            status, res = call("POST", f"/workflows/{w['id']}/activate", {"versionId": vid})
        print(f"  {'ACTIVO' if status < 300 else 'ERROR ' + str(status)}  {w['name']}")


if __name__ == "__main__":
    main()
