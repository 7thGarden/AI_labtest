# 🚀 OpenSRE Dashboard

An AI-powered Kubernetes Observability Platform that combines **OpenSRE**, **Kubernetes**, **VictoriaMetrics**, **OpenTelemetry**, and **Grafana** into a single dashboard for monitoring, troubleshooting, and AI-assisted incident analysis.

The project demonstrates how modern observability tools can be integrated with AI to simplify Kubernetes operations and provide a centralized monitoring experience.

---

## ✨ Features

### Infrastructure

- Kubernetes Cluster (Kind)
- Sample FastAPI Application
- OpenTelemetry Collector
- VictoriaMetrics
- vmagent
- Grafana

### Backend

- FastAPI REST APIs
- Kubernetes Integration
- OpenSRE CLI Integration
- VictoriaMetrics Health Check
- Command Execution Layer

### Frontend

- Dashboard
- Kubernetes Overview
- Metrics Page
- AI Analysis
- Settings Page

---

# 🏗 Architecture

```
                        +----------------------+
                        |     React Frontend   |
                        |     (Dashboard)      |
                        +----------+-----------+
                                   |
                          REST API Calls
                                   |
                                   v
                     +---------------------------+
                     |     FastAPI Backend       |
                     |  OpenSRE API Layer        |
                     +------------+--------------+
                                  |
          +-----------------------+-----------------------+
          |                       |                       |
          |                       |                       |
          v                       v                       v

  Kubernetes Cluster      OpenSRE CLI          VictoriaMetrics

          |                                        |
          |                                        |
          +-------------------+--------------------+
                              |
                              v
                         OpenTelemetry
                              |
                              v
                           Grafana
```

---

# 🛠 Tech Stack

| Category | Technology |
|----------|------------|
| Frontend | React + Vite |
| Backend | FastAPI |
| Container Runtime | Podman |
| Kubernetes | Kind |
| Metrics | VictoriaMetrics |
| Metrics Collection | vmagent |
| Telemetry | OpenTelemetry Collector |
| Visualization | Grafana |
| AI | OpenSRE |
| Language | Python 3.13 |
| Package Manager | pip |
| API Testing | Bruno |
| Version Control | Git & GitHub |

---

# 📂 Project Structure

```
opensre-demo/
│
├── catalog-api/
│
├── frontend/
│
├── opensre-backend/
│
├── infra/
│   ├── kind/
│   └── k8s/
│
├── observability/
│   ├── otel-values.yaml
│   └── vmagent-values.yaml
│
└── README.md
```

---

# ⚙️ Prerequisites

Install the following tools before starting.

- Ubuntu 24.04/26.04 LTS
- Python 3.13+
- Node.js 24+
- Git
- Podman
- Kind
- kubectl
- Helm
- OpenSRE CLI

Verify the installation:

```bash
python3 --version
node -v
npm -v
podman --version
kubectl version --client
kind version
helm version
opensre --version
```
# 🚀 Quick Start

## 1. Clone the Repository

```bash
git clone https://github.com/<YOUR_USERNAME>/opensre-demo.git
cd opensre-demo
```

---

## 2. Create the Kubernetes Cluster

```bash
sudo kind create cluster \
  --name opensre-demo \
  --config infra/kind/kind-config.yaml
```

Verify the cluster:

```bash
kubectl get nodes
```

Expected output:

```
NAME                         STATUS   ROLES
opensre-demo-control-plane   Ready    control-plane
opensre-demo-worker          Ready
```

---

## 3. Build the Sample Application

```bash
cd catalog-api

sudo podman build -t localhost/catalog-api:v1 .
```

Export the image:

```bash
sudo podman save localhost/catalog-api:v1 -o catalog-api.tar
```

Load the image into Kind:

```bash
sudo kind load image-archive catalog-api.tar --name opensre-demo
```

Remove the archive:

```bash
rm catalog-api.tar
```

---

## 4. Deploy the Application

```bash
cd ..

kubectl apply -f infra/k8s/
```

Verify:

```bash
kubectl get all -n opensre
```

Expected:

- catalog-api Deployment
- catalog-api Pod
- catalog-api Service

---

# 📊 Deploy Observability Stack

Create the namespace:

```bash
kubectl create namespace observability
```

## VictoriaMetrics

```bash
helm install victoriametrics vm/victoria-metrics-single \
  -n observability
```

---

## Grafana

```bash
helm install grafana grafana/grafana \
  -n observability \
  --set adminPassword=admin123
```

---

## OpenTelemetry Collector

```bash
helm install otel-collector open-telemetry/opentelemetry-collector \
  -n observability \
  -f observability/otel-values.yaml
```

---

## vmagent

```bash
helm install vmagent vm/victoria-metrics-agent \
  -n observability \
  -f observability/vmagent-values.yaml
```

---

Verify all services:

```bash
kubectl get pods -n observability
```

Expected:

```
grafana
victoriametrics
otel-collector
vmagent
```

All pods should be in the **Running** state.

---

# 🔍 Verify Kubernetes

Check all namespaces:

```bash
kubectl get pods -A
```

Check application:

```bash
kubectl get pods -n opensre
```

Check observability stack:

```bash
kubectl get pods -n observability
```

At this point, the Kubernetes cluster, sample application, and observability stack should all be running successfully.

# ▶️ Running the Project

## Start the Backend

Navigate to the backend directory:

