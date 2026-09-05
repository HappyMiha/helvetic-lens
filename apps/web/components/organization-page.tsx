"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Bot,
  Building2,
  Copy,
  FileText,
  Globe2,
  Loader2,
  MailCheck,
  RotateCcw,
  Shield,
  Trash2,
  UserRoundPlus,
  Users,
} from "lucide-react";
import { Shell } from "./shell";
import { localeNames, locales, type Locale, useI18n } from "@/lib/i18n";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading, SuccessNote } from "./common";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import {
  api,
  errorText,
  invalidateResources,
  resetResourceScope,
  resourceTag,
  useResource,
  type ResourceInvalidation,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import type { OrganizationStatus, Profile } from "@/lib/types";

type Member = {
  id: string;
  role: "organization_admin" | "viewer";
  joined_at: string;
  current: boolean;
  user: { id: string; email: string; name: string };
};
type Invitation = {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  recipient_locale: Locale;
};

function CompanyProfileSection({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const profile = useResource(resources.profile());
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [areas, setAreas] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const allowNavigation = useRef(false);
  const hydrated = useRef(false);
  const dirtyRef = useRef(false);
  const guardToken = useRef(`company-profile-${Date.now()}`);
  const guardEntryActive = useRef(false);
  const unsavedMessage = useRef(t("profile.unsaved"));
  const [savedDraft, setSavedDraft] = useState<string | null>(null);

  unsavedMessage.current = t("profile.unsaved");
  const currentDraft = JSON.stringify({ name, description, areas });
  const dirty = savedDraft !== null && savedDraft !== currentDraft;
  dirtyRef.current = dirty;

  function applyProfile(value: Profile) {
    const next = {
      name: value.name,
      description: value.description,
      areas: value.business_areas.join(", "),
    };
    setName(next.name);
    setDescription(next.description);
    setAreas(next.areas);
    setSavedDraft(JSON.stringify(next));
    hydrated.current = true;
  }

  useEffect(() => {
    if (!profile.data) return;
    if (hydrated.current && dirtyRef.current) return;
    applyProfile(profile.data);
  }, [profile.data]);

  useEffect(() => {
    if (!dirty) return;
    const guardState = {
      ...(window.history.state || {}),
      helveticProfileGuard: guardToken.current,
    };
    if (window.history.state?.helveticProfileGuard !== guardToken.current) {
      window.history.pushState(guardState, "", window.location.href);
    }
    guardEntryActive.current = true;
    function beforeUnload(event: BeforeUnloadEvent) {
      if (allowNavigation.current) return;
      event.preventDefault();
      event.returnValue = "";
    }
    function beforeNavigation(event: Event) {
      if (!window.confirm(unsavedMessage.current)) event.preventDefault();
    }
    function navigationCommitted(event: Event) {
      allowNavigation.current = true;
      if (
        !guardEntryActive.current ||
        window.history.state?.helveticProfileGuard !== guardToken.current
      ) {
        return;
      }
      const continueNavigation = (
        event as CustomEvent<{ continueNavigation?: () => void }>
      ).detail?.continueNavigation;
      if (!continueNavigation) return;
      event.preventDefault();
      guardEntryActive.current = false;
      window.addEventListener("popstate", continueNavigation, { once: true });
      window.history.back();
    }
    function beforeHistoryNavigation() {
      if (allowNavigation.current) return;
      guardEntryActive.current = false;
      if (window.confirm(unsavedMessage.current)) {
        allowNavigation.current = true;
        window.history.back();
      } else {
        window.history.pushState(guardState, "", window.location.href);
        guardEntryActive.current = true;
      }
    }
    function beforeLink(event: MouseEvent) {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      const target = event.target as Element | null;
      const anchor = target?.closest<HTMLAnchorElement>("a[href]");
      if (
        !anchor ||
        anchor.target === "_blank" ||
        anchor.hasAttribute("download")
      ) {
        return;
      }
      const destination = new URL(anchor.href, window.location.href);
      const current = new URL(window.location.href);
      if (
        destination.origin === current.origin &&
        destination.pathname === current.pathname &&
        destination.search === current.search
      ) {
        return;
      }
      if (!window.confirm(unsavedMessage.current)) {
        event.preventDefault();
        event.stopPropagation();
      } else {
        allowNavigation.current = true;
        event.preventDefault();
        event.stopPropagation();
        guardEntryActive.current = false;
        window.addEventListener(
          "popstate",
          () => window.location.assign(destination.href),
          { once: true },
        );
        window.history.back();
      }
    }
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("helvetic:before-navigation", beforeNavigation);
    window.addEventListener(
      "helvetic:navigation-committed",
      navigationCommitted,
    );
    window.addEventListener("popstate", beforeHistoryNavigation);
    document.addEventListener("click", beforeLink, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      window.removeEventListener(
        "helvetic:before-navigation",
        beforeNavigation,
      );
      window.removeEventListener(
        "helvetic:navigation-committed",
        navigationCommitted,
      );
      window.removeEventListener("popstate", beforeHistoryNavigation);
      document.removeEventListener("click", beforeLink, true);
      if (
        guardEntryActive.current &&
        !allowNavigation.current &&
        !dirtyRef.current &&
        window.history.state?.helveticProfileGuard === guardToken.current
      ) {
        guardEntryActive.current = false;
        window.history.back();
      }
      allowNavigation.current = false;
    };
  }, [dirty]);

  function reset() {
    if (!profile.data) return;
    applyProfile(profile.data);
    setError("");
    setSuccess("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const saved = await api<Profile>("/profile", {
        method: "PATCH",
        body: JSON.stringify({
          name,
          description,
          business_areas: areas
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
        }),
      });
      applyProfile(saved);
      profile.setData(saved);
      void invalidateResources(
        resources.organizationStatus(),
        resourceTag("comparison", "organization"),
        resourceTag("impact-matrix", "organization"),
        resourceTag("impact-inbox", "organization"),
        resourceTag("relation-analyses", "organization"),
        resourceTag("digests", "organization"),
        resourceTag("registry", "organization"),
      );
      setSuccess(t("profile.saved"));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card p-6 mb-5 scroll-mt-24" id="company-profile">
      <div className="flex items-start gap-3 mb-5">
        <Building2 className="text-primary mt-0.5" size={21} />
        <div>
          <h2 className="text-lg font-semibold">{t("profile.title")}</h2>
          <p className="text-sm muted m-0">{t("profile.body")}</p>
        </div>
      </div>
      <ErrorNote message={error || profile.error} />
      {success && <SuccessNote>{success}</SuccessNote>}
      {!profile.data ? (
        profile.loading ? (
          <Loading text={t("profile.loading")} />
        ) : (
          <Button onClick={profile.reload} type="button" variant="outline">
            {t("profile.retry")}
          </Button>
        )
      ) : (
        <form className="form-stack" onSubmit={save}>
          <fieldset className="contents" disabled={busy}>
            <label>
              {t("profile.name")}
              <Input
                maxLength={200}
                onChange={(event) => {
                  setName(event.target.value);
                  setSuccess("");
                }}
                required
                readOnly={!canManage}
                value={name}
              />
            </label>
            <label>
              {t("profile.description")}
              <Textarea
                maxLength={6000}
                onChange={(event) => {
                  setDescription(event.target.value);
                  setSuccess("");
                }}
                placeholder={t("profile.descriptionPlaceholder")}
                readOnly={!canManage}
                rows={5}
                value={description}
              />
            </label>
            <label>
              {t("profile.areas")}
              <Input
                onChange={(event) => {
                  setAreas(event.target.value);
                  setSuccess("");
                }}
                placeholder={t("profile.areasPlaceholder")}
                readOnly={!canManage}
                value={areas}
              />
            </label>
          </fieldset>
          {canManage ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button disabled={busy || !dirty || !name.trim()} type="submit">
                {busy && <Loader2 className="animate-spin" />}
                {t("profile.save")}
              </Button>
              <Button
                disabled={busy || !dirty}
                onClick={reset}
                type="button"
                variant="ghost"
              >
                <RotateCcw size={15} />
                {t("profile.discard")}
              </Button>
              {dirty && (
                <span className="text-xs text-amber-700" role="status">
                  {t("profile.unsavedShort")}
                </span>
              )}
            </div>
          ) : (
            <p className="text-sm muted m-0">{t("profile.readOnly")}</p>
          )}
        </form>
      )}
    </section>
  );
}

