TOKEN="$(py-secrets-xethhung12 get RAILWAY_PROJECT_TOKEN)"
ENV_ID="$(py-secrets-xethhung12 get RAILWAY_ENVIRONMENT_ID)"
SERVICE_ID="$(py-secrets-xethhung12 get RAILWAY_SERVICE_ID)"

python3 scripts/redeploy-railway.py --token "$TOKEN" --service-id "$SERVICE_ID" --environment-id "$ENV_ID"
