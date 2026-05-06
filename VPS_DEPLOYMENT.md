# Despliegue en VPS

Esta es la opcion recomendada si quieres una app web estable, repo privado, dominio propio y control total.

## Requisitos

En el VPS:

- Docker
- Docker Compose
- Git
- Un dominio apuntando al servidor, opcional pero recomendado

## 1. Subir o clonar el proyecto

En el VPS:

```bash
git clone https://github.com/davidsaez2026/agente-linkedin.git
cd agente-linkedin
```

Si el repo es privado, usa una deploy key o autentica GitHub en el servidor.

## 2. Configurar variables

```bash
cp .env.example .env
nano .env
```

Rellena al menos:

```text
APP_USERNAME=admin
APP_PASSWORD=una-contrasena-segura
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=tu-service-role-key
SUPABASE_USERS_TABLE=app_users
```

Si no usas Supabase, la app guardara usuarios en `./data/users.db`.

## 3. Arrancar

```bash
docker compose up -d --build
```

Ver logs:

```bash
docker compose logs -f
```

La app quedara disponible en:

```text
http://IP_DEL_SERVIDOR:8501
```

## 4. Dominio y HTTPS

Recomendado: poner Nginx o Caddy delante y exponer la app en `https://tudominio.com`.

Con Caddy, ejemplo de `Caddyfile`:

```text
tudominio.com {
    reverse_proxy 127.0.0.1:8501
}
```

Caddy gestiona HTTPS automaticamente.

## 5. Actualizar la app

```bash
git pull
docker compose up -d --build
```

## 6. Volver el repo a privado

En VPS no necesitas que el repo sea publico. Puedes hacerlo privado y desplegar con:

- Deploy key de GitHub
- Token personal de solo lectura
- GitHub CLI autenticado
- Subida manual por `scp` o `rsync`
