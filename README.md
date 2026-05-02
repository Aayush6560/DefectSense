# DefectSense

AI-powered code risk analysis and MLOps pipeline.

## Features
- Login/register with secure cookies (works with NGINX, HTTPS)
- Upload Python files for static + ML risk analysis
- RAG (Retrieval-Augmented Generation) chat for code insights
- CI/CD pipeline: syntax, tests, ML scan, security, Docker, K8s deploy
- Kubernetes + Docker Compose support
- NGINX ingress for TLS/domain

## Quick Start
1. **Docker Compose:**
   ```sh
   docker compose up -d --build
   ```
2. **Kubernetes:**
   ```sh
   kubectl apply -f k8s/deployment.yaml
   kubectl apply -f k8s/service.yaml
   kubectl apply -f k8s/ingress.yaml
   ```
3. **Access:**
   - https://defectsense.local/ (via NGINX ingress)
   - http://localhost:5000/ (direct Docker)

## Endpoints
- `/` — Login page
- `/app` — Main app (after login)
- `/api/auth/*` — Auth endpoints
- `/api/predict` — File analysis
- `/api/chat` — RAG chat
- `/api/pipeline` — Run pipeline
- `/api/pipeline/history` — Pipeline history
- `/health` or `/health.html` — Health check

## Troubleshooting
- **Cookies not working?**
  - Set `COOKIE_SECURE` and `COOKIE_SAMESITE` env vars for your environment.
  - Use HTTPS and a real domain for cross-site cookies.
- **K8s ingress:**
  - Make sure NGINX forwards all headers and TLS is enabled.
- **CI/CD:**
  - Check GitHub Actions logs for failures.

## Credits
Built with Flask, Gunicorn, Docker, Kubernetes, NGINX, and ❤️.
