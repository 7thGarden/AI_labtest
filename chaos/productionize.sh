#!/usr/bin/env bash
#
# productionize.sh - make the kind cluster look like a production environment
# with degraded services, failing latency, crashlooping/OOM/kubelet failures
# for OpenSRE to investigate.
#
# Usage:
#   ./productionize.sh up      build+load images, deploy fault workloads, start traffic
#   ./productionize.sh down    remove all fault workloads and traffic
#   ./productionize.sh busy    show only the problematic workloads
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
FAULTS_DIR="$ROOT_DIR/infra/k8s/faults"
CLUSTER="opensre-demo"

FLAKY_IMAGE="localhost/flaky-service:v1"
OOM_IMAGE="localhost/oom-hog:v1"
PROBE_IMAGE="localhost/probe:v1"

fault_manifests() {
    ls "$FAULTS_DIR"/*.yaml
}

build_images() {
    echo ">> building images"
    podman build -t "$FLAKY_IMAGE" -f "$ROOT_DIR/fault-apps/flaky-service/Containerfile" "$ROOT_DIR/fault-apps/flaky-service"
    podman build -t "$OOM_IMAGE" -f "$ROOT_DIR/fault-apps/oom-hog/Containerfile" "$ROOT_DIR/fault-apps/oom-hog"
    podman build -t "$PROBE_IMAGE" -f "$ROOT_DIR/fault-apps/probe/Containerfile" "$ROOT_DIR/fault-apps/probe"
    echo ">> loading images into kind ($CLUSTER)"
    kind load docker-image "$FLAKY_IMAGE" --name "$CLUSTER"
    kind load docker-image "$OOM_IMAGE" --name "$CLUSTER"
    kind load docker-image "$PROBE_IMAGE" --name "$CLUSTER"
}

apply_workloads() {
    echo ">> deploying fault workloads"
    for manifest in $(fault_manifests); do
        kubectl apply -f "$manifest"
    done
}

delete_workloads() {
    echo ">> removing fault workloads"
    for manifest in $(fault_manifests); do
        kubectl delete -f "$manifest" --ignore-not-found --wait=false
    done
}

show_busy() {
    echo ">> problematic workloads"
    kubectl get pods -n opensre -o wide \
        -l 'app in (flaky-service,memory-hog,crashloop,imagepull),name in (pending-pod)' \
        2>/dev/null || true
    kubectl get pods -n opensre | grep -E "memory-hog|crashloop|imagepull|pending-pod|flaky-service"
}

case "${1:-up}" in
    up|deploy)
        build_images
        apply_workloads
        echo ">> waiting for traffic generator to start"
        kubectl rollout status deploy/traffic-gen -n opensre --timeout=120s
        echo ">> done. Busy workloads:"
        show_busy
        ;;
    down|cleanup)
        delete_workloads
        echo ">> done. Remaining opensre pods:"
        kubectl get pods -n opensre | grep -E "catalog-api|traffic|flaky|memory|crash|imagepull|pending" || true
        ;;
    busy|show)
        show_busy
        ;;
    *)
        echo "usage: $0 {up|down|busy}" >&2
        exit 1
        ;;
esac