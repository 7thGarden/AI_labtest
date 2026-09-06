import json
import tempfile
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import investigation
from app.services import opensre_cli
from app.services import kubectl
from app.services import yugabyte
from app.services import aerospike
from app.utils.command import run_command

router = APIRouter(
    prefix="/api/demo",
    tags=["Demo"],
)

WORKER_NODE = "opensre-demo-worker"
STRESS_POD = "node-stress-demo"
STRESS_NAMESPACE = "opensre"

INSTANCE_ROWS = [
    (21, "OrderService-001-instance"),
    (22, "OrderService-002-instance"),
    (23, "CatalogSync-instance"),
]

AEROSPIKE_INSTANCES = [
    ("instance-001", "OrderService-001", "active"),
    ("instance-002", "OrderService-002", "active"),
    ("instance-003", "CatalogSync-instance", "stale"),
]


class TargetRequest(BaseModel):
    target: str  # "yugabyte" or "aerospike"


def _target_to_container(target: str):
    return {"yugabyte": "yugabyte", "aerospike": "aerospike"}.get(target, target)


def _seed_yugabyte():
    yugabyte.execute(
        "CREATE TABLE IF NOT EXISTS service_instances "
        "(id INT PRIMARY KEY, name TEXT NOT NULL)"
    )
    inserted = []
    for row_id, name in INSTANCE_ROWS:
        res = yugabyte.execute(
            f"INSERT INTO service_instances (id, name) "
            f"VALUES ({row_id}, '{name}') "
            f"ON CONFLICT (id) DO UPDATE SET name = '{name}' "
            f"RETURNING *"
        )
        if res.get("success"):
            inserted.append(name)
    return {"success": True, "inserted": inserted, "table": "service_instances"}


def _seed_aerospike():
    inserted = []
    for key, name, status in AEROSPIKE_INSTANCES:
        res = aerospike.write("test", "demo", key, {
            "name": name, "status": status, "_key": key,
        })
        if res.get("success"):
            inserted.append(name)
    return {"success": True, "inserted": inserted}


def _stop_container(name: str):
    result = run_command(["docker", "stop", name])
    return {
        "success": result.get("success", False),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }


def _start_container(name: str):
    result = run_command(["docker", "start", name])
    return {
        "success": result.get("success", False),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }


# ------------------------------------------------------------------
# Step 1: Seed + stop  (leaves DB DOWN so audience can see red health)
# ------------------------------------------------------------------
@router.post("/db-failure/fail")
def fail(request: TargetRequest):
    target = request.target.lower()
    container = _target_to_container(target)

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    seed = _seed_yugabyte() if target == "yugabyte" else _seed_aerospike()
    stop = _stop_container(container)

    return {
        "success": stop.get("success", False),
        "target": target,
        "container": container,
        "seed": seed,
        "fault": {
            "action": f"{target}-down",
            "injected": stop.get("success", False),
            "container_stopped": container,
        },
    }


# ------------------------------------------------------------------
# Step 2: Investigate (DB is still DOWN — collect evidence + RCA)
# ------------------------------------------------------------------
@router.post("/db-failure/investigate")
def investigate(request: TargetRequest):
    target = request.target.lower()
    container = _target_to_container(target)

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    evidence_result = investigation.collect_target_evidence(target)

    if not evidence_result.get("success"):
        return {
            "success": False,
            "error": evidence_result.get("error", "Evidence collection failed"),
        }

    evidence = evidence_result["evidence"]
    opensre_result = opensre_cli.investigate(evidence)

    return {
        "success": opensre_result.get("returncode") == 0,
        "target": target,
        "container": container,
        "evidence": evidence,
        "opensre": opensre_result,
    }


# ------------------------------------------------------------------
# Step 3: Recover  (DB comes back UP — health flips green)
# ------------------------------------------------------------------
@router.post("/db-failure/recover")
def recover(request: TargetRequest):
    target = request.target.lower()
    container = _target_to_container(target)

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    start = _start_container(container)
    health = investigation.collect_target_evidence(target)

    return {
        "success": start.get("success", False),
        "target": target,
        "container": container,
        "recovery": {
            "action": f"{target}-up",
            "success": start.get("success", False),
            "container_restarted": container,
        },
        "health": health.get("evidence", {}),
    }


