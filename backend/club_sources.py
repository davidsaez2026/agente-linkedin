import re

import requests
from bs4 import BeautifulSoup


SPAIN_SOURCES_2025_26 = {
    "LALIGA EA SPORTS": "https://en.wikipedia.org/wiki/2025%E2%80%9326_La_Liga",
    "LALIGA HYPERMOTION": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Segunda_Divisi%C3%B3n",
    "Primera RFEF": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Primera_Federaci%C3%B3n",
    "Segunda RFEF": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Segunda_Federaci%C3%B3n",
    "Tercera RFEF": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Tercera_Federaci%C3%B3n",
}

TEAM_HEADERS = {"team", "club", "equipo"}
CITY_HEADERS = {"home city", "city", "localidad", "ciudad"}
CONTEXT_HEADERS = CITY_HEADERS | {"stadium", "estadio", "capacity", "autonomous community", "home ground"}


def fetch_spain_clubs_2025_26(categories):
    targets = []
    for category in categories:
        url = SPAIN_SOURCES_2025_26.get(category)
        if not url:
            continue
        targets.extend(fetch_clubs_from_wikipedia(url, category, "España"))
    return dedupe_targets(targets)


def fetch_clubs_from_wikipedia(url, category, country):
    response = requests.get(url, timeout=25, headers={"User-Agent": "AgenteProspector/1.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    targets = []

    for table in soup.select("table.wikitable"):
        headers = [normalize_text(th.get_text(" ", strip=True)) for th in table.select("tr th")]
        if not looks_like_team_locations_table(headers):
            continue

        header_cells = table.select("tr")[0].find_all(["th", "td"])
        header_names = [normalize_text(cell.get_text(" ", strip=True)) for cell in header_cells]
        team_index = find_header_index(header_names, TEAM_HEADERS)
        city_index = find_header_index(header_names, CITY_HEADERS)
        if team_index is None:
            continue

        for row in table.select("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= team_index:
                continue
            club = clean_club_name(cells[team_index].get_text(" ", strip=True))
            city = clean_club_name(cells[city_index].get_text(" ", strip=True)) if city_index is not None and len(cells) > city_index else ""
            if not is_probable_club_name(club):
                continue
            targets.append(
                {
                    "club": club,
                    "categoria": category,
                    "pais": country,
                    "ciudad": city,
                    "busqueda": club,
                }
            )

    return targets


def looks_like_team_locations_table(headers):
    header_set = set(headers)
    has_team = bool(header_set & TEAM_HEADERS)
    has_context = bool(header_set & CONTEXT_HEADERS)
    return has_team and has_context


def find_header_index(headers, accepted):
    for index, header in enumerate(headers):
        if header in accepted:
            return index
    return None


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def clean_club_name(value):
    text = re.sub(r"\[[^\]]+\]", "", str(value or ""))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_probable_club_name(value):
    text = str(value or "").strip()
    if len(text) < 2:
        return False
    blocked = {"team", "club", "equipo", "total", "notes"}
    return normalize_text(text) not in blocked


def dedupe_targets(targets):
    seen = set()
    unique = []
    for target in targets:
        key = (normalize_text(target.get("club", "")), normalize_text(target.get("categoria", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(target)
    return unique
