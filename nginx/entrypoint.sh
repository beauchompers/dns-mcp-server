#!/bin/sh
set -e

CERT_DIR="/etc/nginx/certs"
DOMAIN="${DOMAIN:-localhost}"

# Generate self-signed certs if they don't exist
if [ ! -f "$CERT_DIR/server.crt" ] || [ ! -f "$CERT_DIR/server.key" ]; then
    echo "Generating self-signed certificate for $DOMAIN..."
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -days 90 -newkey rsa:4096 \
        -keyout "$CERT_DIR/server.key" \
        -out "$CERT_DIR/server.crt" \
        -subj "/CN=$DOMAIN" \
        -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1"
    echo "WARNING: Self-signed certificate generated for development only."
    echo "Certificate generated."
fi

exec "$@"