export function OrganizationPage() {
  const { session, canManage } = useAuth();
  const { locale, t, number } = useI18n();
  const { data: members } = useResource(
    session?.authenticated ? resources.organizationMembers<Member[]>() : null,
  );
  const invitationsResource = useResource(
    session?.authenticated && canManage
      ? resources.organizationInvitations<Invitation[]>()
      : null,
  );
  const invitations = invitationsResource.data;
  const { data: organizationStatus } = useResource(
    session?.authenticated ? resources.organizationStatus() : null,
  );
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"viewer" | "organization_admin">("viewer");
  const [recipientLocale, setRecipientLocale] = useState<Locale>(locale);
  const [inviteToken, setInviteToken] = useState("");
  const [generatedLink, setGeneratedLink] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    setInviteToken(
      new URLSearchParams(window.location.search).get("invite") || "",
    );
  }, []);

  async function act(
    key: string,
    action: () => Promise<unknown>,
    message: string,
    targets: ResourceInvalidation[] = [],
  ) {
    setBusy(key);
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(message);
      if (targets.length) await invalidateResources(...targets);
      return true;
    } catch (cause) {
      setError(errorText(cause));
      return false;
    } finally {
      setBusy("");
    }
  }

  if (!session?.authenticated) {
    return (
      <Shell section={t("nav.profile")}>
        <section className="card p-8">
          <Users size={24} className="mb-4" />
          <h1 className="text-2xl font-semibold">{t("org.localTitle")}</h1>
          <p className="muted max-w-2xl">{t("org.localBody")}</p>
        </section>
        <CompanyProfileSection canManage={canManage} />
      </Shell>
    );
  }

  async function invite(event: React.FormEvent) {
    event.preventDefault();
    setBusy("invite");
    setError("");
    try {
      const value = await api<Invitation & { token: string }>(
        "/organization/invitations",
        {
          method: "POST",
          body: JSON.stringify({
            email,
            role,
            recipient_locale: recipientLocale,
          }),
        },
      );
      const link = `${window.location.origin}/login?invite=${encodeURIComponent(value.token)}&locale=${encodeURIComponent(value.recipient_locale)}`;
      setGeneratedLink(link);
      setEmail("");
      setSuccess(t("org.inviteCreated"));
      if (invitationsResource.data) {
        invitationsResource.setData((current) => [
          value,
          ...(current || []).filter((item) => item.id !== value.id),
        ]);
      } else {
        await invalidateResources(
          resources.organizationInvitations<Invitation[]>(),
        );
      }
      void invalidateResources(resources.organizationStatus());
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <Shell section={t("nav.profile")}>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("org.eyebrow")}</span>
          <h1>{session?.organization?.name || t("org.name")}</h1>
          <p>{t("org.body")}</p>
        </div>
      </div>
      <ErrorNote message={error} />
      {success && <SuccessNote>{success}</SuccessNote>}

      <CompanyProfileSection canManage={canManage} />

      {session.user && !session.user.email_verified && (
        <section className="card p-5 mb-5 flex flex-wrap items-center justify-between gap-4 border-amber-200 bg-amber-50/60">
          <div className="flex items-start gap-3">
            <MailCheck className="mt-0.5 text-amber-700" size={20} />
            <div>
              <strong className="block">{t("org.verify")}</strong>
              <p className="text-sm muted">
                {t("org.verifyBody", { email: session.user.email })}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            disabled={!!busy}
            onClick={() =>
              act(
                "verify-email",
                () =>
                  api("/auth/email-verification/request", {
                    method: "POST",
                    body: JSON.stringify({ email: session.user?.email }),
                  }),
                t("org.verifySent"),
              )
            }
          >
            {busy === "verify-email" ? (
              <Loader2 className="animate-spin" />
            ) : (
              <MailCheck />
            )}
            {t("org.verifySend")}
          </Button>
        </section>
      )}

      {organizationStatus && (
        <>
          <section className="stats-grid mb-5">
            <div className="stat-card">
              <span className="eyebrow">{t("org.monitored")}</span>
              <strong>{organizationStatus.workspace.active_watches}</strong>
              <small>{t("org.activeDocuments")}</small>
            </div>
            <div className="stat-card">
              <span className="eyebrow">{t("org.team")}</span>
              <strong>{organizationStatus.workspace.members}</strong>
              <small>
                {t("org.pending", {
                  count: organizationStatus.workspace.pending_invitations,
                })}
              </small>
            </div>
            <div className="stat-card">
              <span className="eyebrow">{t("org.aiExecution")}</span>
              <strong>
                {organizationStatus.ai.execution === "local"
                  ? t("org.local")
                  : t("org.cloud")}
              </strong>
              <small>
                {t("org.credentials", {
                  provider: organizationStatus.ai.provider,
                  state: organizationStatus.ai.credential_configured
                    ? t("org.configured")
                    : t("org.notRequired"),
                })}
              </small>
            </div>
            <div className="stat-card">
              <span className="eyebrow">{t("org.prompts")}</span>
              <strong>
                {t("org.revision", {
                  revision: organizationStatus.prompts.revision,
                })}
              </strong>
              <small>
                {organizationStatus.prompts.source === "organization_override"
                  ? t("org.override")
                  : t("org.platformDefault")}
              </small>
            </div>
          </section>
          {canManage && (
            <section className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-5">
              <Link href="/sources" className="card p-5 hover:border-primary">
                <Globe2 className="text-primary mb-3" size={20} />
                <strong className="block">{t("org.watchlist")}</strong>
                <small className="muted">{t("org.watchlistBody")}</small>
              </Link>
              <Link href="/prompts" className="card p-5 hover:border-primary">
                <FileText className="text-primary mb-3" size={20} />
                <strong className="block">{t("org.promptOverride")}</strong>
                <small className="muted">{t("org.promptBody")}</small>
              </Link>
              <Link href="/settings" className="card p-5 hover:border-primary">
                <Bot className="text-primary mb-3" size={20} />
                <strong className="block">{t("org.aiProvider")}</strong>
                <small className="muted">{t("org.aiProviderBody")}</small>
              </Link>
            </section>
          )}
          <section className="card p-5 mb-5 grid sm:grid-cols-3 gap-4 text-sm">
            <div>
              <span className="eyebrow">{t("org.savedAi")}</span>
              <strong className="block mt-2">
                {t("org.aiCounts", {
                  analyses: organizationStatus.ai.analyses,
                  answers: organizationStatus.ai.questions,
                })}
              </strong>
            </div>
            <div>
              <span className="eyebrow">{t("org.tokens")}</span>
              <strong className="block mt-2">
                {number(
                  Object.values(organizationStatus.ai.token_counts).reduce(
                    (sum, value) => sum + value,
                    0,
                  ),
                )}
              </strong>
            </div>
            <div>
              <span className="eyebrow">{t("org.quotas")}</span>
              <strong className="block mt-2">
                {Object.keys(organizationStatus.quotas).length
                  ? t("org.quotaConfigured")
                  : t("org.installDefaults")}
              </strong>
            </div>
          </section>
        </>
      )}

      <section className="card p-6 mb-5">
        <div className="flex items-center gap-3 mb-5">
          <Users size={20} />
          <div>
            <h2 className="text-lg font-semibold">{t("org.members")}</h2>
            <p className="text-sm muted">{t("org.membersBody")}</p>
          </div>
        </div>
        <div className="divide-y">
          {(members || []).map((member) => (
            <div
              key={member.id}
              className="py-4 flex flex-wrap items-center gap-3 justify-between"
            >
              <div>
                <strong>{member.user.name}</strong>
                {member.current && (
                  <span className="ml-2 text-xs muted">{t("org.you")}</span>
                )}
                <div className="text-sm muted">{member.user.email}</div>
              </div>
              <div className="flex items-center gap-2">
                {canManage && !member.current ? (
                  <>
                    <select
                      className="h-9 rounded-md border bg-white px-3 text-sm"
                      value={member.role}
                      disabled={!!busy}
                      onChange={(event) =>
                        act(
                          `role-${member.id}`,
                          () =>
                            api(`/organization/members/${member.id}`, {
                              method: "PATCH",
                              body: JSON.stringify({
                                role: event.target.value,
                              }),
                            }),
                          t("org.roleUpdated"),
                          [
                            resources.organizationMembers<Member[]>(),
                            resources.organizationStatus(),
                          ],
                        )
                      }
                    >
                      <option value="viewer">{t("org.viewer")}</option>
                      <option value="organization_admin">
                        {t("org.admin")}
                      </option>
                    </select>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!!busy}
                      onClick={() =>
                        act(
                          `handover-${member.id}`,
                          () =>
                            api("/organization/handover", {
                              method: "POST",
                              body: JSON.stringify({
                                membership_id: member.id,
                              }),
                            }),
                          t("org.handoverDone"),
                          [
                            resources.organizationMembers<Member[]>(),
                            resources.organizationStatus(),
                            resources.authSession(),
                          ],
                        )
                      }
                    >
                      <Shield size={14} /> {t("org.handover")}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("org.removeLabel", {
                        name: member.user.name,
                      })}
                      disabled={!!busy}
                      onClick={() =>
                        window.confirm(
                          t("org.removeConfirm", { name: member.user.name }),
                        ) &&
                        act(
                          `remove-${member.id}`,
                          () =>
                            api(`/organization/members/${member.id}`, {
                              method: "DELETE",
                            }),
                          t("org.memberRemoved"),
                          [
                            resources.organizationMembers<Member[]>(),
                            resources.organizationStatus(),
                          ],
                        )
                      }
                    >
                      <Trash2 size={15} />
                    </Button>
                  </>
                ) : (
                  <span className="rounded-full border px-3 py-1 text-xs">
                    {member.role === "viewer"
                      ? t("org.viewer")
                      : t("org.admin")}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {canManage && (
        <section className="card p-6 mb-5">
          <div className="flex items-center gap-3 mb-5">
            <UserRoundPlus size={20} />
            <div>
              <h2 className="text-lg font-semibold">{t("org.invite")}</h2>
              <p className="text-sm muted">{t("org.inviteBody")}</p>
            </div>
          </div>
          <form
            onSubmit={invite}
            className="grid md:grid-cols-[1fr_170px_170px_auto] gap-3 items-end"
          >
            <label>
              {t("org.email")}
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              {t("org.role")}
              <select
                className="h-10 w-full rounded-md border bg-white px-3"
                value={role}
                onChange={(e) => setRole(e.target.value as typeof role)}
              >
                <option value="viewer">{t("org.viewer")}</option>
                <option value="organization_admin">{t("org.admin")}</option>
              </select>
            </label>
            <label>
              {t("org.inviteLanguage")}
              <select
                className="h-10 w-full rounded-md border bg-white px-3"
                value={recipientLocale}
                onChange={(e) => setRecipientLocale(e.target.value as Locale)}
              >
                {locales.map((value) => (
                  <option value={value} key={value}>
                    {localeNames[value]}
                  </option>
                ))}
              </select>
            </label>
            <Button type="submit" disabled={!!busy}>
              {busy === "invite" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <UserRoundPlus />
              )}{" "}
              {t("org.createInvite")}
            </Button>
          </form>
          {generatedLink && (
            <div className="mt-4 flex gap-2">
              <Input readOnly value={generatedLink} />
              <Button
                variant="outline"
                onClick={() => navigator.clipboard.writeText(generatedLink)}
              >
                <Copy /> {t("org.copy")}
              </Button>
            </div>
          )}
          {!!invitations?.length && (
            <div className="mt-6 divide-y">
              {invitations.map((invitation) => (
                <div
                  key={invitation.id}
                  className="py-3 flex justify-between gap-3"
                >
                  <span>
                    <strong>{invitation.email}</strong>
                    <small className="block muted">
                      {invitation.role === "viewer"
                        ? t("org.viewer")
                        : t("org.admin")}{" "}
                      · {invitation.status} ·{" "}
                      {localeNames[invitation.recipient_locale] ||
                        invitation.recipient_locale}
                    </small>
                  </span>
                  {invitation.status === "pending" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        act(
                          `revoke-${invitation.id}`,
                          () =>
                            api(`/organization/invitations/${invitation.id}`, {
                              method: "DELETE",
                            }),
                          t("org.revoked"),
                          [
                            resources.organizationInvitations<Invitation[]>(),
                            resources.organizationStatus(),
                          ],
                        )
                      }
                    >
                      {t("org.revoke")}
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="card p-6">
        <h2 className="text-lg font-semibold mb-2">{t("org.join")}</h2>
        <p className="text-sm muted mb-4">{t("org.joinBody")}</p>
        <div className="flex gap-2">
          <Input
            value={inviteToken}
            onChange={(e) => setInviteToken(e.target.value)}
            placeholder={t("org.inviteToken")}
          />
          <Button
            disabled={inviteToken.length < 20 || !!busy}
            onClick={() =>
              act(
                "accept",
                () =>
                  api("/invitations/accept", {
                    method: "POST",
                    body: JSON.stringify({ token: inviteToken }),
                  }),
                t("org.accepted"),
              ).then((changed) => {
                if (!changed) return;
                resetResourceScope("all");
                window.location.reload();
              })
            }
          >
            {t("org.joinButton")}
          </Button>
        </div>
      </section>
    </Shell>
  );
}
