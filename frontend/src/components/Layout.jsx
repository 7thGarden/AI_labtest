import { useState } from "react";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";

export default function Layout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="main">
        <Navbar onMenuClick={() => setSidebarOpen(true)} />

        <main className="content">{children}</main>
      </div>
    </div>
  );
}
