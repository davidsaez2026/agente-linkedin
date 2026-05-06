from .settings import BASE_DIR


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
