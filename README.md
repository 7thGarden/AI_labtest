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
- Aerospike Database
- YugabyteDB Database

### Backend

- FastAPI REST APIs
- Kubernetes Integration
- OpenSRE CLI Integration
- VictoriaMetrics Health Check
- Command Execution Layer
- GitHub Integration (commits, branches, workflows, issues)
- Aerospike Connector
- YugabyteDB Connector

### Frontend

- Dashboard
- Kubernetes Overview
- Metrics Page
- AI Analysis
- GitHub Integration
- Aerospike Console
- YugabyteDB Console
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
| NoSQL Database | Aerospike |
| Distributed SQL Database | YugabyteDB |
| Source Control Integration | GitHub API |
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
│   ├── vmagent-values.yaml
│   └── grafana-values.yaml
│
├── chaos/
│   ├── runbook.sh
│   └── README.md
│
├── docker-compose.yml
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

The Grafana chart is deployed with a VictoriaMetrics datasource and a pre-provisioned **"Catalog API Overview"** dashboard (viewable live inside the Metrics page):

```bash
helm install grafana grafana/grafana \
  -n observability \
  -f observability/grafana-values.yaml
```

The values file enables anonymous Viewer access and iframe embedding so the dashboard harts can be rendered live in the React frontend. Login with `admin` / `admin123` for full access.

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

## Start the Databases (Aerospike & YugabyteDB)

The backend connects to Aerospike and YugabyteDB for the database analytics pages. Start them with Docker Compose:

```bash
docker compose up -d
```

Or with Podman:

```bash
podman run -d --name aerospike -p 3001:3000 docker.io/aerospike/aerospike-server
podman run -d --name yugabyte --network host docker.io/yugabytedb/yugabyte \
  bin/yugabyted start --daemon=false --listen=0.0.0.0
```

YugabyteDB's YSQL (PostgreSQL-compatible API) listens on `localhost:5433` and Aerospike on `localhost:3001`.

---

### Configure GitHub

Copy the integration credentials into `opensre-backend/.env`:

```
GITHUB_TOKEN=ghp_xxxxx
GITHUB_REPO=owner/repo-name
```

Create a Personal Access Token at https://github.com/settings/tokens (scope: `repo` for private repos or `public_repo` for public repos).

Restart the backend after editing `.env`.

---

# 🎭 Chaos Engineering / Failure Demo

This project ships with a chaos runbook to inject real failures into YugabyteDB,
Aerospike, and the Kubernetes cluster so they can be observed and analyzed live
through the OpenSRE dashboard. See [`chaos/README.md`](chaos/README.md) for the
full guide.

```bash
# Show current state (read-only)
./chaos/runbook.sh status

# Inject a failure
./chaos/runbook.sh aerospike-down      # Aerospike container down
./chaos/runbook.sh yugabyte-down       # YugabyteDB container down
./chaos/runbook.sh pod-crash           # Force catalog-api crash/restart
./chaos/runbook.sh pod-cpu             # CPU spike in catalog-api pod
./chaos/runbook.sh pod-memory          # Memory spike in catalog-api pod
./chaos/runbook.sh system-pod-kill     # Kill a kube-system pod (self-healing)
./chaos/runbook.sh node-cordon         # Cordon the worker node
./chaos/runbook.sh node-drain          # Drain the worker node

# Recover
./chaos/runbook.sh recover all
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

## Aerospike

```
GET /api/aerospike/health
```

Checks Aerospike connectivity.

```
GET /api/aerospike/query?namespace=test&set=users&key=1
```

Fetches a record by key.

```
POST /api/aerospike/write
```

Writes a record.

```
POST /api/aerospike/scan
```

Scans all records in a set.

```
POST /api/aerospike/delete
```

Deletes a record.

---

## YugabyteDB

```
GET /api/yugabyte/health
```

Checks YugabyteDB connectivity.

```
POST /api/yugabyte/query
```

Runs a read SQL query.

```
POST /api/yugabyte/execute
```

Runs any SQL statement.

```
POST /api/yugabyte/insert
```

Inserts a row and returns it.

```
POST /api/yugabyte/update
```

Updates rows matching a `where` clause.

```
POST /api/yugabyte/delete
```

Deletes rows matching a `where` clause.

---

## GitHub

```
GET /api/github/health
```

Checks GitHub connectivity and returns the connected repository.

```
GET /api/github/branches
```

Lists all repository branches.

```
GET /api/github/commits?sha=main&limit=50
```

Lists commits, optionally filtered by branch/SHA and date range (`since`, `until`).

```
GET /api/github/workflows?limit=20
```

Lists recent GitHub Actions workflow runs.

```
GET /api/github/issues?state=open&limit=30
```

Lists repository issues, filtered by state.

```
GET /api/github/repo
```

Returns repository metadata (stars, forks, description, visibility).

---

# 🖥 Dashboard Overview

The React dashboard consists of the following pages:

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
- Live embedded Grafana dashboard (Catalog API Overview) with real-time panels

---

### 🗄 Aerospike

- Connection status
- Record browser (query / scan / write / delete)

---

### 🗄 YugabyteDB

- Connection status
- SQL console (query / execute / insert / update / delete)

---

### 🤖 AI Analysis

- OpenSRE Version
- OpenSRE Doctor Output
- Backend integration status

---

### 🔗 GitHub

- Repository overview
- Branch selector
- Commit history
- GitHub Actions workflow runs
- Issues feed

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
- ✔ Aerospike Connector
- ✔ YugabyteDB Connector
- ✔ GitHub Integration

---

## ⭐ Notes

This project is intended as a local development and learning environment for exploring Kubernetes observability and AI-assisted operations using OpenSRE. It provides a reproducible setup for experimenting with monitoring, telemetry collection, and dashboard development before deploying to a production environment.