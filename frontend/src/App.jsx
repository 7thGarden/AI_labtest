import { Routes, Route } from "react-router-dom";

import Layout from "./components/Layout";

import Dashboard from "./pages/Dashboard";
import Kubernetes from "./pages/Kubernetes";
import Metrics from "./pages/Metrics";
import AIAnalysis from "./pages/AIAnalysis";
import Settings from "./pages/Settings";

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/kubernetes" element={<Kubernetes />} />
        <Route path="/metrics" element={<Metrics />} />
        <Route path="/analysis" element={<AIAnalysis />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}

export default App;