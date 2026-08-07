import { useEffect, useState } from "react";
import api from "../api/api";

export default function Kubernetes() {
  const [nodes, setNodes] = useState([]);
  const [pods, setPods] = useState([]);

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
            </tr>
          </thead>

          <tbody>
            {pods.map((pod, index) => {
              const cols = pod.trim().split(/\s+/);

              return (
                <tr key={index}>
                  <td>{cols[0]}</td>
                  <td>{cols[1]}</td>
                  <td>{cols[2]}</td>
                  <td>{cols[3]}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}