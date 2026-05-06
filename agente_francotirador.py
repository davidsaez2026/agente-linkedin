import os, time, re, random, requests, json
import urllib.parse
import smtplib, socket
import dns.resolver
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# CONFIGURACIÓN MAESTRA
# ==========================================
WEBHOOK_URL = os.getenv(
    "AGENTE_WEBHOOK_URL",
    "https://script.google.com/macros/s/AKfycbz4yUNqyKsCEmsiLDWfGjoRFEFXOL5yHwDpYxsKax17gk0koChI3xLHF8grKoRASwG3sg/exec",
)
OBJETIVO_SESION = int(os.getenv("AGENTE_OBJETIVO_SESION", "50"))
ARCHIVO_MEMORIA_URLS = "visitados_maestro.txt"

# ==========================================
# 1. UTILIDADES Y MEMORIA
# ==========================================
def cargar_memoria(archivo):
    if not os.path.exists(archivo): return set()
    with open(archivo, "r", encoding="utf-8") as f: return set(f.read().splitlines())

def guardar_memoria(archivo, dato):
    with open(archivo, "a", encoding="utf-8") as f: f.write(str(dato) + "\n")

def matar_cookies(driver):
    try:
        botones = driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.XPATH, "//div[@role='button']")
        for b in botones:
            if b.is_displayed() and ("aceptar" in b.text.lower() or "accept" in b.text.lower()):
                b.click(); time.sleep(1); return True
    except: pass
    return False

def enviar_a_sheets(nombre, apellidos, url, empresa, cargo, email, ciudad, pais, etiqueta):
    payload = {"nombre": nombre, "apellidos": apellidos, "url_perfil": url, "empresa": empresa, "cargo": cargo, "email": email, "telefono": "", "palabra_clave": etiqueta, "ciudad": ciudad, "pais": pais}
    try: 
        requests.post(WEBHOOK_URL, json=payload); return True
    except: return False

# ==========================================
# 2. MOTOR GOOGLE MAPS (OPCIONES 1, 2, 3)
# ==========================================
def modo_maps_basico(driver, memoria, busqueda=None, ciudad=None, pais=None):
    busqueda = busqueda or input("👉 Qué buscas en Maps (ej: club de futbol): ")
    ciudad = ciudad or input("👉 Ciudad: ")
    pais = pais or input("👉 País: ")
    
    query = urllib.parse.quote(f"{busqueda} en {ciudad}")
    driver.get(f"https://www.google.com/maps/search/{query}")
    time.sleep(5)
    matar_cookies(driver)
    
    print(f"🌍 Extrayendo entidades en {ciudad}...")
    # Lógica de scroll y captura de Maps
    resultados = driver.find_elements(By.CLASS_NAME, "hf713d") 
    total = 0
    for res in resultados:
        if total >= OBJETIVO_SESION: break
        try:
            nombre = res.get_attribute("aria-label")
            if nombre not in memoria:
                if enviar_a_sheets(nombre, "", "Google Maps", nombre, "Entidad", "", ciudad, pais, "Maps"):
                    total += 1
                    guardar_memoria(ARCHIVO_MEMORIA_URLS, nombre)
                    print(f"   ✅ Maps: {nombre}")
        except: continue

