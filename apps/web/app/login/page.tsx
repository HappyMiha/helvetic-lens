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
import { BrandLockup } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LanguageSelector, useI18n } from "@/lib/i18n";
import styles from "./login.module.css";

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
    if (
      requestedLocale &&
      ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"].includes(requestedLocale)
    ) {
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
        .then(() => setMessage(t("login.emailVerified")))
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
    <main className={styles.page}>
      <div className={`${styles.language} language-selector`}>
        <LanguageSelector />
      </div>
      <div className={styles.card}>
        <section className={styles.story}>
          <div className={styles.storyTop}>
            <BrandLockup inverse />
            <h1>{t("brand.tagline")}</h1>
            <p className={styles.storyBody}>{t("login.productBody")}</p>
          </div>
          <div className={styles.features}>
            <div className={styles.feature}>
              <span className={styles.featureIcon}>
                <FileSearch size={18} />
              </span>
              {t("login.exactEvidence")}
            </div>
            <div className={styles.feature}>
              <span className={styles.featureIcon}>
                <ShieldCheck size={18} />
              </span>
              {t("login.sharedWorkspace")}
            </div>
            <div className={styles.feature}>
              <span className={styles.featureIcon}>
                <Eye size={18} />
              </span>
              {t("login.aiEvidence")}
            </div>
          </div>
        </section>

        <section className={styles.formPanel}>
          <div className={styles.formContent}>
            {mode !== "verify" && mode !== "reset" && mode !== "forgot" && (
              <div className={styles.modeSwitcher}>
                {(["register", "login"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={mode === value}
                    onClick={() => {
                      setMode(value);
                      setError("");
                    }}
                    className={`${styles.modeButton} ${mode === value ? styles.modeButtonActive : ""}`}
                  >
                    {value === "register"
                      ? t("login.createWorkspace")
                      : t("login.signIn")}
                  </button>
                ))}
              </div>
            )}
            <h2 className={styles.heading}>
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
            <p className={styles.description}>
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
              <div className={styles.form}>
                {busy && (
                  <div className={styles.status}>
                    <Loader2 className="animate-spin" size={18} />{" "}
                    {t("login.verifying")}
                  </div>
                )}
                {message && <div className={styles.message}>{message}</div>}
                {error && <div className={styles.error}>{error}</div>}
                {!busy && (
                  <Button
                    type="button"
                    onClick={() => {
                      setMode("login");
                      setError("");
                    }}
                    className={styles.submit}
                  >
                    <ArrowRight size={18} /> {t("login.continue")}
                  </Button>
                )}
              </div>
            ) : (
              <form onSubmit={submit} className={styles.form}>
                {mode === "register" && (
                  <>
                    <label className={styles.field}>
                      {t("login.name")}
                      <Input
                        className={styles.input}
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                        maxLength={200}
                        autoComplete="name"
                      />
                    </label>
                    {!invitationToken && (
                      <label className={styles.field}>
                        <span className={styles.fieldLabel}>
                          {t("login.organization")}
                          <span className={styles.optional}>
                            ({t("common.optional")})
                          </span>
                        </span>
                        <Input
                          className={styles.input}
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
                  <label className={styles.field}>
                    {t("login.email")}
                    <Input
                      className={styles.input}
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
                  <label className={styles.field}>
                    {t("login.password")}
                    <Input
                      className={styles.input}
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={
                        mode === "register" || mode === "reset" ? 10 : 1
                      }
                      maxLength={1024}
                      autoComplete={
                        mode === "register" || mode === "reset"
                          ? "new-password"
                          : "current-password"
                      }
                    />
                    {(mode === "register" || mode === "reset") && (
                      <span className={styles.hint}>
                        {t("login.passwordHint")}
                      </span>
                    )}
                  </label>
                )}
                {message && <div className={styles.message}>{message}</div>}
                {error && <div className={styles.error}>{error}</div>}
                <Button disabled={busy} className={styles.submit}>
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
                </Button>
                {mode === "login" && (
                  <div className={styles.textActions}>
                    <button
                      type="button"
                      onClick={() => {
                        setMode("forgot");
                        setError("");
                        setMessage("");
                      }}
                      className={styles.textButton}
                    >
                      {t("login.forgot")}
                    </button>
                    <button
                      type="button"
                      disabled={busy || !email}
                      onClick={resendVerification}
                      className={styles.textButton}
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
                    className={styles.textButton}
                  >
                    {t("login.back")}
                  </button>
                )}
              </form>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
