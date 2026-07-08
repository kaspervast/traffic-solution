/**
 * Minimal client-side auth state for the JWT issued by POST /api/auth/login.
 * Stored in localStorage -- acceptable for this MVP pilot (single shared
 * deployment, no sensitive PII beyond traffic ops data); a production
 * rollout would want an httpOnly cookie instead. Never import this from a
 * server component -- it touches `window` and is guarded accordingly.
 */

const TOKEN_KEY = "rajkot_auth_token";
const USER_KEY = "rajkot_auth_user";

export interface AuthUser {
  username: string;
  role: "admin" | "operator" | "viewer";
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: AuthUser): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new Event("rajkot-auth-changed"));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event("rajkot-auth-changed"));
}
