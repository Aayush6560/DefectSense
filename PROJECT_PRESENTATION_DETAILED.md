# DefectSense Presentation Guide

This file is written as a presentation script plus technical notes.
Use it to explain the project from scratch to end in a viva or demo.

## How to present this project

You can present it in 3 layers:

1. Simple explanation: what the user sees and why it matters.
2. Technical explanation: what code runs and how data moves.
3. Defense explanation: why each technology and algorithm was chosen.

---

## Slide 1: Title

### Say this simply
DefectSense is an AI-powered software defect prediction and deployment workflow system.

### Say this technically
The system is a Flask-based MLOps application that performs static defect prediction on uploaded Python files using a stacking ensemble model trained on NASA KC1-style metrics, and then connects prediction output with explanation, CI/CD simulation, Docker, Kubernetes, and Ansible generation.

### What to mention
- It is not just a classifier.
- It is a complete project showing ML + web app + deployment automation.

---

## Slide 2: Problem Statement

### Say this simply
Before deployment, we want to know whether a code file is risky or likely to contain defects.

### Say this technically
Defect prediction helps detect structural code quality risk before execution by analyzing static metrics such as cyclomatic complexity, Halstead measures, and size-based features.

### Why this matters
- Bugs are cheaper to fix before release.
- Static analysis can catch risk without running the code.
- This is useful in CI/CD pipelines.

---

## Slide 3: Project Objective

### Say this simply
The goal is to upload a Python file, analyze it, predict defect risk, explain the result, and show how it behaves in a DevOps pipeline.

### Say this technically
The application ingests source code, extracts a 21-dimensional feature vector, applies a trained stacking classifier, calibrates the probability, generates interpretability outputs, and streams CI/CD stage results.

### Main outputs
- Risk label
- Probability
- Confidence band
- Top risk factors
- Chat explanation
- Pipeline stage report

---

## Slide 4: System Architecture

### Say this simply
The project has four major parts: login, code analysis, AI explanation, and deployment pipeline.

### Say this technically
The architecture is split into Flask blueprints and service modules:
- auth.py / auth_routes.py for authentication
- routes.py for prediction, chat, and pipeline APIs
- extractor.py for feature extraction
- model.py for inference and calibration
- rag_chat.py for retrieval-grounded explanation
- pipeline.py for CI/CD execution
- dashboard.py for metrics, system status, and Ansible playbook generation

### Key flow
Upload file -> extract metrics -> ML prediction -> explanation -> pipeline simulation -> deployment artifacts.

---

## Slide 5: Login and Security

### Say this simply
Users must log in before they can upload files or use chat and pipeline features.

### Say this technically
The app uses a lightweight token-based authentication system. Passwords are stored as SHA-256 hashes, login creates an HMAC-signed JWT-like token, and protected endpoints validate the token through a decorator.

### Why this is used
- Protects the upload and prediction APIs.
- Keeps the demo controlled.
- Avoids external auth dependencies.

### Code references
- auth.py
- auth_routes.py
- routes.py

---

## Slide 6: File Upload and Preprocessing

### Say this simply
The user uploads a Python file, and the system reads the file safely before analysis.

### Say this technically
In POST /api/predict, the uploaded file is validated as .py, decoded as UTF-8, checked for minimum length, and then passed to the static extractor.

### What happens next
1. File is read from request.files.
2. Source code is passed to extractor.py.
3. Metrics are converted into numeric features.
4. Features are sent to the trained ML model.

---

## Slide 7: Metrics Extraction

### Say this simply
The system does not guess randomly. It measures the code using software quality metrics.

### Say this technically
extractor.py computes 21 metrics from the Python source code:
- Size metrics: loc, lOCode, lOComment, lOBlank, locCodeAndComment
- Cyclomatic complexity metrics: v(g), ev(g), iv(g), branchCount
- Halstead metrics: n, v, l, d, i, e, b, t
- Token counts: uniq_Op, uniq_Opnd, total_Op, total_Opnd

### Why these metrics are used
These metrics capture structural risk, maintainability, branching complexity, and cognitive load.