# ==================================================================
# NODE FAILURE DEMO
# ==================================================================

class NodeRequest(BaseModel):
    node: str = WORKER_NODE
    context: str | None = "kind-opensre-demo"


STRESS_YAML = """\
apiVersion: v1
kind: Pod
metadata:
  name: {pod}
  namespace: {ns}
  labels:
    app: node-stress-demo
spec:
  nodeName: {node}
  terminationGracePeriodSeconds: 5
  containers:
  - name: stress
    image: busybox:1.36
    command: ["sh", "-c", "while true; do dd if=/dev/urandom of=/tmp/fill bs=64M count=1 2>/dev/null; sleep 0.5; done"]
    resources:
      requests:
        cpu: "999m"
        memory: "512Mi"
      limits:
        cpu: "999m"
        memory: "512Mi"
"""


def _kubectl_cmd(context: str | None = None):
    cmd = ["kubectl"]
    if context:
        cmd.extend(["--context", context])
    return cmd


# ------------------------------------------------------------------
# Step 1: Cordons the worker node + deploys a stress pod
# ------------------------------------------------------------------
@router.post("/node-failure/fail")
def node_fail(request: NodeRequest):
    node = request.node
    ctx = request.context

    # Cordon node
    cordon_result = kubectl.cordon_node(node, ctx)

    # Deploy stress pod
    yaml_content = STRESS_YAML.format(pod=STRESS_POD, ns=STRESS_NAMESPACE, node=node)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        tmp.write(yaml_content)
        tmp.close()
        apply_result = run_command(_kubectl_cmd(ctx) + ["apply", "-f", tmp.name])
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    # Get node state after cordon
    node_state = kubectl.get_node_state(node, ctx)
    node_usage = kubectl.get_node_resource_usage(node, ctx)

    return {
        "success": cordon_result.get("success", False),
        "node": node,
        "fault": {
            "action": "node-cordon",
            "cordon_success": cordon_result.get("success", False),
            "stress_pod_deployed": apply_result.get("success", False),
            "stress_pod": STRESS_POD,
            "namespace": STRESS_NAMESPACE,
        },
        "node_state": node_state.get("node") if node_state.get("success") else node_state,
        "node_usage": node_usage if node_usage.get("success") else None,
    }


# ------------------------------------------------------------------
# Step 2: Collect evidence + run OpenSRE investigation
# ------------------------------------------------------------------
@router.post("/node-failure/investigate")
def node_investigate(request: NodeRequest):
    node = request.node
    ctx = request.context

    # Collect node state
    node_state = kubectl.get_node_state(node, ctx)
    node_usage = kubectl.get_node_resource_usage(node, ctx)

    # Get node conditions for evidence summary
    conditions = []
    if node_state.get("success"):
        for c in node_state.get("node", {}).get("conditions", []):
            if c.get("status") != "True":
                continue
            conditions.append(f"{c['type']}={c['status']} ({c.get('reason', '')})")

    # Collect stack-level evidence (includes Kubernetes + VM + Grafana)
    evidence_result = investigation.collect_stack_evidence(ctx)

    evidence = evidence_result.get("evidence", {}) if evidence_result.get("success") else {}

    # Inject the node problem into evidence for OpenSRE
    evidence["node_problem"] = {
        "node": node,
        "unschedulable": node_state.get("node", {}).get("unschedulable", False) if node_state.get("success") else None,
        "conditions": conditions,
        "pod_count": node_usage.get("pod_count"),
        "restarts_total": node_usage.get("restarts_total"),
        "pods": node_usage.get("pods", []),
    }

    evidence["target"] = {
        "type": "node",
        "name": node,
    }

    # Build a question for OpenSRE
    evidence["question"] = (
        f"The Kubernetes node {node} is reporting as SchedulingDisabled "
        f"and has {node_usage.get('restarts_total', 0)} pod restarts across "
        f"{node_usage.get('pod_count', 0)} pods. "
        f"What is causing this node degradation and what should be done?"
    )

    # Run OpenSRE
    opensre_result = opensre_cli.investigate(evidence)

    return {
        "success": opensre_result.get("returncode") == 0,
        "node": node,
        "evidence": evidence,
        "opensre": opensre_result,
    }


