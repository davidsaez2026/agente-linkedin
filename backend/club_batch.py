import csv
from io import StringIO

from .places_provider import search_and_send_places


REQUIRED_COLUMNS = ["club"]
OPTIONAL_COLUMNS = ["categoria", "pais", "ciudad", "busqueda"]
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def parse_club_text(text, default_country):
    targets = []
    for line in str(text or "").splitlines():
        club = line.strip()
        if not club or club.startswith("#"):
            continue
        targets.append(
            {
                "club": club,
                "categoria": "",
                "pais": default_country,
                "ciudad": "",
                "busqueda": club,
            }
        )
    return targets


def parse_club_csv(content, default_country):
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else str(content or "")
    reader = csv.DictReader(StringIO(text))
    targets = []
    for row in reader:
        normalized = {key: str(row.get(key, "") or "").strip() for key in ALL_COLUMNS}
        if not normalized["club"]:
            continue
        if not normalized["pais"]:
            normalized["pais"] = default_country
        if not normalized["busqueda"]:
            normalized["busqueda"] = normalized["club"]
        targets.append(normalized)
    return targets


def run_club_batch(config, targets, max_results_per_club=1, enrich_emails=True, limit=None):
    results = []
    total_sent = 0
    total_skipped = 0
    selected_targets = targets[:limit] if limit else targets

    for target in selected_targets:
        query_name = target.get("busqueda") or target.get("club", "")
        result = search_and_send_places(
            config,
            query_name,
            target.get("ciudad", ""),
            target.get("pais", ""),
            int(max_results_per_club),
            enrich_emails=enrich_emails,
            tag=build_tag(target),
        )
        total_sent += result.get("sent", 0)
        total_skipped += result.get("skipped", 0)
        results.append(
            {
                "club": target.get("club", ""),
                "categoria": target.get("categoria", ""),
                "pais": target.get("pais", ""),
                "ciudad": target.get("ciudad", ""),
                "query": result.get("query", ""),
                "enviados": result.get("sent", 0),
                "duplicados": result.get("skipped", 0),
                "encontrados": len(result.get("places", [])),
                "error": result.get("errors", [""])[0] if result.get("errors") else "",
            }
        )

    return {"results": results, "sent": total_sent, "skipped": total_skipped}


def build_tag(target):
    parts = ["Clubes"]
    if target.get("pais"):
        parts.append(target["pais"])
    if target.get("categoria"):
        parts.append(target["categoria"])
    return ": ".join(parts)