```bash
cd opensre-backend
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Start the FastAPI server:

```bash
uvicorn app.main:app --reload --port 8001
```

Backend API:

```
http://localhost:8001
```

Swagger Documentation:

```
http://localhost:8001/docs
```

---

## Start the Frontend

Navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Frontend URL:

```
http://localhost:5173
```

---

# 📡 Available API Endpoints

## Health

```
GET /api/health
```

Checks whether the backend service is running.

---

## Kubernetes

```
GET /api/kubernetes/nodes
```

Returns all Kubernetes nodes.

```
GET /api/kubernetes/pods
```

Returns all running pods.

```
GET /api/kubernetes/services
```

Returns all Kubernetes services.

```
GET /api/kubernetes/deployments
```

Returns all deployments.

---

## Metrics

```
GET /api/metrics/health
```

Checks VictoriaMetrics connectivity.

---

## OpenSRE

```
GET /api/opensre/version
```

Returns the installed OpenSRE version.

```
GET /api/opensre/doctor
```

Runs `opensre doctor` and returns the diagnostic output.

---

# 🖥 Dashboard Overview

The React dashboard consists of five pages:

### 📊 Dashboard

- Cluster overview
- Node count
- Pod count
- Service count
- Deployment count
- Cluster health summary

---

### ☸ Kubernetes

- Node information
- Pod information
- Cluster resource overview

---

### 📈 Metrics

- VictoriaMetrics health status
- Grafana integration

---

### 🤖 AI Analysis

- OpenSRE Version
- OpenSRE Doctor Output
- Backend integration status

---

### ⚙ Settings

- Backend status
- Kubernetes status
- VictoriaMetrics status
- OpenSRE status
- Quick links to Grafana and Swagger

---

# ✅ Verification

Verify that everything is running correctly.

Backend:

```bash
curl http://localhost:8001/api/health
```

Frontend:

Open:

```
http://localhost:5173
```

Grafana:

```
http://localhost:3000
```

OpenSRE:

```bash
opensre --version
```

Kubernetes:

```bash
kubectl get nodes
kubectl get pods -A
```

If all commands execute successfully and all pods are in the **Running** state, the platform has been deployed successfully.

# 🔧 Troubleshooting

## 1. Kubernetes Cluster Not Reachable

**Error**

```text
The connection to the server 127.0.0.1:<PORT> was refused
```

### Solution

If the Kind cluster was recreated using `sudo`, refresh your kubeconfig:

```bash
mkdir -p ~/.kube

sudo cp /root/.kube/config ~/.kube/config

sudo chown $USER:$USER ~/.kube/config

chmod 600 ~/.kube/config
```

Verify:

```bash
kubectl get nodes
```

---

## 2. catalog-api Pod Stuck in `ErrImageNeverPull`

This happens because the Docker/Podman image hasn't been loaded into the Kind cluster.

Rebuild the image:

```bash
cd catalog-api

sudo podman build -t localhost/catalog-api:v1 .
```

Export the image:

```bash
sudo podman save localhost/catalog-api:v1 -o catalog-api.tar
```

Load it into Kind:

```bash
sudo kind load image-archive catalog-api.tar --name opensre-demo
```

Restart the deployment:

```bash
kubectl rollout restart deployment/catalog-api -n opensre
```

---

## 3. OpenTelemetry Collector CrashLoopBackOff

If the collector fails to start, verify the configuration file:

```bash
observability/otel-values.yaml
```

Apply the updated configuration:

```bash
helm upgrade otel-collector open-telemetry/opentelemetry-collector \
  -n observability \
  -f observability/otel-values.yaml
```

---

## 4. vmagent Installation Failed

Verify the configuration file exists:

```bash
ls observability/
```

Expected:

```
otel-values.yaml
vmagent-values.yaml
```

Install vmagent again:

```bash
helm install vmagent vm/victoria-metrics-agent \
  -n observability \
  -f observability/vmagent-values.yaml
```

---

## 5. Frontend Cannot Connect to Backend

Verify the backend is running:

```bash
curl http://localhost:8001/api/health
```

If not, restart it:

```bash
cd opensre-backend

source .venv/bin/activate

uvicorn app.main:app --reload --port 8001
```

---

## 6. React Dashboard Shows No Data

Verify Kubernetes:

```bash
kubectl get nodes

kubectl get pods -A
```

Verify Backend:

```
http://localhost:8001/docs
```

Verify Frontend:

```
http://localhost:5173
```

---

# 📸 Screenshots

Screenshots of the application will be added after the dashboard UI is finalized.

- Dashboard
- Kubernetes
- Metrics
- AI Analysis
- Settings

---

# 🚀 Future Improvements

- AI-powered incident investigation
- One-click root cause analysis
- AlertManager integration
- Log aggregation with Loki
- Historical incident timeline
- Dashboard charts and graphs
- Authentication & RBAC
- Production deployment on AWS

---

# ✅ Current Status

- ✔ Kubernetes Cluster
- ✔ FastAPI Sample Application
- ✔ React Dashboard
- ✔ OpenSRE Backend
- ✔ VictoriaMetrics
- ✔ vmagent
- ✔ OpenTelemetry Collector
- ✔ Grafana
- ✔ Kubernetes REST APIs
- ✔ OpenSRE CLI Integration

---

## ⭐ Notes

This project is intended as a local development and learning environment for exploring Kubernetes observability and AI-assisted operations using OpenSRE. It provides a reproducible setup for experimenting with monitoring, telemetry collection, and dashboard development before deploying to a production environment.