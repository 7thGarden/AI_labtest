import Navbar from "./Navbar";
import Sidebar from "./Sidebar";

export default function Layout({ children }) {
  return (
    <div className="app">
      <Sidebar />

      <div className="main">
        <Navbar />

        <div className="content">
          {children}
        </div>
      </div>
    </div>
  );
}