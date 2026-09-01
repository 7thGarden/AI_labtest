import { Routes, Route } from "react-router-dom";

import Layout from "./components/Layout";

import Dashboard from "./pages/Dashboard";
import Kubernetes from "./pages/Kubernetes";
import Metrics from "./pages/Metrics";
import Aerospike from "./pages/Aerospike";
import Yugabyte from "./pages/Yugabyte";
import AIAnalysis from "./pages/AIAnalysis";
import Incident from "./pages/Incident";
import Settings from "./pages/Settings";
import GitHub from "./pages/GitHub";
import Chaos from "./pages/Chaos";

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/kubernetes" element={<Kubernetes />} />
        <Route path="/metrics" element={<Metrics />} />
        <Route path="/aerospike" element={<Aerospike />} />
        <Route path="/yugabyte" element={<Yugabyte />} />
        <Route path="/analysis" element={<AIAnalysis />} />
        <Route path="/incident" element={<Incident />} />
        <Route path="/github" element={<GitHub />} />
        <Route path="/chaos" element={<Chaos />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}

export default App;