### Good defense line
The model predicts defect risk from code structure, not from runtime behavior.

---

## Slide 8: How Cyclomatic Complexity is Calculated

### Say this simply
Cyclomatic complexity counts how many different paths a function can take.

### Say this technically
The AST visitor in extractor.py increases complexity for if, for, while, except, with, assert, Boolean operations, and ternary expressions. Complexity is aggregated per function.

### Why it matters
- More paths means more testing effort.
- More branching usually means more risk.
- Very high complexity often correlates with maintainability issues.

### Example line
If a file has many nested conditions and loops, the score becomes high.

---

## Slide 9: Halstead Metrics Explained

### Say this simply
Halstead metrics measure how dense and difficult the code is.

### Say this technically
The code uses AST token analysis to count operators and operands, then derives:
- Volume: information content of the program
- Difficulty: cognitive effort to understand/write the code
- Effort: V times D
- Bugs estimate: V / 3000

### Why it matters
These features help estimate how hard the code is to maintain and how likely it is to contain mistakes.

### Good defense line
Halstead measures are a classic static-analysis signal for software quality prediction.

---

## Slide 10: ML Model Used

### Say this simply
We use multiple models together so prediction is stronger than using one model only.

### Say this technically
The final model is a stacking ensemble:
- RandomForestClassifier
- GradientBoostingClassifier
- DecisionTreeClassifier
- LogisticRegression as meta learner

### Why this algorithm
- Random Forest captures non-linear feature interactions.
- Gradient Boosting improves hard cases.
- Decision Tree adds a rule-based view.
- Logistic Regression combines them into a stable final decision.

### Strong viva answer
Stacking usually performs better than a single classifier because it combines different inductive biases.

---

## Slide 11: Training Process

### Say this simply
The model is trained on a labeled defect dataset.

### Say this technically
In train.py:
1. Load NASA KC1-style dataset.
2. Clean missing values and convert numeric columns.
3. Split train/test with stratification.
4. Scale features using StandardScaler.
5. Train stacking ensemble.
6. Predict on holdout set.
7. Tune decision threshold using F1 and balanced accuracy.
8. Save model artifacts.

### Why threshold tuning is important
Defect datasets are imbalanced, so 0.5 is often not the best cutoff.

### The tuned threshold logic
The best threshold is selected from a sweep between 0.25 and 0.75 using:
score = 0.7 * F1 + 0.3 * BalancedAccuracy

---

## Slide 12: Prediction Working

### Say this simply
The model gives a probability, and then the system decides whether the file is risky or safe.

### Say this technically
model.py:
1. Loads model, scaler, and feature columns.
2. Builds input row from extracted metrics.
3. Applies scaler.
4. Gets raw defect probability from predict_proba.
5. Applies decision threshold from model metadata.
6. Applies file-aware calibration.
7. Returns final label, raw probability, calibrated probability, confidence band, and explanation features.

### Why calibration exists
Some files are orchestration-heavy or very simple glue code. Raw model probability can over-flag these. Calibration reduces false positives in those cases.

---

## Slide 13: Confidence Bands

### Say this simply
The system also tells how confident it is.

### Say this technically
The confidence band is based on the distance between probability and threshold:
- high: far from threshold
- medium: moderately far
- low: close to threshold

### Why this helps
It is better than showing only a yes/no label because it helps the evaluator understand uncertainty.

---

## Slide 14: Explainability Layer

### Say this simply
The app tells why it predicted defect-prone.

### Say this technically
The system returns top_features using a SHAP-like proxy based on:
- Random Forest feature importances
- Standardized deviation of the file metrics

It also produces a human-readable risk breakdown from extractor.py.

### Why this is useful
It makes the prediction understandable to a professor or reviewer.

---

## Slide 15: RAG Chat Explanation

### Say this simply
The chat answer is grounded in a knowledge base, not random text.

### Say this technically
rag_chat.py uses ChromaDB with MiniLM embeddings to retrieve relevant knowledge base snippets about complexity, Halstead metrics, risk, Docker, Kubernetes, and refactoring. Then it builds a response using the uploaded file context and the prediction result.

