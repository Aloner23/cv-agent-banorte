# Despliegue en Google Cloud Run

El mismo código que corre en Render se publica como contenedor en Cloud Run. Render sigue siendo la vía más simple; Cloud Run muestra cómo operaría el agente en una nube empresarial: imagen reproducible, secretos gestionados, identidad de mínimo privilegio, escalado automático y observabilidad nativa.

## Arquitectura

```
 Plataforma del reto / chat web
        │  HTTPS · Authorization: Bearer
        ▼
 Cloud Run (servicio carlos-cv-agent, us-central1)
   ├─ contenedor python:3.12-slim, usuario sin privilegios (uid 10001)
   ├─ 0–3 instancias, 20 solicitudes concurrentes por instancia, 512 MiB
   ├─ variables: proveedor, modelo, límites
   └─ secretos montados como variables ◀── Secret Manager
          gemini-api-key, agent-api-key        (sólo los lee la cuenta de servicio)
        │
        ├──▶ Gemini API (generativelanguage.googleapis.com)
        └──▶ Cloud Logging / Cloud Trace (logs JSON, X-Cloud-Trace-Context)
```

## Decisiones

| Decisión | Por qué | Costo o límite |
|---|---|---|
| `gcloud run deploy --source .` con el `Dockerfile` del repo | Un comando construye en Cloud Build, guarda la imagen en Artifact Registry y despliega; el mismo `Dockerfile` sirve fuera de Google | La primera construcción tarda unos minutos |
| Claves en **Secret Manager** | No quedan en variables planas, en la consola ni en el historial; se rotan agregando una versión | Hay que dar acceso explícito a la cuenta de servicio |
| Cuenta de servicio `cv-agent-runtime` | La cuenta por defecto de Compute tiene permisos de editor; ésta sólo lee dos secretos | Un paso más en el despliegue |
| `--allow-unauthenticated` + Bearer en la aplicación | La plataforma del reto llama con un token Bearer propio, no con identidad de Google; IAM de Cloud Run lo rechazaría | La protección depende de la clave del agente y del límite por IP |
| `min-instances 0`, `max-instances 3` | Costo cero sin tráfico y techo de gasto ante abuso | Arranque en frío de unos segundos (mucho menor que el plan gratuito de Render) |
| `concurrency 20`, `timeout 120 s` | El trabajo es esperar al modelo (E/S), no CPU; el timeout supera los 90 s internos | — |
| Logs JSON con `severity`, `httpRequest` y trace | Cloud Logging los indexa sin agentes extra; se filtra por `request_id`, estado, latencia o tokens | Las métricas de `/metrics` son por instancia |
| Región `us-central1` | Capa gratuita de Cloud Run y cercanía razonable a México | Se cambia con `REGION=` |

## Pasos (Cloud Shell)

1. Abrir [Cloud Shell](https://shell.cloud.google.com) con la cuenta que tiene facturación activa.
2. Seleccionar o crear el proyecto:
   ```bash
   gcloud projects create carlos-cv-agent-<sufijo>      # opcional, si no existe
   gcloud config set project <PROJECT_ID>
   gcloud billing projects describe <PROJECT_ID>         # billingEnabled: true
   ```
3. Clonar y desplegar:
   ```bash
   git clone https://github.com/Aloner23/cv-agent-banorte && cd cv-agent-banorte
   ./deploy/cloudrun.sh
   ```
   El script habilita las APIs, crea la cuenta de servicio, pide **una sola vez** las dos claves (sin mostrarlas) y despliega. Es idempotente: volver a correrlo publica una versión nueva.
4. Registrar en la plataforma del reto la URL base `https://<servicio>.run.app/v1` y la clave del agente, o importar la tarjeta desde `https://<servicio>.run.app`.

## Verificación

```bash
URL=$(gcloud run services describe carlos-cv-agent --region us-central1 --format 'value(status.url)')
curl -s $URL/health
curl -s $URL/.well-known/agent-card.json | head -c 300
read -rs KEY; curl -s $URL/v1/responses -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"input":"¿Qué proyectos de IA has construido?"}' | python3 -m json.tool | head -40
curl -s -H "Authorization: Bearer $KEY" $URL/metrics | python3 -m json.tool
```

## Operación

- **Logs:** Cloud Logging → filtro `resource.type="cloud_run_revision" jsonPayload.message="response"`; campos `status`, `ms`, `ttft_ms`, `input_tokens`, `output_tokens`, `flags`, `request_id`.
- **Errores:** `severity>=WARNING`; `jsonPayload.error_code` distingue cuota del proveedor (`provider_rate_limit`), timeout y fallos de modelo.
- **Métricas agregadas:** Cloud Monitoring ya trae solicitudes, latencia, instancias y errores 5xx del servicio; se pueden crear métricas basadas en logs para tokens o guardrails.
- **Rotar claves:** `printf '%s' "$NUEVA" | gcloud secrets versions add agent-api-key --data-file=-` y redeplegar (`./deploy/cloudrun.sh`).
- **Volver a una versión anterior:** `gcloud run services update-traffic carlos-cv-agent --region us-central1 --to-revisions <revision>=100`.
- **Apagar:** `gcloud run services delete carlos-cv-agent --region us-central1`.

## Límites

- El historial para `previous_response_id` vive en memoria de cada instancia: con varias instancias o tras escalar a cero puede no encontrarse. Para la plataforma se usa **reproducción de transcripción**, que no depende de ese estado. Para persistirlo, el siguiente paso sería Firestore o Memorystore.
- `/metrics` refleja sólo la instancia que atiende; la vista global está en Cloud Monitoring.
- No es una arquitectura certificada para producción bancaria: faltan, por ejemplo, red privada (VPC-SC), WAF/Cloud Armor y gestión de identidades corporativa.
