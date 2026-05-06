# Agente LinkedIn

Aplicacion para controlar los agentes de prospeccion desde un panel web.

## Arranque rapido

### Opcion Streamlit

```bash
streamlit run streamlit_app.py
```

Despues abre la URL que muestre Streamlit, normalmente:

```text
http://localhost:8501
```

Por defecto el acceso es:

```text
usuario: admin
contrasena: admin
```

Para cambiarlo en local, crea `.streamlit/secrets.toml` usando `.streamlit/secrets.toml.example` como referencia.

Al iniciar, la app crea el usuario administrador definido en Secrets. Desde la pestaña `Usuarios`, un administrador puede crear nuevos usuarios o activar/desactivar cuentas. Las contrasenas se guardan hasheadas.

### Opcion Python puro

```bash
python3 app.py
```

Despues abre:

```text
http://127.0.0.1:8787
```

## Que incluye el panel

- Configuracion centralizada para OpenAI, webhook de Google Apps Script, busqueda de Maps, objetivo por sesion y palabras clave de LinkedIn.
- Contadores de memoria para URLs visitadas y ciudades.
- Generador de candidatos de email corporativo.
- Busqueda de entidades en Google Places API sin Selenium.
- Botones para iniciar/detener agentes y consultar logs.
- Acceso controlado por usuario y contrasena en la version Streamlit.
- Gestion de usuarios desde la pestaña `Usuarios` para administradores.
- Capa `backend/` separada para configuracion, memoria, herramientas de email y ejecucion de jobs.
- Agentes Maps y Francotirador preparados para recibir parametros desde Streamlit sin pedirlos por consola.

## Despliegue gratuito en Streamlit Community Cloud

Recomendacion actual: **Streamlit Community Cloud + Supabase Free**.

1. Sube el proyecto a GitHub.
2. Entra en Streamlit Community Cloud y crea una app nueva apuntando a `streamlit_app.py`.
3. En `Advanced settings > Secrets`, define:

```toml
APP_USERNAME = "tu_usuario"
APP_PASSWORD = "tu_contrasena_segura"
OPENAI_API_KEY = "sk-..."
WEBHOOK_URL = "https://script.google.com/..."
GOOGLE_PLACES_API_KEY = "..."
BUSQUEDA_MAPS = "Futbol Club"
OBJETIVO_SESION = 10
PALABRAS_CLAVE_LINKEDIN = "futbol data, analista deportivo, scouting futbol"
```

Streamlit instalara automaticamente las dependencias desde `requirements.txt`.

## Notas importantes

Los agentes actuales siguen usando Selenium e inputs por consola. Si un agente pide datos o login manual, respondelo en la terminal donde ejecutaste `python3 app.py` y completa el login en la ventana de Chrome que abra Selenium.

En Streamlit Community Cloud, los agentes basados en Selenium y login manual pueden no funcionar bien porque el entorno no esta pensado para abrir Chrome interactivo. La app ya separa los jobs en `backend/jobs.py`, pero el siguiente salto para hacerlos 100% cloud-friendly es sustituir scraping con navegador por APIs o servicios backend que no requieran login manual.

La primera sustitucion ya esta implementada: la pestaña `Maps API` usa Google Places Text Search API, no Selenium. Necesita `GOOGLE_PLACES_API_KEY` y puede enviar los resultados al webhook de Google Sheets.

Para LinkedIn no hay una sustitucion directa equivalente con API publica abierta para buscar perfiles y contactar usuarios. La ruta estable es una de estas:

- Usar productos oficiales de LinkedIn con acceso aprobado.
- Integrar un proveedor de datos/CRM con API.
- Cambiar el flujo a importacion de CSV/Sheets y enriquecimiento posterior, sin automatizar navegacion ni mensajes.

La pestaña `Importar` implementa esta ultima ruta: permite subir un CSV con leads y enviarlos al webhook sin usar navegador.

## Aplicacion web multiusuario

Para que la usen varios usuarios, despliegala en un hosting web:

- Streamlit Community Cloud sirve para una demo privada sencilla.
- Para uso estable con varios usuarios, despliegala en Render, Railway, Fly.io, Cloud Run o un VPS.
- Si necesitas persistencia robusta de usuarios, cambia `users.json` por una base externa como Supabase, Postgres o Firebase Auth.
- La app ya soporta SQLite local por defecto y Supabase opcional para usuarios persistentes.

En despliegues gratuitos tipo Streamlit Cloud, el archivo SQLite local puede no ser persistente entre reinicios o redeploys. Para un equipo real, conviene usar Supabase o una base de datos gestionada.

### Usuarios persistentes con Supabase

1. Crea un proyecto en Supabase.
2. Ejecuta el SQL de `supabase_schema.sql` en el SQL editor.
3. Define estos Secrets en Streamlit/hosting:

```toml
SUPABASE_URL = "https://tu-proyecto.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "tu-service-role-key"
SUPABASE_USERS_TABLE = "app_users"
```

La app usara Supabase automaticamente para login y gestion de usuarios. Si esos Secrets no existen, usara SQLite local en `users.db`.

Consulta `DEPLOYMENT.md` para el paso a paso completo.

## Ejecucion no interactiva de agentes

El panel Streamlit lanza los agentes como procesos backend con variables de entorno.

Maps usa:

```text
AGENTE_MAPS_MODO=basico
AGENTE_MAPS_CIUDAD=Madrid
AGENTE_MAPS_PAIS=España
AGENTE_BUSQUEDA_MAPS=Futbol Club
```

Francotirador usa:

```text
AGENTE_FRANCO_MODO=linkedin
AGENTE_FRANCO_CARGO=analista de datos
AGENTE_FRANCO_CIUDAD=Madrid
AGENTE_FRANCO_PAIS=España
```

La configuracion local se guarda en `app_config.json`. Evita subirlo a un repositorio si contiene claves reales.

## Dependencias

Para la app web cloud:

```bash
pip install -r requirements.txt
```

Para usar tambien los agentes locales legacy con Selenium:

```bash
pip install -r requirements-local.txt
```
