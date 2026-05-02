# DefectSense Project: Full Working Guide (Simple + Technical)

This document explains the complete project flow from start to finish.
It is written in two ways:
- Simple explanation (for quick understanding)
- Technical explanation (for implementation-level clarity)

It also explains why each technology and algorithm is used.

## 1) Project Goal

DefectSense predicts whether an uploaded Python file is likely to be defect-prone.

In addition to prediction, it provides:
- Risk metrics and feature explanations
- Chat-based explanation (RAG-assisted)
- Simulated CI/CD execution pipeline
- Docker/Kubernetes deployment artifacts
- Auto-generated Ansible playbook suggestion
- Operational dashboard

## 2) High-Level Architecture (Simple)

1. User logs in.
2. User uploads a Python file.
3. System extracts static code quality metrics.
4. Trained ML model predicts defect probability.
5. UI shows risk label, top factors, and confidence.
6. User can ask chat questions about risk/fixes.
7. User can run a CI/CD pipeline simulation.
8. System can build Docker image and validate/deploy Kubernetes manifests depending on environment availability.

## 3) Repository Components and Purpose

- app.py: Creates Flask app, registers blueprints, CORS, upload limits.
- run.py: Entry point to run Flask app.
- auth.py, auth_routes.py: Login/register/token verification.
- routes.py: Core APIs (predict, chat, pipeline, model-info).
- extractor.py: Extracts 21 static software metrics from uploaded Python code.
- model.py: Loads trained artifacts, runs prediction, calibration, confidence bands.
- train.py: Trains the stacking ensemble model on NASA KC1-style dataset.
- rag_chat.py: Retrieval + rule-guided explanation engine using ChromaDB.
- pipeline.py: Real local CI/CD stage executor with streamed stage updates.
- dashboard.py: Runtime telemetry + model metadata + pipeline history + Ansible generation endpoint.
- Dockerfile: Container image build definition.
- docker-compose.yml: Local multi-service runtime (web service defined).
- k8s/deployment.yaml, k8s/service.yaml: Kubernetes deployment manifests.
- .github/workflows/ci.yml: GitHub Actions CI pipeline.

## 4) Detailed Request/Response Mechanism

### 4.1 Authentication flow

Implemented in auth.py and auth_routes.py.

Mechanism:
1. Client sends username/password to POST /api/auth/login.
2. Password is SHA-256 hashed and compared to stored hash.
3. A signed JWT-like token is generated using HMAC-SHA256.
4. Protected APIs use require_auth decorator to verify token and attach request.current_user.

Why used:
- Keeps protected endpoints restricted (predict/chat/pipeline).
- Lightweight and local, no external auth server required.

### 4.2 Defect prediction flow

Implemented mainly in routes.py, extractor.py, model.py.

Mechanism:
1. User uploads .py file to POST /api/predict.
2. Source code is decoded and validated.
3. extractor.py computes metric vector.
4. model.py loads scaler + stacking model + feature columns.
5. Model returns raw defect probability.
6. File-aware calibration adjusts probability in specific practical cases.
7. Decision threshold from training metadata is applied.
8. Label, confidence band, top features, and risks are returned.

Why this is strong:
- Not a binary raw threshold-only model.
- Uses threshold tuning and confidence bands.
- Keeps raw and calibrated probabilities for transparency.

## 5) Metrics Used and Why

The model uses 21 static features (FEATURE_COLS in extractor.py), including:

- Size metrics: loc, lOCode, lOComment, lOBlank
- Complexity metrics: v(g), ev(g), iv(g), branchCount
- Halstead metrics: n, v, l, d, i, e, b, t
- Token/operator metrics: uniq_Op, uniq_Opnd, total_Op, total_Opnd

Purpose of these metrics:
- Estimate structural complexity and maintainability risk.
- Provide architecture-independent static signals before runtime.
- Enable fast defect-likelihood estimation without executing code.

## 6) ML Model: Algorithm, Reason, and Working

Implemented in train.py and model.py.

### 6.1 Algorithm used

