import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "app_config.json"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = Path(os.getenv("AGENTE_DATA_DIR", os.getenv("DATA_DIR", BASE_DIR))).resolve()

DEFAULT_CONFIG = {
    "openai_api_key": "",
    "webhook_url": "",
    "google_places_api_key": "",
    "busqueda_maps": "Futbol Club",
    "objetivo_sesion": 10,
    "palabras_clave_linkedin": "futbol data, analista deportivo, scouting futbol",
    "show_legacy_agents": False,
}

SECRET_MAP = {
    "openai_api_key": "OPENAI_API_KEY",
    "webhook_url": "WEBHOOK_URL",
    "google_places_api_key": "GOOGLE_PLACES_API_KEY",
    "busqueda_maps": "BUSQUEDA_MAPS",
    "objetivo_sesion": "OBJETIVO_SESION",
    "palabras_clave_linkedin": "PALABRAS_CLAVE_LINKEDIN",
    "show_legacy_agents": "SHOW_LEGACY_AGENTS",
}


def load_config(secret_getter=None):
    config = DEFAULT_CONFIG.copy()

    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                config.update(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass

    for key, secret_name in SECRET_MAP.items():
        value = None
        if secret_getter:
            value = secret_getter(secret_name, None)
        if value in ("", None):
            value = os.getenv(secret_name, "")
        if value not in ("", None):
            config[key] = value

    try:
        config["objetivo_sesion"] = max(1, int(config["objetivo_sesion"]))
    except (TypeError, ValueError):
        config["objetivo_sesion"] = DEFAULT_CONFIG["objetivo_sesion"]
    config["show_legacy_agents"] = str(config.get("show_legacy_agents", "")).lower() in {"1", "true", "yes", "on"}
    config["webhook_url"] = normalize_webhook_url(config.get("webhook_url", ""))
    return config


def save_config(config):
    clean = DEFAULT_CONFIG.copy()
    clean.update(config)
    clean["objetivo_sesion"] = max(1, int(clean["objetivo_sesion"]))
    clean["webhook_url"] = normalize_webhook_url(clean.get("webhook_url", ""))
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    return clean


def config_env(config, params=None):
    params = params or {}
    env = {
        "AGENTE_OPENAI_API_KEY": config.get("openai_api_key", ""),
        "AGENTE_WEBHOOK_URL": config.get("webhook_url", ""),
        "AGENTE_BUSQUEDA_MAPS": config.get("busqueda_maps", ""),
        "AGENTE_OBJETIVO_SESION": str(config.get("objetivo_sesion", "")),
        "AGENTE_PALABRAS_CLAVE_LINKEDIN": config.get("palabras_clave_linkedin", ""),
    }
    env.update({key: str(value) for key, value in params.items() if value not in ("", None)})
    return {key: value for key, value in env.items() if value not in ("", None)}


def normalize_webhook_url(value):
    url = str(value or "").strip().strip('"').strip("'")
    if not url:
        return ""

    apps_script_prefix = "https://script.google.com/macros/s/"
    if url.count(apps_script_prefix) > 1:
        url = apps_script_prefix + url.split(apps_script_prefix)[-1]

    if url.startswith("AKfy"):
        url = f"{apps_script_prefix}{url}"

    if url.startswith(apps_script_prefix) and not url.endswith("/exec"):
        url = url.rstrip("/") + "/exec"

    return url
