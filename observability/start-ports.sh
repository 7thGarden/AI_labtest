#!/usr/bin/env bash
# start-ports.sh — Start kubectl port-forwards for ELK stack
# Run this script before using the Logs page or Kibana
#
# Usage:
#   ./observability/start-ports.sh
#
# Keeps running in foreground. Press Ctrl+C to stop.

set -euo pipefail

NAMESPACE="observability"

cleanup() {
    echo ""
    echo ">> Stopping port-forwards..."
    kill $(jobs -p) 2>/dev/null || true
    wait 2>/dev/null || true
    echo ">> Done."
}
trap cleanup EXIT INT TERM

echo ">> Starting port-forwards for ELK stack..."

kubectl port-forward -n "$NAMESPACE" svc/opensre-es-master 9200:9200 &
ES_PID=$!
echo "   Elasticsearch: http://localhost:9200 (PID: $ES_PID)"

kubectl port-forward -n "$NAMESPACE" svc/opensre-kibana-kibana 5601:5601 &
KB_PID=$!
echo "   Kibana:        http://localhost:5601 (PID: $KB_PID)"

kubectl port-forward -n "$NAMESPACE" svc/victoriametrics-victoria-metrics-single-server 8428:8428 &
VM_PID=$!
echo "   VictoriaMetrics: http://localhost:8428 (PID: $VM_PID)"

echo ""
echo ">> All port-forwards active. Press Ctrl+C to stop."
echo ">> Keep this terminal open while using the app."
echo ""

wait
