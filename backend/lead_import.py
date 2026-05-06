from .sheets import send_lead


LEAD_FIELDS = [
    "nombre",
    "apellidos",
    "url_perfil",
    "empresa",
    "cargo",
    "email",
    "telefono",
    "palabra_clave",
    "ciudad",
    "pais",
]


def normalize_lead(row, default_tag="Importado"):
    lead = {}
    for field in LEAD_FIELDS:
        value = row.get(field, "")
        if value is None:
            value = ""
        lead[field] = str(value).strip()

    if not lead["palabra_clave"]:
        lead["palabra_clave"] = default_tag
    return lead


def send_imported_leads(webhook_url, rows, default_tag="Importado"):
    sent = 0
    errors = []
    for row in rows:
        lead = normalize_lead(row, default_tag)
        if not lead["nombre"] and not lead["empresa"]:
            continue
        ok, message = send_lead(webhook_url, lead)
        if ok:
            sent += 1
        else:
            errors.append(message)
    return {"sent": sent, "errors": errors}