# ------------------------------------------------------------------
# Step 3: Uncordon node + remove taint + delete stress pod
# ------------------------------------------------------------------
@router.post("/node-failure/recover")
def node_recover(request: NodeRequest):
    node = request.node
    ctx = request.context

    # Delete stress pod
    delete_result = run_command(
        _kubectl_cmd(ctx) + ["delete", "pod", STRESS_POD, "-n", STRESS_NAMESPACE, "--ignore-not-found"]
    )

    # Delete permanent stress pod too
    run_command(
        _kubectl_cmd(ctx) + ["delete", "pod", "node-stress-permanent", "-n", "opensre", "--ignore-not-found"]
    )

    # Remove taint
    untaint_result = run_command(
        _kubectl_cmd(ctx) + ["taint", "nodes", node, "demo-unhealthy-", "--overwrite"]
    )

    # Uncordon node
    uncordon_result = kubectl.uncordon_node(node, ctx)

    # Get post-recovery state
    node_state = kubectl.get_node_state(node, ctx)

    return {
        "success": uncordon_result.get("success", False),
        "node": node,
        "recovery": {
            "action": "node-uncordon",
            "uncordon_success": uncordon_result.get("success", False),
            "stress_pod_deleted": delete_result.get("success", False),
            "taint_removed": untaint_result.get("success", False),
        },
        "node_state": node_state.get("node") if node_state.get("success") else node_state,
    }


# ------------------------------------------------------------------
# List available nodes
# ------------------------------------------------------------------
@router.get("/node-failure/nodes")
def list_nodes():
    ctx = "kind-opensre-demo"
    result = kubectl.get_nodes(ctx)
    return {
        "success": result.get("success", False),
        "nodes": result.get("stdout", ""),
    }


@router.post("/node-failure/re-fail")
def node_refail(request: NodeRequest):
    """Re-cordon the node + deploy stress pod after recovery."""
    node = request.node
    ctx = request.context

    # Cordon node
    cordon_result = kubectl.cordon_node(node, ctx)

    # Add taint
    taint_result = run_command(
        _kubectl_cmd(ctx) + [
            "taint", "nodes", node, "demo-unhealthy=true:NoExecute", "--overwrite"
        ]
    )

    # Deploy stress pod
    yaml_content = STRESS_YAML.format(pod=STRESS_POD, ns=STRESS_NAMESPACE, node=node)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        tmp.write(yaml_content)
        tmp.close()
        apply_result = run_command(_kubectl_cmd(ctx) + ["apply", "-f", tmp.name])
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    # Get node state
    node_state = kubectl.get_node_state(node, ctx)

    return {
        "success": cordon_result.get("success", False),
        "node": node,
        "fault": {
            "action": "node-cordon",
            "cordon_success": cordon_result.get("success", False),
            "taint_applied": taint_result.get("success", False),
            "stress_pod_deployed": apply_result.get("success", False),
            "stress_pod": STRESS_POD,
            "namespace": STRESS_NAMESPACE,
        },
        "node_state": node_state.get("node") if node_state.get("success") else node_state,
    }


@router.get("/node-failure/health")
def node_health():
    """Check the health status of the worker node."""
    ctx = "kind-opensre-demo"
    node = WORKER_NODE

    node_state = kubectl.get_node_state(node, ctx)
    node_usage = kubectl.get_node_resource_usage(node, ctx)

    is_unschedulable = False
    taints = []
    conditions = []

    if node_state.get("success"):
        is_unschedulable = node_state.get("node", {}).get("unschedulable", False)
        taints = node_state.get("node", {}).get("taints", [])
        conditions = node_state.get("node", {}).get("conditions", [])

    # Check for stress pod
    stress_check = run_command(
        _kubectl_cmd(ctx) + [
            "get", "pod", STRESS_POD, "-n", STRESS_NAMESPACE, "--ignore-not-found"
        ]
    )
    stress_pod_running = STRESS_POD in stress_check.get("stdout", "")

    healthy = not is_unschedulable and not any(
        t.get("key") == "demo-unhealthy" for t in taints
    )

    return {
        "success": True,
        "node": node,
        "healthy": healthy,
        "unschedulable": is_unschedulable,
        "taints": taints,
        "conditions": conditions,
        "stress_pod_running": stress_pod_running,
        "pod_count": node_usage.get("pod_count"),
        "restarts_total": node_usage.get("restarts_total"),
    }


