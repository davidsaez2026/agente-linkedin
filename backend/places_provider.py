import time

import requests

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
            "maxResultCount": min(20, max_results - len(places)),
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
        "email": "",
        "telefono": place.get("telefono", ""),
        "palabra_clave": etiqueta,
        "ciudad": ciudad,
        "pais": pais,
        "direccion": place.get("direccion", ""),
        "maps_url": place.get("maps_url", ""),
        "rating": place.get("rating", ""),
        "reviews": place.get("reviews", ""),
    }


PLACES_MEMORY_FILE = "visitados_places_api.txt"


def search_and_send_places(config, busqueda, ciudad, pais, max_results):
    query = f"{busqueda} en {ciudad}, {pais}".strip()
    places = search_places(config.get("google_places_api_key", ""), query, max_results=max_results)
    seen_ids = load_seen_ids(PLACES_MEMORY_FILE)
    new_places = [place for place in places if place.get("place_id") and place["place_id"] not in seen_ids]
    sent = 0
    errors = []
    skipped = len(places) - len(new_places)
    for place in new_places:
        lead = place_to_lead(place, ciudad, pais, f"Places API: {busqueda}")
        ok, message = send_lead(config.get("webhook_url", ""), lead)
        if ok:
            sent += 1
            append_seen_id(PLACES_MEMORY_FILE, place.get("place_id"))
        else:
            errors.append(message)
    return {"query": query, "places": places, "new_places": new_places, "sent": sent, "skipped": skipped, "errors": errors}
