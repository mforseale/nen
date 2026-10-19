"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { API_URL } from "./api";

export type AuthUser = {
  id: number;
  username: string;
  email: string;
  full_name: string;
  created_at: string;
};

type Credentials = {
  login: string;
  password: string;
};

type Registration = {
  username: string;
  email: string;
  full_name: string;
  password: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  authError: string | null;
  login: (credentials: Credentials) => Promise<void>;
  register: (registration: Registration) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function responseError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null) as { detail?: string } | null;
  return new Error(typeof body?.detail === "string" ? body.detail : "Проверьте заполненные поля и попробуйте снова.");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    fetch(`${API_URL}/auth/me`, { credentials: "include" })
      .then(async (response) => {
        if (response.status === 401) return null;
        if (!response.ok) throw await responseError(response);
        return response.json() as Promise<AuthUser>;
      })
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch(() => {
        if (active) setAuthError("Не удалось связаться с сервером авторизации.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (credentials: Credentials) => {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    if (!response.ok) throw await responseError(response);
    setUser(await response.json() as AuthUser);
    setAuthError(null);
  }, []);

  const register = useCallback(async (registration: Registration) => {
    const response = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(registration),
    });
    if (!response.ok) throw await responseError(response);
    setUser(await response.json() as AuthUser);
    setAuthError(null);
  }, []);

  const logout = useCallback(async () => {
    const response = await fetch(`${API_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) throw await responseError(response);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const response = await fetch(`${API_URL}/auth/me`, { credentials: "include" });
    if (!response.ok) throw await responseError(response);
    setUser(await response.json() as AuthUser);
  }, []);

  const value = useMemo(
    () => ({ user, loading, authError, login, register, logout, refreshUser }),
    [user, loading, authError, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
