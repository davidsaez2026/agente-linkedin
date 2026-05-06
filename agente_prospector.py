import os
import time
import json
import random
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import openai

# ==========================================
# CONFIGURACIÓN (Rellena tus datos aquí)
# ==========================================
OPENAI_API_KEY = os.getenv("AGENTE_OPENAI_API_KEY", "TU_API_KEY_DE_OPENAI")
WEBHOOK_URL = os.getenv(
    "AGENTE_WEBHOOK_URL",
    "https://script.google.com/macros/s/AKfycbz4yUNqyKsCEmsiLDWfGjoRFEFXOL5yHwDpYxsKax17gk0koChI3xLHF8grKoRASwG3sg/exec",
)

PALABRAS_CLAVE = [
    palabra.strip()
    for palabra in os.getenv(
        "AGENTE_PALABRAS_CLAVE_LINKEDIN",
        "futbol data, analista deportivo, scouting futbol",
    ).split(",")
    if palabra.strip()
]
MAX_PAGINAS = int(os.getenv("AGENTE_MAX_PAGINAS_LINKEDIN", "3"))
ARCHIVO_MEMORIA = "visitados_linkedin.txt" # 🟢 El cerebro del bot para LinkedIn

openai.api_key = OPENAI_API_KEY

# ==========================================
# 1. FUNCIONES DE MEMORIA
# ==========================================
def cargar_memoria():
    """Lee el archivo de texto y carga las URLs ya visitadas."""
    if not os.path.exists(ARCHIVO_MEMORIA):
        return set()
    with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
        return set(f.read().splitlines())

def guardar_en_memoria(url):
    """Anota una nueva URL en el archivo para no visitarla más."""
    with open(ARCHIVO_MEMORIA, "a", encoding="utf-8") as f:
        f.write(url + "\n")

# ==========================================
# 2. FUNCIÓN: GUARDAR EN GOOGLE SHEETS
# ==========================================
def guardar_en_sheets(nombre, apellidos, url_perfil, empresa, cargo, email, telefono, palabra_clave):
    payload = {
        "nombre": nombre,
        "apellidos": apellidos,
        "url_perfil": url_perfil,
        "empresa": empresa,
        "cargo": cargo,
        "email": email,
        "telefono": telefono,
        "palabra_clave": palabra_clave 
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            resp_json = response.json()
            if resp_json.get("status") == "duplicado_ignorado":
                print(f"   ⚠️ Perfil duplicado en la hoja ignorado: {nombre}")
            else:
                print(f"   ✅ Lead guardado ({palabra_clave}): {nombre} | {cargo}")
        else:
            print(f"   ❌ Error al guardar. Código: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error de conexión con Sheets: {e}")

# ==========================================
# 3. FUNCIÓN: EXTRAER DATOS CON IA
# ==========================================
def extraer_datos_con_ia(texto_perfil, url_perfil, palabra_clave):
    prompt = f"""
    Eres un asistente experto en extracción de datos de LinkedIn.
    Extrae: Nombre, Apellidos, Empresa actual, Cargo actual, Email y Teléfono.
    Si no hay email o teléfono, devuelve "".
    Devuelve ÚNICAMENTE un JSON válido con las claves: "nombre", "apellidos", "empresa", "cargo", "email", "telefono".
    
    Texto del perfil:
    {texto_perfil}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" } 
        )
        
        datos = json.loads(response.choices[0].message.content)
        
        guardar_en_sheets(
            datos.get("nombre", ""),
            datos.get("apellidos", ""),
            url_perfil,
            datos.get("empresa", ""),
            datos.get("cargo", ""),
            datos.get("email", ""),
            datos.get("telefono", ""),
            palabra_clave 
        )
        return True # Indicamos que la extracción fue un éxito
            
    except Exception as e:
        print(f"   ⚠️ Error IA: {e}")
        return False # Indicamos fallo

# ==========================================
# 4. NAVEGADOR Y BUCLE MULTI-BÚSQUEDA
# ==========================================
def iniciar_navegador():
    options = Options()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def prospectar_linkedin():
    driver = iniciar_navegador()
    memoria_urls = cargar_memoria() # 🟢 Cargamos la memoria al arrancar
    
    print(f"🧠 Memoria cargada: {len(memoria_urls)} perfiles de LinkedIn ya visitados históricamente.")
    
    driver.get("https://www.linkedin.com/login")
    print("\n" + "="*50)
    print("Inicia sesión manualmente en Chrome.")
    input("👉 Presiona ENTER aquí cuando estés dentro de LinkedIn... ")
    print("="*50 + "\n")
    
    for termino in PALABRAS_CLAVE:
        print(f"\n🚀 === INICIANDO BÚSQUEDA PARA: '{termino.upper()}' ===")
        
        for pagina in range(1, MAX_PAGINAS + 1):
            print(f"\n📄 --- PÁGINA {pagina} DE {MAX_PAGINAS} ('{termino}') ---")
            
            termino_url = termino.replace(" ", "%20")
            url_busqueda = f"https://www.linkedin.com/search/results/people/?keywords={termino_url}&page={pagina}"
            driver.get(url_busqueda)
            time.sleep(random.uniform(4, 6))
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Extraemos todos los enlaces de la página de resultados
            enlaces = driver.find_elements(By.XPATH, "//a[contains(@href, 'https://www.linkedin.com/in/')]")
            urls_extraidas = list(set([enlace.get_attribute("href").split('?')[0] for enlace in enlaces]))
            
            # 🟢 Filtramos la lista: Solo nos quedamos con los que NO están en la memoria
            urls_nuevas = [url for url in urls_extraidas if url not in memoria_urls]
            
            print(f"🔍 Encontrados {len(urls_extraidas)} perfiles en la página.")
            print(f"🛡️ Descartados {len(urls_extraidas) - len(urls_nuevas)} por estar ya en memoria. Procesando {len(urls_nuevas)} perfiles nuevos.")
            
            for url in urls_nuevas:
                driver.get(url)
                time.sleep(random.uniform(4, 7)) 
                
                try:
                    btn_contacto = driver.find_element(By.ID, "top-card-text-details-contact-info")
                    btn_contacto.click()
                    time.sleep(random.uniform(2, 4))
                except:
                    pass 
                
                texto_pagina = driver.find_element(By.TAG_NAME, "body").text
                exito = extraer_datos_con_ia(texto_pagina, url, termino) 
                
                # 🟢 Si logramos extraer y enviar el dato, lo guardamos para siempre en la memoria
                if exito:
                    guardar_en_memoria(url)
                    memoria_urls.add(url)
                
                tiempo_espera = random.uniform(5, 9)
                time.sleep(tiempo_espera)
                
    print("\n✅ Proceso de prospección total finalizado.")
    driver.quit()

if __name__ == "__main__":
    prospectar_linkedin()
