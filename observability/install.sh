#!/usr/bin/env bash
#
# install.sh - reproducible OpenSRE observability stack (pinned chart versions)
#
# Installs / upgrades: VictoriaMetrics single, Grafana, OpenTelemetry collector,
# vmagent, kube-state-metrics, node-exporter.
# NEW: Elasticsearch, Kibana, Fluent Bit for ELK log stack
#
# Usage:
#   ./observability/install.sh
#
# Idempotent: safe to re-run after chart version or values changes.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="observability"

# Chart versions (pinned for reproducibility)
VICTORIAMETRICS_CHART_VERSION="0.45.0"
VMAGENT_CHART_VERSION="0.46.0"
GRAFANA_CHART_VERSION="10.5.15"
OTEL_CHART_VERSION="0.172.0"
KUBE_STATE_METRICS_CHART_VERSION="8.4.1"
NODE_EXPORTER_CHART_VERSION="4.56.3"
ELASTICSEARCH_CHART_VERSION="8.5.1"
KIBANA_CHART_VERSION="8.5.1"

ensure_repos() {
    helm repo add vm https://victoriametrics.github.io/helm-charts/ >/dev/null 2>&1 || true
    helm repo add grafana https://grafana.github.io/helm-charts/ >/dev/null 2>&1 || true
    helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts >/dev/null 2>&1 || true
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts/ >/dev/null 2>&1 || true
    helm repo add elastic https://helm.elastic.co >/dev/null 2>&1 || true
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

# Elasticsearch single-node cluster for demo
install_elasticsearch() {
    echo ">> installing Elasticsearch (single-node demo)..."
    helm upgrade --install opensre-es elastic/elasticsearch \
        --namespace "$NAMESPACE" \
        --version "$ELASTICSEARCH_CHART_VERSION" \
        --values "$SCRIPT_DIR/es-values.yaml"
}

# Wait for Elasticsearch to be ready
wait_for_elasticsearch() {
    echo ">> waiting for Elasticsearch to be ready..."
    for i in $(seq 1 30); do
        if kubectl exec -n "$NAMESPACE" opensre-es-master-0 -- curl -sf http://localhost:9200/_cluster/health >/dev/null 2>&1; then
            HEALTH=$(kubectl exec -n "$NAMESPACE" opensre-es-master-0 -- curl -s http://localhost:9200/_cluster/health)
            STATUS=$(echo "$HEALTH" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
            if [ "$STATUS" = "green" ] || [ "$STATUS" = "yellow" ]; then
                echo ">> Elasticsearch cluster status: $STATUS"
                return 0
            fi
        fi
        echo ">> waiting for ES cluster (attempt $i/30)..."
        sleep 10
    done
    echo ">> WARNING: Elasticsearch not ready after 5 minutes"
    return 1
}

# Kibana dashboard
install_kibana() {
    echo ">> installing Kibana..."
    wait_for_elasticsearch

    # Clean up any stale Kibana resources from previous failed installs
    kubectl delete job -n "$NAMESPACE" -l app=kibana --ignore-not-found 2>/dev/null || true
    kubectl delete configmap -n "$NAMESPACE" -l app=kibana --ignore-not-found 2>/dev/null || true
    kubectl delete role -n "$NAMESPACE" pre-install-opensre-kibana-kibana --ignore-not-found 2>/dev/null || true
    kubectl delete rolebinding -n "$NAMESPACE" pre-install-opensre-kibana-kibana --ignore-not-found 2>/dev/null || true
    kubectl delete serviceaccount -n "$NAMESPACE" pre-install-opensre-kibana-kibana --ignore-not-found 2>/dev/null || true

    # Create empty cert secret to satisfy chart volume mount
    kubectl create secret generic elasticsearch-master-certs \
        --from-literal=tls.crt="" \
        --from-literal=tls.key="" \
        --from-literal=ca.crt="" \
        -n "$NAMESPACE" 2>/dev/null || true

    # Create token secret to satisfy chart
    kubectl create secret generic opensre-kibana-kibana-es-token \
        --from-literal=token="" \
        -n "$NAMESPACE" 2>/dev/null || true

    # Delete existing release if failed
    helm delete opensre-kibana -n "$NAMESPACE" --no-hooks 2>/dev/null || true

    helm install opensre-kibana elastic/kibana \
        --namespace "$NAMESPACE" \
        --version "$KIBANA_CHART_VERSION" \
        --set service.type=NodePort \
        --set service.nodePort=30001 \
        --set elasticsearchHosts="http://opensre-es-master:9200" \
        --set healthCheckPath="/api/status" \
        --no-hooks
}

# Fluent Bit log shipper
install_fluent_bit() {
    echo ">> installing Fluent Bit DaemonSet..."
    kubectl apply -f "$SCRIPT_DIR/fluent-bit.yaml"
}

echo ">> ensuring helm repos"
ensure_repos
echo ">> ensuring namespace '$NAMESPACE'"
ensure_namespace

# Core metrics stack
install_victoriametrics
install_grafana
install_otel_collector
install_vmagent
install_kube_state_metrics
install_node_exporter

# ELK log stack
install_elasticsearch
install_kibana
install_fluent_bit

echo ">> done. Verifying:"
kubectl get pods -n "$NAMESPACE"

# Wait for Elasticsearch
echo ">> waiting for Elasticsearch cluster health..."
sleep 15
wait_for_elasticsearch || true

# Create ILM policy
echo ">> creating ILM policy..."
kubectl exec -n "$NAMESPACE" opensre-es-master-0 -- curl -sf -X PUT "http://localhost:9200/_ilm/policy/logs-opensre-policy" \
  -H "Content-Type: application/json" \
  -d '{
    "policy": {
      "phases": {
        "hot": {
          "min_age": "0ms",
          "actions": {
            "rollover": { "max_primary_shard_size": "2gb", "max_age": "1d" },
            "set_priority": { "priority": 100 }
          }
        },
        "warm": {
          "min_age": "7d",
          "actions": {
            "shrink": { "number_of_shards": 1 },
            "forcemerge": { "max_num_segments": 1 },
            "set_priority": { "priority": 50 }
          }
        },
        "delete": {
          "min_age": "30d",
          "actions": { "delete": {} }
        }
      }
    }
  }' || true

# Create index template
echo ">> creating index template for logs-opensre-*..."
kubectl exec -n "$NAMESPACE" opensre-es-master-0 -- curl -sf -X PUT "http://localhost:9200/_index_template/logs-opensre-template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["logs-opensre-*"],
    "priority": 200,
    "template": {
      "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "index.lifecycle.name": "logs-opensre-policy",
        "index.lifecycle.rollover_alias": "logs-opensre"
      },
      "mappings": {
        "properties": {
          "@timestamp": { "type": "date" },
          "log": { "type": "text" },
          "stream": { "type": "keyword" },
          "cluster_name": { "type": "keyword" },
          "environment": { "type": "keyword" },
          "k8s_namespace": { "type": "keyword" },
          "k8s_pod_name": { "type": "keyword" },
          "k8s_container_name": { "type": "keyword" },
          "k8s_node_name": { "type": "keyword" },
          "k8s_labels": { "type": "object", "enabled": true }
        }
      }
    }
  }' || true

