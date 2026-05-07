import re

import dns.resolver

from .sheets import send_lead


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def verify_email_candidates(emails):
    mx_cache = {}
    results = []
    for email in emails:
        email = str(email or "").strip().lower()
        domain = email.split("@")[-1] if "@" in email else ""
        syntax_ok = bool(EMAIL_RE.match(email))
        mx_ok = False
        mx_records = []
        error = ""

        if syntax_ok:
            if domain not in mx_cache:
                mx_cache[domain] = lookup_mx(domain)
            mx_ok, mx_records, error = mx_cache[domain]
        else:
            error = "Formato no válido"

        results.append(
            {
                "email": email,
                "dominio": domain,
                "formato_valido": syntax_ok,
                "mx_valido": mx_ok,
                "mx_records": ", ".join(mx_records[:3]),
                "estado": "dominio_con_mx" if syntax_ok and mx_ok else "no_validado",
                "nota": error,
            }
        )
    return results


def lookup_mx(domain):
    try:
        answers = dns.resolver.resolve(domain, "MX")
        records = sorted(str(answer.exchange).rstrip(".") for answer in answers)
        return True, records, ""
    except Exception as exc:
        return False, [], str(exc)


def send_verified_emails_to_sheets(webhook_url, verification_results, source="Radar emails"):
    sent = 0
    errors = []
    for result in verification_results:
        if not result.get("formato_valido") or not result.get("mx_valido"):
            continue
        lead = {
            "nombre": result["email"],
            "apellidos": "Email candidato",
            "empresa": result.get("dominio", ""),
            "cargo": "Email candidato verificado por MX",
            "email": result["email"],
            "telefono": "",
            "url_perfil": "",
            "palabra_clave": source,
            "ciudad": "",
            "pais": "",
            "direccion": "",
            "maps_url": "",
            "rating": "dominio_con_mx",
            "reviews": result.get("mx_records", ""),
        }
        ok, message = send_lead(webhook_url, lead)
        if ok:
            sent += 1
        else:
            errors.append(message)
    return {"sent": sent, "errors": errors}
