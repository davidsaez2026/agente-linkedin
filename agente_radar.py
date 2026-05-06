import smtplib
import dns.resolver
import socket
import time

# ==========================================
# 1. MOTOR DE PERMUTACIÓN (Generador de ideas)
# ==========================================
def generar_permutaciones(nombre, apellido, dominio):
    # Limpiamos los textos (minúsculas, sin espacios extra)
    n = nombre.lower().strip()
    a = apellido.lower().strip()
    d = dominio.lower().strip()
    
    # Quitamos espacios compuestos (ej. "de la torre" -> "delatorre")
    n = n.replace(" ", "")
    a = a.replace(" ", "")

    return [
        f"{n}@{d}",              # david@club.com
        f"{n}.{a}@{d}",          # david.saez@club.com
        f"{n[0]}{a}@{d}",        # dsaez@club.com
        f"{n[0]}.{a}@{d}",       # d.saez@club.com
        f"{n}{a[0]}@{d}",        # davids@club.com
        f"{n}_{a}@{d}",          # david_saez@club.com
        f"{n}{a}@{d}"            # davidsaez@club.com
    ]

# ==========================================
# 2. MOTOR DE VALIDACIÓN (El "Llamapuertas")
# ==========================================
def verificar_email_smtp(email):
    dominio = email.split('@')[1]
    
    try:
        # 1. Preguntamos a Internet cuál es el servidor de correo (MX) de este dominio
        registros_mx = dns.resolver.resolve(dominio, 'MX')
        servidor_correo = str(registros_mx[0].exchange)
        
        # 2. Nos conectamos al servidor
        server = smtplib.SMTP(timeout=5)
        server.set_debuglevel(0) # Ponlo en 1 si quieres ver las entrañas del servidor matrix
        server.connect(servidor_correo)
        server.helo(socket.getfqdn())
        
        # 3. Simulamos que somos un remitente cualquiera
        server.mail('contacto_prueba@gmail.com')
        
        # 4. Hacemos la pregunta clave: "¿Existe este destinatario?"
        codigo, respuesta = server.rcpt(email)
        server.quit()
        
        # El código 250 en lenguaje de servidores significa "OK / Sí existe"
        if codigo == 250:
            return True
        else:
            return False
            
    except dns.resolver.NXDOMAIN:
        print(f"   ❌ El dominio {dominio} no existe o no tiene correo.")
        return None
    except Exception as e:
        # Algunos servidores tienen escudos anti-ping (Firewalls)
        return None

# ==========================================
# 3. INTERFAZ Y ARRANQUE
# ==========================================
def iniciar_radar():
    print("\n" + "="*50)
    print("📡 RADAR B2B: DESCIFRADOR DE EMAILS CORPORATIVOS")
    print("="*50)
    
    nombre = input("👉 Nombre del objetivo (ej. David): ")
    apellido = input("👉 Apellido del objetivo (ej. Saez): ")
    dominio = input("👉 Dominio de su empresa (ej. realmadrid.com): ")
    
    print(f"\n⚙️ Generando permutaciones para {nombre} {apellido}...")
    candidatos = generar_permutaciones(nombre, apellido, dominio)
    
    print("🚀 Iniciando pinging a los servidores (esto puede tardar unos segundos)...\n")
    
    encontrado = False
    
    for email in candidatos:
        print(f"   🔎 Probando: {email}...", end=" ", flush=True)
        
        resultado = verificar_email_smtp(email)
        
        if resultado is True:
            print("✅ ¡BINGO! EMAIL VÁLIDO.")
            print("\n" + "="*50)
            print(f"🎯 EL CORREO DE CONTACTO ES: {email}")
            print("="*50 + "\n")
            encontrado = True
            break # Si lo encuentra, paramos de buscar
        elif resultado is False:
            print("❌ No existe.")
        else:
            print("🛡️ Servidor blindado (No responde).")
            
        time.sleep(1) # Pausa por cortesía con el servidor
        
    if not encontrado:
        print("\n🏁 Análisis terminado. Ninguna de las permutaciones estándar parece ser la correcta o el servidor usa un escudo Catch-All (acepta todo o bloquea todo).")

if __name__ == "__main__":
    iniciar_radar()