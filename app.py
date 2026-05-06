import html
import json
import os
import subprocess
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "app_config.json"
LOG_DIR = BASE_DIR / "logs"

DEFAULT_CONFIG = {
    "openai_api_key": "",
    "webhook_url": "",
    "busqueda_maps": "Futbol Club",
    "objetivo_sesion": 10,
    "palabras_clave_linkedin": "futbol data, analista deportivo, scouting futbol",
}

AGENTS = {
    "maps": {
        "title": "Agente Maps",
        "script": "agente_maps.py",
        "description": "Busca entidades en Google Maps y las envia a Sheets.",
    },
    "francotirador": {
        "title": "Agente Francotirador",
        "script": "agente_francotirador.py",
        "description": "Localiza perfiles con busquedas tipo Google/LinkedIn.",
    },
    "prospector": {
        "title": "Agente Prospector",
        "script": "agente_prospector.py",
        "description": "Prospecciona perfiles dentro de LinkedIn.",
    },
    "mensajero": {
        "title": "Agente Mensajero",
        "script": "agente_mensajero.py",
        "description": "Genera notas y prepara invitaciones de LinkedIn.",
    },
}

RUNNING = {}
RUNNING_LOCK = threading.Lock()


def load_config():
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULT_CONFIG, **data}
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()


def save_config(data):
    clean = DEFAULT_CONFIG.copy()
    for key in clean:
        if key in data:
            value = data[key]
            if key == "objetivo_sesion":
                try:
                    value = max(1, int(value))
                except ValueError:
                    value = DEFAULT_CONFIG[key]
            clean[key] = value
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    return clean


def read_lines(path):
    file_path = BASE_DIR / path
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
        return [line.strip() for line in f if line.strip()]


def memory_stats():
    files = [
        ("visitados_maps.txt", "URLs visitadas en Maps"),
        ("visitados_maestro.txt", "URLs visitadas en agente maestro"),
        ("ciudades_completadas.txt", "Ciudades completadas"),
        ("ciudades_maestra.txt", "Ciudades disponibles"),
    ]
    return [
        {
            "file": file_name,
            "label": label,
            "count": len(read_lines(file_name)),
        }
        for file_name, label in files
    ]


def generate_email_permutations(nombre, apellido, dominio):
    n = nombre.lower().strip().replace(" ", "")
    a = apellido.lower().strip().replace(" ", "")
    d = dominio.lower().strip()
    if not n or not d:
        return []

    candidates = [f"{n}@{d}"]
    if a:
        candidates.extend(
            [
                f"{n}.{a}@{d}",
                f"{n[0]}{a}@{d}",
                f"{n[0]}.{a}@{d}",
                f"{n}{a[0]}@{d}",
                f"{n}_{a}@{d}",
                f"{n}{a}@{d}",
            ]
        )
    return list(dict.fromkeys(candidates))


def agent_status():
    with RUNNING_LOCK:
        statuses = {}
        for key, item in list(RUNNING.items()):
            process = item["process"]
            code = process.poll()
            statuses[key] = {
                "running": code is None,
                "returncode": code,
                "started_at": item["started_at"],
                "log": item["log"],
            }
        return statuses


def start_agent(key):
    agent = AGENTS.get(key)
    if not agent:
        return False, "Agente no reconocido."
    script_path = BASE_DIR / agent["script"]
    if not script_path.exists():
        return False, f"No existe {agent['script']}."

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{key}-{time.strftime('%Y%m%d-%H%M%S')}.log"

    with RUNNING_LOCK:
        current = RUNNING.get(key)
        if current and current["process"].poll() is None:
            return False, "Ese agente ya esta ejecutandose."

        log_file = log_path.open("w", encoding="utf-8")
        process = subprocess.Popen(
            ["python3", str(script_path)],
            cwd=str(BASE_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, **config_env(load_config())},
        )
        RUNNING[key] = {"process": process, "started_at": time.time(), "log": log_path}
    return True, f"{agent['title']} iniciado. Si pide datos, responde desde la terminal donde corre esta app."


def stop_agent(key):
    with RUNNING_LOCK:
        current = RUNNING.get(key)
        if not current or current["process"].poll() is not None:
            return False, "No hay proceso activo para ese agente."
        current["process"].terminate()
    return True, "Agente detenido."


def config_env(config):
    env = {
        "AGENTE_OPENAI_API_KEY": config.get("openai_api_key", ""),
        "AGENTE_WEBHOOK_URL": config.get("webhook_url", ""),
        "AGENTE_BUSQUEDA_MAPS": config.get("busqueda_maps", ""),
        "AGENTE_OBJETIVO_SESION": str(config.get("objetivo_sesion", "")),
        "AGENTE_PALABRAS_CLAVE_LINKEDIN": config.get("palabras_clave_linkedin", ""),
    }
    return {k: v for k, v in env.items() if v}


