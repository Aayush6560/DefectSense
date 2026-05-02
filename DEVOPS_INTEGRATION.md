# DevOps Integration Guide

## Full Backend-Frontend Connected System

Everything in the project is now **fully connected to the backend** for a complete DevOps demo.

---

## 🔌 Backend Endpoints (All Connected)

### Pipeline & Artifacts
- **POST** `/api/pipeline` — Run full CI/CD pipeline (6 stages: lint → test → ML scan → security → Docker build → K8s deploy)
- **GET** `/api/pipeline/history` — Pipeline run history
- **GET** `/api/pipeline-artifact/<pipeline_id>` — Fetch pipeline artifact (logs/results JSON)
- **GET** `/api/pipeline-artifact/<pipeline_id>/download` — Download artifact file

### Docker Integration
- **GET** `/api/docker/images` — List all Docker images
- **GET** `/api/docker/containers` — List all running containers

### Kubernetes Integration
- **GET** `/api/kubernetes/cluster-info` — Cluster status (connected/disconnected)
- **GET** `/api/kubernetes/pods?namespace=default` — List K8s pods
- **GET** `/api/kubernetes/deployments?namespace=default` — List K8s deployments

### GitHub Actions Integration
- **GET** `/api/github/status` — Check if workflows are configured
- **GET** `/api/github/workflows` — List all GitHub Actions workflows

### DevOps Status (Unified)
- **GET** `/api/devops/status` — Unified status of Docker, K8s, and GitHub (all-in-one)

---

## 🎨 Frontend Pages

### Pipeline Page (`/app` → Pipeline tab)
- **Run CI/CD Pipeline** button
- Real-time streaming of 6 pipeline stages:
  1. ✓ Syntax Check (Python compilation)
  2. 🧪 Unit Tests (unittest discover)
  3. 🤖 ML Defect Scan (stacking ensemble model)
  4. 🔒 Security Audit (bandit + manual rules)
  5. 🐳 Docker Build (docker build via socket API)
  6. ☸️ Kubernetes Deploy (kubectl apply + rollout check)
- **Pipeline Artifacts**: View and download full logs as JSON after each run
- **Pipeline History**: See all previous runs with status and timestamps

### DevOps Dashboard Page (`/app` → DevOps Dashboard tab)
**NEW** — Real-time integration view showing:

#### Status Summary Cards (4-up):
- **Overall Health**: Shows healthy/degraded based on K8s connectivity
- **Docker**: # of images and containers
- **Kubernetes**: Cluster connection status
- **GitHub**: # of configured workflows

#### Docker Section:
- Docker Images table (Repository, Tag, Size)
- Docker Containers table (Name, Status, Image)

#### Kubernetes Section:
- Kubernetes Pods table (Name, Status, Ready count)
- Kubernetes Deployments table (Name, Ready replicas, Container image)

#### GitHub Section:
- GitHub Actions Workflows table (Workflow name, File, Triggers)

#### Refresh Button:
- `🔄 Refresh All` button to reload all statuses in real-time

---

## 🚀 What to Demo

### Full Flow:
1. **Upload a Python file** → See analysis + ML prediction
2. **Run CI/CD Pipeline** → See all 6 stages stream in real-time
3. **Download Artifact** → Save full pipeline logs
4. **Check DevOps Dashboard** → Show Docker, K8s pods/deployments, and GitHub workflows
5. **View Pipeline History** → Show trend of pipeline runs

### Key Features to Highlight:
- ✓ Real-time streaming pipeline stages
- ✓ ML defect gating (blocks deployment if risk > 70%)
- ✓ Docker build via Docker Engine API (works in containers)
- ✓ Kubernetes deployment + rollout monitoring
- ✓ GitHub Actions workflow visibility
- ✓ Artifact storage (all logs saved as JSON)
- ✓ Optional webhook notifications (configurable via env var)
- ✓ Full integration: backend → frontend

---

## 🔧 Configuration

### Optional Webhook Notifications
Set environment variable to send pipeline completion notifications:
```bash
export PIPELINE_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

After pipeline completes, a POST will be sent with:
```json
{
  "pipeline_id": "ABC123XY",
  "filename": "app.py",
  "status": "success",
  "timestamp": "2026-05-01T10:30:00"
}
```

### Kubernetes Namespace
By default, queries look in `default` namespace. To change:
- Modify `/api/kubernetes/pods?namespace=custom`
- Modify `/api/kubernetes/deployments?namespace=custom`

---

## 📊 Example Artifact (Saved in `data/pipeline_artifacts/{id}.json`)
```json
{
  "pipeline_id": "ABC123XY",
  "filename": "app.py",
  "status": "success",
  "timestamp": "2026-05-01T10:30:00",
  "results": [
    {
      "stage": "lint",
      "status": "pass",
      "returncode": 0,
      "stdout": "",
      "stderr": "",
      "duration": 0.5
    },
    {
      "stage": "k8s_deploy",
      "status": "pass",
      "stdout": "deployment.apps/proj3-defectsense configured",
      "stderr": "",
      "duration": 2.3
    }
  ]
}
```

---

## ✅ What's Connected Now

| Component | Backend | Frontend | Status |
|-----------|---------|----------|--------|
| **Pipeline Runner** | ✓ Full 6-stage pipeline | ✓ Real-time UI + artifact download | ✅ |
| **Docker** | ✓ Images & containers API | ✓ DevOps dashboard | ✅ |
| **Kubernetes** | ✓ Cluster info, pods, deployments | ✓ DevOps dashboard | ✅ |
| **GitHub Actions** | ✓ Workflow detection | ✓ DevOps dashboard | ✅ |
| **Artifacts** | ✓ Save to disk + download | ✓ Download button + viewer | ✅ |
| **Webhooks** | ✓ Optional notifications | - | ✅ (optional) |
| **History** | ✓ Tracked in JSON | ✓ History table | ✅ |

---

## 🎯 For Your Demo

All the infrastructure is now visible and controllable from the frontend:
- Run a pipeline and watch it succeed/fail in real-time
- Click the **DevOps Dashboard** to see Docker, K8s, and GitHub status live
- Show the artifact download to prove all logs are persisted
- Explain the ML defect gate (blocks bad code from deploying)
- Highlight the end-to-end integration

This is **production-ready** demo code! 🚀
