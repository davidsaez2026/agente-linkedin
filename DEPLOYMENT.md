# Despliegue recomendado: Streamlit Cloud + Supabase

Esta es la ruta recomendada para tener una URL web publica, coste inicial cero y usuarios persistentes.

## 1. Crear Supabase

1. Crea un proyecto gratis en Supabase.
2. Abre `SQL Editor`.
3. Ejecuta el contenido de `supabase_schema.sql`.
4. Copia:
   - `Project URL`
   - `service_role key`

Usa la `service_role key` solo como Secret del servidor. No la pongas en codigo ni en archivos del repositorio.

## 2. Subir el proyecto a GitHub

El repositorio debe incluir:

- `streamlit_app.py`
- `backend/`
- `requirements.txt`
- `.streamlit/config.toml`
- `supabase_schema.sql`

No subas:

- `.streamlit/secrets.toml`
- `app_config.json`
- `users.db`
- `logs/`

Ya estan protegidos en `.gitignore`.

## 3. Crear app en Streamlit Community Cloud

1. Entra en `https://share.streamlit.io`.
2. Pulsa `Create app`.
3. Selecciona el repo de GitHub.
4. Entry point: `streamlit_app.py`.
5. En `Advanced settings > Secrets`, pega tus Secrets.

Ejemplo:

```toml
APP_USERNAME = "admin"
APP_PASSWORD = "cambia-esta-contrasena"

WEBHOOK_URL = "https://script.google.com/..."
GOOGLE_PLACES_API_KEY = "..."
BUSQUEDA_MAPS = "Futbol Club"
OBJETIVO_SESION = 10
PALABRAS_CLAVE_LINKEDIN = "futbol data, analista deportivo, scouting futbol"

SUPABASE_URL = "https://tu-proyecto.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "tu-service-role-key"
SUPABASE_USERS_TABLE = "app_users"
```

## 4. Primer acceso

Streamlit te dara una URL tipo:

```text
https://nombre-de-tu-app.streamlit.app
```

Entra con el usuario `APP_USERNAME` y `APP_PASSWORD`. Despues ve a la pestaña `Usuarios` y crea las cuentas del equipo.

## 5. Flujo recomendado sin Selenium

- `Maps API`: busca entidades con Google Places API y envia resultados a Sheets.
- `Importar`: sube CSV de leads desde fuentes permitidas y envia al webhook.
- `Usuarios`: crea y desactiva accesos.

Los agentes legacy con Selenium quedan para uso local con `requirements-local.txt`.
