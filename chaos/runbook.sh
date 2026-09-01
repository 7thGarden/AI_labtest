#!/usr/bin/env bash
#
# =============================================================================
#  OpenSRE DEMO - CHAOS RUNBOOK
# =============================================================================
#  Inject failures into YugabyteDB, Aerospike, Kubernetes pods and nodes so
#  they can be observed and analyzed through the OpenSRE dashboard.
#
#  USAGE
#  -----
#    ./chaos/runbook.sh <failure> [options]
#
#  FAILURES (inject)
#  -----------------
#    aerospike-down          Stop the Aerospike container (health & queries fail)
#    yugabyte-down           Stop the YugabyteDB container (SQL fails)
#    pod-crash               Force the catalog-api pod to crash-loop / restart
#    pod-delete              Delete the catalog-api pod (K8s reschedules -> restart)
#    pod-cpu                 Inject a CPU spike into the catalog-api pod
#    pod-memory              Inject a memory spike into the catalog-api pod
#    system-pod-kill         Kill a kube-system pod (e.g. coredns) -> self-healing
#    node-cordon             Cordon the worker node (no new pods scheduled)
#    node-drain              Drain the worker node (evicts pods)
#
#  RECOVERY (restore)
#  ------------------
#    ./chaos/runbook.sh recover aerospike-up    Start Aerospike again
#    ./chaos/runbook.sh recover yugabyte-up     Start Yugabyte again
#    ./chaos/runbook.sh recover uncordon        Uncordon the worker node
#    ./chaos/runbook.sh recover all             Restore everything
#
# =============================================================================

set -euo pipefail

# ---------- Configuration --------------------------------------------------
CLUSTER="${CLUSTER:-kind-opensre-demo}"
CATALOG_DEPLOY="catalog-api"
CATALOG_NS="opensre"
WORKER_NODE="${WORKER_NODE:-opensre-demo-worker}"
SYSTEM_POD_PATTERN="${SYSTEM_POD_PATTERN:-coredns}"

# ---------- Pretty printing ------------------------------------------------
BOLD="\033[1m"
DIM="\033[2m"
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RESET="\033[0m"

banner() { printf "${CYAN}\n==============================================\n  %s\n==============================================\n${RESET}\n" "$*"; }
step()   { printf "${BOLD}${YELLOW}» %s${RESET}\n" "$*"; }
ok()     { printf "${GREEN}  ✓ %s${RESET}\n" "$*"; }
warn()   { printf "${YELLOW}  ⚠ %s${RESET}\n" "$*"; }
fail()   { printf "${RED}  ✗ %s${RESET}\n" "$*"; }
note()   { printf "${DIM}    %s${RESET}\n" "$*"; }

usage() {
  sed -n '3,33p' "$0"
  exit 1
}

# ---------- Preflight ------------------------------------------------------
preflight() {
  step "Preflight checks"

  if ! command -v kubectl &>/dev/null; then
    fail "kubectl not found on PATH"; exit 1
  fi

  if ! kubectl config get-contexts -o name 2>/dev/null | grep -q "${CLUSTER}"; then
    warn "Cluster context '${CLUSTER}' not found in kubeconfig"
    note "Available contexts:"
    kubectl config get-contexts -o name 2>/dev/null | sed 's/^/      /' || true
  fi

  if command -v docker &>/dev/null; then
    note "docker detected — using it for container commands"
  elif command -v podman &>/dev/null; then
    warn "podman detected — using it (aliasing docker)"
    docker() { command podman "$@"; }
  else
    warn "Neither docker nor podman found — container failures will be skipped"
  fi

  ok "Preflight done"
  echo
}

# ---------- Container helpers ----------------------------------------------

# ---------- Failure: Aerospike down ----------------------------------------
aerospike_down() {
  banner "Injecting failure: AEROSPIKE DOWN"
  step "Killing the Aerospike container"
  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^aerospike$'; then
    docker stop aerospike
    ok "Aerospike container stopped"
  else
    warn "No 'aerospike' container found — nothing to do"
  fi
  echo
  echo "  >>> Open the Aerospike page in the dashboard — health should flip to"
  echo "      'Unreachable' and scans/queries will error out."
  echo
  echo "  >>> Then run './chaos/runbook.sh recover aerospike-up' to bring it back."
}

# ---------- Failure: Yugabyte down -----------------------------------------
yugabyte_down() {
  banner "Injecting failure: YUGABYTE DOWN"
  step "Killing the YugabyteDB container"
  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^yugabyte$'; then
    docker stop yugabyte
    ok "YugabyteDB container stopped"
  else
    warn "No 'yugabyte' container found — nothing to do"
  fi
  echo
  echo "  >>> Open the YugabyteDB page in the dashboard — health should flip to"
  echo "      'Unreachable' and SQL queries will fail with a connection error."
  echo
  echo "  >>> Then run './chaos/runbook.sh recover yugabyte-up' to bring it back."
}

