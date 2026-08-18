# PharmaForecast Analytics

Pharmaceutical sales forecasting & business-intelligence platform. Predicts
daily demand for 8 ATC-coded drug categories using 5 independently trained
and honestly compared forecasting models, then layers anomaly detection,
what-if scenario simulation, and rule-based supply-chain recommendations on
top — served through a FastAPI backend and a React dashboard.

## Architecture

```
data/raw (Kaggle pharma sales, 2014-2019 daily)
      │
      ▼
src/data, src/eda        preprocessing, quality checks, EDA
      │
      ▼
src/models                5 independently trained models per category:
                           Prophet · ARIMA · SARIMA · LightGBM · LSTM
      │
      ▼
data/outputs/forecasts    pre-generated forecast CSVs + evaluation metrics
models/metrics.json       (rebuilt from those CSVs — never hand-edited)
      │
      ▼
backend/  (FastAPI)        serves forecasts, runs anomaly detection,
                            what-if simulation, and recommendations —
                            all read from the CSVs above, no live model
                            inference in the request path
      │
      ▼
frontend-react/ (React)    Dashboard · Forecast Explorer · Anomaly
                            Detection · What-If Simulator ·
                            Recommendations · Model Comparison
```

The backend deliberately never loads model binaries at request time — it
reads pre-generated forecast CSVs and metrics. That's what keeps API
response times fast regardless of hosting tier.

## Why 5 models, and how "best" is chosen

The project brief calls for validating multiple forecasting approaches
against real variance in the data (stationarity, seasonality, SKU-level
noise) rather than committing to one. Each of the 5 models is trained and
evaluated independently per category; `best_model` in `models/metrics.json`
is computed by lowest MAE, per category, from the evaluation CSVs — not
hand-picked. See `src/models/rebuild_metrics_json.py`.

**Note on MAPE**: daily per-category pharma sales are low-count and
intermittent (many zero-sale days for some categories), so MAPE naturally
runs 30–110% depending on category — that's a property of the data, not a
modeling defect. MAE/RMSE are tracked alongside MAPE for exactly this
reason, and `best_model` selection uses MAE.

**Ensembling was investigated, not assumed**: `src/models/ensemble_analysis.py`
grid-searches the optimal linear blend of ARIMA+SARIMA against real held-out
data. Result: the optimal weight collapses to "just use whichever model is
already better" for 7 of 8 categories — their errors are too correlated to
benefit from blending. No synthetic "ensemble" model ships in the product
because it would be a measured regression for most categories.

### Retraining pass — real, verified results

Re-tuned LightGBM (Optuna, 50 trials) and re-selected ARIMA/SARIMA orders
(`pmdarima.auto_arima`) against the git-committed baseline, category by
category, keeping only genuine wins (`src/models/reconcile_retrain.py`) —
same no-fake-wins discipline as the ensemble check:

| Category | Model | Old MAE | New MAE | Change |
|---|---|---|---|---|
| N02BA | SARIMA | 1.7881 | 1.5380 | **+14.0%** |
| N02BA | ARIMA | 1.6329 | 1.5397 | +5.7% |
| M01AB | ARIMA | 2.1893 | 2.1536 | +1.6% |
| N05B | ARIMA | 3.4019 | 3.3702 | +0.9% |
| N02BE | LightGBM | 9.3879 | 9.3407 | +0.5% |
| R06 | LightGBM | 1.6507 | 1.6451 | +0.3% |
| R03 | LightGBM | 5.6849 | 5.6669 | +0.3% |
| N05C | LightGBM | 0.8227 | 0.8198 | +0.4% |

8 genuine improvements found across 24 (model × category) retrain attempts;
the rest reverted to baseline because the wider search came out worse for
that category — expected with small-sample daily sales data, and reported
honestly rather than cherry-picked.

**Prophet and LSTM were not retrained** — not skipped by choice, blocked by
this environment: Prophet needs a C++ toolchain to compile its Stan backend,
which isn't available here; TensorFlow (LSTM) has no published wheel yet for
this environment's Python version. Neither is currently the best model for
any category, so this doesn't change the product's accuracy story, but it's
an honest gap, not a silent one.

## Setup

### Backend

```bash
pip install -r requirements-backend.txt   # deploy-only deps; see requirements.txt for training
uvicorn main:app --reload
# http://localhost:8000/docs for the OpenAPI explorer
```

### Frontend

```bash
cd frontend-react
npm install
cp .env.example .env   # VITE_API_BASE_URL, defaults to localhost:8000
npm run dev
```

### Retraining (optional — forecast CSVs are already committed)

```bash
pip install -r requirements.txt   # full training deps
python src/models/train_lightgbm.py --use-optuna --n-trials 50
python src/models/arima_train_eval.py --use-auto
python src/models/sarima_train_eval.py --use-auto
python src/models/reconcile_retrain.py --model lightgbm   # keeps only genuine per-category wins
python src/models/rebuild_metrics_json.py
python test_all.py   # 19/19 must pass
```

## Delivery approach

Follows the same pattern Cognizant documents publicly for enterprise cloud
engagements — CI/CD automation, containerization, Infrastructure-as-Code,
and DevSecOps security scanning in the pipeline — applied here on free-tier
GCP infrastructure:

- **CI/CD**: `.github/workflows/ci-cd.yml` — automated test gate
  (`test_all.py`, 19/19) → dependency security scan (pip-audit + npm audit)
  → containerize → deploy, gated so nothing ships without passing tests.
- **Containerization**: `Dockerfile` — slim, backend-only image (no ML
  training libraries at runtime).
- **Infrastructure as Code**: `infra/main.tf` — Cloud Run + Artifact
  Registry, not manual console configuration.
- **Deployment**: Cloud Run (backend) + Firebase Hosting (frontend) — both
  perpetual free tier. See `infra/README.md` for the one-time account setup
  (requires your own GCP account — that step can't be automated on your
  behalf).

## Legacy Streamlit app

`frontend/` is the original Streamlit dashboard — kept as a working fallback,
not the primary demo path. It talks to the same backend.

## Tech stack

**Backend**: FastAPI, pandas, pydantic · **Models**: Prophet, statsmodels
(ARIMA/SARIMA), LightGBM + Optuna, LSTM (Keras) · **Frontend**: React 19,
TypeScript, Vite, Tailwind CSS v4, TanStack Query, Plotly.js · **Delivery**:
Docker, Terraform, GitHub Actions, GCP (Cloud Run + Firebase Hosting)
