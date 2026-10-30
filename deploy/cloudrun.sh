#!/usr/bin/env bash
# Despliega el agente de CV en Google Cloud Run con las claves en Secret Manager.
# Pensado para correr en Cloud Shell desde la raíz del repo:
#   PROJECT_ID=mi-proyecto ./deploy/cloudrun.sh
# Es idempotente: se puede volver a correr para publicar una versión nueva.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-carlos-cv-agent}"
SA_NAME="${SA_NAME:-cv-agent-runtime}"
LLM_MODEL="${LLM_MODEL:-gemini-3.5-flash-lite}"

[[ -n "$PROJECT_ID" ]] || { echo "Define PROJECT_ID (gcloud config set project <id>)"; exit 1; }
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud config set project "$PROJECT_ID" >/dev/null

echo "==> Habilitando APIs (Cloud Run, Cloud Build, Artifact Registry, Secret Manager)"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com

echo "==> Cuenta de servicio de ejecución con privilegios mínimos: $SA_EMAIL"
gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --display-name "CV agent runtime"

ensure_secret() {  # $1 = nombre del secreto, $2 = texto del prompt
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    echo "    secreto '$1' ya existe (para rotarlo: gcloud secrets versions add $1 --data-file=-)"
  else
    read -r -s -p "$2: " value; echo
    [[ -n "$value" ]] || { echo "Valor vacío para $1"; exit 1; }
    printf '%s' "$value" | gcloud secrets create "$1" --replication-policy=automatic --data-file=-
    unset value
  fi
  gcloud secrets add-iam-policy-binding "$1" --member "serviceAccount:$SA_EMAIL" \
    --role roles/secretmanager.secretAccessor >/dev/null
}
echo "==> Secretos en Secret Manager (no se escriben en disco ni en el historial)"
ensure_secret gemini-api-key "Pega tu GEMINI_API_KEY"
ensure_secret agent-api-key  "Pega tu AGENT_API_KEY (la clave Bearer del agente)"

echo "==> Construyendo y desplegando con Cloud Build -> Cloud Run ($REGION)"
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --service-account "$SA_EMAIL" \
  --allow-unauthenticated \
  --cpu 1 --memory 512Mi \
  --concurrency 20 --min-instances 0 --max-instances 3 \
  --timeout 120 \
  --set-env-vars "LLM_PROVIDER=gemini,LLM_MODEL=${LLM_MODEL},KNOWLEDGE_MODE=full,MAX_HISTORY_TURNS=30,MAX_HISTORY_CHARS=40000,GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest,AGENT_API_KEY=agent-api-key:latest"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')"
gcloud run services update "$SERVICE" --region "$REGION" --update-env-vars "PUBLIC_BASE_URL=${URL}" >/dev/null

echo
echo "Listo: $URL"
echo "  Salud:            $URL/health"
echo "  Tarjeta A2A:      $URL/.well-known/agent-card.json"
echo "  URL base (reto):  $URL/v1"
curl -fsS "$URL/health" && echo
