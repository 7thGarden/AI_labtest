#!/usr/bin/env bash
#
# install.sh - reproducible OpenSRE observability stack (pinned chart versions)
#
# Installs / upgrades: VictoriaMetrics single (with 1-month retention + persistent
# volume), Grafana, OpenTelemetry collector, vmagent (pods + kube-state-metrics +
# node-exporter + kubelet cAdvisor scrapes), kube-state-metrics and node-exporter.
#
# Usage:
#   ./observability/install.sh
#
# Idempotent: safe to re-run after chart version or values changes.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="observability"

VICTORIAMETRICS_CHART_VERSION="0.45.0"
VMAGENT_CHART_VERSION="0.46.0"
GRAFANA_CHART_VERSION="10.5.15"
OTEL_CHART_VERSION="0.172.0"
KUBE_STATE_METRICS_CHART_VERSION="8.4.1"
NODE_EXPORTER_CHART_VERSION="4.56.3"

ensure_repos() {
    helm repo add vm https://victoriametrics.github.io/helm-charts/ >/dev/null 2>&1 || true
    helm repo add grafana https://grafana.github.io/helm-charts/ >/dev/null 2>&1 || true
    helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts >/dev/null 2>&1 || true
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
    helm repo update >/dev/null
}

ensure_namespace() {
    kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 \
        || kubectl create namespace "$NAMESPACE"
}

install_victoriametrics() {
    helm upgrade --install victoriametrics vm/victoria-metrics-single \
        --namespace "$NAMESPACE" \
        --version "$VICTORIAMETRICS_CHART_VERSION" \
        --values "$SCRIPT_DIR/vm-values.yaml"
}

install_grafana() {
    helm upgrade --install grafana grafana/grafana \
        --namespace "$NAMESPACE" \
        --version "$GRAFANA_CHART_VERSION" \
        --values "$SCRIPT_DIR/grafana-values.yaml"
}

install_otel_collector() {
    helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
        --namespace "$NAMESPACE" \
        --version "$OTEL_CHART_VERSION" \
        --values "$SCRIPT_DIR/otel-values.yaml"
}

install_vmagent() {
    helm upgrade --install vmagent vm/victoria-metrics-agent \
        --namespace "$NAMESPACE" \
        --version "$VMAGENT_CHART_VERSION" \
        --values "$SCRIPT_DIR/vmagent-values.yaml"
}

install_kube_state_metrics() {
    helm upgrade --install kube-state-metrics prometheus-community/kube-state-metrics \
        --namespace "$NAMESPACE" \
        --version "$KUBE_STATE_METRICS_CHART_VERSION"
}

install_node_exporter() {
    helm upgrade --install node-exporter prometheus-community/prometheus-node-exporter \
        --namespace "$NAMESPACE" \
        --version "$NODE_EXPORTER_CHART_VERSION"
}

echo ">> ensuring helm repos"
ensure_repos
echo ">> ensuring namespace '$NAMESPACE'"
ensure_namespace

install_victoriametrics
install_grafana
install_otel_collector
install_vmagent
install_kube_state_metrics
install_node_exporter

echo ">> done. Verifying:"
kubectl get pods -n "$NAMESPACE"