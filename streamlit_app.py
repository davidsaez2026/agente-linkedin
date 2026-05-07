import hmac
import os

import pandas as pd
import streamlit as st

from backend.auth import authenticate, create_user, ensure_admin_user, public_users, set_user_active
from backend.club_batch import parse_club_csv, parse_club_text, run_club_batch
from backend.club_sources import SPAIN_SOURCES_2025_26, fetch_spain_clubs_2025_26
from backend.email_tools import generate_email_permutations
from backend.email_verifier import send_verified_emails_to_sheets, verify_email_candidates
from backend.jobs import AGENTS, JobManager, is_cloud_runtime
from backend.lead_import import LEAD_FIELDS, send_imported_leads
from backend.linkedin_tools import (
    DEFAULT_LINKEDIN_ROLES,
    build_linkedin_searches,
    searches_to_csv,
    send_linkedin_searches_to_sheets,
)
from backend.memory import memory_stats
from backend.places_provider import build_places_query, enrich_places_with_emails, search_and_send_places
from backend.settings import load_config, save_config


def get_secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        return os.getenv(name.upper(), default)


def hydrate_backend_env():
    for name in ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_USERS_TABLE", "DATABASE_PATH"]:
        value = get_secret(name, "")
        if value not in ("", None):
            os.environ[name] = str(value)


def check_password(username, password):
    expected_user = str(get_secret("APP_USERNAME", "admin"))
    expected_password = str(get_secret("APP_PASSWORD", "admin"))
    ensure_admin_user(expected_user, expected_password)
    user = authenticate(username, password, expected_user, expected_password)
    return user


def login():
    if st.session_state.get("authenticated"):
        return True

    st.title("Agente LinkedIn")
    st.caption("Acceso privado")
    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contrasena", type="password")
        submitted = st.form_submit_button("Entrar", use_container_width=True)

    if submitted:
        user = check_password(username, password)
        if user:
            st.session_state.authenticated = True
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("Usuario o contrasena incorrectos.")
    return False


def render_config(config):
    st.subheader("Configuracion")
    with st.form("config_form"):
        openai_api_key = st.text_input("OpenAI API key", value=config["openai_api_key"], type="password")
        webhook_url = st.text_input("Webhook de Google Apps Script", value=config["webhook_url"])
        google_places_api_key = st.text_input(
            "Google Places API key",
            value=config.get("google_places_api_key", ""),
            type="password",
        )
        busqueda_maps = st.text_input("Busqueda por defecto en Maps", value=config["busqueda_maps"])
        objetivo_sesion = st.number_input("Objetivo por sesion", min_value=1, value=int(config["objetivo_sesion"]))
        palabras_clave = st.text_area("Palabras clave de LinkedIn", value=config["palabras_clave_linkedin"])
        show_legacy_agents = st.checkbox(
            "Mostrar agentes legacy con Selenium",
            value=bool(config.get("show_legacy_agents", False)),
            help="Solo recomendado en ejecucion local con Chrome/Selenium instalado.",
        )
        submitted = st.form_submit_button("Guardar configuracion")

    if submitted:
        save_config(
            {
                "openai_api_key": openai_api_key,
                "webhook_url": webhook_url,
                "google_places_api_key": google_places_api_key,
                "busqueda_maps": busqueda_maps,
                "objetivo_sesion": objetivo_sesion,
                "palabras_clave_linkedin": palabras_clave,
                "show_legacy_agents": show_legacy_agents,
            }
        )
        st.success("Configuracion guardada.")


def render_radar(config):
    st.subheader("Radar de emails")
    st.caption("Puedes generar candidatos personales con nombre/apellido o direcciones generales usando solo dominio.")
    with st.form("radar_form"):
        nombre = st.text_input("Nombre", placeholder="Opcional")
        apellido = st.text_input("Apellido", placeholder="Opcional")
        dominio = st.text_input("Dominio", placeholder="club.com")
        submitted = st.form_submit_button("Generar candidatos")

    if submitted:
        emails = generate_email_permutations(nombre, apellido, dominio)
        if emails:
            st.session_state.radar_emails = emails
            st.code("\n".join(emails), language="text")
        else:
            st.warning("Introduce al menos un dominio.")

    emails = st.session_state.get("radar_emails", [])
    if emails:
        left, right = st.columns(2)
        if left.button("Comprobar formato y MX", use_container_width=True):
            st.session_state.radar_verification = verify_email_candidates(emails)
        if right.button("Guardar comprobados en Sheets", use_container_width=True):
            if not config.get("webhook_url"):
                st.error("Falta WEBHOOK_URL.")
            else:
                results = st.session_state.get("radar_verification") or verify_email_candidates(emails)
                result = send_verified_emails_to_sheets(config["webhook_url"], results)
                st.success(f"{result['sent']} emails con dominio MX guardados en Sheets.")
                if result["errors"]:
                    st.warning(result["errors"][0])

    if st.session_state.get("radar_verification"):
        st.dataframe(pd.DataFrame(st.session_state.radar_verification), use_container_width=True)
        st.caption(
            "La comprobación valida formato y registros MX del dominio. "
            "No confirma que el buzón exacto exista."
        )


