"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { setAuth } from "@/lib/auth";

interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
  role: "admin" | "operator" | "viewer";
}

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const res = await api.post<LoginResponse>("/api/auth/login", { username, password });
      setAuth(res.access_token, { username: res.username, role: res.role });
      router.push("/command-center");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-49px)] items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded border border-slate-800 bg-slate-900 p-6"
      >
        <h1 className="mb-1 text-lg font-semibold text-slate-100">Sign in</h1>
        <p className="mb-4 text-xs text-slate-500">
          Required for probe point edits, alert approval, and SUMO scenario approve/run. Dashboard
          views work without signing in.
        </p>

        <label className="mb-1 block text-xs text-slate-400">Username</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          className="mb-3 w-full rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100"
          required
        />

        <label className="mb-1 block text-xs text-slate-400">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          className="mb-4 w-full rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100"
          required
        />

        {error && <p className="mb-3 text-xs text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded bg-sky-700 px-3 py-2 text-sm text-white hover:bg-sky-600 disabled:opacity-50"
        >
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
