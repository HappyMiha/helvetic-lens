"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Eye, FileSearch, Loader2, ShieldCheck } from "lucide-react";
import { api, errorText } from "@/lib/api";
import type { AuthSession } from "@/components/auth-gate";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [organization, setOrganization] = useState("");
  const [invitationToken, setInvitationToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("invite") || "";
    setInvitationToken(token);
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<AuthSession>(`/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify(
          mode === "register"
            ? {
                email,
                password,
                name,
                organization_name: organization,
                invitation_token: invitationToken,
              }
            : { email, password },
        ),
      });
      if (mode === "login" && invitationToken) {
        await api("/invitations/accept", {
          method: "POST",
          body: JSON.stringify({ token: invitationToken }),
        });
        window.location.assign("/organization");
      } else {
        window.location.assign(result.onboarding_required ? "/onboarding" : "/");
      }
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f3f3ee] p-5 md:p-10 grid place-items-center">
      <div className="w-full max-w-5xl overflow-hidden rounded-[28px] border border-[#dfe3da] bg-white shadow-[0_24px_80px_rgba(31,45,36,.12)] grid lg:grid-cols-[1.05fr_.95fr]">
        <section className="bg-[#173f35] text-white p-8 md:p-12 flex flex-col justify-between min-h-[360px] lg:min-h-[680px]">
          <div>
            <div className="flex items-center gap-3 font-semibold text-xl">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-[#d44b36] text-sm">HL</span>
              Helvetic Lens
            </div>
            <h1 className="mt-16 max-w-md text-4xl md:text-5xl font-semibold leading-[1.08] tracking-[-.04em]">
              See what changed. Understand what matters.
            </h1>
            <p className="mt-6 max-w-md text-[#c7d8d1] leading-7">
              Monitor Swiss legal sources, keep every saved version, and review evidence-backed changes with local Apertus.
            </p>
          </div>
          <div className="grid gap-4 text-sm text-[#dce8e3]">
            <div className="flex gap-3"><FileSearch size={19} /> Exact saved evidence and visual changes</div>
            <div className="flex gap-3"><ShieldCheck size={19} /> Your organization shares one private workspace</div>
            <div className="flex gap-3"><Eye size={19} /> AI conclusions always link back to evidence</div>
          </div>
        </section>

        <section className="p-8 md:p-12 lg:p-14 flex flex-col justify-center">
          <div className="flex rounded-xl bg-[#f1f3ed] p-1 mb-9">
            {(["register", "login"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => { setMode(value); setError(""); }}
                className={`flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                  mode === value ? "bg-white text-[#173f35] shadow-sm" : "text-[#6c766e]"
                }`}
              >
                {value === "register" ? "Create workspace" : "Sign in"}
              </button>
            ))}
          </div>
          <h2 className="text-3xl font-semibold tracking-[-.03em] text-[#17231f]">
            {mode === "register" ? "Start monitoring" : "Welcome back"}
          </h2>
          <p className="mt-2 mb-8 text-sm text-[#69746c]">
            {invitationToken
              ? "This invitation is bound to the invited email and can be used once."
              : mode === "register"
              ? "A personal workspace is created when organization is left empty."
              : "Use the email and password for your workspace."}
          </p>
          <form onSubmit={submit} className="grid gap-5">
            {mode === "register" && (
              <>
                <label className="grid gap-2 text-sm font-medium text-[#27342f]">
                  Your name
                  <input className="input" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} autoComplete="name" />
                </label>
                {!invitationToken && (
                  <label className="grid gap-2 text-sm font-medium text-[#27342f]">
                    Organization <span className="font-normal text-[#7b857e]">(optional)</span>
                    <input className="input" value={organization} onChange={(e) => setOrganization(e.target.value)} maxLength={200} autoComplete="organization" />
                  </label>
                )}
              </>
            )}
            <label className="grid gap-2 text-sm font-medium text-[#27342f]">
              Email
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={320} autoComplete="email" />
            </label>
            <label className="grid gap-2 text-sm font-medium text-[#27342f]">
              Password
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === "register" ? 10 : 1} maxLength={1024} autoComplete={mode === "register" ? "new-password" : "current-password"} />
              {mode === "register" && <span className="font-normal text-xs text-[#7b857e]">At least 10 characters</span>}
            </label>
            {error && <div className="rounded-xl border border-[#efc2b9] bg-[#fff3f0] px-4 py-3 text-sm text-[#a63b2b]">{error}</div>}
            <button disabled={busy} className="mt-2 flex items-center justify-center gap-2 rounded-xl bg-[#cf4936] px-5 py-3.5 font-medium text-white transition hover:bg-[#b93d2c] disabled:opacity-60">
              {busy ? <Loader2 className="animate-spin" size={18} /> : <ArrowRight size={18} />}
              {invitationToken
                ? mode === "register"
                  ? "Create account and join"
                  : "Sign in and join"
                : mode === "register"
                  ? "Create my workspace"
                  : "Sign in"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