# ==================================================================
# UNHEALTHY POD DEMO
# ==================================================================

UNHEALTHY_POD_YAML = """\
apiVersion: v1
kind: Pod
metadata:
  name: order-service-bad
  namespace: opensre
  labels:
    app: order-service
    version: bad
spec:
  containers:
  - name: order-service
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      echo "[order-service] Starting v2.3.1 ..."
      echo "[order-service] ERROR: Failed to connect to database at yugabyte:5433"
      echo "[order-service] ERROR: connection refused (host=127.0.0.1 port=5433)"
      echo "[order-service] WARN: Retry 1/3 ..."
      sleep 1
      echo "[order-service] WARN: Retry 2/3 ..."
      sleep 1
      echo "[order-service] WARN: Retry 3/3 ..."
      sleep 1
      echo "[order-service] FATAL: Could not initialize database connection after 3 retries"
      echo "[order-service] FATAL: Exiting with code 1"
      exit 1
    resources:
      requests:
        cpu: "100m"
        memory: "64Mi"
      limits:
        cpu: "200m"
        memory: "128Mi"
  restartPolicy: Always
"""


@router.post("/unhealthy-pod/deploy")
def deploy_unhealthy_pod():
    ctx = "kind-opensre-demo"

    # Check if already exists
    check = run_command(
        _kubectl_cmd(ctx) + [
            "get", "pod", "order-service-bad", "-n", "opensre", "--ignore-not-found"
        ]
    )
    stdout = check.get("stdout", "").strip()
    if "order-service-bad" in stdout:
        return {
            "success": True,
            "status": "already_exists",
            "pod": "order-service-bad",
            "namespace": "opensre",
        }

    # Deploy
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        tmp.write(UNHEALTHY_POD_YAML)
        tmp.close()
        result = run_command(_kubectl_cmd(ctx) + ["apply", "-f", tmp.name])
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    return {
        "success": result.get("success", False),
        "status": "deployed",
        "pod": "order-service-bad",
        "namespace": "opensre",
    }


@router.post("/unhealthy-pod/delete")
def delete_unhealthy_pod():
    ctx = "kind-opensre-demo"
    result = run_command(
        _kubectl_cmd(ctx) + [
            "delete", "pod", "order-service-bad", "-n", "opensre", "--ignore-not-found"
        ]
    )
    return {
        "success": result.get("success", False),
        "pod": "order-service-bad",
        "namespace": "opensre",
    }


@router.get("/unhealthy-pod/status")
def unhealthy_pod_status():
    ctx = "kind-opensre-demo"
    result = run_command(
        _kubectl_cmd(ctx) + [
            "get", "pod", "order-service-bad", "-n", "opensre",
            "-o", "json"
        ]
    )

    if not result.get("success"):
        return {"exists": False}

    try:
        pod = json.loads(result.get("stdout", "{}"))
    except (TypeError, ValueError):
        return {"exists": False}

    status = pod.get("status", {})
    phase = status.get("phase", "Unknown")
    container_status = status.get("containerStatuses", [{}])[0] if status.get("containerStatuses") else {}
    restart_count = container_status.get("restartCount", 0)
    last_reason = None
    if container_status.get("lastState", {}).get("terminated"):
        last_reason = container_status["lastState"]["terminated"].get("reason")

    return {
        "exists": True,
        "phase": phase,
        "restarts": restart_count,
        "last_reason": last_reason,
        "node": pod.get("spec", {}).get("nodeName"),
    }
