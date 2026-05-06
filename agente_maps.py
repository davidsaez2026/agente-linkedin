import os
import time
import re
import random
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
WEBHOOK_URL = os.getenv(
    "AGENTE_WEBHOOK_URL",
    "https://script.google.com/macros/s/AKfycbz4yUNqyKsCEmsiLDWfGjoRFEFXOL5yHwDpYxsKax17gk0koChI3xLHF8grKoRASwG3sg/exec",
)
BUSQUEDA = os.getenv("AGENTE_BUSQUEDA_MAPS", "Fútbol Club")
OBJETIVO_TOTAL_SESION = int(os.getenv("AGENTE_OBJETIVO_SESION", "10"))

ARCHIVO_MEMORIA_URLS = "visitados_maps.txt" 
ARCHIVO_HISTORIAL_ZONAS = "zonas_completadas.txt" 

# ==========================================
# 1. FUNCIONES COMPARTIDAS (MEMORIA Y GUARDADO)
# ==========================================
def cargar_memoria(archivo):
    if not os.path.exists(archivo): return set()
    with open(archivo, "r", encoding="utf-8") as f:
        return set(f.read().splitlines())

def guardar_memoria(archivo, dato):
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(str(dato) + "\n")

def buscar_emails_en_web(driver, url_web):
    if not url_web or any(x in url_web for x in ["google", "facebook", "instagram"]): return ""
    try:
        driver.get(url_web)
        time.sleep(4)
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', driver.page_source)
        return ", ".join(list(set([e for e in emails if not e.endswith(('.png', '.jpg', '.gif', '.webp'))]))[:2]) 
    except: return ""

def guardar_en_sheets(nombre, web, telefono, email, zona, pais):
    payload = {
        "nombre": nombre, "apellidos": "Institución", "url_perfil": web,
        "empresa": nombre, "cargo": "Club/Entidad", "email": email,
        "telefono": telefono, "palabra_clave": f"Maps: {BUSQUEDA}", 
        "ciudad": zona, "pais": pais
    }
    try:
        requests.post(WEBHOOK_URL, json=payload)
        return True
    except: return False

# ==========================================
# 2. EL MOTOR DE EXTRACCIÓN (NÚCLEO)
# ==========================================
# Esta función es el "taladro". Da igual si le mandas una ciudad o unas coordenadas,
# ella entra a Maps, hace scroll y extrae.
def extraer_zona(driver, url_busqueda, nombre_zona, nombre_pais, memoria_urls, total_nuevos):
    print(f"\n🌍 === EXPLORANDO: {nombre_zona.upper()} ===")
    driver.get(url_busqueda)
    time.sleep(5)

    try:
        for b in driver.find_elements(By.TAG_NAME, "button"):
            if "aceptar" in b.text.lower() or "rechazar" in b.text.lower():
                b.click(); time.sleep(2); break
    except: pass

    urls_extraidas = []
    intentos_scroll = 0
    while len(urls_extraidas) < (OBJETIVO_TOTAL_SESION - total_nuevos) and intentos_scroll < 6:
        enlaces = driver.find_elements(By.XPATH, "//a[contains(@href, '/maps/place/')]")
        nuevos = 0
        for e in enlaces:
            u = e.get_attribute("href")
            if u and u not in memoria_urls and u not in urls_extraidas:
                urls_extraidas.append(u); nuevos += 1
        
        if nuevos == 0: intentos_scroll += 1
        else: intentos_scroll = 0
        
        if enlaces:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", enlaces[-1])
                time.sleep(3)
            except: break

    if not urls_extraidas:
        print(f"   🏁 Zona agotada o sin resultados nuevos.")
        return total_nuevos, True # Devuelve True indicando que la zona está completada

    for url in urls_extraidas:
        if total_nuevos >= OBJETIVO_TOTAL_SESION: break
        try:
            driver.get(url); time.sleep(random.uniform(3, 5))
            try: nombre = driver.find_element(By.XPATH, "//h1").text
            except: nombre = "Desconocido"
            
            try: tel = driver.find_element(By.XPATH, "//button[contains(@data-item-id, 'phone:')]").get_attribute("aria-label").replace("Teléfono: ", "")
            except: tel = ""
            
            try: web = driver.find_element(By.XPATH, "//a[contains(@data-item-id, 'authority')]").get_attribute("href")
            except: web = ""

            email = buscar_emails_en_web(driver, web) if web else ""

            if guardar_en_sheets(nombre, web, tel, email, nombre_zona, nombre_pais):
                total_nuevos += 1
                guardar_memoria(ARCHIVO_MEMORIA_URLS, url); memoria_urls.add(url)
                print(f"   ✅ [{total_nuevos}/{OBJETIVO_TOTAL_SESION}] {nombre}")
        except: continue
        
    zona_completada = (total_nuevos < OBJETIVO_TOTAL_SESION)
    return total_nuevos, zona_completada

# ==========================================
# 3. LOS TRES MODOS DE ATAQUE
# ==========================================

def modo_diccionario(driver, memoria_urls, zonas_completadas, diccionario=None):
    diccionario = diccionario or {"España": ["Madrid", "Barcelona"], "Mexico": ["Monterrey"]}
    total = 0
    for pais, ciudades in diccionario.items():
        for ciudad in ciudades:
            if ciudad in zonas_completadas: continue
            if total >= OBJETIVO_TOTAL_SESION: return
            
            url = f"https://www.google.es/maps/search/{BUSQUEDA.replace(' ', '+')}+en+{ciudad.replace(' ', '+')},+{pais.replace(' ', '+')}"
            total, completada = extraer_zona(driver, url, ciudad, pais, memoria_urls, total)
            if completada: guardar_memoria(ARCHIVO_HISTORIAL_ZONAS, ciudad)