def render_places_api(config):
    st.subheader("Maps sin Selenium")
    st.caption("Usa Google Places Text Search API y envia resultados al webhook de Sheets.")
    with st.form("places_api_form"):
        busqueda = st.text_input("Busqueda", value=config["busqueda_maps"])
        ciudad = st.text_input("Ciudad", placeholder="Opcional")
        pais = st.text_input("Pais", placeholder="España")
        max_results = st.number_input("Maximo de resultados", min_value=1, max_value=200, value=20)
        send_to_sheets = st.checkbox("Enviar a Google Sheets", value=True)
        enrich_emails = st.checkbox("Buscar emails públicos en la web", value=True)
        include_email_candidates = st.checkbox(
            "Si no hay email público, generar candidatos por dominio",
            value=False,
            help="Genera correos tipo info@dominio.com o contacto@dominio.com. No están verificados.",
        )
        submitted = st.form_submit_button("Buscar con API")

    if submitted:
        if not pais:
            st.warning("Introduce al menos un pais.")
            return
        if not config.get("google_places_api_key"):
            st.error("Falta Google Places API key en Configuracion o Secrets.")
            return
        try:
            with st.spinner("Consultando Google Places..."):
                if send_to_sheets:
                    result = search_and_send_places(
                        config,
                        busqueda,
                        ciudad,
                        pais,
                        int(max_results),
                        enrich_emails=enrich_emails,
                        include_email_candidates=include_email_candidates,
                    )
                    st.success(
                        f"{result['sent']} nuevos enviados a Sheets. "
                        f"{result['skipped']} duplicados ignorados de {len(result['places'])} resultados."
                    )
                    if result["errors"]:
                        st.warning(result["errors"][0])
                    places = result["places"]
                else:
                    from backend.places_provider import search_places

                    query = build_places_query(busqueda, ciudad, pais)
                    places = search_places(config.get("google_places_api_key", ""), query, int(max_results))
                    if enrich_emails:
                        places = enrich_places_with_emails(places, include_candidates=include_email_candidates)
                    st.success(f"{len(places)} resultados encontrados.")
            st.dataframe(places, use_container_width=True)
        except Exception as exc:
            st.error(f"No se pudo completar la busqueda: {exc}")


def render_import(config):
    st.subheader("Importar leads sin Selenium")
    st.caption("Sube un CSV exportado desde Sheets, LinkedIn Sales Navigator, CRM u otra fuente permitida.")
    uploaded = st.file_uploader("CSV de leads", type=["csv"])
    default_tag = st.text_input("Etiqueta por defecto", value="Importado sin Selenium")

    st.write("Columnas reconocidas:")
    st.code(", ".join(LEAD_FIELDS), language="text")

    if not uploaded:
        return

    try:
        df = pd.read_csv(uploaded).fillna("")
    except Exception as exc:
        st.error(f"No se pudo leer el CSV: {exc}")
        return

    st.dataframe(df.head(50), use_container_width=True)
    missing = [field for field in ["nombre", "empresa"] if field not in df.columns]
    if missing:
        st.info("No es obligatorio tener todas las columnas, pero conviene incluir nombre o empresa.")

    if st.button("Enviar leads al webhook", use_container_width=True):
        if not config.get("webhook_url"):
            st.error("Falta WEBHOOK_URL en Configuracion o Secrets.")
            return
        result = send_imported_leads(config["webhook_url"], df.to_dict("records"), default_tag)
        st.success(f"{result['sent']} leads enviados.")
        if result["errors"]:
            st.warning(result["errors"][0])


