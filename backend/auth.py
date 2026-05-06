import hashlib
import hmac
import secrets

from .user_store import get_user_store


PBKDF2_ITERATIONS = 260000


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password, stored_hash):
    try:
        algorithm, iterations, salt, digest = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def ensure_admin_user(username, password):
    store = get_user_store()
    if store.get_user(username):
        return
    store.create_user(username, hash_password(password), "admin", True)


def authenticate(username, password, fallback_username=None, fallback_password=None):
    user = get_user_store().get_user(username)
    if user and user.get("active", True):
        if verify_password(password, user.get("password_hash", "")):
            return {"username": username, "role": user.get("role", "user")}
        return None

    if fallback_username and fallback_password:
        if hmac.compare_digest(username, fallback_username) and hmac.compare_digest(password, fallback_password):
            return {"username": username, "role": "admin"}
    return None


def create_user(username, password, role="user"):
    username = username.strip()
    if not username:
        return False, "El usuario no puede estar vacio."
    if len(password) < 8:
        return False, "La contrasena debe tener al menos 8 caracteres."
    if role not in {"admin", "user"}:
        return False, "Rol no valido."

    store = get_user_store()
    if store.get_user(username):
        return False, "Ese usuario ya existe."

    try:
        store.create_user(username, hash_password(password), role, True)
        return True, "Usuario creado."
    except Exception as exc:
        return False, f"No se pudo crear el usuario: {exc}"


def set_user_active(username, active):
    try:
        if not get_user_store().set_active(username, active):
            return False, "Usuario no encontrado."
        return True, "Usuario actualizado."
    except Exception as exc:
        return False, f"No se pudo actualizar el usuario: {exc}"


def public_users():
    return [
        {"usuario": row["username"], "rol": row.get("role", "user"), "activo": bool(row.get("active", True))}
        for row in get_user_store().list_users()
    ]