def modo_auto_api(driver, memoria_urls, zonas_completadas, pais=None):
    pais = pais or input("👉 Escribe el país que quieres atacar (ej. Colombia): ")
    print(f"📡 Conectando a OpenStreetMap para descargar ciudades de {pais}...")
    
    # Usamos una API pública gratuita para sacar ciudades
    url_api = f"https://nominatim.openstreetmap.org/search?country={pais}&format=json&featuretype=city"
    headers = {'User-Agent': 'BotProspeccion/1.0'}
    
    try:
        respuesta = requests.get(url_api, headers=headers).json()
        ciudades = list(set([item['name'] for item in respuesta if 'name' in item]))
        print(f"🎯 ¡Descarga completada! {len(ciudades)} ciudades encontradas.")
    except:
        print("❌ Error al conectar con la API. Prueba con otro país o revisa tu conexión.")
        return

    total = 0
    for ciudad in ciudades:
        if ciudad in zonas_completadas: continue
        if total >= OBJETIVO_TOTAL_SESION: return
        
        url = f"https://www.google.es/maps/search/{BUSQUEDA.replace(' ', '+')}+en+{ciudad.replace(' ', '+')},+{pais.replace(' ', '+')}"
        total, completada = extraer_zona(driver, url, ciudad, pais, memoria_urls, total)
        if completada: guardar_memoria(ARCHIVO_HISTORIAL_ZONAS, ciudad)

def modo_satelite(driver, memoria_urls, zonas_completadas, lat=None, lon=None):
    print("🛰️ MODO SATÉLITE: Búsqueda por coordenadas GPS.")
    lat = float(lat if lat is not None else input("👉 Latitud central (ej. 40.4167): "))
    lon = float(lon if lon is not None else input("👉 Longitud central (ej. -3.7032): "))
    
    # Generamos una mini cuadrícula de 5 puntos
    coordenadas = [
        (lat, lon), (lat+0.1, lon), (lat-0.1, lon), (lat, lon+0.1), (lat, lon-0.1)
    ]
    
    total = 0
    pais = "Coordenadas"
    for c in coordenadas:
        if total >= OBJETIVO_TOTAL_SESION: return
        zona_nombre = f"{c[0]},{c[1]}"
        if zona_nombre in zonas_completadas: continue
        
        url = f"https://www.google.es/maps/search/{BUSQUEDA.replace(' ', '+')}/@{c[0]},{c[1]},12z"
        total, completada = extraer_zona(driver, url, zona_nombre, pais, memoria_urls, total)
        if completada: guardar_memoria(ARCHIVO_HISTORIAL_ZONAS, zona_nombre)

# ==========================================
# 4. EL MENÚ MAESTRO
# ==========================================
def iniciar_navegador():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def menu_principal():
    print("\n" + "="*40)
    print("🚀 CENTRO DE MANDO: AGENTE TRIDENTE 🚀")
    print("="*40)
    print("1. Modo Diccionario (Rápido y controlado)")
    print("2. Modo Auto-API (Descarga países enteros)")
    print("3. Modo Satélite (Barrido GPS para zonas rurales)")
    print("="*40)
    
    opcion = input("👉 Elige tu estrategia (1, 2 o 3): ")
    
    if opcion not in ["1", "2", "3"]:
        print("❌ Opción no válida. Cerrando sistema.")
        return

    memoria_urls = cargar_memoria(ARCHIVO_MEMORIA_URLS)
    zonas_completadas = cargar_memoria(ARCHIVO_HISTORIAL_ZONAS)
    
    driver = iniciar_navegador()

    if opcion == "1":
        modo_diccionario(driver, memoria_urls, zonas_completadas)
    elif opcion == "2":
        modo_auto_api(driver, memoria_urls, zonas_completadas)
    elif opcion == "3":
        modo_satelite(driver, memoria_urls, zonas_completadas)

    print("\n✅ Misión Tridente Finalizada.")
    driver.quit()

def ejecutar_desde_entorno():
    modo = os.getenv("AGENTE_MAPS_MODO", "").strip().lower()
    if not modo:
        return False

    memoria_urls = cargar_memoria(ARCHIVO_MEMORIA_URLS)
    zonas_completadas = cargar_memoria(ARCHIVO_HISTORIAL_ZONAS)
    driver = iniciar_navegador()
    try:
        if modo == "basico":
            ciudad = os.getenv("AGENTE_MAPS_CIUDAD", "").strip()
            pais = os.getenv("AGENTE_MAPS_PAIS", "").strip()
            if not ciudad or not pais:
                raise ValueError("AGENTE_MAPS_CIUDAD y AGENTE_MAPS_PAIS son obligatorios.")
            modo_diccionario(driver, memoria_urls, zonas_completadas, {pais: [ciudad]})
        elif modo == "auto_api":
            modo_auto_api(driver, memoria_urls, zonas_completadas, os.getenv("AGENTE_MAPS_PAIS", "").strip())
        elif modo == "satelite":
            modo_satelite(
                driver,
                memoria_urls,
                zonas_completadas,
                os.getenv("AGENTE_MAPS_LAT"),
                os.getenv("AGENTE_MAPS_LON"),
            )
        else:
            raise ValueError(f"Modo Maps no reconocido: {modo}")
    finally:
        driver.quit()
    print("\n✅ Misión Tridente Finalizada.")
    return True

if __name__ == "__main__":
    if not ejecutar_desde_entorno():
        menu_principal()
