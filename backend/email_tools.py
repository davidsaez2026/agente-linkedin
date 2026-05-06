def generate_email_permutations(nombre, apellido, dominio):
    n = nombre.lower().strip().replace(" ", "")
    a = apellido.lower().strip().replace(" ", "")
    d = dominio.lower().strip()
    if not n or not d:
        return []

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