# ---------- Failure: Pod crash-loop ----------------------------------------
pod_crash() {
  banner "Injecting failure: CATALOG-API POD CRASH-LOOP"
  step "Scaling deployment to 0 then back up to force a crash"
  kubectl --context "${CLUSTER}" scale deploy "${CATALOG_DEPLOY}" -n "${CATALOG_NS}" --replicas=0
  ok "Scaled catalog-api to 0"
  sleep 2
  kubectl --context "${CLUSTER}" scale deploy "${CATALOG_DEPLOY}" -n "${CATALOG_NS}" --replicas=1
  ok "Scaled catalog-api back to 1"
  echo
  echo "  >>> The pod is being recreated. To observe a CRASH (restart count climbing),"
  echo "      call the injected crash endpoint:"
  echo
  echo "          curl -s <service-url>/failure/crash"
  echo
  echo "  >>> Watch the Kubernetes page: the pod RESTARTS column will increase."
}

# ---------- Failure: Pod delete (reschedule) -------------------------------
pod_delete() {
  banner "Injecting failure: CATALOG-API POD DELETE"
  step "Deleting the catalog-api pod (K8s will reschedule it)"
  local pod
  pod=$(kubectl --context "${CLUSTER}" get pod -n "${CATALOG_NS}" -l app=catalog-api -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  if [[ -z "${pod}" ]]; then
    warn "No catalog-api pod found — nothing to delete"
    return
  fi
  kubectl --context "${CLUSTER}" delete pod "${pod}" -n "${CATALOG_NS}" --wait=false
  ok "Deleted pod '${pod}'"
  echo
  echo "  >>> Kubernetes will immediately recreate it. This is a good one to show"
  echo "      'self-healing' + the pod restart count / events in OpenSRE."
}

# ---------- Failure: Pod CPU spike -----------------------------------------
pod_cpu() {
  banner "Injecting failure: CATALOG-API CPU SPIKE"
  step "Running the /failure/cpu endpoint"
  local ep
  ep=$(kubectl --context "${CLUSTER}" get pod -n "${CATALOG_NS}" -l app=catalog-api -o jsonpath='{.items[0].status.podIP}' 2>/dev/null || true)
  if [[ -z "${ep}" ]]; then
    warn "No catalog-api pod found — cannot hit CPU endpoint"
    return
  fi
  ok "Hitting http://${ep}:8000/failure/cpu (~20s busy loop)"
  curl -s --max-time 30 "http://${ep}:8000/failure/cpu" || true
  echo
  echo "  >>> CPU metric should spike in Grafana / VictoriaMetrics."
}

# ---------- Failure: Pod memory spike --------------------------------------
pod_memory() {
  banner "Injecting failure: CATALOG-API MEMORY SPIKE"
  step "Running the /failure/memory endpoint (allocates ~300 MB)"
  local ep
  ep=$(kubectl --context "${CLUSTER}" get pod -n "${CATALOG_NS}" -l app=catalog-api -o jsonpath='{.items[0].status.podIP}' 2>/dev/null || true)
  if [[ -z "${ep}" ]]; then
    warn "No catalog-api pod found — cannot hit memory endpoint"
    return
  fi
  ok "Hitting http://${ep}:8000/failure/memory"
  curl -s --max-time 30 "http://${ep}:8000/failure/memory" || true
  echo
  echo "  >>> Resident memory metric should climb. Watch for an OOM/terminate".
}

# ---------- Failure: Kill a system pod (self-healing) ----------------------
system_pod_kill() {
  banner "Injecting failure: KILL SYSTEM POD (${SYSTEM_POD_PATTERN})"
  step "Finding and deleting a matching kube-system pod"
  local pod
  pod=$(kubectl --context "${CLUSTER}" get pod -n kube-system --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null | grep -E "^${SYSTEM_POD_PATTERN}" | head -1 | awk '{print $1}' || true)
  if [[ -z "${pod}" ]]; then
    warn "No kube-system pod matching '${SYSTEM_POD_PATTERN}' found"
    return
  fi
  kubectl --context "${CLUSTER}" delete pod "${pod}" -n kube-system --wait=false
  ok "Deleted system pod '${pod}'"
  echo
  echo "  >>> Kubelet will immediately recreate it. A great visual for cluster"
  echo "      self-healing — watch the pod come back in kubectl get pods -A."
}

# ---------- Failure: Node cordon -------------------------------------------
node_cordon() {
  banner "Injecting failure: CORDON WORKER NODE (${WORKER_NODE})"
  step "Marking worker node as unschedulable"
  kubectl --context "${CLUSTER}" cordon "${WORKER_NODE}"
  ok "Node '${WORKER_NODE}' cordoned (SchedulingDisabled)"
  echo
  echo "  >>> Show kubectl get nodes — the worker will show 'Ready,SchedulingDisabled'."
  echo "  >>> New pods will no longer schedule onto it."
  echo
  echo "  >>> Recover with './chaos/runbook.sh recover uncordon'"
}

# ---------- Failure: Node drain --------------------------------------------
node_drain() {
  banner "Injecting failure: DRAIN WORKER NODE (${WORKER_NODE})"
  step "Draining node (evicts pods, marks unschedulable)"
  kubectl --context "${CLUSTER}" drain "${WORKER_NODE}" \
    --ignore-daemonsets --delete-emptydir-data --force
  ok "Node drained"
  echo
  echo "  >>> Workload pods are evicted from the worker node."
  echo "  >>> Recover with './chaos/runbook.sh recover uncordon' (then re-start any evicted app pods)."
}

# ---------- Recovery -------------------------------------------------------
recover() {
  local target="${1:-all}"
  banner "RECOVERY: ${target}"

  case "${target}" in
    aerospike-up)
      step "Starting Aerospike container"
      docker start aerospike 2>/dev/null && ok "Aerospike started" || warn "Could not start Aerospike"
      ;;
    yugabyte-up)
      step "Starting YugabyteDB container"
      docker start yugabyte 2>/dev/null && ok "Yugabyte started" || warn "Could not start Yugabyte"
      ;;
    uncordon)
      step "Uncordoning worker node"
      kubectl --context "${CLUSTER}" uncordon "${WORKER_NODE}" && ok "Node uncordoned" || warn "Uncordon failed"
      ;;
    all)
      step "Restoring all services"
      docker start aerospike 2>/dev/null && ok "Aerospike started" || warn "No aerospike container"
      docker start yugabyte 2>/dev/null && ok "Yugabyte started" || warn "No yugabyte container"
      kubectl --context "${CLUSTER}" uncordon "${WORKER_NODE}" 2>/dev/null && ok "Node uncordoned" || warn "Uncordon failed"
      kubectl --context "${CLUSTER}" rollout status deploy "${CATALOG_DEPLOY}" -n "${CATALOG_NS}" 2>/dev/null && ok "catalog-api running" || warn "catalog-api not scaling"
      ;;
    *)
      warn "Unknown recovery target '${target}'"
      usage
      ;;
  esac
  echo
  echo "  >>> Verify:"
  echo "      docker ps            (containers)"
  echo "      kubectl get nodes    (node state)"
  echo "      kubectl get pods -A  (pod state)"
}

