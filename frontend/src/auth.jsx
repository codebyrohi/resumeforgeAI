import { createContext, useContext, useEffect, useState } from "react";
import { api, tokens } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokens.access) {
      setLoading(false);
      return;
    }
    api("/auth/me")
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    tokens.set(await api("/auth/login", { method: "POST", json: { email, password }, retry: false }));
    setUser(await api("/auth/me"));
  }

  async function signup(email, password) {
    await api("/auth/signup", { method: "POST", json: { email, password }, retry: false });
    await login(email, password);
  }

  function logout() {
    tokens.clear();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