Stacking ensemble:
- Base learners:
  - RandomForestClassifier
  - GradientBoostingClassifier
  - DecisionTreeClassifier
- Meta learner:
  - LogisticRegression

Why this algorithm:
- Different base models capture different non-linear patterns.
- Stacking combines their strengths and usually improves robustness.
- Logistic regression as meta model provides stable final decision boundary.

### 6.2 Data source

Training uses data/dataset.csv in NASA KC1-style format.

Expected:
- Required 21 feature columns
- defects target label

### 6.3 Training process

1. Load and clean dataset.
2. Convert numeric fields and map defects labels to 0/1.
3. Split into train/test with stratification.
4. Standardize features with StandardScaler.
5. Train stacking ensemble.
6. Compute probabilities on holdout test set.
7. Tune decision threshold (0.25 to 0.75 sweep) using weighted score:
   score = 0.7 * F1 + 0.3 * BalancedAccuracy
8. Save artifacts:
   - models/stacking_model.pkl
   - models/scaler.pkl
   - models/feature_cols.pkl
   - models/model_meta.pkl

Why threshold tuning is needed:
- Defect datasets are usually imbalanced.
- Fixed 0.5 threshold often gives poor minority-class detection.
- Tuned threshold gives better practical defect recall/precision balance.

### 6.4 Inference and calibration

At prediction time:
1. Extracted metrics are scaled.
2. Model predicts raw probability.
3. Calibrator adjusts score in specific profiles:
   - Orchestration-like file naming and profile
   - Very low-complexity profile guardrail (reduces false positives)
4. Final label is based on calibrated probability vs learned threshold.
5. Confidence band is assigned by probability margin from threshold.

Returned fields include:
- raw_probability
- probability (calibrated)
- decision_threshold
- confidence_band
- calibration details

## 7) Explainability Mechanism

### 7.1 Feature influence

model.py computes a proxy SHAP-like value using:
- RF feature importances
- standardized feature deviation

It returns top contributing features for interpretation.

### 7.2 Risk breakdown rules

extractor.py also provides rule-based risks for readability, such as:
- high cyclomatic complexity
- high Halstead volume/difficulty
- high estimated bugs
- very high LOC

These are human-readable overlays, not replacement for ML score.

## 8) RAG Chat Mechanism

Implemented in rag_chat.py.

How it works:
1. Knowledge snippets are stored in ChromaDB collection.
2. Query combines user question + feature hints + filename.
3. Relevant snippets are retrieved using embeddings (all-MiniLM-L6-v2).
4. Rule-guided response builder generates grounded explanation.
5. Response is streamed back token-by-token (SSE style).

Why this approach:
- Retrieval grounding reduces hallucination risk.
- Uses repository/domain knowledge for contextual answers.
- Gives explainable and practical guidance (why risky, what to fix, deploy steps).

## 9) CI/CD Pipeline Mechanism

Implemented in pipeline.py and exposed via POST /api/pipeline.

Stages:
1. Syntax check (py_compile)
2. Unit test execution (unittest discover)
3. Defect scan gate (uses prediction probability)
4. Security scan (static rules + optional bandit + pip check)
5. Docker build
6. Kubernetes deploy/validation path

Important control logic:
- Syntax failure blocks pipeline.
- Very high ML risk can trigger defect gate block.
- Docker/kubectl unavailability may downgrade to warning/validation path depending on context.
- Kubernetes stage can do client-side/local manifest validation when cluster is not reachable.

Output behavior:
- Streamed stage updates for UI.
- Final status: success, warning, or blocked.
- History persisted to data/pipeline_history.json.

## 10) Docker Usage and Purpose

### 10.1 Dockerfile

Purpose:
- Creates reproducible runtime image.
- Installs dependencies and runs app through gunicorn.
- Includes healthcheck on /health.

### 10.2 docker-compose.yml

Purpose:
- One-command local startup.
- Maps port 5000.
- Mounts models and data directories for persistence.
- Mounts Docker socket for local pipeline build fallback scenarios.