# Wait for Kibana
echo ">> waiting for Kibana..."
for i in $(seq 1 30); do
    if kubectl get pod -n "$NAMESPACE" -l app=kibana -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null | grep -q "True"; then
        echo ">> Kibana is ready"
        break
    fi
    echo ">> waiting for Kibana (attempt $i/30)..."
    sleep 10
done

# Create Kibana index pattern
echo ">> creating Kibana index pattern..."
KIBANA_POD=$(kubectl get pod -n "$NAMESPACE" -l app=kibana -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$KIBANA_POD" ]; then
    kubectl exec -n "$NAMESPACE" "$KIBANA_POD" -- curl -sf -X POST "http://localhost:5601/api/saved_objects/index-pattern/logs-opensre-*" \
      -H "Content-Type: application/json" \
      -H "kbn-xsrf: true" \
      -d '{
        "attributes": {
          "title": "logs-opensre-*",
          "timeFieldName": "@timestamp"
        }
      }' || true

    # Set as default index pattern
    kubectl exec -n "$NAMESPACE" "$KIBANA_POD" -- curl -sf -X POST "http://localhost:5601/api/kibana/settings/defaultIndex" \
      -H "Content-Type: application/json" \
      -H "kbn-xsrf: true" \
      -d '{"value":"logs-opensre-*"}' || true
fi

echo ""
echo "==========================================="
echo "  ELK Stack Installation Complete!"
echo "==========================================="
echo ""
echo "  Elasticsearch : http://localhost:9200 (NodePort 30920)"
echo "  Kibana        : http://localhost:3001 (NodePort 30001)"
echo "  Logs Explorer : http://localhost:5173/logs"
echo ""
echo "  Index pattern : logs-opensre-*"
echo "  ILM policy    : logs-opensre-policy (hot 1d, warm 7d, delete 30d)"
echo "==========================================="
