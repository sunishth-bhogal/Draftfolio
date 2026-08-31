"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { Card } from "@/components/ui";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res =
        mode === "signup"
          ? await api.signup(email, username, password)
          : await api.login(username || email, password);
      setToken(res.token);
      window.location.href = "/";
    } catch {
      setErr(mode === "signup" ? "Could not sign up (email/username may be taken)." : "Invalid credentials.");
      setBusy(false);
    }
  }

  return (
    <div className="max-w-md mx-auto mt-6">
      <h1 className="text-3xl font-semibold tracking-tight mb-1">
        {mode === "signup" ? "Create your team" : "Welcome back"}
      </h1>
      <p className="text-ink-soft text-sm mb-6">
        One team, $100k to draft, and a climb through the divisions.
      </p>

      <Card>
        <form onSubmit={submit} className="space-y-4">
          {mode === "signup" && (
            <div>
              <label className="text-xs uppercase tracking-wide text-ink-faint">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-line px-3 py-2 focus:border-ink outline-none"
              />
            </div>
          )}
          <div>
            <label className="text-xs uppercase tracking-wide text-ink-faint">
              {mode === "signup" ? "Username" : "Username or email"}
            </label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="mt-1 w-full rounded-lg border border-line px-3 py-2 focus:border-ink outline-none"
            />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wide text-ink-faint">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="mt-1 w-full rounded-lg border border-line px-3 py-2 focus:border-ink outline-none"
            />
          </div>

          {err && <div className="text-down text-sm">{err}</div>}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-ink text-cream py-3 font-medium disabled:opacity-40 hover:opacity-90"
          >
            {busy ? "…" : mode === "signup" ? "Create team" : "Log in"}
          </button>
        </form>
      </Card>

      <button
        onClick={() => {
          setMode(mode === "signup" ? "login" : "signup");
          setErr(null);
        }}
        className="mt-4 text-sm text-ink-soft hover:text-ink w-full text-center"
      >
        {mode === "signup" ? "Already have a team? Log in" : "New here? Create a team"}
      </button>
    </div>
  );
}
