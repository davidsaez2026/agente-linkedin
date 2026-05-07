DOMAIN_ROLE_PREFIXES = [
    "info",
    "contacto",
    "contact",
    "hola",
    "hello",
    "admin",
    "administracion",
    "secretaria",
    "marketing",
    "comercial",
    "sales",
    "ventas",
    "partners",
    "sponsors",
    "sponsorship",
    "prensa",
    "media",
    "comunicacion",
    "rrhh",
    "jobs",
    "soporte",
    "support",
]


def clean_domain(dominio):
    domain = dominio.lower().strip()
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.split("/")[0]
    return domain


def generate_email_permutations(nombre, apellido, dominio):
    n = nombre.lower().strip().replace(" ", "")
    a = apellido.lower().strip().replace(" ", "")
    d = clean_domain(dominio)
    if not d:
        return []
    if not n:
        return generate_domain_email_candidates(d)

    candidates = [f"{n}@{d}"]
    if a:
        candidates.extend(
            [
                f"{n}.{a}@{d}",
                f"{n[0]}{a}@{d}",
                f"{n[0]}.{a}@{d}",
                f"{n}{a[0]}@{d}",
                f"{n}_{a}@{d}",
                f"{n}{a}@{d}",
            ]
        )
    return list(dict.fromkeys(candidates))


def generate_domain_email_candidates(dominio):
    d = clean_domain(dominio)
    if not d:
        return []
    return [f"{prefix}@{d}" for prefix in DOMAIN_ROLE_PREFIXES]
