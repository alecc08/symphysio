/* One minimal form: email + password. No wizard, no symbol rules. */

import { useState, type FormEvent } from "react";

import { ApiError } from "../api/client";
import { PhysioHero } from "../components/icons/Tile";
import { useSession } from "../state/session";

const MIN_PASSWORD = 12;

export function AuthPage() {
  const session = useSession();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const tooShort = mode === "register" && password.length > 0 && password.length < MIN_PASSWORD;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (mode === "register" && password.length < MIN_PASSWORD) {
      setError(`Password must be at least ${MIN_PASSWORD} characters.`);
      return;
    }
    try {
      if (mode === "register") await session.register(email, password);
      else await session.login(email, password);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Try again.");
    }
  }

  return (
    <div className="app-shell mx-auto flex min-h-dvh max-w-md flex-col justify-center px-5 pb-10">
      <div className="mb-6 flex items-center gap-3">
        <span className="text-physio-ink">
          <PhysioHero className="h-10 w-10" />
        </span>
        <div>
          <p className="text-xl font-extrabold tracking-tight">Symphysio</p>
          <p className="text-sm text-muted">Click and log. See what actually correlates.</p>
        </div>
      </div>

      <form
        onSubmit={submit}
        className="rounded-3xl border border-line bg-card p-5 shadow-sm sm:p-6"
      >
        <div className="mb-4 grid grid-cols-2 gap-1 rounded-xl bg-canvas p-1">
          {(["register", "login"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setMode(value);
                setError(null);
              }}
              aria-pressed={mode === value}
              className={`rounded-lg py-2 text-sm font-bold ${
                mode === value ? "bg-card text-ink shadow-sm" : "text-muted"
              }`}
            >
              {value === "register" ? "Create account" : "Log in"}
            </button>
          ))}
        </div>

        <label className="block text-sm font-semibold" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          required
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="mt-1.5 w-full rounded-xl border border-line bg-canvas px-3.5 py-3 text-base"
        />

        <label className="mt-4 block text-sm font-semibold" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          required
          minLength={mode === "register" ? MIN_PASSWORD : 1}
          autoComplete={mode === "register" ? "new-password" : "current-password"}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="mt-1.5 w-full rounded-xl border border-line bg-canvas px-3.5 py-3 text-base"
        />
        {mode === "register" ? (
          <p className={`mt-1.5 text-xs ${tooShort ? "text-symptom-ink" : "text-muted"}`}>
            At least {MIN_PASSWORD} characters. Length beats symbols — breached passwords are
            rejected.
          </p>
        ) : null}

        {error ? (
          <p role="alert" className="mt-4 rounded-xl bg-symptom-soft px-3 py-2.5 text-sm font-semibold text-symptom-ink">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={session.busy}
          className="mt-5 w-full rounded-xl bg-physio py-3.5 text-base font-bold text-white disabled:opacity-60"
        >
          {session.busy
            ? "Working…"
            : mode === "register"
              ? "Create account & start logging"
              : "Log in"}
        </button>
      </form>

      <p className="mt-4 text-center text-xs text-muted">
        Your data stays on your own server and exports to CSV or JSON any time.
      </p>
    </div>
  );
}