def render_club_batch(config):
    st.subheader("Búsqueda por clubes")
    st.caption(
        "Ejecuta búsquedas por lote a partir de un listado de clubes por país/categoría. "
        "Ideal para LALIGA, RFEF u otras competiciones si aportas el listado objetivo."
    )

    default_country = st.text_input("País por defecto", value="España")
    st.markdown("**Catálogo automático**")
    source_country = st.selectbox("País del catálogo", ["España"], index=0)
    categories = st.multiselect(
        "Categorías",
        list(SPAIN_SOURCES_2025_26.keys()),
        default=["LALIGA EA SPORTS", "LALIGA HYPERMOTION"],
    )
    use_auto_catalog = st.button("Cargar catálogo automático", use_container_width=True)

    if use_auto_catalog:
        try:
            with st.spinner("Cargando clubes desde fuentes públicas..."):
                if source_country == "España":
                    st.session_state.club_catalog_targets = fetch_spain_clubs_2025_26(categories)
            st.success(f"{len(st.session_state.club_catalog_targets)} clubes cargados.")
        except Exception as exc:
            st.error(f"No se pudo cargar el catálogo: {exc}")

    max_results_per_club = st.number_input("Resultados por club", min_value=1, max_value=5, value=1)
    limit = st.number_input("Máximo de clubes a procesar en esta ejecución", min_value=1, max_value=500, value=25)
    enrich_emails = st.checkbox("Buscar emails públicos en la web", value=True, key="club_batch_emails")
    include_email_candidates = st.checkbox(
        "Si no hay email público, generar candidatos por dominio",
        value=False,
        key="club_batch_candidates",
        help="Genera correos tipo info@dominio.com o contacto@dominio.com. No están verificados.",
    )

    st.markdown("**Opción rápida: pegar clubes, uno por línea**")
    clubs_text = st.text_area(
        "Clubes",
        placeholder="Real Madrid\nFC Barcelona\nValencia CF",
        height=160,
    )

    st.markdown("**Opción avanzada: subir CSV**")
    st.caption("Columnas admitidas: club,categoria,pais,ciudad,busqueda")
    uploaded = st.file_uploader("CSV de clubes", type=["csv"], key="club_csv")

    targets = st.session_state.get("club_catalog_targets", [])
    if uploaded:
        targets = parse_club_csv(uploaded.getvalue(), default_country)
    elif clubs_text.strip():
        targets = parse_club_text(clubs_text, default_country)

    if targets:
        st.write(f"{len(targets)} clubes cargados.")
        st.dataframe(pd.DataFrame(targets).head(100), use_container_width=True)

    if st.button("Buscar clubes y enviar nuevos leads", use_container_width=True):
        if not targets:
            st.warning("Pega clubes o sube un CSV.")
            return
        if not config.get("google_places_api_key"):
            st.error("Falta Google Places API key.")
            return
        if not config.get("webhook_url"):
            st.error("Falta WEBHOOK_URL.")
            return

        with st.spinner("Procesando clubes..."):
            result = run_club_batch(
                config,
                targets,
                max_results_per_club=int(max_results_per_club),
                enrich_emails=enrich_emails,
                limit=int(limit),
                include_email_candidates=include_email_candidates,
            )
        st.success(f"{result['sent']} nuevos enviados. {result['skipped']} duplicados ignorados.")
        st.dataframe(pd.DataFrame(result["results"]), use_container_width=True)