Why Docker is used:
- Environment consistency across machines.
- Easy deployment and testing.
- Cleaner professor demo execution.

## 11) Kubernetes Usage and Purpose

Manifest files:
- k8s/deployment.yaml
- k8s/service.yaml

What they define:
- Deployment with container spec and resources.
- Liveness and readiness probes (/health).
- Service exposure (NodePort).

Why Kubernetes is used:
- Demonstrates production-style orchestration.
- Enables health-based rollout behavior.
- Separates app deployment concerns from code.

## 12) Ansible Usage and Purpose

Implemented in dashboard.py endpoint:
- POST /api/ansible-playbook

What it does now:
- Generates an Ansible playbook text dynamically based on predicted risk.
- Selects deployment strategy profile (rolling/canary/blue-green style selection logic).
- Includes kubectl-based rollout and endpoint checks.

Important note:
- Current project generates playbooks but does not automatically execute ansible-playbook command in the backend pipeline.
- So Ansible integration is generation-first (advisory/automation template), not full remote execution orchestration.

This is still valid for demonstration because it shows policy-driven deployment-as-code generation from ML risk.

## 13) GitHub Actions CI

Defined in .github/workflows/ci.yml.

Workflow includes:
1. Checkout
2. Python setup
3. Dependency install
4. Syntax checks
5. Unit tests
6. Docker build
7. kubectl install
8. Kubernetes dry-run validation

Purpose:
- Continuous integration checks on push/PR.
- Early failure detection.
- Confidence before deployment.

## 14) End-to-End Mechanism Summary (Simple)

Think of the system as 4 engines working together:

1. Analysis engine: Converts code into measurable quality signals.
2. Prediction engine: Uses trained ensemble ML to estimate defect risk.
3. Explanation engine: Turns model output into understandable reasoning (chat + top factors).
4. Delivery engine: Simulates CI/CD and supports container/K8s deployment flows.

So the project is not only a classifier; it is a complete mini-MLOps workflow.

## 15) End-to-End Mechanism Summary (Technical)

Data path:
1. Uploaded Python source -> extractor.py -> 21D numeric feature vector.
2. model.py loads scaler + stacking model -> P(defect).
3. Calibration layer adjusts domain-mismatch risk patterns.
4. Threshold decision gives class label.
5. API returns prediction + explainability + confidence.
6. pipeline.py consumes same prediction and gates build/deploy stages.
7. rag_chat.py consumes prediction context + retrieval context and streams grounded answers.

This provides a closed feedback loop:
- Static metrics -> ML inference -> explainability -> operational gate decision -> deployment validation.

## 16) Why Professor Should Trust the Mechanism

- Uses standard software quality metrics from static analysis.
- Uses proven ML ensemble strategy rather than single fragile model.
- Uses explicit threshold tuning for imbalanced classification.
- Keeps calibrated and raw outputs transparent.
- Adds confidence levels and explicit calibration reasons.
- Integrates prediction with CI/CD decision points.
- Supports reproducible deployment with Docker and Kubernetes manifests.
- Provides generated Ansible playbook logic for deployment automation planning.

## 17) Known Boundaries (Honest Technical Statement)

- Defect prediction is probabilistic, not a guaranteed bug finder.
- Dataset domain mismatch can affect some file categories.
- Current Ansible integration generates playbooks; it does not execute remote orchestration by itself.
- Some CI/CD stages are environment-aware and may switch to validation-only mode if docker/kubectl/cluster is unavailable.

These boundaries are expected in real MLOps systems and are handled transparently in this project.

## 18) Quick Demo Script (What to show sir)

1. Login and upload a Python file.
2. Show extracted key metrics and prediction with confidence.
3. Explain raw vs calibrated probability and threshold.
4. Ask chat: why risky and how to fix.
5. Run pipeline and show stage-wise gate decisions.
6. Show Docker/K8s manifests and health probes.
7. Generate Ansible playbook and explain strategy selection.
8. Open model info to show architecture + AUC + dataset metadata.

This sequence demonstrates the full mechanism from source code to operational decision.
