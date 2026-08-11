import { useEffect, useState } from "react";
import api from "../api/api";

export default function AIAnalysis() {
  const [version, setVersion] = useState("");
  const [doctor, setDoctor] = useState("Loading...");

  const [pods, setPods] = useState([]);
  const [namespace, setNamespace] = useState("");
  const [podName, setPodName] = useState("");

  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const versionRes = await api.get("/opensre/version");
        setVersion(versionRes.data.stdout);

        const doctorRes = await api.get("/opensre/doctor");
        setDoctor(doctorRes.data.stdout);

        const podRes = await api.get("/kubernetes/pods");

        const podLines = podRes.data.stdout
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
        }
      } catch (err) {
        console.error(err);
        setDoctor("Unable to connect to OpenSRE Backend.");
      }
    }

    load();
  }, []);

  async function investigatePod() {
    if (!namespace || !podName) {
      return;
    }

    setLoading(true);
    setInvestigation(null);

    try {
      const response = await api.get(
        `/opensre/investigate/pod/${namespace}/${podName}`
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

  const cliOutput = investigation
    ? [
        investigation.stdout || "",
        investigation.stderr
          ? `\n\n--- STDERR ---\n${investigation.stderr}`
          : "",
      ].join("")
    : "";

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
          >
            {[...new Set(pods.map((pod) => pod.namespace))].map((ns) => (
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
          >
            {pods
              .filter((pod) => pod.namespace === namespace)
              .map((pod) => (
                <option key={pod.name} value={pod.name}>
                  {pod.name}
                </option>
              ))}
          </select>
        </label>

        <br />
        <br />

        <button onClick={investigatePod} disabled={loading}>
          {loading ? "Investigating..." : "Investigate Pod"}
        </button>
      </div>

      <br />

      {investigation && (
        <div className="table">
          <h2>OpenSRE Investigation Output</h2>

          <br />

          <p>
            <strong>Pod:</strong> {podName}
          </p>

          <p>
            <strong>Namespace:</strong> {namespace}
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
    </>
  );
}