def render_linkedin_targets(config):
    st.subheader("Perfiles LinkedIn objetivo")
    st.caption(
        "Genera búsquedas dirigidas por club y rol. No automatiza LinkedIn ni extrae perfiles; "
        "te da URLs para trabajo manual, Sales Navigator o exportación autorizada."
    )

    st.markdown("**Catálogo automático**")
    source_country = st.selectbox("País del catálogo", ["España"], index=0, key="linkedin_catalog_country")
    categories = st.multiselect(
        "Categorías",
        list(SPAIN_SOURCES_2025_26.keys()),
        default=["LALIGA EA SPORTS", "LALIGA HYPERMOTION"],
        key="linkedin_catalog_categories",
    )
    if st.button("Cargar catálogo automático", use_container_width=True, key="linkedin_load_catalog"):
        try:
            with st.spinner("Cargando clubes desde fuentes públicas..."):
                if source_country == "España":
                    st.session_state.linkedin_catalog_targets = fetch_spain_clubs_2025_26(categories)
            st.success(f"{len(st.session_state.linkedin_catalog_targets)} clubes cargados.")
        except Exception as exc:
            st.error(f"No se pudo cargar el catálogo: {exc}")

    country = st.text_input("País/contexto", value="España", key="linkedin_country")
    use_catalog = st.checkbox(
        "Usar clubes del catálogo automático",
        value=bool(st.session_state.get("linkedin_catalog_targets")),
        key="linkedin_use_catalog",
    )
    clubs_text = st.text_area(
        "Clubes, uno por línea",
        placeholder="Real Madrid\nFC Barcelona\nValencia CF",
        height=140,
        disabled=use_catalog,
        key="linkedin_clubs",
    )
    roles_text = st.text_area(
        "Roles objetivo, uno por línea",
        value="\n".join(DEFAULT_LINKEDIN_ROLES),
        height=180,
        key="linkedin_roles",
    )
    max_rows = st.number_input("Máximo de búsquedas a generar", min_value=1, max_value=1000, value=200)

    if st.button("Generar búsquedas LinkedIn", use_container_width=True):
        if use_catalog:
            clubs = st.session_state.get("linkedin_catalog_targets", [])
        else:
            clubs = [{"club": line.strip(), "categoria": ""} for line in clubs_text.splitlines() if line.strip()]
        roles = [line.strip() for line in roles_text.splitlines() if line.strip()]
        searches = build_linkedin_searches(clubs, roles, country=country)[: int(max_rows)]
        st.session_state.linkedin_searches = searches

    if st.session_state.get("linkedin_catalog_targets"):
        st.write(f"{len(st.session_state.linkedin_catalog_targets)} clubes disponibles desde catálogo.")
        st.dataframe(pd.DataFrame(st.session_state.linkedin_catalog_targets).head(100), use_container_width=True)

    searches = st.session_state.get("linkedin_searches", [])
    if searches:
        st.success(f"{len(searches)} búsquedas generadas.")
        st.dataframe(pd.DataFrame(searches), use_container_width=True)
        if st.button("Guardar búsquedas LinkedIn en Google Sheets", use_container_width=True):
            if not config.get("webhook_url"):
                st.error("Falta WEBHOOK_URL.")
            else:
                result = send_linkedin_searches_to_sheets(config["webhook_url"], searches, country=country)
                st.success(f"{result['sent']} búsquedas guardadas en Sheets.")
                if result["errors"]:
                    st.warning(result["errors"][0])
        st.download_button(
            "Descargar CSV de búsquedas",
            data=searches_to_csv(searches),
            file_name="busquedas_linkedin_clubes.csv",
            mime="text/csv",
            use_container_width=True,
        )
        first = searches[0]
        st.markdown("Primera búsqueda:")
        st.link_button("Abrir en LinkedIn", first["linkedin_people_url"])
        st.link_button("Abrir en Google", first["google_linkedin_url"])


def render_users():
    st.subheader("Usuarios")
    if st.session_state.get("role") != "admin":
        st.info("Solo los administradores pueden gestionar usuarios.")
        return

    with st.form("create_user_form"):
        username = st.text_input("Nuevo usuario")
        password = st.text_input("Contrasena temporal", type="password")
        role = st.selectbox("Rol", ["user", "admin"])
        submitted = st.form_submit_button("Crear usuario")
    if submitted:
        ok, message = create_user(username, password, role)
        (st.success if ok else st.error)(message)

    users = public_users()
    if users:
        st.dataframe(users, use_container_width=True)

    with st.form("disable_user_form"):
        selected = st.selectbox("Usuario a activar/desactivar", [u["usuario"] for u in users] or [""])
        active = st.checkbox("Activo", value=True)
        submitted = st.form_submit_button("Actualizar estado")
    if submitted and selected:
        ok, message = set_user_active(selected, active)
        (st.success if ok else st.error)(message)


