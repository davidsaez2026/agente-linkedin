import re
import time
from urllib.parse import urljoin, urlparse

import requests

from .email_tools import generate_domain_email_candidates
from .memory import append_seen_id, load_seen_ids
from .sheets import send_lead


PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DEFAULT_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.rating",
        "places.userRatingCount",
        "nextPageToken",
    ]
)


def search_places(api_key, query, max_results=20, language_code="es"):
    if not api_key:
        raise ValueError("Falta GOOGLE_PLACES_API_KEY.")
    if not query:
        raise ValueError("Falta query de busqueda.")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": DEFAULT_FIELD_MASK,
    }
    places = []
    page_token = None

    while len(places) < max_results:
        payload = {
            "textQuery": query,
            "languageCode": language_code,
            "pageSize": min(20, max_results - len(places)),
        }
        if page_token:
            payload["pageToken"] = page_token
            time.sleep(2)

        response = requests.post(PLACES_TEXT_SEARCH_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        places.extend(data.get("places", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return [normalize_place(place) for place in places[:max_results]]


def normalize_place(place):
    display_name = place.get("displayName") or {}
    phone = place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber") or ""
    return {
        "place_id": place.get("id", ""),
        "nombre": display_name.get("text", ""),
        "direccion": place.get("formattedAddress", ""),
        "telefono": phone,
        "web": place.get("websiteUri", ""),
        "maps_url": place.get("googleMapsUri", ""),
        "rating": place.get("rating", ""),
        "reviews": place.get("userRatingCount", ""),
    }


def place_to_lead(place, ciudad, pais, etiqueta):
    return {
        "nombre": place.get("nombre", ""),
        "apellidos": "Institución",
        "url_perfil": place.get("web") or place.get("maps_url", ""),
        "empresa": place.get("nombre", ""),
        "cargo": "Club/Entidad",
        "email": place.get("email", ""),
        "telefono": place.get("telefono", ""),
        "palabra_clave": etiqueta,
        "ciudad": ciudad,
        "pais": pais,
        "direccion": place.get("direccion", ""),
        "maps_url": place.get("maps_url", ""),
        "rating": place.get("rating", ""),
        "reviews": place.get("reviews", ""),
        "email_tipo": place.get("email_tipo", ""),
    }


PLACES_MEMORY_FILE = "visitados_places_api.txt"
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
CONTACT_PATHS = [
    "",
    "/contacto",
    "/contact",
    "/club/contacto",
    "/contact-us",
    "/contactanos",
    "/contactar",
    "/aviso-legal",
    "/legal",
    "/privacidad",
    "/privacy",
    "/sobre-nosotros",
    "/about",
    "/club",
]
CONTACT_LINK_KEYWORDS = ["contact", "contacto", "legal", "privacidad", "privacy", "about", "club"]
SITEMAP_PATHS = ["/sitemap.xml", "/sitemap_index.xml"]


def search_and_send_places(
    config,
    busqueda,
    ciudad,
    pais,
    max_results,
    enrich_emails=False,
    tag=None,
    include_email_candidates=False,
):
    query = build_places_query(busqueda, ciudad, pais)
    places = search_places(config.get("google_places_api_key", ""), query, max_results=max_results)
    seen_ids = load_seen_ids(PLACES_MEMORY_FILE)
    new_places = [place for place in places if place.get("place_id") and place["place_id"] not in seen_ids]
    sent = 0
    errors = []
    skipped = len(places) - len(new_places)
    for place in new_places:
        if enrich_emails:
            enrich_place_email(place, include_candidates=include_email_candidates)
        lead = place_to_lead(place, ciudad, pais, tag or f"Places API: {busqueda}")
        ok, message = send_lead(config.get("webhook_url", ""), lead)
        if ok:
            sent += 1
            append_seen_id(PLACES_MEMORY_FILE, place.get("place_id"))
        else:
            errors.append(message)
    return {"query": query, "places": places, "new_places": new_places, "sent": sent, "skipped": skipped, "errors": errors}


def build_places_query(busqueda, ciudad="", pais=""):
    parts = [str(busqueda or "").strip()]
    location = ", ".join(part for part in [str(ciudad or "").strip(), str(pais or "").strip()] if part)
    if location:
        parts.append(f"en {location}")
    return " ".join(part for part in parts if part)


def enrich_places_with_emails(places, include_candidates=False):
    for place in places:
        enrich_place_email(place, include_candidates=include_candidates)
    return places


def enrich_place_email(place, include_candidates=False):
    if place.get("email") or not place.get("web"):
        return place
    public_emails = find_public_emails(place["web"])
    if public_emails:
        place["email"] = public_emails
        place["email_tipo"] = "publico"
    elif include_candidates:
        candidates = generate_domain_email_candidates(urlparse(normalize_website_url(place["web"])).netloc)
        place["email"] = ", ".join(candidates[:5])
        place["email_tipo"] = "candidato"
    return place


def find_public_emails(website_url, max_pages=15):
    base_url = normalize_website_url(website_url)
    if not base_url or should_skip_email_lookup(base_url):
        return ""

    emails = []
    visited = set()
    urls_to_visit = build_email_lookup_urls(base_url, max_pages)
    urls_to_visit.extend(fetch_sitemap_contact_urls(base_url, max_pages=max_pages))
    for url in urls_to_visit:
        if url in visited:
            continue
        visited.add(url)
        try:
            response = requests.get(
                url,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0 AgenteProspector/1.0"},
            )
            if response.status_code >= 400:
                continue
            found = extract_emails_from_html(response.text)
            add_emails(emails, found, base_url)
            for link in extract_contact_links(response.text, url):
                if len(urls_to_visit) >= max_pages:
                    break
                if link not in visited and link not in urls_to_visit:
                    urls_to_visit.append(link)
        except requests.RequestException:
            continue
        if len(emails) >= 5:
            break
    return ", ".join(emails[:5])


def build_email_lookup_urls(base_url, max_pages):
    urls = []
    for path in CONTACT_PATHS:
        url = urljoin(base_url, path)
        if url not in urls:
            urls.append(url)
        if len(urls) >= max_pages:
            break
    return urls


def extract_contact_links(html, current_url):
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    links = []
    base_host = urlparse(current_url).netloc.lower()
    for href in hrefs:
        href_lower = href.lower()
        if not any(keyword in href_lower for keyword in CONTACT_LINK_KEYWORDS):
            continue
        absolute = urljoin(current_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != base_host:
            continue
        clean_url = parsed._replace(fragment="", query="").geturl()
        if clean_url not in links:
            links.append(clean_url)
    return links


def fetch_sitemap_contact_urls(base_url, max_pages=15):
    urls = []
    base_host = urlparse(base_url).netloc.lower()
    for path in SITEMAP_PATHS:
        sitemap_url = urljoin(base_url, path)
        try:
            response = requests.get(
                sitemap_url,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0 AgenteProspector/1.0"},
            )
            if response.status_code >= 400:
                continue
        except requests.RequestException:
            continue

        locs = re.findall(r"<loc>\s*([^<]+)\s*</loc>", response.text, flags=re.IGNORECASE)
        for loc in locs:
            loc = loc.strip()
            parsed = urlparse(loc)
            if parsed.netloc.lower() != base_host:
                continue
            if not any(keyword in loc.lower() for keyword in CONTACT_LINK_KEYWORDS):
                continue
            clean_url = parsed._replace(fragment="", query="").geturl()
            if clean_url not in urls:
                urls.append(clean_url)
            if len(urls) >= max_pages:
                return urls
    return urls


def extract_emails_from_html(html):
    emails = EMAIL_PATTERN.findall(html)
    emails.extend(extract_mailto_emails(html))
    emails.extend(extract_obfuscated_emails(html))
    emails.extend(extract_cloudflare_emails(html))
    return emails


def extract_mailto_emails(html):
    mailtos = re.findall(r"mailto:([^\"'?>\s]+)", html, flags=re.IGNORECASE)
    return [item.split("?")[0] for item in mailtos]


def extract_obfuscated_emails(html):
    text = re.sub(r"<[^>]+>", " ", html)
    pattern = re.compile(
        r"([a-zA-Z0-9._%+-]+)\s*(?:\[?\s*at\s*\]?|@)\s*([a-zA-Z0-9.-]+)\s*(?:\[?\s*dot\s*\]?|\.)\s*([a-zA-Z]{2,})",
        flags=re.IGNORECASE,
    )
    return [f"{user}@{domain}.{tld}" for user, domain, tld in pattern.findall(text)]


def extract_cloudflare_emails(html):
    protected = re.findall(r"/cdn-cgi/l/email-protection#([a-fA-F0-9]+)", html)
    decoded = []
    for value in protected:
        email = decode_cloudflare_email(value)
        if email:
            decoded.append(email)
    return decoded


def decode_cloudflare_email(value):
    try:
        data = bytes.fromhex(value)
        key = data[0]
        return "".join(chr(byte ^ key) for byte in data[1:])
    except (ValueError, IndexError):
        return ""


def add_emails(emails, candidates, website_url):
    website_domain = normalized_domain(urlparse(website_url).netloc)
    for email in candidates:
        email = email.strip().lower()
        if not is_valid_public_email(email):
            continue
        email_domain = normalized_domain(email.split("@")[-1])
        if website_domain and email_domain and not domains_match(email_domain, website_domain):
            continue
        if email not in emails:
            emails.append(email)


def normalized_domain(domain):
    value = str(domain or "").lower().strip()
    if value.startswith("www."):
        value = value[4:]
    return value


def domains_match(email_domain, website_domain):
    return email_domain == website_domain or email_domain.endswith("." + website_domain)


def normalize_website_url(url):
    value = str(url or "").strip()
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    return value


def should_skip_email_lookup(url):
    host = urlparse(url).netloc.lower()
    blocked = ["google.", "facebook.", "instagram.", "twitter.", "x.com", "linkedin.", "youtube."]
    return any(item in host for item in blocked)


def is_valid_public_email(email):
    blocked_suffixes = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
    blocked_fragments = ["example.com", "sentry.io", "wixpress.com"]
    return not email.endswith(blocked_suffixes) and not any(fragment in email for fragment in blocked_fragments)