# ---------- Status ---------------------------------------------------------
show_status() {
  banner "CURRENT DEMO STATE"

  echo "--- Containers ---"
  if command -v docker &>/dev/null; then
    docker ps -a --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null | grep -iE "NAME|aero|yuga" || true
  else
    podman ps -a --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null | grep -iE "NAME|aero|yuga" || true
  fi

  echo
  echo "--- Nodes ---"
  kubectl --context "${CLUSTER}" get nodes 2>/dev/null || true

  echo
  echo "--- catalog-api pods ---"
  kubectl --context "${CLUSTER}" get pods -n "${CATALOG_NS}" -o wide 2>/dev/null || true

  echo
  echo "--- Sign of life checks ---"
  if (command docker ps 2>/dev/null || command podman ps 2>/dev/null) | grep -q aerospike; then
    ok "Aerospike: RUNNING"
  else
    fail "Aerospike: DOWN"
  fi
  if (command docker ps 2>/dev/null || command podman ps 2>/dev/null) | grep -q yugabyte; then
    ok "Yugabyte: RUNNING"
  else
    fail "Yugabyte: DOWN"
  fi
  local node_state
  node_state=$(kubectl --context "${CLUSTER}" get nodes "${WORKER_NODE}" --no-headers 2>/dev/null | awk '{print $2}' || true)
  case "${node_state}" in
    *SchedulingDisabled*) fail "Worker node: CORDONED/DRAINED" ;;
    Ready) ok "Worker node: Ready" ;;
    *) warn "Worker node: ${node_state:-unknown}" ;;
  esac
}

# ---------- Dispatch -------------------------------------------------------
main() {
  [[ $# -lt 1 ]] && usage

  local action="$1"; shift

  case "${action}" in
    aerospike-down)   preflight; aerospike_down ;;
    yugabyte-down)    preflight; yugabyte_down ;;
    pod-crash)        preflight; pod_crash ;;
    pod-delete)       preflight; pod_delete ;;
    pod-cpu)          preflight; pod_cpu ;;
    pod-memory)       preflight; pod_memory ;;
    system-pod-kill)  preflight; system_pod_kill ;;
    node-cordon)      preflight; node_cordon ;;
    node-drain)       preflight; node_drain ;;
    status)           preflight; show_status ;;
    recover)          recover "${@:-all}" ;;
    help|--help|-h)   usage ;;
    *)                usage ;;
  esac
}

main "$@"
