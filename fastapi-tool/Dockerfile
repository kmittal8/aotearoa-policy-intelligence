FROM python:3.12-slim

# Install nginx and openssl (nginx terminates TLS; openssl generates dev cert)
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx openssl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user that runs uvicorn
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install Python deps (cached layer — only rebuilds when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and set ownership
COPY . .
RUN chown -R appuser:appuser /app

# Nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Startup script
RUN chmod +x /app/entrypoint.sh

# 443 = HTTPS (nginx), 8080 = direct uvicorn (health checks / internal use)
EXPOSE 443 8080

ENTRYPOINT ["/app/entrypoint.sh"]
