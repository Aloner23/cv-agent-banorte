#!/usr/bin/env bash
# Ejecutar desde la raíz del repo, después de revisar costos, permisos y proyecto.
set -euo pipefail
: "${PROJECT_ID:?Define PROJECT_ID explícitamente}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-carlos-cv-agent}"
DATABASE="${FIRESTORE_DATABASE:-cv-agent}"
SA_NAME="${SA_NAME:-cv-agent-runtime}"
LLM_MODEL="${LLM_MODEL:-gemini-3.5-flash-lite}"
PROJECT_ID="$(gcloud projects describe "$PROJECT_ID" --format='value(projectId)')"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
REVISION="$(git rev-parse HEAD)"
[[ -z "$(git status --porcelain)" ]] || { echo 'Publica un commit limpio antes de desplegar.'; exit 1; }
[[ "$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)')" == 'True' ]] || { echo 'El proyecto necesita facturación habilitada.'; exit 1; }
echo "Proyecto: $PROJECT_ID; servicio: $SERVICE; región: $REGION; revisión: $REVISION"
# No modificar la configuración global de gcloud.
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com firestore.googleapis.com logging.googleapis.com monitoring.googleapis.com --project "$PROJECT_ID"
gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --display-name 'CV agent runtime' --project "$PROJECT_ID"
ensure_secret() {
  if ! gcloud secrets describe "$1" --project "$PROJECT_ID" >/dev/null 2>&1; then
    read -r -s -p "$2: " secret_value; echo
    [[ -n "$secret_value" ]] || { echo 'El secreto no puede estar vacío.'; exit 1; }
    printf '%s' "$secret_value" | gcloud secrets create "$1" --project "$PROJECT_ID" --replication-policy=automatic --data-file=-
    unset secret_value
  fi
  gcloud secrets add-iam-policy-binding "$1" --project "$PROJECT_ID" \
    --member "serviceAccount:$SA_EMAIL" --role roles/secretmanager.secretAccessor >/dev/null
}
ensure_secret cv-agent-gemini-key 'GEMINI_API_KEY'
ensure_secret cv-agent-access-key 'AGENT_API_KEY'
# Fijar versiones numéricas: rollback reproducible sin depender de latest.
GEMINI_VERSION="$(gcloud secrets versions list cv-agent-gemini-key --project "$PROJECT_ID" --filter='state=ENABLED' --sort-by='~createTime' --limit=1 --format='value(name)')"
AGENT_VERSION="$(gcloud secrets versions list cv-agent-access-key --project "$PROJECT_ID" --filter='state=ENABLED' --sort-by='~createTime' --limit=1 --format='value(name)')"
GEMINI_VERSION="${GEMINI_VERSION##*/}"; AGENT_VERSION="${AGENT_VERSION##*/}"
[[ -n "$GEMINI_VERSION" && -n "$AGENT_VERSION" ]] || { echo 'Faltan versiones de secretos habilitadas.'; exit 1; }
gcloud firestore databases describe --database "$DATABASE" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud firestore databases create --database "$DATABASE" --location "$REGION" --type firestore-native --project "$PROJECT_ID"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA_EMAIL" --role roles/datastore.user \
  --condition="expression=resource.name==\"projects/${PROJECT_ID}/databases/${DATABASE}\",title=cv-agent-database" >/dev/null
gcloud firestore fields ttls update expires_at --collection-group=cv_responses --database "$DATABASE" \
  --enable-ttl --project "$PROJECT_ID" --quiet
# Evitar índices de contenido conversacional (no se consulta por contenido).
gcloud firestore indexes fields update payload --collection-group=cv_responses --database "$DATABASE" \
  --disable-indexes --project "$PROJECT_ID" --quiet

gcloud run deploy "$SERVICE" --source . --project "$PROJECT_ID" --region "$REGION" \
  --service-account "$SA_EMAIL" --allow-unauthenticated \
  --cpu 1 --memory 512Mi --concurrency 20 --min-instances 0 --max-instances 2 --timeout 120 \
  --set-env-vars "LLM_PROVIDER=gemini,LLM_MODEL=${LLM_MODEL},KNOWLEDGE_MODE=full,MAX_HISTORY_TURNS=30,MAX_HISTORY_CHARS=40000,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},RESPONSE_STORE_BACKEND=firestore,FIRESTORE_DATABASE=${DATABASE},APP_REVISION=${REVISION},LOG_FORMAT=json" \
  --set-secrets "GEMINI_API_KEY=cv-agent-gemini-key:${GEMINI_VERSION},AGENT_API_KEY=cv-agent-access-key:${AGENT_VERSION}"
URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
gcloud run services update "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --update-env-vars "PUBLIC_BASE_URL=${URL}" >/dev/null
python3 deploy/observability.py --project "$PROJECT_ID" --service "$SERVICE" --apply
printf 'Servicio: %s\nEndpoint: %s/v1/responses\n' "$URL" "$URL"
curl -fsS "$URL/health"
echo
