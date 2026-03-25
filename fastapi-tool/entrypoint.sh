#!/bin/bash
# Entrypoint: generate self-signed cert → start uvicorn → start nginx
set -e

SSL_DIR=/etc/nginx/ssl
CERT="${SSL_DIR}/server.crt"
KEY="${SSL_DIR}/server.key"

# Generate self-signed cert once (replace with real cert by mounting over these paths)
mkdir -p "${SSL_DIR}"
if [ ! -f "${CERT}" ]; then
    echo "[entrypoint] Generating self-signed TLS certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "${KEY}" \
        -out "${CERT}" \
        -subj "/CN=aotearoa-pi/O=Oracle/C=AU" 2>/dev/null
    chmod 600 "${KEY}"
    echo "[entrypoint] Certificate written to ${CERT}"
fi

# Start uvicorn (4 workers) as appuser, bound to loopback only
echo "[entrypoint] Starting uvicorn (4 workers) on 127.0.0.1:8080..."
su -s /bin/sh appuser -c \
    "cd /app && uvicorn main:app --host 127.0.0.1 --port 8080 --workers 4" &

# Give uvicorn a moment to bind before nginx starts accepting traffic
sleep 2

# Start nginx in foreground (PID 1 heir — receives Docker signals)
echo "[entrypoint] Starting nginx (HTTPS :443)..."
exec nginx -g 'daemon off;'