def escape(value):
    return html.escape(str(value), quote=True)


def redirect(location="/"):
    return 303, {"Location": location}, b""


def render_page(message=""):
    config = load_config()
    stats = memory_stats()
    statuses = agent_status()
    cards = "\n".join(
        f"""
        <article class="stat">
            <strong>{stat['count']}</strong>
            <span>{escape(stat['label'])}</span>
            <small>{escape(stat['file'])}</small>
        </article>
        """
        for stat in stats
    )

    agent_cards = "\n".join(render_agent_card(key, agent, statuses.get(key)) for key, agent in AGENTS.items())
    recent_logs = render_recent_logs(statuses)

    body = f"""<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Agente LinkedIn</title>
    <style>
        :root {{
            color-scheme: light;
            --bg: #f6f7f9;
            --panel: #ffffff;
            --ink: #1e293b;
            --muted: #64748b;
            --line: #d8dee8;
            --accent: #0f766e;
            --accent-dark: #115e59;
            --danger: #b42318;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: var(--bg);
            color: var(--ink);
        }}
        header {{
            background: #102a43;
            color: white;
            padding: 28px min(5vw, 48px);
        }}
        header h1 {{ margin: 0 0 6px; font-size: clamp(28px, 4vw, 42px); letter-spacing: 0; }}
        header p {{ margin: 0; color: #d9e2ec; max-width: 760px; }}
        main {{ padding: 28px min(5vw, 48px) 44px; display: grid; gap: 24px; }}
        section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 20px; }}
        h2 {{ margin: 0 0 16px; font-size: 20px; }}
        .message {{ border-color: #99f6e4; background: #ecfeff; color: #134e4a; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }}
        .stat {{ border: 1px solid var(--line); border-radius: 8px; padding: 16px; min-height: 120px; }}
        .stat strong {{ display: block; font-size: 32px; color: var(--accent-dark); }}
        .stat span {{ display: block; margin-top: 8px; font-weight: 650; }}
        .stat small {{ display: block; margin-top: 8px; color: var(--muted); overflow-wrap: anywhere; }}
        form {{ display: grid; gap: 12px; }}
        label {{ display: grid; gap: 6px; font-weight: 650; }}
        input, textarea {{
            width: 100%;
            border: 1px solid var(--line);
            border-radius: 6px;
            padding: 10px 12px;
            font: inherit;
            color: var(--ink);
            background: white;
        }}
        textarea {{ min-height: 80px; resize: vertical; }}
        button, .button {{
            border: 0;
            border-radius: 6px;
            padding: 10px 14px;
            background: var(--accent);
            color: white;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            justify-content: center;
            align-items: center;
            min-height: 42px;
        }}
        button.secondary {{ background: #334155; }}
        button.danger {{ background: var(--danger); }}
        .agent {{ display: grid; gap: 12px; border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
        .agent h3 {{ margin: 0; font-size: 17px; }}
        .agent p {{ margin: 0; color: var(--muted); }}
        .actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
        .status {{ font-size: 14px; color: var(--muted); }}
        .running {{ color: var(--accent-dark); font-weight: 750; }}
        pre {{
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            background: #0f172a;
            color: #e2e8f0;
            padding: 16px;
            border-radius: 8px;
            max-height: 340px;
            overflow: auto;
        }}
        .two {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, 0.75fr); gap: 24px; align-items: start; }}
        @media (max-width: 860px) {{ .two {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <header>
        <h1>Agente LinkedIn</h1>
        <p>Panel local para configurar, supervisar y ejecutar tus agentes de prospeccion desde una interfaz mas comoda.</p>
    </header>
    <main>
        {f'<section class="message">{escape(message)}</section>' if message else ''}
        <section>
            <h2>Estado</h2>
            <div class="grid">{cards}</div>
        </section>
        <div class="two">
            <section>
                <h2>Configuracion</h2>
                <form method="post" action="/config">
                    <label>OpenAI API key
                        <input type="password" name="openai_api_key" value="{escape(config['openai_api_key'])}" placeholder="sk-...">
                    </label>
                    <label>Webhook de Google Apps Script
                        <input name="webhook_url" value="{escape(config['webhook_url'])}" placeholder="https://script.google.com/...">
                    </label>
                    <label>Busqueda por defecto en Maps
                        <input name="busqueda_maps" value="{escape(config['busqueda_maps'])}">
                    </label>
                    <label>Objetivo por sesion
                        <input type="number" min="1" name="objetivo_sesion" value="{escape(config['objetivo_sesion'])}">
                    </label>
                    <label>Palabras clave de LinkedIn
                        <textarea name="palabras_clave_linkedin">{escape(config['palabras_clave_linkedin'])}</textarea>
                    </label>
                    <button>Guardar configuracion</button>
                </form>
            </section>
            <section>
                <h2>Radar de emails</h2>
                <form method="post" action="/radar">
                    <label>Nombre <input name="nombre" placeholder="David"></label>
                    <label>Apellido <input name="apellido" placeholder="Saez"></label>
                    <label>Dominio <input name="dominio" placeholder="club.com"></label>
                    <button>Generar candidatos</button>
                </form>
            </section>
        </div>
        <section>
            <h2>Agentes</h2>
            <div class="grid">{agent_cards}</div>
        </section>
        <section>
            <h2>Logs recientes</h2>
            {recent_logs}
        </section>
    </main>
</body>
</html>"""
    return body.encode("utf-8")


