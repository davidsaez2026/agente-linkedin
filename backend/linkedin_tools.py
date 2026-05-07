import csv
from io import StringIO
from urllib.parse import quote_plus

from .sheets import send_lead


DEFAULT_LINKEDIN_ROLES = [
    "director deportivo",
    "responsable de cantera",
    "analista de datos",
    "analista de rendimiento",
    "scouting",
    "recruitment",
    "head of scouting",
    "academy director",
    "chief data officer",
]


def build_linkedin_searches(clubs, roles=None, country=""):
    roles = roles or DEFAULT_LINKEDIN_ROLES
    searches = []
    for club in clubs:
        club_name = str(club.get("club") if isinstance(club, dict) else club).strip()
        category = str(club.get("categoria", "") if isinstance(club, dict) else "").strip()
        if not club_name:
            continue
        for role in roles:
            query = " ".join(part for part in [role, club_name, country] if part).strip()
            searches.append(
                {
                    "club": club_name,
                    "categoria": category,
                    "rol": role,
                    "query": query,
                    "linkedin_people_url": linkedin_people_url(query),
                    "google_linkedin_url": google_linkedin_url(query),
                }
            )
    return searches


def linkedin_people_url(query):
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"


def google_linkedin_url(query):
    dork = f'site:linkedin.com/in/ "{query}"'
    return f"https://www.google.com/search?q={quote_plus(dork)}"


def searches_to_csv(searches):
    output = StringIO()
    fieldnames = ["club", "categoria", "rol", "query", "linkedin_people_url", "google_linkedin_url"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in searches:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output.getvalue()


def linkedin_search_to_lead(search, country=""):
    return {
        "nombre": search.get("club", ""),
        "apellidos": "LinkedIn search",
        "empresa": search.get("club", ""),
        "cargo": search.get("rol", ""),
        "email": "",
        "telefono": "",
        "url_perfil": search.get("linkedin_people_url", ""),
        "palabra_clave": f"LinkedIn: {search.get('rol', '')}",
        "ciudad": "",
        "pais": country,
        "direccion": "",
        "maps_url": search.get("google_linkedin_url", ""),
        "rating": "",
        "reviews": "",
    }


def send_linkedin_searches_to_sheets(webhook_url, searches, country=""):
    sent = 0
    errors = []
    for search in searches:
        ok, message = send_lead(webhook_url, linkedin_search_to_lead(search, country))
        if ok:
            sent += 1
        else:
            errors.append(message)
    return {"sent": sent, "errors": errors}
