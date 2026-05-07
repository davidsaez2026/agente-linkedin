from .settings import BASE_DIR, DATA_DIR


MEMORY_FILES = [
    ("visitados_maps.txt", "URLs Maps"),
    ("visitados_maestro.txt", "URLs maestro"),
    ("ciudades_completadas.txt", "Ciudades completadas"),
    ("ciudades_maestra.txt", "Ciudades disponibles"),
]


def read_lines(file_name):
    path = BASE_DIR / file_name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return [line.strip() for line in f if line.strip()]


def memory_stats():
    return [(label, len(read_lines(file_name))) for file_name, label in MEMORY_FILES]


def load_seen_ids(file_name):
    return set(read_persistent_lines(file_name))


def append_seen_id(file_name, item_id):
    if not item_id:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / file_name
    with path.open("a", encoding="utf-8") as f:
        f.write(str(item_id).strip() + "\n")


def read_persistent_lines(file_name):
    path = DATA_DIR / file_name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return [line.strip() for line in f if line.strip()]
