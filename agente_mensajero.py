import time
import requests
import random
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import openai

# ==========================================
# CONFIGURACIÓN
# ==========================================
OPENAI_API_KEY = os.getenv("AGENTE_OPENAI_API_KEY", "TU_API_KEY_DE_OPENAI")
WEBHOOK_URL = os.getenv("AGENTE_WEBHOOK_URL", "TU_URL_DE_APPS_SCRIPT")

openai.api_key = OPENAI_API_KEY

def generar_mensaje(nombre, cargo):
    prompt = f"Escribe una nota de invitación a conectar en LinkedIn (MÁX 250 caracteres) para {nombre}, que es {cargo}. Somos una escuela de Análisis de Datos y Deporte. Sé directo y profesional."
    try:
        response = openai.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content.strip()
    except:
        return f"Hola {nombre}, me gustaría conectar contigo. Un saludo."

def actualizar_estado_en_sheets(url_perfil, estado):
    payload = {"accion": "actualizar_estado", "url": url_perfil, "estado": estado}
    try:
        requests.post(WEBHOOK_URL, json=payload)
        print(f"   📝 Hoja actualizada: {estado}")
    except Exception as e:
        print(f"   ⚠️ Error actualizando hoja: {e}")

def enviar_invitacion(driver, url_perfil, mensaje):
    driver.get(url_perfil)
    time.sleep(random.uniform(5, 8))

    # Identificar grado de contacto
    try:
        # Buscamos el texto que indica el grado en la parte superior
        perfil_info = driver.find_element(By.CLASS_NAME, "pv-top-card").text
        if "1er" in perfil_info or "1st" in perfil_info:
            print("   🤝 Detectado: Ya es contacto de 1er grado.")
            actualizar_estado_en_sheets(url_perfil, "Ya es contacto")
            return False
    except:
        pass

    try:
        # Intentar conectar
        conectar_btn = None
        botones = driver.find_elements(By.TAG_NAME, "button")
        for btn in botones:
            if btn.text.strip() == "Conectar":
                conectar_btn = btn
                break
        
        if not conectar_btn:
            driver.find_element(By.XPATH, "//button[span[text()='Más']]").click()
            time.sleep(1)
            driver.find_element(By.XPATH, "//div[contains(@class, 'dropdown')]//span[text()='Conectar']").click()
        else:
            conectar_btn.click()

        time.sleep(2)
        driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Añadir una nota')]").click()
        time.sleep(1)
        driver.find_element(By.NAME, "message").send_keys(mensaje)
        time.sleep(2)

        # DESCOMENTA LA LÍNEA DE ABAJO PARA ENVIAR REALMENTE
        # driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Enviar invitación')]").click()
        
        print("   ✅ Mensaje listo en pantalla.")
        actualizar_estado_en_sheets(url_perfil, "Contactado")
        return True
    except:
        print("   ⏭️ No se pudo procesar este perfil.")
        actualizar_estado_en_sheets(url_perfil, "Fallo/Ignorado")
        return False

def iniciar_navegador():
    options = Options()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def ejecutar_mensajero():
    print("📡 Obteniendo leads de la hoja...")
    try:
        candidatos = requests.get(WEBHOOK_URL).json()
    except:
        print("❌ Error de conexión.")
        return

    if not candidatos:
        print("No hay leads pendientes.")
        return

    driver = iniciar_navegador()
    driver.get("https://www.linkedin.com/login")
    input("👉 Inicia sesión y pulsa ENTER...")

    for i, c in enumerate(candidatos):
        print(f"\n[{i+1}/{len(candidatos)}] {c['nombre']}")
        msg = generar_mensaje(c['nombre'], c['cargo'])
        enviar_invitacion(driver, c['url'], msg)
        time.sleep(random.uniform(15, 25))

    driver.quit()

if __name__ == "__main__":
    ejecutar_mensajero()