# ==========================================
# 3. MOTOR INFILTRADO LINKEDIN (OPCIÓN 4)
# ==========================================
def extraer_datos_reales_linkedin(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(random.uniform(5, 7))
        matar_cookies(driver)
        
        keywords = ["club", "futbol", "soccer", "real", "atletico", "fc", "cf", "sd", "ud", "ad", "deportivo", "academia", "juvenil", "cantera"]
        empresa = "Perfil Profesional"
        
        try:
            headline = driver.find_element(By.CSS_SELECTOR, "h2.top-card-layout__headline").text
            if " en " in headline.lower(): empresa = headline.split(" en ")[-1]
            elif " at " in headline.lower(): empresa = headline.split(" at ")[-1]
            else: empresa = headline
        except: pass

        try:
            bloques = driver.find_elements(By.CSS_SELECTOR, "section.experience-section li, .experience-item, .profile-section-card")
            for bloque in bloques:
                txt = bloque.text
                if any(k in txt.lower() for k in keywords):
                    lineas = txt.split("\n")
                    if len(lineas) > 1: empresa = lineas[1]; break
        except: pass

        empresa = empresa.strip().split(" · ")[0].split(" - ")[0].split("(")[0].strip()
        return empresa if len(empresa) > 2 and "linkedin" not in empresa.lower() else "Perfil Profesional"
    except: return "Perfil Profesional"

def modo_francotirador(driver, memoria_urls, cargo=None, ciudad=None, pais=None, interactive=True):
    cargo = cargo or input("👉 Cargo: ")
    ciudad = ciudad or input("👉 Ciudad: ")
    pais = pais or input("👉 País: ")
    driver.get("https://www.google.es"); time.sleep(2); matar_cookies(driver)
    dork = f'site:linkedin.com/in/ {cargo} {ciudad}'
    
    total = 0
    for offset in range(0, 100, 10): 
        if total >= OBJETIVO_SESION: break
        print(f"📄 --- PÁGINA {(offset // 10) + 1} ---")
        driver.get(f"https://www.google.es/search?q={urllib.parse.quote_plus(dork)}&start={offset}")
        time.sleep(random.uniform(5, 8))
        
        if "sorry/index" in driver.current_url:
            print("🚨 CAPTCHA detectado.")
            if interactive:
                input("Resuélvelo en el navegador y pulsa ENTER al terminar...")
            else:
                print("Ejecucion no interactiva detenida por CAPTCHA.")
                return

        resultados = driver.find_elements(By.CSS_SELECTOR, "div.g")
        for res in resultados:
            try:
                link = res.find_element(By.TAG_NAME, "a").get_attribute("href")
                if "linkedin.com/in/" in link and link not in memoria_urls:
                    nombre_h3 = res.find_element(By.TAG_NAME, "h3").text.split(" - ")[0].split(" | ")[0].strip()
                    print(f"🕵️  Analizando: {nombre_h3}...", end=" ", flush=True)
                    emp_real = extraer_datos_reales_linkedin(driver, link)
                    
                    p_n = nombre_h3.split(" ", 1)
                    n = p_n[0]; a = p_n[1] if len(p_n) > 1 else ""

                    if enviar_a_sheets(n, a, link, emp_real, cargo.title(), "", ciudad, pais, "Francotirador"):
                        total += 1; guardar_memoria(ARCHIVO_MEMORIA_URLS, link); memoria_urls.add(link)
                        print(f"✅ [{emp_real}]")
                    time.sleep(random.uniform(3, 5))
            except: continue

# ==========================================
# 4. MOTOR RADAR SMTP (OPCIÓN 5)
# ==========================================
def modo_radar_masivo(driver):
    print("\n📡 CONECTANDO A SHEETS..."); r = requests.get(WEBHOOK_URL).json()
    leads = [L for L in r if not L.get('email') and L.get('empresa') != 'Perfil Profesional']
    if not leads: print("✅ Nada que enriquecer."); return
    # (Aquí va la lógica SMTP que ya tienes configurada)
    print(f"🎯 Encontrados {len(leads)} perfiles para validar.")

# ==========================================
# 5. MENÚ PRINCIPAL
# ==========================================
def iniciar_navegador():
    opt = Options(); opt.add_argument("--start-maximized")
    opt.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    opt.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opt)

def main():
    while True:
        print("\n" + "="*40 + "\n🚀 AGENTE MAESTRO: SISTEMA INTEGRADO\n" + "="*40)
        print("1. Maps: Diccionario Manual\n2. Maps: Auto-API\n3. Maps: Satélite\n4. Francotirador: LinkedIn\n5. Radar: Enriquecer Emails\n0. Salir")
        print("="*40)
        op = input("👉 Elige: ")
        if op == "0": break
        if op not in ["1","2","3","4","5"]: continue
        
        driver = iniciar_navegador(); memoria = cargar_memoria(ARCHIVO_MEMORIA_URLS)
        if op in ["1","2","3"]: modo_maps_basico(driver, memoria)
        elif op == "4": modo_francotirador(driver, memoria)
        elif op == "5": modo_radar_masivo(driver)
        driver.quit()

def ejecutar_desde_entorno():
    modo = os.getenv("AGENTE_FRANCO_MODO", "").strip().lower()
    cargo = os.getenv("AGENTE_FRANCO_CARGO", "").strip()
    ciudad = os.getenv("AGENTE_FRANCO_CIUDAD", "").strip()
    pais = os.getenv("AGENTE_FRANCO_PAIS", "").strip()
    if not modo and not any([cargo, ciudad, pais]):
        return False
    if not all([cargo, ciudad, pais]):
        raise ValueError("AGENTE_FRANCO_CARGO, AGENTE_FRANCO_CIUDAD y AGENTE_FRANCO_PAIS son obligatorios.")

    driver = iniciar_navegador()
    try:
        memoria = cargar_memoria(ARCHIVO_MEMORIA_URLS)
        modo_francotirador(driver, memoria, cargo, ciudad, pais, interactive=False)
    finally:
        driver.quit()
    return True

if __name__ == "__main__":
    if not ejecutar_desde_entorno():
        main()