### Why RAG is used
- Avoids hallucination.
- Gives grounded answers.
- Lets the user ask: why risky, what to fix, where to start, deployment questions.

### Important point
The chat is rule-guided plus retrieval-based, not a free-form large language model that invents answers.

---

## Slide 16: CI/CD Pipeline

### Say this simply
The project also simulates a real software delivery pipeline.

### Say this technically
pipeline.py executes these stages:
1. Syntax check with py_compile
2. Unit tests
3. ML defect gate
4. Security scan
5. Docker build
6. Kubernetes deployment or validation

### How the gate works
- Syntax failure blocks the pipeline.
- High defect probability can block the build.
- Docker and Kubernetes stages use environment-aware fallback logic.

### Why this matters
This shows how ML can be inserted into a DevOps workflow.

---

## Slide 17: Docker

### Say this simply
Docker packages the app so it runs the same way everywhere.

### Say this technically
The Dockerfile:
- uses python:3.10-slim
- installs system dependencies
- installs Python dependencies
- copies project files
- exposes port 5000
- runs the app through gunicorn
- checks /health with a Docker healthcheck

### Why Docker is used
- Reproducibility
- Easy demo deployment
- Consistent environment

### docker-compose.yml role
It starts the web app locally and mounts models/data and the Docker socket for runtime integration.

---

## Slide 18: Kubernetes

### Say this simply
Kubernetes shows how the app would be deployed in production.

### Say this technically
The project includes:
- deployment.yaml with replicas, container port, probes, and resource limits
- service.yaml with NodePort exposure

### Why Kubernetes is used
- Demonstrates orchestration
- Supports rollout behavior
- Shows readiness/liveness checks

### Good defense line
Kubernetes is used for deployment demonstration and manifest validation, not just for running a container.

---

## Slide 19: Ansible

### Say this simply
The project can also generate an Ansible playbook for deployment planning.

### Say this technically
dashboard.py provides /api/ansible-playbook, which generates a playbook string based on the prediction risk level and suggested deployment strategy.

### What it does
- Chooses rolling, canary, or blue-green style logic
- Adds kubectl deployment steps
- Adds rollout and endpoint validation checks

### Important honesty statement
The current project generates the playbook, but it does not automatically execute Ansible on the server.

---

## Slide 20: Monitoring and Dashboard

### Say this simply
The dashboard shows system status and recent pipeline activity.

### Say this technically
dashboard.py collects:
- CPU, memory, disk, network
- Docker container status
- Kubernetes pod status
- model metadata
- pipeline history

### Why this is useful
It makes the project look like a proper MLOps system, not just a single API.

---

## Slide 21: End-to-End Flow

### Say this simply
The entire project works like this:
login -> upload code -> predict defect risk -> explain -> run pipeline -> show deployment path.

### Say this technically
1. User authenticates.
2. Uploads Python code.
3. Metrics are extracted.
4. Stacking model predicts defect probability.
5. Calibration and threshold decide final class.
6. Top features and risks are shown.
7. Chat explains the result through retrieval grounding.
8. CI/CD pipeline simulates real checks.
9. Docker/Kubernetes/Ansible demonstrate delivery automation.

---

## Slide 22: Why This Project is Technically Strong

### Say this simply
It combines ML, explanation, deployment, and DevOps in one workflow.

### Say this technically
The project is strong because it contains:
- real static metric extraction
- ensemble ML prediction
- threshold optimization
- probability calibration
- explainability
- RAG-based question answering
- CI/CD simulation
- Docker and Kubernetes artifacts
- Ansible playbook generation

### Best summary line
This is an end-to-end MLOps defect prediction platform, not just a classifier.

---

## Slide 23: What Sir May Ask and What You Should Say

### Question: What algorithm did you use?
Say: We used a stacking ensemble with Random Forest, Gradient Boosting, Decision Tree, and Logistic Regression as meta learner.

