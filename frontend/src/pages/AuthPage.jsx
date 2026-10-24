import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function AuthPage({ mode }) {
  const { user, login, signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isSignup = mode === "signup";

  if (user) return <Navigate to="/" replace />;

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await (isSignup ? signup(email, password) : login(email, password));
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth card">
      <h1>{isSignup ? "Create your account" : "Welcome back"}</h1>
      <form onSubmit={submit} className="stack">
        <label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>
          Password
          <input type="password" required minLength={isSignup ? 8 : undefined} maxLength={72}
                 value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? "Please wait…" : isSignup ? "Sign up" : "Log in"}</button>
      </form>
      <p className="muted">
        {isSignup ? <>Have an account? <Link to="/login">Log in</Link></>
                  : <>New here? <Link to="/signup">Create an account</Link></>}
      </p>
    </div>
  );
}