def agent_params_form(key, config):
    if key == "maps":
        st.text_input("Ciudad", key=f"{key}_ciudad", placeholder="Madrid")
        st.text_input("Pais", key=f"{key}_pais", placeholder="España")
        st.text_input("Busqueda", key=f"{key}_busqueda", value=config["busqueda_maps"])
        return {
            "AGENTE_MAPS_MODO": "basico",
            "AGENTE_MAPS_CIUDAD": st.session_state.get(f"{key}_ciudad", ""),
            "AGENTE_MAPS_PAIS": st.session_state.get(f"{key}_pais", ""),
            "AGENTE_BUSQUEDA_MAPS": st.session_state.get(f"{key}_busqueda", config["busqueda_maps"]),
        }
    if key == "francotirador":
        st.text_input("Cargo", key=f"{key}_cargo", placeholder="analista de datos")
        st.text_input("Ciudad", key=f"{key}_ciudad", placeholder="Madrid")
        st.text_input("Pais", key=f"{key}_pais", placeholder="España")
        return {
            "AGENTE_FRANCO_MODO": "linkedin",
            "AGENTE_FRANCO_CARGO": st.session_state.get(f"{key}_cargo", ""),
            "AGENTE_FRANCO_CIUDAD": st.session_state.get(f"{key}_ciudad", ""),
            "AGENTE_FRANCO_PAIS": st.session_state.get(f"{key}_pais", ""),
        }
    return {}


def validate_agent_params(key, params):
    required = {
        "maps": ["AGENTE_MAPS_CIUDAD", "AGENTE_MAPS_PAIS"],
        "francotirador": ["AGENTE_FRANCO_CARGO", "AGENTE_FRANCO_CIUDAD", "AGENTE_FRANCO_PAIS"],
    }
    missing = [name for name in required.get(key, []) if not params.get(name)]
    return missing


def render_agents(config, jobs):
    st.subheader("Agentes")
    if is_cloud_runtime():
        st.warning(
            "Este entorno parece Streamlit Cloud. Los agentes con Selenium quedan como jobs backend, "
            "pero pueden fallar si necesitan Chrome interactivo o login manual."
        )
    cols = st.columns(2)
    for index, (key, agent) in enumerate(AGENTS.items()):
        with cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"**{agent['title']}**")
                st.caption(agent["description"])
                status = jobs.status(key)
                running = status["running"]
                st.write("Estado:", "En ejecucion" if running else "Detenido")
                params = agent_params_form(key, config)

                left, right = st.columns(2)
                if left.button("Iniciar", key=f"start_{key}", use_container_width=True):
                    missing = validate_agent_params(key, params)
                    if missing:
                        st.warning("Faltan parametros para iniciar este agente.")
                    else:
                        ok, message = jobs.start(key, config, params)
                        (st.success if ok else st.error)(message)
                if right.button("Detener", key=f"stop_{key}", use_container_width=True):
                    ok, message = jobs.stop(key)
                    (st.success if ok else st.info)(message)

                if status.get("log"):
                    with st.expander("Ver log"):
                        st.code(jobs.log_tail(key) or "Log vacio.", language="text")


def main():
    st.set_page_config(page_title="Agente LinkedIn", page_icon="🔒", layout="wide")
    hydrate_backend_env()
    if not login():
        return

    config = load_config(get_secret)
    jobs = JobManager(st.session_state)

    top_left, top_right = st.columns([0.8, 0.2])
    top_left.title("Agente LinkedIn")
    top_left.caption(f"Panel privado de prospeccion y enriquecimiento. Usuario: {st.session_state.get('username')}")
    if top_right.button("Cerrar sesion", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.rerun()

    stats = memory_stats()
    cols = st.columns(len(stats))
    for col, (label, value) in zip(cols, stats):
        col.metric(label, value)

    tab_names = ["Maps API", "Clubes", "LinkedIn", "Importar", "Configuracion", "Herramientas", "Usuarios"]
    if config.get("show_legacy_agents"):
        tab_names.insert(0, "Agentes legacy")

    tabs = st.tabs(tab_names)
    tab_index = 0
    if config.get("show_legacy_agents"):
        with tabs[tab_index]:
            render_agents(config, jobs)
        tab_index += 1

    with tabs[tab_index]:
        render_places_api(config)
    tab_index += 1
    with tabs[tab_index]:
        render_club_batch(config)
    tab_index += 1
    with tabs[tab_index]:
        render_linkedin_targets(config)
    tab_index += 1
    with tabs[tab_index]:
        render_import(config)
    tab_index += 1
    with tabs[tab_index]:
        render_config(config)
    tab_index += 1
    with tabs[tab_index]:
        render_radar(config)
    tab_index += 1
    with tabs[tab_index]:
        render_users()


if __name__ == "__main__":
    main()