### Question: Why not one model only?
Say: Because different base models capture different patterns. Stacking gives better robustness.

### Question: How does the model predict defects?
Say: It converts code into static metrics such as complexity, Halstead metrics, and size features, then feeds them into the trained classifier.

### Question: Why is pipeline.py high risk?
Say: Because it has high complexity, large Halstead volume, and many orchestration branches. The model also applies a file-aware calibration layer for practicality.

### Question: Why use threshold tuning?
Say: Because defect prediction is imbalanced. A fixed 0.5 threshold is usually not optimal.

### Question: What is the purpose of Docker and Kubernetes?
Say: Docker gives reproducibility, and Kubernetes demonstrates deployment orchestration with health checks and rollout behavior.

### Question: What does Ansible do here?
Say: It generates a deployment playbook based on the defect risk so deployment strategy can be automated or reviewed.

---

## Slide 24: Final Conclusion

### Say this simply
DefectSense predicts defect risk, explains the result, and demonstrates how the prediction can influence deployment decisions.

### Say this technically
The project implements a static-analysis-driven defect prediction pipeline with calibrated ensemble inference, retrieval-grounded explanation, and CI/CD deployment simulation using Docker, Kubernetes, and Ansible generation.

### Final line for presentation
This project shows the full lifecycle from code analysis to defect prediction to deployment awareness.

---

# Technical Appendix: File-by-File Explanation

This section is for the deepest technical questions.
If sir asks "which file does what?" or "what exact code is used?", use this section.

## A. Root Files

### __init__.py
- Package marker file.
- Makes the folder importable as a Python package when needed.
- No core logic.

### app.py
- Creates the Flask application object through create_app().
- Usually serves as the central app factory entry point.
- Important because it keeps app setup separated from runtime execution.

### run.py
- Main executable entry point.
- Imports create_app() from app.py, builds the Flask app, prints the local startup banner, and calls app.run(...).
- This is what you run when starting the project locally outside Docker.

### requirements.txt
- Lists all Python dependencies used by the project.
- Includes Flask, scikit-learn, pandas, numpy, chromadb, psutil, gunicorn, PyYAML, and other support libraries.
- Purpose: reproducible installs.

### .gitignore
- Prevents committing generated or local-only files such as __pycache__, virtual environments, models, and user data.
- Keeps repository clean and avoids leaking runtime artifacts.

### Dockerfile
- Defines the container image build steps.
- Uses python:3.10-slim.
- Installs system packages needed for build/runtime.
- Installs Python dependencies.
- Copies project files.
- Runs the app with gunicorn on port 5000.
- Adds healthcheck to ensure the app is alive.

### docker-compose.yml
- Defines local multi-container runtime for the web service.
- Maps port 5000.
- Mounts models and data directories so trained artifacts persist.
- Mounts Docker socket so the pipeline can perform Docker-based build fallback in environments where CLI is unavailable.

### test_smoke.py
- Contains smoke tests for core authentication and prediction flow.
- Purpose is to verify that the app boots, login works, and prediction endpoint can be reached with valid auth.
- This is the minimal evidence that the main system path is functioning.

### sample_defect.py
- A sample Python file likely used for manual demo or prediction testing.
- Demonstrates a code file that can be uploaded to the prediction endpoint.

### demo_clean.py, demo_medium.py, demo_risky.py
- Demo files used to show different risk levels in presentation.
- Useful because they give the professor clear examples of low-risk, moderate-risk, and high-risk prediction behavior.

## B. Authentication Layer

### auth.py
This file implements the security layer.

What code is used:
- SHA-256 for password hashing.
- HMAC-SHA256 for token signing.
- Base64 URL-safe encoding for token transport.
- A JWT-like custom token format.

What it does:
- Loads demo users from data/users.json if available.
- Falls back to in-memory demo accounts.
- Provides login(), register(), verify_token(), require_auth(), and counters.

Why it is implemented this way:
- Lightweight and fully local.
- Suitable for a classroom/demo project.
- No external identity provider is needed.

