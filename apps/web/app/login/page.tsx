"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Eye,
  FileSearch,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { api, errorText } from "@/lib/api";
import type { AuthSession } from "@/components/auth-gate";
import { LanguageSelector, useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const { locale, t, setLocale } = useI18n();
  const [mode, setMode] = useState<
    "login" | "register" | "forgot" | "verify" | "reset"
  >("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [organization, setOrganization] = useState("");
  const [invitationToken, setInvitationToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [accountToken, setAccountToken] = useState("");
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const token =
      new URLSearchParams(window.location.search).get("invite") || "";
    setInvitationToken(token);
    const parameters = new URLSearchParams(window.location.search);
    const verify = parameters.get("verify") || "";
    const reset = parameters.get("reset") || "";
    const requestedLocale = parameters.get("locale");
    if (requestedLocale && ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"].includes(requestedLocale)) {
      void setLocale(requestedLocale as typeof locale, false);
    }
    if (reset) {
      setAccountToken(reset);
      setMode("reset");
    } else if (verify) {
      setMode("verify");
      setBusy(true);
      api<{ verified: boolean }>("/auth/email-verification/complete", {
        method: "POST",
        body: JSON.stringify({ token: verify }),
      })
        .then(() =>
          setMessage(
            t("login.emailVerified"),
          ),
        )
        .catch((cause) => setError(errorText(cause)))
        .finally(() => setBusy(false));
    }
  }, [locale, setLocale, t]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (mode === "forgot") {
        const result = await api<{ message: string }>(
          "/auth/password-reset/request",
          {
            method: "POST",
            body: JSON.stringify({ email }),
          },
        );
        setMessage(result.message);
        return;
      }
      if (mode === "reset") {
        await api("/auth/password-reset/complete", {
          method: "POST",
          body: JSON.stringify({ token: accountToken, password }),
        });
        setPassword("");
        setMessage(t("login.passwordChanged"));
        setMode("login");
        window.history.replaceState({}, "", "/login");
        return;
      }
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
                locale,
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
        window.location.assign(
          result.onboarding_required ? "/onboarding" : "/",
        );
      }
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  async function resendVerification() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api<{ message: string }>(
        "/auth/email-verification/request",
        {
          method: "POST",
          body: JSON.stringify({ email }),
        },
      );
      setMessage(result.message);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative min-h-screen bg-[#f3f3ee] p-5 md:p-10 grid place-items-center">
      <div className="absolute right-5 top-5 md:right-10 md:top-8 z-10"><LanguageSelector /></div>
      <div className="w-full max-w-5xl overflow-hidden rounded-[28px] border border-[#dfe3da] bg-white shadow-[0_24px_80px_rgba(31,45,36,.12)] grid lg:grid-cols-[1.05fr_.95fr]">
        <section className="bg-[#173f35] text-white p-8 md:p-12 flex flex-col justify-between min-h-[360px] lg:min-h-[680px]">
          <div>
            <div className="flex items-center gap-3 font-semibold text-xl">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-[#d44b36] text-sm">
                HL
              </span>
              Helvetic Lens
            </div>
            <h1 className="mt-16 max-w-md text-4xl md:text-5xl font-semibold leading-[1.08] tracking-[-.04em]">
              {t("brand.tagline")}
            </h1>
            <p className="mt-6 max-w-md text-[#c7d8d1] leading-7">
              {t("login.productBody")}
            </p>
          </div>
          <div className="grid gap-4 text-sm text-[#dce8e3]">
            <div className="flex gap-3">
              <FileSearch size={19} /> {t("login.exactEvidence")}
            </div>
            <div className="flex gap-3">
              <ShieldCheck size={19} /> {t("login.sharedWorkspace")}
            </div>
            <div className="flex gap-3">
              <Eye size={19} /> {t("login.aiEvidence")}
            </div>
          </div>
        </section>

        <section className="p-8 md:p-12 lg:p-14 flex flex-col justify-center">
          {mode !== "verify" && mode !== "reset" && mode !== "forgot" && (
            <div className="flex rounded-xl bg-[#f1f3ed] p-1 mb-9">
              {(["register", "login"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => {
                    setMode(value);
                    setError("");
                  }}
                  className={`flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                    mode === value
                      ? "bg-white text-[#173f35] shadow-sm"
                      : "text-[#6c766e]"
                  }`}
                >
                  {value === "register" ? t("login.createWorkspace") : t("login.signIn")}
                </button>
              ))}
            </div>
          )}
          <h2 className="text-3xl font-semibold tracking-[-.03em] text-[#17231f]">
            {mode === "register"
              ? t("login.startMonitoring")
              : mode === "forgot"
                ? t("login.resetPassword")
                : mode === "reset"
                  ? t("login.choosePassword")
                  : mode === "verify"
                    ? t("login.verifyEmail")
                    : t("login.welcomeBack")}
          </h2>
          <p className="mt-2 mb-8 text-sm text-[#69746c]">
            {invitationToken
              ? t("login.inviteHelp")
              : mode === "verify"
                ? t("login.verifyHelp")
                : mode === "reset"
                  ? t("login.resetHelp")
                  : mode === "forgot"
                    ? t("login.forgotHelp")
                    : mode === "register"
                      ? t("login.registerHelp")
                      : t("login.signInHelp")}
          </p>
          {mode === "verify" ? (
            <div className="grid gap-4">
              {busy && (
                <div className="flex items-center gap-2 text-sm text-[#69746c]">
                  <Loader2 className="animate-spin" size={18} /> {t("login.verifying")}
                </div>
              )}
              {message && (
                <div className="rounded-xl border border-[#c9ddc2] bg-[#f3faef] px-4 py-3 text-sm text-[#315d32]">
                  {message}
                </div>
              )}
              {error && (
                <div className="rounded-xl border border-[#efc2b9] bg-[#fff3f0] px-4 py-3 text-sm text-[#a63b2b]">
                  {error}
                </div>
              )}
              {!busy && (
                <button
                  type="button"
                  onClick={() => {
                    setMode("login");
                    setError("");
                  }}
                  className="flex items-center justify-center gap-2 rounded-xl bg-[#cf4936] px-5 py-3.5 font-medium text-white"
                >
                  <ArrowRight size={18} /> {t("login.continue")}
                </button>
              )}
            </div>
          ) : (
            <form onSubmit={submit} className="grid gap-5">
              {mode === "register" && (
                <>
                  <label className="grid gap-2 text-sm font-medium text-[#27342f]">
                    {t("login.name")}
                    <input
                      className="input"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      maxLength={200}
                      autoComplete="name"
                    />
                  </label>
                  {!invitationToken && (
                    <label className="grid gap-2 text-sm font-medium text-[#27342f]">
                      {t("login.organization")}{" "}
                      <span className="font-normal text-[#7b857e]">
                        ({t("common.optional")})
                      </span>
                      <input
                        className="input"
                        value={organization}
                        onChange={(e) => setOrganization(e.target.value)}
                        maxLength={200}
                        autoComplete="organization"
                      />
                    </label>
                  )}
                </>
              )}
              {mode !== "reset" && (
                <label className="grid gap-2 text-sm font-medium text-[#27342f]">
                  {t("login.email")}
                  <input
                    className="input"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    maxLength={320}
                    autoComplete="email"
                  />
                </label>
              )}
              {mode !== "forgot" && (
                <label className="grid gap-2 text-sm font-medium text-[#27342f]">
                  {t("login.password")}
                  <input
                    className="input"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={mode === "register" || mode === "reset" ? 10 : 1}
                    maxLength={1024}
                    autoComplete={
                      mode === "register" || mode === "reset"
                        ? "new-password"
                        : "current-password"
                    }
                  />
                  {(mode === "register" || mode === "reset") && (
                    <span className="font-normal text-xs text-[#7b857e]">
                      {t("login.passwordHint")}
                    </span>
                  )}
                </label>
              )}
              {message && (
                <div className="rounded-xl border border-[#c9ddc2] bg-[#f3faef] px-4 py-3 text-sm text-[#315d32]">
                  {message}
                </div>
              )}
              {error && (
                <div className="rounded-xl border border-[#efc2b9] bg-[#fff3f0] px-4 py-3 text-sm text-[#a63b2b]">
                  {error}
                </div>
              )}
              <button
                disabled={busy}
                className="mt-2 flex items-center justify-center gap-2 rounded-xl bg-[#cf4936] px-5 py-3.5 font-medium text-white transition hover:bg-[#b93d2c] disabled:opacity-60"
              >
                {busy ? (
                  <Loader2 className="animate-spin" size={18} />
                ) : (
                  <ArrowRight size={18} />
                )}
                {mode === "forgot"
                  ? t("login.sendReset")
                  : mode === "reset"
                    ? t("login.changePassword")
                    : invitationToken
                      ? mode === "register"
                        ? t("login.createJoin")
                        : t("login.signInJoin")
                      : mode === "register"
                        ? t("login.createMine")
                        : t("login.signIn")}
              </button>
              {mode === "login" && (
                <div className="flex flex-wrap justify-center gap-x-5 gap-y-2">
                  <button
                    type="button"
                    onClick={() => {
                      setMode("forgot");
                      setError("");
                      setMessage("");
                    }}
                    className="text-sm font-medium text-[#356b5a]"
                  >
                    {t("login.forgot")}
                  </button>
                  <button
                    type="button"
                    disabled={busy || !email}
                    onClick={resendVerification}
                    className="text-sm font-medium text-[#356b5a] disabled:opacity-50"
                  >
                    {t("login.resend")}
                  </button>
                </div>
              )}
              {(mode === "forgot" || mode === "reset") && (
                <button
                  type="button"
                  onClick={() => {
                    setMode("login");
                    setError("");
                    setMessage("");
                    window.history.replaceState({}, "", "/login");
                  }}
                  className="text-sm font-medium text-[#356b5a]"
                >
                  {t("login.back")}
                </button>
              )}
            </form>
          )}
        </section>
      </div>
    </main>
  );
}
