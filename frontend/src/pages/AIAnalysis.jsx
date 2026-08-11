import { useEffect, useState } from "react";
import api from "../api/api";

export default function AIAnalysis() {
  const [version, setVersion] = useState("");
  const [doctor, setDoctor] = useState("Loading...");

  const [clusters, setClusters] = useState([]);
  const [cluster, setCluster] = useState("");

  const [pods, setPods] = useState([]);
  const [namespace, setNamespace] = useState("");
  const [podName, setPodName] = useState("");

  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(false);

  const [message, setMessage] = useState("");
  const [chat, setChat] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);

  const [podsLoading, setPodsLoading] = useState(false);

  useEffect(() => {
    async function loadInitialData() {
      try {
        const versionRes = await api.get("/opensre/version");
        setVersion(versionRes.data.stdout);

        const doctorRes = await api.get("/opensre/doctor");
        setDoctor(doctorRes.data.stdout);

        const clusterRes = await api.get("/kubernetes/clusters");

        const clusterLines = (clusterRes.data.stdout || "")
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);

        setClusters(clusterLines);

        if (clusterLines.length > 0) {
          setCluster(clusterLines[0]);
        }
      } catch (err) {
        console.error(err);
        setDoctor("Unable to connect to OpenSRE Backend.");
      }
    }

    loadInitialData();
  }, []);

  useEffect(() => {
    if (!cluster) {
      setPods([]);
      setNamespace("");
      setPodName("");
      return;
    }

    async function loadPods() {
      setPodsLoading(true);

      try {
        const response = await api.get("/kubernetes/pods", {
          params: {
            context: cluster,
          },
        });

        const podLines = (response.data.stdout || "")
          .split("\n")
          .slice(1)
          .filter(Boolean);

        const podData = podLines.map((line) => {
          const cols = line.trim().split(/\s+/);

          return {
            namespace: cols[0],
            name: cols[1],
            ready: cols[2],
            status: cols[3],
          };
        });

        setPods(podData);

        if (podData.length > 0) {
          setNamespace(podData[0].namespace);
          setPodName(podData[0].name);
        } else {
          setNamespace("");
          setPodName("");
        }

        setInvestigation(null);
      } catch (err) {
        console.error("Failed to load pods:", err);
        setPods([]);
        setNamespace("");
        setPodName("");
      } finally {
        setPodsLoading(false);
      }
    }

    loadPods();
  }, [cluster]);

  async function investigatePod() {
    if (!namespace || !podName) {
      return;
    }

    setLoading(true);
    setInvestigation(null);

    try {
      const response = await api.get(
        `/opensre/investigate/pod/${namespace}/${podName}`,
        {
          params: {
            context: cluster,
          },
        }
      );

      setInvestigation(response.data);
    } catch (err) {
      console.error(err);

      setInvestigation({
        success: false,
        stdout: "",
        stderr: `Unable to connect to OpenSRE backend.\n\n${err.message}`,
      });
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage() {
    const text = message.trim();

    if (!text || chatLoading) {
      return;
    }

    setChat((previous) => [
      ...previous,
      {
        role: "user",
        content: text,
      },
    ]);

    setMessage("");
    setChatLoading(true);

    try {
      const response = await api.post("/opensre/chat", {
        message: text,
        cluster: cluster,
        namespace: namespace,
        pod: podName,
      });

      const data = response.data;

      const output = [
        data.stdout || "",
        data.stderr
          ? `\n\n--- STDERR ---\n${data.stderr}`
          : "",
      ].join("");

      setChat((previous) => [
        ...previous,
        {
          role: "opensre",
          content: output || "OpenSRE returned no output.",
        },
      ]);
    } catch (err) {
      console.error(err);

      setChat((previous) => [
        ...previous,
        {
          role: "opensre",
          content: `OpenSRE request failed.\n\n${err.message}`,
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  const cliOutput = investigation
    ? [
        investigation.stdout || "",
        investigation.stderr
          ? `\n\n--- STDERR ---\n${investigation.stderr}`
          : "",
      ].join("")
    : "";

  const namespaces = [
    ...new Set(pods.map((pod) => pod.namespace)),
  ];

  const selectedNamespacePods = pods.filter(
    (pod) => pod.namespace === namespace
  );

  return (
    <>
      <h1>AI Analysis</h1>

      <div className="table">
        <h2>OpenSRE Version</h2>

        <br />

        <pre>{version}</pre>
      </div>

      <br />

      <div className="table">
        <h2>OpenSRE Doctor</h2>

        <br />

        <pre>{doctor}</pre>
      </div>

      <br />

      <div className="table">
        <h2>Pod Investigation</h2>

        <br />

        <label>
          Cluster
          <br />

          <select
            value={cluster}
            onChange={(e) => setCluster(e.target.value)}
            disabled={clusters.length === 0}
          >
            {clusters.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <br />
        <br />

        <label>
          Namespace
          <br />

          <select
            value={namespace}
            onChange={(e) => {
              const newNamespace = e.target.value;

              setNamespace(newNamespace);

              const firstPod = pods.find(
                (pod) => pod.namespace === newNamespace
              );

              setPodName(firstPod ? firstPod.name : "");
            }}
            disabled={podsLoading || namespaces.length === 0}
          >
            {namespaces.map((ns) => (
              <option key={ns} value={ns}>
                {ns}
              </option>
            ))}
          </select>
        </label>

        <br />
        <br />

        <label>
          Pod
          <br />

          <select
            value={podName}
            onChange={(e) => setPodName(e.target.value)}
            disabled={podsLoading || selectedNamespacePods.length === 0}
          >
            {selectedNamespacePods.map((pod) => (
              <option key={pod.name} value={pod.name}>
                {pod.name}
              </option>
            ))}
          </select>
        </label>

        {podsLoading && (
          <>
            <br />
            <br />
            <span>Loading pods from selected cluster...</span>
          </>
        )}

        <br />
        <br />

        <button
          onClick={investigatePod}
          disabled={loading || podsLoading || !namespace || !podName}
        >
          {loading ? "Investigating..." : "Investigate Pod"}
        </button>
      </div>

      <br />

      {investigation && (
        <div className="table">
          <h2>OpenSRE Investigation Output</h2>

          <br />

          <p>
            <strong>Cluster:</strong>{" "}
            {cluster || "None selected"}
          </p>

          <p>
            <strong>Namespace:</strong> {namespace}
          </p>

          <p>
            <strong>Pod:</strong> {podName}
          </p>

          <br />

          <pre
            style={{
              whiteSpace: "pre-wrap",
              textAlign: "left",
              overflowX: "auto",
            }}
          >
            {cliOutput || "OpenSRE returned no output."}
          </pre>
        </div>
      )}

      <br />

      <div className="table">
        <h2>OpenSRE CLI</h2>

        <br />

        <div
          style={{
            padding: "12px",
            marginBottom: "15px",
            border: "1px solid #ccc",
          }}
        >
          <strong>Cluster:</strong>{" "}
          {cluster || "None selected"}
          <br />

          <strong>Namespace:</strong>{" "}
          {namespace || "None selected"}
          <br />

          <strong>Pod:</strong>{" "}
          {podName || "None selected"}
        </div>

        <div
          style={{
            minHeight: "300px",
            maxHeight: "500px",
            overflowY: "auto",
            padding: "15px",
            border: "1px solid #ccc",
            marginBottom: "15px",
            background: "#111",
            color: "#eee",
          }}
        >
          {chat.length === 0 ? (
            <pre
              style={{
                whiteSpace: "pre-wrap",
                textAlign: "left",
              }}
            >
{`OpenSRE CLI ready.

Cluster: ${cluster || "None selected"}
Namespace: ${namespace || "None selected"}
Pod: ${podName || "None selected"}

Ask OpenSRE about this Kubernetes environment...`}
            </pre>
          ) : (
            chat.map((item, index) => (
              <div key={index} style={{ marginBottom: "20px" }}>
                <strong>
                  {item.role === "user" ? "You" : "OpenSRE"}
                </strong>

                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    textAlign: "left",
                    marginTop: "8px",
                  }}
                >
                  {item.content}
                </pre>
              </div>
            ))
          )}

          {chatLoading && (
            <pre
              style={{
                whiteSpace: "pre-wrap",
                textAlign: "left",
              }}
            >
              OpenSRE is investigating...
            </pre>
          )}
        </div>

        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask OpenSRE about this pod..."
          rows={3}
          style={{
            width: "100%",
            boxSizing: "border-box",
            resize: "vertical",
          }}
          disabled={chatLoading}
        />

        <br />
        <br />

        <button
          onClick={sendMessage}
          disabled={chatLoading || !message.trim()}
        >
          {chatLoading ? "Thinking..." : "Send"}
        </button>
      </div>
    </>
  );
}
