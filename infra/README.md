# Deploying to GCP (free tier)

Backend on **Cloud Run**, frontend on **Firebase Hosting** — both have a
perpetual (not just 12-month trial) free tier, and both are fast enough to
support "no lag": Firebase Hosting is a static global CDN (zero cold start),
and this backend image has no heavy ML imports at runtime so Cloud Run's
cold start is short.

**Account setup is a step only you can do** — GCP requires a payment method
for identity verification even to use the free tier, so this can't be
automated on your behalf.

## 1. One-time account setup

1. Create a GCP account at https://console.cloud.google.com (free trial
   credit is separate from, and additional to, the perpetual free tier used
   here — you won't be charged for anything in this guide unless you exceed
   the free tier limits).
2. Create a new project, note its **Project ID**.
3. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install) and
   run `gcloud init` to authenticate.
4. Install [Terraform](https://developer.hashicorp.com/terraform/install).
5. Install the [Firebase CLI](https://firebase.google.com/docs/cli):
   `npm install -g firebase-tools`, then `firebase login`.

## 2. Provision infrastructure (Terraform)

```bash
cd infra
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

This creates the Artifact Registry repo and the Cloud Run service (scaled
to zero, so it costs nothing while idle).

## 3. First deploy (manual, before CI/CD takes over)

```bash
# Backend
gcloud run deploy pharma-forecast-api \
  --source . \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --allow-unauthenticated

# Frontend — set VITE_API_BASE_URL to the Cloud Run URL printed above first
cd frontend-react
firebase init hosting   # point the public dir at "dist"
npm run build
firebase deploy --only hosting --project YOUR_PROJECT_ID
```

Then set the backend's `FRONTEND_ORIGIN` env var (Cloud Run console, or
`terraform apply -var="frontend_origin=https://YOUR_PROJECT_ID.web.app"`) to
the Firebase Hosting URL so CORS allows it.

## 4. Hand off to CI/CD

Once the manual first deploy works, `.github/workflows/ci-cd.yml` takes over
future deploys on every push to `main`. It needs:

- Repo variable `GCP_PROJECT_ID` set to your project ID
- Secrets `GCP_WIF_PROVIDER` / `GCP_SERVICE_ACCOUNT` — set up
  [Workload Identity Federation](https://github.com/google-github-actions/auth#setting-up-workload-identity-federation)
  so GitHub Actions authenticates without a long-lived service account key
  (the standard enterprise-security pattern — no secret keys sitting in
  repo secrets)
- Secret `FIREBASE_TOKEN` — from `firebase login:ci`

## 5. Keep it warm for the demo

`.github/workflows/keep-alive.yml` pings `/health` every 10 minutes once
`BACKEND_URL` (repo variable) is set to the Cloud Run URL. Also just hit the
URL a couple of times yourself right before presenting — belt and suspenders.