### auth_routes.py
- Defines /api/auth/login, /api/auth/register, and /api/auth/verify.
- Acts as the Flask blueprint that exposes auth.py functionality over HTTP.

Technical flow:
1. User sends JSON credentials.
2. Login validates password hash.
3. Token is generated.
4. Client sends token in Authorization header for protected endpoints.

## C. Flask Application Wiring

### app.py
This is the app factory.

What code is used:
- Flask(__name__, template_folder=root, static_folder=root)
- CORS(app, origins=['*'])
- Blueprint registration for routes, dashboard, and auth.

Why it matters:
- Separates app creation from business logic.
- Makes the project easier to scale, test, and deploy.

Technical role:
- Sets SECRET_KEY.
- Sets MAX_CONTENT_LENGTH to 5 MB.
- Registers all route collections.

### routes.py
This is the main API orchestration file.

Endpoints:
- / -> login page
- /app -> main app page
- /health -> health check
- /api/predict -> file upload + ML prediction
- /api/chat -> explanation chat
- /api/pipeline -> CI/CD pipeline execution
- /api/pipeline/history -> stored pipeline runs
- /api/model-info -> model metadata
- /api/rag-search -> knowledge base search

Technical flow of /api/predict:
1. Check if file exists in request.
2. Ensure it ends with .py.
3. Read the uploaded code.
4. Extract metrics using extractor.py.
5. Get code summary.
6. Call model.predict_file(metrics, filename).
7. Get risk breakdown.
8. Return JSON response for UI.

Why this file is important:
- It binds together the extractor, model, RAG explanation, and pipeline.

### dashboard.py
This file provides system and deployment dashboard functionality.

What code is used:
- psutil for system metrics.
- subprocess for Docker and kubectl inspection.
- Flask blueprints for API endpoints.

Endpoints:
- /dashboard -> dashboard UI
- /api/system-status -> CPU, memory, disk, network, Docker, K8s, model state
- /api/metrics-history -> historical system metrics
- /api/ansible-playbook -> generated Ansible playbook

Why it matters:
- Gives operational visibility.
- Demonstrates that this project is more than a classifier; it is an MLOps demo.

## D. Feature Extraction and Static Analysis

### extractor.py
This is one of the most important files in the project.

What code is used:
- ast module for parsing Python source code.
- math for Halstead calculations.
- Regular expressions and string analysis for line metrics.

Main job:
- Convert raw Python code into a numeric feature vector of 21 metrics.

Metrics extracted:
- loc
- v(g)
- ev(g)
- iv(g)
- n
- v
- l
- d
- i
- e
- b
- t
- lOCode
- lOComment
- lOBlank
- locCodeAndComment
- uniq_Op
- uniq_Opnd
- total_Op
- total_Opnd
- branchCount

How complexity is measured:
- AST visitor counts branching nodes like if, for, while, except, with, assert, Boolean logic, and ternary expressions.

How Halstead metrics are computed:
- Count operators and operands.
- Derive vocabulary, volume, difficulty, effort, bugs estimate, and time.

Why this file is critical:
- The ML model cannot directly read source code.
- It needs structured numeric inputs.
- extractor.py bridges code -> features -> model.

Important technical note:
- This project predicts defect risk from static structure, not from runtime execution traces.

### get_code_summary() in extractor.py
Extracts human-readable metadata:
- function names
- class names
- imports
- docstrings
- comprehensions
- syntax errors

This supports the explanation UI and chat responses.

### get_risk_breakdown() in extractor.py
Adds rule-based risk messages:
- high cyclomatic complexity
- high Halstead volume
- bug estimate risk
- large file size
- high Halstead difficulty

Why it exists:
- Easy for a professor to understand.
- Complements ML output with domain-readable reasons.

## E. Machine Learning

### train.py
This file trains the defect prediction model.

What code is used:
- scikit-learn ensemble classifiers.
- StandardScaler.
- train_test_split.
- roc_auc_score, f1_score, balanced_accuracy_score.

Model architecture:
- RandomForestClassifier
- GradientBoostingClassifier
- DecisionTreeClassifier
- LogisticRegression meta learner

