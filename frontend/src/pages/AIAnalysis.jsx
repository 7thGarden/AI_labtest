import { useEffect, useState } from "react";
import api from "../api/api";

export default function AIAnalysis() {
  const [version, setVersion] = useState("");
  const [doctor, setDoctor] = useState("Loading...");

  useEffect(() => {
    async function load() {
      try {
        const versionRes = await api.get("/opensre/version");
        setVersion(versionRes.data.stdout);

        const doctorRes = await api.get("/opensre/doctor");
        setDoctor(doctorRes.data.stdout);
      } catch (err) {
        setDoctor("Unable to connect to OpenSRE Backend.");
      }
    }

    load();
  }, []);

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
    </>
  );
}