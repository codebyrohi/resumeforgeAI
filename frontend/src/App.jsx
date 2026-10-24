import { Link, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";
import Editor from "./pages/Editor";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="center muted">Loading…</p>;
  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const { user, logout } = useAuth();
  return (
    <>
      <nav className="topbar">
        <Link to="/" className="brand">ResumeForgeAI</Link>
        {user && (
          <div className="nav-links">
            <Link to="/">Dashboard</Link>
            <Link to="/editor">Editor</Link>
            <span className="muted">{user.email}</span>
            <button className="link" onClick={logout}>Log out</button>
          </div>
        )}
      </nav>
      <main className="container">
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/signup" element={<AuthPage mode="signup" />} />
          <Route path="/" element={<Protected><Dashboard /></Protected>} />
          <Route path="/editor" element={<Protected><Editor /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}
