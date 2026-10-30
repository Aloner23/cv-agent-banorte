# Imagen de producción del agente de CV (Cloud Run, o cualquier runtime de contenedores).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 \
    LOG_FORMAT=json

WORKDIR /srv

# Dependencias primero para aprovechar la caché de capas; versiones fijadas con constraints.txt.
COPY requirements.txt constraints.txt ./
RUN pip install -r requirements.txt -c constraints.txt

# Sólo lo que el servicio necesita en ejecución: código, base de conocimiento y chat web.
COPY app ./app
COPY knowledge ./knowledge
COPY web ./web

# Usuario sin privilegios.
RUN useradd --system --uid 10001 agent
USER agent

EXPOSE 8080
# Cloud Run termina TLS y sólo su front end llega al contenedor, así que se confía en sus
# encabezados X-Forwarded-* para obtener la IP real (límite de solicitudes) y el esquema https.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" \
    --proxy-headers --forwarded-allow-ips="*" --no-access-log --timeout-graceful-shutdown 8
