import os
import subprocess
import time

from .settings import BASE_DIR, LOG_DIR, config_env


AGENTS = {
    "maps": {
        "title": "Agente Maps",
        "script": "agente_maps.py",
        "description": "Busca entidades en Google Maps y las envia a Sheets.",
        "cloud_ready": False,
    },
    "francotirador": {
        "title": "Agente Francotirador",
        "script": "agente_francotirador.py",
        "description": "Localiza perfiles con busquedas tipo Google/LinkedIn.",
        "cloud_ready": False,
    },
    "prospector": {
        "title": "Agente Prospector",
        "script": "agente_prospector.py",
        "description": "Prospecciona perfiles dentro de LinkedIn.",
        "cloud_ready": False,
    },
    "mensajero": {
        "title": "Agente Mensajero",
        "script": "agente_mensajero.py",
        "description": "Genera notas y prepara invitaciones de LinkedIn.",
        "cloud_ready": False,
    },
}


def is_cloud_runtime():
    return bool(os.getenv("STREAMLIT_SHARING") or os.getenv("STREAMLIT_CLOUD"))


class JobManager:
    def __init__(self, state):
        self.state = state
        if "agent_processes" not in self.state:
            self.state.agent_processes = {}

    @property
    def processes(self):
        return self.state["agent_processes"]

    def start(self, key, config, params=None):
        agent = AGENTS[key]
        script_path = BASE_DIR / agent["script"]
        if not script_path.exists():
            return False, f"No existe {agent['script']}."

        current = self.processes.get(key)
        if current and current["process"].poll() is None:
            return False, "Ese agente ya esta ejecutandose."

        LOG_DIR.mkdir(exist_ok=True)
        log_path = LOG_DIR / f"{key}-{time.strftime('%Y%m%d-%H%M%S')}.log"
        log_file = log_path.open("w", encoding="utf-8")
        process = subprocess.Popen(
            ["python3", str(script_path)],
            cwd=str(BASE_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, **config_env(config, params)},
        )
        self.processes[key] = {"process": process, "log": log_path, "started_at": time.time()}
        return True, f"{agent['title']} iniciado."

    def stop(self, key):
        current = self.processes.get(key)
        if not current or current["process"].poll() is not None:
            return False, "No hay proceso activo para ese agente."
        current["process"].terminate()
        return True, "Agente detenido."

    def status(self, key):
        current = self.processes.get(key)
        if not current:
            return {"running": False, "log": None, "returncode": None}
        return {
            "running": current["process"].poll() is None,
            "log": current.get("log"),
            "returncode": current["process"].poll(),
            "started_at": current.get("started_at"),
        }

    def log_tail(self, key, limit=8000):
        status = self.status(key)
        log_path = status.get("log")
        if not log_path:
            return ""
        try:
            return log_path.read_text(encoding="utf-8", errors="ignore")[-limit:]
        except OSError:
            return "No se pudo leer el log."