Training logic:
1. Load dataset from data/dataset.csv.
2. Clean and type-convert columns.
3. Split train/test.
4. Scale features.
5. Train stacking ensemble.
6. Predict probabilities on test set.
7. Sweep thresholds to maximize weighted performance.
8. Save model, scaler, feature columns, and metadata.

Why stacking was chosen:
- Random forest handles strong feature interactions.
- Gradient boosting captures difficult nonlinear patterns.
- Decision tree adds interpretable base behavior.
- Logistic regression combines them into one final probability.

Why threshold tuning is used:
- Defect datasets are usually imbalanced.
- A plain 0.5 cutoff can miss many defect-prone files.
- Threshold tuning improves real practical decision quality.

### model.py
This file performs inference.

What code is used:
- pickle for loading artifacts.
- numpy for array preparation.
- StandardScaler transform from saved scaler.

What it does:
1. Loads trained model artifacts.
2. Converts metrics into model row.
3. Scales the row.
4. Gets raw probability.
5. Applies decision threshold.
6. Applies file-aware calibration.
7. Returns explanation fields.

Why calibration exists:
- Some files are orchestration-heavy or simple glue code.
- Those can be over-flagged by a raw model.
- Calibration improves practical usefulness without hiding the raw score.

What the final prediction contains:
- probability
- raw_probability
- decision_threshold
- confidence_band
- calibration explanation
- label
- shap-like top features
- model metadata

### model_meta.pkl
This saved metadata file stores:
- auc_roc
- cv_auc_mean
- cv_auc_std
- decision_threshold
- f1_at_threshold
- balanced_accuracy_at_threshold
- n_train
- n_test
- defect_rate
- feature importances

Why it matters:
- Provides reproducibility and presentation evidence.

## F. RAG and Explanation Engine

### rag_chat.py
This file powers the AI-style explanation system.

What code is used:
- ChromaDB persistent vector store.
- SentenceTransformer embedding function: all-MiniLM-L6-v2.
- Tokenization and rule-based response routing.

What it does:
1. Stores a knowledge base of software engineering facts.
2. Embeds and retrieves relevant snippets.
3. Combines the file prediction context with user question.
4. Builds streamed explanation text.

Why it is not just a plain chatbot:
- It is retrieval-grounded.
- It uses the uploaded file context and prediction context.
- It answers risk, fix, deployment, and metric questions with code-aware logic.

Technical behavior:
- If the question asks for metrics, it explains the exact metric values.
- If the question asks where the error is, it points to likely hotspots.
- If the question asks how to fix it, it suggests a refactor plan.
- If the question asks about deployment, it explains pipeline/K8s logic.

## G. CI/CD and Deployment Pipeline

### pipeline.py
This file simulates a real CI/CD pipeline and is one of the most advanced backend modules.

What code is used:
- subprocess for running commands.
- tarfile and HTTP socket API for Docker build fallback.
- json for streamed stage output.
- pathlib for file handling.
- kubectl and py_compile integration.

Pipeline stages:
1. Syntax check.
2. Unit tests.
3. Defect scan using ML prediction.
4. Security scan.
5. Docker build.
6. Kubernetes deploy or manifest validation.

How it works technically:
- The source code is written to a temporary file.
- Python syntax is compiled using py_compile.
- Tests are run with unittest discover.
- The model risk score is used as a gate.
- Security checks scan for dangerous patterns and pip dependency issues.
- Docker build is attempted through CLI, with socket fallback when needed.
- Kubernetes stage validates manifests or performs rollout depending on environment.

Why this file is important:
- It shows how ML can influence DevOps decision-making.
- It is a staged pipeline, not just a static report.

### _docker_build_via_socket()
- Sends tarred build context to Docker Engine API over Unix socket.
- Used when Docker CLI is unavailable inside the runtime.

### _validate_k8s_manifests_local()
- Parses YAML locally if kubectl/cluster access is missing.
- Prevents the K8s stage from being opaque or stuck.