def render_agent_card(key, agent, status):
    running = bool(status and status["running"])
    state = '<span class="running">En ejecucion</span>' if running else "Detenido"
    log_link = ""
    if status and status.get("log"):
        log_link = f'<a class="button" href="/log?agent={escape(key)}">Ver log</a>'
    stop = f'<button class="danger" name="agent" value="{escape(key)}">Detener</button>' if running else ""
    return f"""
    <article class="agent">
        <h3>{escape(agent['title'])}</h3>
        <p>{escape(agent['description'])}</p>
        <div class="status">Estado: {state}</div>
        <div class="actions">
            <form method="post" action="/start"><button name="agent" value="{escape(key)}">Iniciar</button></form>
            <form method="post" action="/stop">{stop}</form>
            {log_link}
        </div>
    </article>
    """


def render_recent_logs(statuses):
    if not statuses:
        return "<p>Todavia no hay logs de ejecucion.</p>"
    items = []
    for key, status in statuses.items():
        log_path = status.get("log")
        if log_path:
            items.append(f'<li><a href="/log?agent={escape(key)}">{escape(AGENTS[key]["title"])}</a></li>')
    return "<ul>" + "".join(items) + "</ul>" if items else "<p>Todavia no hay logs de ejecucion.</p>"


def parse_post(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8")
    parsed = urllib.parse.parse_qs(raw)
    return {k: v[0] for k, v in parsed.items()}


class AppHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        path, _, query = self.path.partition("?")
        params = urllib.parse.parse_qs(query)
        if path == "/log":
            self.send_log(params.get("agent", [""])[0])
            return
        message = params.get("message", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(render_page(message))

    def do_POST(self):
        data = parse_post(self)
        if self.path == "/config":
            save_config(data)
            self.respond_redirect("Configuracion guardada.")
            return
        if self.path == "/radar":
            emails = generate_email_permutations(data.get("nombre", ""), data.get("apellido", ""), data.get("dominio", ""))
            message = "Candidatos: " + ", ".join(emails) if emails else "Faltan nombre y dominio."
            self.respond_redirect(message)
            return
        if self.path == "/start":
            ok, message = start_agent(data.get("agent", ""))
            self.respond_redirect(message if ok else f"No se pudo iniciar: {message}")
            return
        if self.path == "/stop":
            ok, message = stop_agent(data.get("agent", ""))
            self.respond_redirect(message if ok else f"No se pudo detener: {message}")
            return
        self.send_error(404)

    def respond_redirect(self, message):
        location = "/?message=" + urllib.parse.quote(message)
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def send_log(self, agent_key):
        status = agent_status().get(agent_key)
        if not status or not status.get("log"):
            self.send_error(404, "Log no encontrado")
            return
        log_path = status["log"]
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")[-12000:]
        except OSError:
            content = "No se pudo leer el log."
        page = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Log</title><style>body{{font-family:ui-sans-serif,system-ui;margin:24px;background:#f6f7f9;color:#1e293b}}a{{color:#0f766e}}pre{{white-space:pre-wrap;background:#0f172a;color:#e2e8f0;padding:16px;border-radius:8px;overflow:auto}}</style></head>
<body><p><a href="/">Volver al panel</a></p><h1>{escape(AGENTS.get(agent_key, {}).get('title', agent_key))}</h1><pre>{escape(content)}</pre></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode("utf-8"))

    def log_message(self, format, *args):
        return


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8787), AppHandler)
    print("App disponible en http://127.0.0.1:8787")
    print("Pulsa Ctrl+C para detenerla.")
    server.serve_forever()


if __name__ == "__main__":
    main()
