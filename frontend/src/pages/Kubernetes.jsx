import { useEffect, useState } from "react";
import api from "../api/api";

export default function Kubernetes() {
  const [nodes, setNodes] = useState([]);
  const [pods, setPods] = useState([]);

  const [selectedPod, setSelectedPod] = useState(null);
  const [investigation, setInvestigation] = useState("");
  const [investigating, setInvestigating] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const nodeRes = await api.get("/kubernetes/nodes");
        const podRes = await api.get("/kubernetes/pods");

        const nodeLines = nodeRes.data.stdout
          .split("\n")
          .slice(1)
          .filter(Boolean);

        const podLines = podRes.data.stdout
          .split("\n")
          .slice(1)
          .filter(Boolean);

        setNodes(nodeLines);
        setPods(podLines);
      } catch (err) {
        console.error(err);
      }
    }

    load();
  }, []);

  async function investigatePod(namespace, podName) {
    setSelectedPod(`${namespace}/${podName}`);
    setInvestigation("Starting OpenSRE investigation...\n");
    setInvestigating(true);

    try {
      const response = await api.get(
        `/opensre/investigate/pod/${namespace}/${podName}`
      );

      const data = response.data;

      const stdout = data.stdout || "";
      const stderr = data.stderr || "";

      let output = "";

      if (stdout) {
        output += stdout;
      }

      if (stderr) {
        output += "\n\n--- STDERR ---\n";
        output += stderr;
      }

      if (!output.trim()) {
        output = "OpenSRE returned no output.";
      }

      setInvestigation(output);
    } catch (err) {
      console.error(err);

      setInvestigation(
        `Unable to connect to OpenSRE backend.\n\n${err.message}`
      );
    } finally {
      setInvestigating(false);
    }
  }

  return (
    <>
      <h1>Kubernetes Cluster</h1>

      <div className="table">
        <h2>Nodes</h2>

        <br />

        <table width="100%">
          <thead>
            <tr>
              <th align="left">Node</th>
              <th align="left">Status</th>
              <th align="left">Role</th>
              <th align="left">Version</th>
            </tr>
          </thead>

          <tbody>
            {nodes.map((node, index) => {
              const cols = node.trim().split(/\s+/);

              return (
                <tr key={index}>
                  <td>{cols[0]}</td>
                  <td>{cols[1]}</td>
                  <td>{cols[2]}</td>
                  <td>{cols[4]}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <br />

      <div className="table">
        <h2>Pods</h2>

        <br />

        <table width="100%">
          <thead>
            <tr>
              <th align="left">Namespace</th>
              <th align="left">Pod</th>
              <th align="left">Ready</th>
              <th align="left">Status</th>
              <th align="left">Action</th>
            </tr>
          </thead>

          <tbody>
            {pods.map((pod, index) => {
              const cols = pod.trim().split(/\s+/);

              const namespace = cols[0];
              const podName = cols[1];

              return (
                <tr key={index}>
                  <td>{namespace}</td>
                  <td>{podName}</td>
                  <td>{cols[2]}</td>
                  <td>{cols[3]}</td>
                  <td>
                    <button
                      onClick={() => investigatePod(namespace, podName)}
                      disabled={investigating}
                    >
                      {investigating &&
                      selectedPod === `${namespace}/${podName}`
                        ? "Investigating..."
                        : "Investigate"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {investigation && (
        <>
          <br />

          <div className="table">
            <h2>OpenSRE Investigation</h2>

            <p>
              <strong>Pod:</strong> {selectedPod}
            </p>

            <br />

            <pre
              style={{
                whiteSpace: "pre-wrap",
                textAlign: "left",
              }}
            >
              {investigation}
            </pre>
          </div>
        </>
      )}
    </>
  );
}
