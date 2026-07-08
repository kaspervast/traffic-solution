"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { clearAuth, getUser, type AuthUser } from "@/lib/auth";

const LINKS = [
  { href: "/command-center", label: "Live Map + Command Center" },
  { href: "/sumo-lab", label: "SUMO What-If Lab" },
  { href: "/network-builder", label: "Network Builder" },
  { href: "/anomalies", label: "Anomaly Monitor" },
  { href: "/reports", label: "Reports" },
  { href: "/admin", label: "Admin" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const sync = () => setUser(getUser());
    sync();
    window.addEventListener("rajkot-auth-changed", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("rajkot-auth-changed", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return (
    <nav className="flex flex-wrap items-center gap-1 border-b border-slate-800 bg-slate-900 px-4 py-2">
      <span className="mr-4 shrink-0 font-semibold text-slate-200">
        Rajkot AI Traffic Command Center{" "}
        <span className="rounded bg-amber-900/40 px-2 py-0.5 text-xs font-normal text-amber-300">
          1 km pilot
        </span>
      </span>
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={clsx(
            "rounded px-3 py-1.5 text-sm transition-colors",
            pathname?.startsWith(l.href)
              ? "bg-slate-700 text-white"
              : "text-slate-300 hover:bg-slate-800 hover:text-white",
          )}
        >
          {l.label}
        </Link>
      ))}
      <span className="ml-auto flex items-center gap-2 text-sm">
        {user ? (
          <>
            <span className="text-slate-400">
              {user.username} <span className="text-slate-600">({user.role})</span>
            </span>
            <button
              onClick={() => {
                clearAuth();
                router.refresh();
              }}
              className="rounded px-3 py-1.5 text-slate-300 hover:bg-slate-800 hover:text-white"
            >
              Sign out
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className="rounded px-3 py-1.5 text-slate-300 hover:bg-slate-800 hover:text-white"
          >
            Sign in
          </Link>
        )}
      </span>
    </nav>
  );
}