### get_pipeline_history()
- Reads past pipeline runs from data/pipeline_history.json.
- Enables the dashboard and history view.

## H. Web and UI Layer

### login.html
- Login screen.
- Sends username/password to auth API.
- This is the entry page for the app.

### index.html
- Main application UI after login.
- Handles upload, prediction display, chat, pipeline status, and supporting panels.
- Also renders color/status logic for warnings and results.

### dashboard.html
- Dashboard screen for system metrics and operational status.
- Shows Docker, K8s, model, and pipeline information.

Why these HTML files matter:
- They make the project demoable and understandable.
- They are the presentation layer on top of the ML backend.

## I. Kubernetes Files

### k8s/deployment.yaml
- Defines the app deployment.
- Includes container image, containerPort 5000, resource requests/limits, readinessProbe, and livenessProbe.

Why these fields matter:
- readinessProbe controls if traffic can go to the pod.
- livenessProbe restarts unhealthy containers.
- resource limits make deployment realistic.

### k8s/service.yaml
- Exposes the deployment using a NodePort service.
- Maps service port 5000 to target port 5000.

Why it matters:
- Makes the app reachable outside the cluster.

## J. CI Workflow

### .github/workflows/ci.yml
This is the GitHub Actions pipeline.

What code is used:
- actions/checkout
- actions/setup-python
- pip install -r requirements.txt
- py_compile syntax checks
- unittest discovery
- docker build
- kubectl client install
- kubectl apply --dry-run=client -f k8s/

Why it matters:
- Verifies code quality on push and pull request.
- Shows a proper DevOps CI design.

## K. Data and Model Artifacts

### data/
- Stores training and runtime history data.
- Includes dataset.csv, users.json, pipeline history, and metrics history when generated.

### models/
- Stores trained artifacts:
	- stacking_model.pkl
	- scaler.pkl
	- feature_cols.pkl
	- model_meta.pkl

Why separate storage is used:
- Keeps training artifacts distinct from source code.
- Makes deployment and retraining simpler.

## L. Scripts Folder

### scripts/download_kaggle_dataset.py
- Helper script for downloading or preparing the dataset.
- Used for dataset setup and repeatability.

## M. Algorithm Summary for Viva

If sir asks "what algorithm did you use and why?", answer this:

We used a stacking ensemble classifier.
The base models are Random Forest, Gradient Boosting, and Decision Tree, and the final learner is Logistic Regression.
The reason is that defect prediction is a structured classification task with imbalanced data, and stacking gives better robustness than a single classifier.

If sir asks "how does the model decide defect or clean?", answer this:

The file is converted into 21 static metrics, the model predicts a probability, then the system applies a trained threshold and calibration logic before assigning the final label.

If sir asks "what exactly is the project mechanism?", answer this:

The project takes code, extracts software metrics, predicts defect risk, explains the reason using retrieval-grounded text, and then simulates CI/CD and deployment decisions.

## N. One-Line File Map

- app.py: Flask app factory
- run.py: local entry point
- routes.py: main APIs
- auth.py: token auth logic
- auth_routes.py: auth endpoints
- dashboard.py: system dashboard and Ansible generation
- extractor.py: metric extraction
- train.py: model training
- model.py: inference and calibration
- rag_chat.py: retrieval-grounded explanation
- pipeline.py: CI/CD pipeline simulation
- Dockerfile: container build
- docker-compose.yml: local runtime orchestration
- k8s/: Kubernetes deployment
- .github/workflows/ci.yml: CI pipeline
- templates/pages: UI layer
- data/: runtime data and histories
- models/: trained artifacts

## O. Final Technical Conclusion

This project is a complete static defect prediction and MLOps demonstration system.
It uses AST-based metric extraction, a stacking ensemble classifier, threshold tuning, probability calibration, retrieval-grounded explanation, pipeline gating, Docker-based runtime packaging, Kubernetes deployment manifests, and generated Ansible playbook logic.

If you present it properly, the strongest message is:
this project does not just predict defects, it shows how defect prediction can drive the whole delivery lifecycle.
