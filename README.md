# 🚀 OpenSRE Demo Platform

> **An AI-powered Site Reliability Engineering (SRE) Platform built using Kubernetes, OpenTelemetry, VictoriaMetrics, Grafana, and OpenSRE.**

![Status](https://img.shields.io/badge/Status-In%20Development-orange)
![Python](https://img.shields.io/badge/Python-3.14-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![React](https://img.shields.io/badge/React-Frontend-61DAFB)
![Kubernetes](https://img.shields.io/badge/Kubernetes-v1.36-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📖 Overview

Modern distributed applications generate thousands of metrics, logs, and alerts every second. During incidents, Site Reliability Engineers (SREs) spend significant time navigating dashboards, investigating infrastructure, and identifying the root cause of failures.

**OpenSRE Demo Platform** is a cloud-native observability platform that demonstrates how AI can assist SREs during incident investigation.

The platform combines:

- Kubernetes
- OpenTelemetry
- VictoriaMetrics
- Grafana
- OpenSRE CLI
- FastAPI
- React

into a single web application capable of monitoring workloads, visualizing metrics, and performing AI-assisted diagnostics.

---

## 🎯 Project Objectives

The primary objectives of this project are:

- Build a complete cloud-native observability stack.
- Deploy applications on Kubernetes.
- Collect application metrics using OpenTelemetry.
- Store metrics inside VictoriaMetrics.
- Visualize infrastructure using Grafana.
- Integrate OpenSRE for AI-assisted troubleshooting.
- Build a modern web dashboard for SRE operations.
- Demonstrate an end-to-end observability workflow.

---

## 🏗️ High-Level Architecture

```text
                           React Dashboard
                                  │
                                  ▼
                     OpenSRE Backend (FastAPI)
                     │          │            │
                     │          │            │
                     ▼          ▼            ▼
               OpenSRE CLI   kubectl   VictoriaMetrics
                                   │
                                   ▼
                           Kubernetes Cluster
                                   │
                              Catalog API
                                   │
                            /metrics endpoint
                                   │
                                   ▼
                               vmagent
                                   │
                                   ▼
                          VictoriaMetrics
                                   │
                                   ▼
                               Grafana
```

---

## ✨ Features

### Infrastructure

- Kubernetes Cluster (Kind)
- Podman Container Runtime
- Helm Package Management

### Observability

- OpenTelemetry Collector
- VictoriaMetrics
- vmagent
- Grafana Dashboards

### Backend

- FastAPI REST APIs
- Kubernetes Integration
- OpenSRE Integration
- Metrics API

### Frontend *(In Progress)*

- React Dashboard
- Incident Dashboard
- Cluster Health
- AI Assistant
- Metrics Visualization

---

## 🛠️ Tech Stack

### Programming Languages

- Python 3.14
- JavaScript
- YAML
- Bash

---

### Backend

- FastAPI
- Uvicorn
- Requests
- Kubernetes Python Client

---

### Frontend

- React
- Vite
- Axios *(Planned)*

---

### Containerization

- Podman

---

### Container Orchestration

- Kubernetes (Kind)

---

### Observability

- OpenTelemetry Collector
- VictoriaMetrics
- vmagent
- Grafana

---

### AI Layer

- OpenSRE CLI

---

### DevOps Tools

- Git
- GitHub
- Helm
- kubectl
- Kind

---

## 📂 Project Structure

```
opensre-demo/
│
├── catalog-api/                 # Demo application
│
├── opensre-backend/             # FastAPI backend
│
├── frontend/                    # React frontend
│
├── infra/
│   ├── helm/
│   ├── k8s/
│   ├── kind/
│   └── scripts/
│
├── observability/
│   ├── otel-values.yaml
│   ├── vmagent-values.yaml
│   └── ...
│
├── docs/
│
├── README.md
│
└── .gitignore
```

---

# 📋 Prerequisites

The project has been tested on:

- Ubuntu 26.04 LTS
- Python 3.14
- Podman 5.x
- Kubernetes v1.36
- Helm v3
- Kind
- Git

Although Windows with WSL may work, this project is primarily developed and tested on Ubuntu.

---

# 📦 Required Software

Install the following tools before starting:

| Tool | Purpose |
|-------|----------|
| Git | Version Control |
| Python 3.14 | Backend Development |
| Podman | Container Runtime |
| kubectl | Kubernetes CLI |
| Helm | Kubernetes Package Manager |
| Kind | Local Kubernetes Cluster |
| VS Code | Development |
| OpenSRE CLI | AI Incident Analysis |

---

# 🚀 Getting Started

Clone the repository:

```bash
git clone https://github.com/Ankit-Kumar77/AI_labtest.git

cd AI_labtest
```

---

## Install Basic Packages

```bash
sudo apt update

sudo apt install -y \
curl \
wget \
git \
vim \
nano \
zip \
unzip \
jq \
ca-certificates \
gnupg \
software-properties-common \
apt-transport-https \
build-essential
```

---

## Install Podman

```bash
sudo apt install -y podman
```

Verify:

```bash
podman --version

podman info
```

Run a test container:

```bash
podman run hello-world
```

---

## Install kubectl

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s \
https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

chmod +x kubectl

sudo mv kubectl /usr/local/bin/
```

Verify:

```bash
kubectl version --client
```

---

## Install Helm

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

Verify:

```bash
helm version
```

---

## Install Kind

```bash
curl -Lo ./kind \
https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64

chmod +x kind

sudo mv kind /usr/local/bin/
```

Verify:

```bash
kind version
```

---

## Install OpenSRE CLI

```bash
curl -fsSL https://install.opensre.com | bash

source ~/.bashrc
```

Verify:

```bash
opensre --version
```

> **Note:** OpenSRE onboarding and API key configuration can be completed later. The project can be developed without completing the onboarding wizard immediately.

---

# 🚀 Deploying the Project

Follow the steps below to deploy the complete observability stack.

---

# 1. Create the Kubernetes Cluster

Navigate to the project root.

```bash
cd opensre-demo
```

Create the cluster.

```bash
sudo kind create cluster \
  --name opensre-demo \
  --config infra/kind/kind-config.yaml
```

Verify the cluster.

```bash
kubectl get nodes
```

Expected output:

```text
NAME                         STATUS   ROLES           VERSION
opensre-demo-control-plane   Ready    control-plane
opensre-demo-worker          Ready    <none>
```

---

# 2. Build the Catalog API

Navigate to the application.

```bash
cd catalog-api
```

Create the virtual environment.

```bash
python3 -m venv .venv

source .venv/bin/activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Build the container image.

```bash
sudo podman build \
-t localhost/catalog-api:v1 .
```

Export the image.

```bash
sudo podman save \
-o catalog-api.tar \
localhost/catalog-api:v1
```

Load the image into Kind.

```bash
sudo kind load image-archive \
catalog-api.tar \
--name opensre-demo
```

Delete the archive.

```bash
rm catalog-api.tar
```

---

# 3. Deploy the Application

Return to the project root.

```bash
cd ..
```

Deploy the application.

```bash
kubectl apply -f infra/k8s/
```

Verify deployment.

```bash
kubectl get all -n opensre
```

Expected:

- Deployment Running
- Service Running
- Pod Running

---

# 4. Deploy VictoriaMetrics

Add the Helm repository.

```bash
helm repo add vm \
https://victoriametrics.github.io/helm-charts/

helm repo update
```

Create namespace.

```bash
kubectl create namespace observability
```

Install VictoriaMetrics.

```bash
helm install victoriametrics \
vm/victoria-metrics-single \
--namespace observability
```

Verify.

```bash
kubectl get pods -n observability
```

---

# 5. Install Grafana

```bash
helm repo add grafana \
https://grafana.github.io/helm-charts

helm repo update
```

Install.

```bash
helm install grafana \
grafana/grafana \
--namespace observability \
--set adminPassword=admin123
```

Verify.

```bash
kubectl get pods -n observability
```

---

# 6. Install OpenTelemetry Collector

```bash
helm repo add open-telemetry \
https://open-telemetry.github.io/opentelemetry-helm-charts

helm repo update
```

Install.

```bash
helm install otel-collector \
open-telemetry/opentelemetry-collector \
-n observability \
--set mode=deployment \
--set image.repository=ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-k8s \
--set command.name=otelcol-k8s
```

Upgrade using the custom configuration.

```bash
helm upgrade otel-collector \
open-telemetry/opentelemetry-collector \
-n observability \
-f observability/otel-values.yaml
```

---

# 7. Install vmagent

Install vmagent.

```bash
helm install vmagent \
vm/victoria-metrics-agent \
-n observability \
--set remoteWrite[0].url=http://victoriametrics-victoria-metrics-single-server.observability.svc.cluster.local:8428/api/v1/write
```

Upgrade with the scrape configuration.

```bash
helm upgrade vmagent \
vm/victoria-metrics-agent \
-n observability \
-f observability/vmagent-values.yaml
```

---

# 8. Verify the Stack

```bash
kubectl get pods -n observability
```

Expected:

```text
grafana                              Running

otel-collector                       Running

victoriametrics                      Running

vmagent                              Running
```

---

# 9. Start the Catalog API

```bash
cd catalog-api

source .venv/bin/activate

uvicorn app.main:app \
--reload
```

Open:

```
http://localhost:8000/docs
```

Metrics endpoint:

```
http://localhost:8000/metrics
```

---

# 10. Start the Backend

```bash
cd opensre-backend

source .venv/bin/activate

uvicorn app.main:app \
--reload \
--port 8001
```

Open:

```
http://localhost:8001/docs
```

---

# Current API Endpoints

## Catalog API

```
GET /
GET /health
GET /products
GET /metrics
```

---

## OpenSRE Backend

```
GET /api/health

GET /api/kubernetes/nodes

GET /api/kubernetes/pods

GET /api/kubernetes/services

GET /api/metrics/health

GET /api/opensre/version

GET /api/opensre/doctor
```

---

# Current Project Status

| Component | Status |
|------------|--------|
| Ubuntu Setup | ✅ |
| GitHub Repository | ✅ |
| Podman | ✅ |
| Kind Cluster | ✅ |
| Catalog API | ✅ |
| Kubernetes Deployment | ✅ |
| OpenTelemetry Collector | ✅ |
| VictoriaMetrics | ✅ |
| vmagent | ✅ |
| Grafana | ✅ |
| FastAPI Backend | ✅ |
| React Frontend | 🚧 |
| OpenSRE Integration | 🚧 |
| AI Incident Analysis | 🚧 |
| Dashboard UI | 🚧 |

# ⚙️ Environment Variables

Create a `.env` file inside the **opensre-backend** directory.

```env
# OpenSRE CLI

OPENSRE_BINARY=opensre

# Kubernetes

KUBECONFIG=~/.kube/config

# VictoriaMetrics

VICTORIA_METRICS_URL=http://localhost:8428

# Grafana

GRAFANA_URL=http://localhost:3000

# OpenAI (Optional)

OPENAI_API_KEY=YOUR_OPENAI_API_KEY
```

> **Note:** The project can be developed without configuring the API key. The key is only required for AI-assisted incident analysis through OpenSRE.

---

# 📊 Monitoring Stack

The observability stack consists of the following components:

| Component | Purpose |
|------------|---------|
| Catalog API | Demo Application |
| OpenTelemetry Collector | Telemetry Collection |
| vmagent | Metrics Scraping |
| VictoriaMetrics | Time Series Database |
| Grafana | Visualization |
| OpenSRE | AI Incident Analysis |

---

# 📌 Roadmap

## Phase 1 — Infrastructure ✅

- [x] Ubuntu Development Environment
- [x] Git & GitHub
- [x] Podman Installation
- [x] Kubernetes Cluster (Kind)
- [x] Catalog API
- [x] Kubernetes Deployment

---

## Phase 2 — Observability ✅

- [x] OpenTelemetry Collector
- [x] VictoriaMetrics
- [x] vmagent
- [x] Grafana
- [x] Metrics Collection

---

## Phase 3 — Backend 🚧

- [x] FastAPI Setup
- [x] Kubernetes APIs
- [x] Metrics APIs
- [ ] OpenSRE Service Layer
- [ ] Incident APIs
- [ ] AI Analysis APIs

---

## Phase 4 — Frontend 🚧

- [ ] React Dashboard
- [ ] Cluster Overview
- [ ] Metrics Dashboard
- [ ] Incident Dashboard
- [ ] AI Assistant

---

## Phase 5 — AI Integration 🚧

- [ ] OpenSRE Onboarding
- [ ] LLM Integration
- [ ] Root Cause Analysis
- [ ] AI Recommendations

---

# 🛠️ Troubleshooting

## Kind Cluster Not Reachable

If `kubectl` shows:

```text
The connection to the server localhost:8080 was refused
```

Copy the kubeconfig:

```bash
mkdir -p ~/.kube

sudo cp /root/.kube/config ~/.kube/config

sudo chown $USER:$USER ~/.kube/config

chmod 600 ~/.kube/config
```

---

## Rootless Podman Issues

If Kind cannot create the cluster with rootless Podman:

```text
Delegate=yes
```

Use root Podman for Kind:

```bash
sudo kind create cluster \
--name opensre-demo \
--config infra/kind/kind-config.yaml
```

---

## Catalog Image Not Found

If Kind reports:

```text
image not known
```

Rebuild the image:

```bash
sudo podman build \
-t localhost/catalog-api:v1 .
```

Export:

```bash
sudo podman save \
-o catalog-api.tar \
localhost/catalog-api:v1
```

Load:

```bash
sudo kind load image-archive \
catalog-api.tar \
--name opensre-demo
```

---

## OpenTelemetry Collector CrashLoopBackOff

If the Collector enters `CrashLoopBackOff`, verify the configuration:

```bash
kubectl logs \
-n observability \
deployment/otel-collector-opentelemetry-collector
```

Then update the Helm release:

```bash
helm upgrade otel-collector \
open-telemetry/opentelemetry-collector \
-n observability \
-f observability/otel-values.yaml
```

---

## vmagent Installation Error

If Helm reports:

```text
Please define at least one remoteWrite
```

Install using:

```bash
helm install vmagent \
vm/victoria-metrics-agent \
-n observability \
--set remoteWrite[0].url=http://victoriametrics-victoria-metrics-single-server.observability.svc.cluster.local:8428/api/v1/write
```

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Push the branch.
5. Open a Pull Request.

---

# 📜 License

This project is licensed under the **MIT License**.

---

# 👨‍💻 Author

**Ankit Kumar**

- GitHub: https://github.com/Ankit-Kumar77
- LinkedIn: *(Add your LinkedIn profile here)*

---

# ⭐ Support

If you found this project useful:

- ⭐ Star the repository
- 🍴 Fork the project
- 🐛 Report issues
- 💡 Suggest improvements

Your support helps improve the project and encourages further development.

---

> **OpenSRE Demo Platform** is being developed as a demonstration of modern cloud-native observability, Kubernetes monitoring, and AI-assisted Site Reliability Engineering using OpenSRE.