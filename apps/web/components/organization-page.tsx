"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Check, Copy, FileText, Globe2, Loader2, MailCheck, Shield, Trash2, UserRoundPlus, Users } from "lucide-react";
import { Shell } from "./shell";
import { localeNames, locales, type Locale, useI18n } from "@/lib/i18n";
import { useAuth } from "./auth-gate";
import { ErrorNote, SuccessNote } from "./common";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { api, errorText, refreshWorkspace, useResource } from "@/lib/api";
import type { OrganizationStatus } from "@/lib/types";

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

export function OrganizationPage() {
  const { session, canManage } = useAuth();
  const { locale } = useI18n();
  const { data: members, reload: reloadMembers } = useResource<Member[]>(
    session?.authenticated ? "/organization/members" : null,
  );
  const { data: invitations, reload: reloadInvitations } = useResource<Invitation[]>(
    session?.authenticated && canManage ? "/organization/invitations" : null,
  );
  const { data: organizationStatus, reload: reloadStatus } = useResource<OrganizationStatus>(
    session?.authenticated ? "/organization/status" : null,
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
    setInviteToken(new URLSearchParams(window.location.search).get("invite") || "");
  }, []);

  async function act(key: string, action: () => Promise<unknown>, message: string) {
    setBusy(key);
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(message);
      reloadMembers();
      reloadInvitations();
      reloadStatus();
      refreshWorkspace();
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
      <Shell section="Organization">
        <section className="card p-8">
          <Users size={24} className="mb-4" />
          <h1 className="text-2xl font-semibold">Local development workspace</h1>
          <p className="muted max-w-2xl">Accounts and organization membership are available when authentication is enabled. This explicit development workspace keeps the existing local demo flow.</p>
        </section>
      </Shell>
    );
  }

  async function invite(event: React.FormEvent) {
    event.preventDefault();
    setBusy("invite");
    setError("");
    try {
      const value = await api<Invitation & { token: string }>("/organization/invitations", {
        method: "POST",
        body: JSON.stringify({ email, role, recipient_locale: recipientLocale }),
      });
      const link = `${window.location.origin}/login?invite=${encodeURIComponent(value.token)}&locale=${encodeURIComponent(value.recipient_locale)}`;
      setGeneratedLink(link);
      setEmail("");
      setSuccess("Invitation created. Copy the private link and send it to the invited person.");
      reloadInvitations();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <Shell section="Organization">
      <div className="page-heading">
        <div>
          <span className="eyebrow">SHARED WORKSPACE</span>
          <h1>{session?.organization?.name || "Organization"}</h1>
          <p>Members share the same monitored documents, evidence, settings, and AI history.</p>
        </div>
      </div>
      <ErrorNote message={error} />
      {success && <SuccessNote>{success}</SuccessNote>}

      {session.user && !session.user.email_verified && (
        <section className="card p-5 mb-5 flex flex-wrap items-center justify-between gap-4 border-amber-200 bg-amber-50/60">
          <div className="flex items-start gap-3">
            <MailCheck className="mt-0.5 text-amber-700" size={20} />
            <div>
              <strong className="block">Verify your email</strong>
              <p className="text-sm muted">Confirm {session.user.email} so you can recover access if you forget your password.</p>
            </div>
          </div>
          <Button
            variant="outline"
            disabled={!!busy}
            onClick={() => act(
              "verify-email",
              () => api("/auth/email-verification/request", { method: "POST", body: JSON.stringify({ email: session.user?.email }) }),
              "If this address can be verified, a fresh one-time link has been sent.",
            )}
          >
            {busy === "verify-email" ? <Loader2 className="animate-spin" /> : <MailCheck />}
            Send verification link
          </Button>
        </section>
      )}

      {organizationStatus && (
        <>
          <section className="stats-grid mb-5">
            <div className="stat-card"><span className="eyebrow">MONITORED</span><strong>{organizationStatus.workspace.active_watches}</strong><small>Active laws and documents</small></div>
            <div className="stat-card"><span className="eyebrow">TEAM</span><strong>{organizationStatus.workspace.members}</strong><small>{organizationStatus.workspace.pending_invitations} pending invitations</small></div>
            <div className="stat-card"><span className="eyebrow">AI EXECUTION</span><strong>{organizationStatus.ai.execution === "local" ? "Local" : "Cloud opt-in"}</strong><small>{organizationStatus.ai.provider} · credentials {organizationStatus.ai.credential_configured ? "configured" : "not required"}</small></div>
            <div className="stat-card"><span className="eyebrow">PROMPTS</span><strong>Revision {organizationStatus.prompts.revision}</strong><small>{organizationStatus.prompts.source === "organization_override" ? "Organization override" : "Platform default"}</small></div>
          </section>
          {canManage && (
            <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
              <Link href="/sources" className="card p-5 hover:border-primary"><Globe2 className="text-primary mb-3" size={20} /><strong className="block">Watchlist & sources</strong><small className="muted">Add, pause, edit or remove monitored sources.</small></Link>
              <Link href="/prompts" className="card p-5 hover:border-primary"><FileText className="text-primary mb-3" size={20} /><strong className="block">Prompt override</strong><small className="muted">Change AI behaviour for this organization only.</small></Link>
              <Link href="/settings" className="card p-5 hover:border-primary"><Bot className="text-primary mb-3" size={20} /><strong className="block">AI provider</strong><small className="muted">Local by default; cloud transfer requires explicit opt-in.</small></Link>
              <button type="button" onClick={() => document.querySelector<HTMLButtonElement>(".workspace")?.click()} className="card p-5 text-left hover:border-primary"><Shield className="text-primary mb-3" size={20} /><strong className="block">Company profile</strong><small className="muted">Context used to personalize impact analysis.</small></button>
            </section>
          )}
          <section className="card p-5 mb-5 grid sm:grid-cols-3 gap-4 text-sm">
            <div><span className="eyebrow">SAVED AI WORK</span><strong className="block mt-2">{organizationStatus.ai.analyses} analyses · {organizationStatus.ai.questions} answers</strong></div>
            <div><span className="eyebrow">RECORDED TOKENS</span><strong className="block mt-2">{Object.values(organizationStatus.ai.token_counts).reduce((sum, value) => sum + value, 0).toLocaleString()}</strong></div>
            <div><span className="eyebrow">QUOTAS</span><strong className="block mt-2">{Object.keys(organizationStatus.quotas).length ? "Configured" : "Installation defaults"}</strong></div>
          </section>
        </>
      )}

      {session?.organizations && session.organizations.length > 1 && (
        <section className="card p-6 mb-5">
          <h2 className="text-lg font-semibold mb-2">Your workspaces</h2>
          <div className="flex flex-wrap gap-2">
            {session.organizations.map((organization) => (
              <Button
                key={organization.id}
                variant={organization.current ? "default" : "outline"}
                disabled={organization.current || !!busy}
                onClick={() =>
                  act(
                    `switch-${organization.id}`,
                    () =>
                      api("/auth/session/organization", {
                        method: "POST",
                        body: JSON.stringify({ organization_id: organization.id }),
                      }),
                    `Opened ${organization.name}.`,
                  ).then((changed) => changed && window.location.reload())
                }
              >
                {organization.current && <Check size={15} />}
                {organization.name} · {organization.role === "viewer" ? "Viewer" : "Admin"}
              </Button>
            ))}
          </div>
        </section>
      )}

      <section className="card p-6 mb-5">
        <div className="flex items-center gap-3 mb-5">
          <Users size={20} />
          <div>
            <h2 className="text-lg font-semibold">Members</h2>
            <p className="text-sm muted">Administrators manage the workspace. Viewers can inspect it.</p>
          </div>
        </div>
        <div className="divide-y">
          {(members || []).map((member) => (
            <div key={member.id} className="py-4 flex flex-wrap items-center gap-3 justify-between">
              <div>
                <strong>{member.user.name}</strong>{member.current && <span className="ml-2 text-xs muted">You</span>}
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
                              body: JSON.stringify({ role: event.target.value }),
                            }),
                          "Member role updated.",
                        )
                      }
                    >
                      <option value="viewer">Viewer</option>
                      <option value="organization_admin">Administrator</option>
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
                              body: JSON.stringify({ membership_id: member.id }),
                            }),
                          "Administration handed over. Your workspace is now read-only.",
                        )
                      }
                    >
                      <Shield size={14} /> Handover
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${member.user.name}`}
                      disabled={!!busy}
                      onClick={() =>
                        window.confirm(`Remove ${member.user.name} from this organization?`) &&
                        act(
                          `remove-${member.id}`,
                          () => api(`/organization/members/${member.id}`, { method: "DELETE" }),
                          "Member removed and their workspace sessions revoked.",
                        )
                      }
                    >
                      <Trash2 size={15} />
                    </Button>
                  </>
                ) : (
                  <span className="rounded-full border px-3 py-1 text-xs">
                    {member.role === "viewer" ? "Viewer" : "Administrator"}
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
            <div><h2 className="text-lg font-semibold">Invite a member</h2><p className="text-sm muted">Links expire after seven days and work once for the invited email.</p></div>
          </div>
          <form onSubmit={invite} className="grid md:grid-cols-[1fr_170px_170px_auto] gap-3 items-end">
            <label>Email<Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
            <label>Role<select className="h-10 w-full rounded-md border bg-white px-3" value={role} onChange={(e) => setRole(e.target.value as typeof role)}><option value="viewer">Viewer</option><option value="organization_admin">Administrator</option></select></label>
            <label>Invitation language<select className="h-10 w-full rounded-md border bg-white px-3" value={recipientLocale} onChange={(e) => setRecipientLocale(e.target.value as Locale)}>{locales.map((value) => <option value={value} key={value}>{localeNames[value]}</option>)}</select></label>
            <Button type="submit" disabled={!!busy}>{busy === "invite" ? <Loader2 className="animate-spin" /> : <UserRoundPlus />} Create invitation</Button>
          </form>
          {generatedLink && <div className="mt-4 flex gap-2"><Input readOnly value={generatedLink} /><Button variant="outline" onClick={() => navigator.clipboard.writeText(generatedLink)}><Copy /> Copy</Button></div>}
          {!!invitations?.length && <div className="mt-6 divide-y">{invitations.map((invitation) => <div key={invitation.id} className="py-3 flex justify-between gap-3"><span><strong>{invitation.email}</strong><small className="block muted">{invitation.role.replace("organization_", "")} · {invitation.status} · {localeNames[invitation.recipient_locale] || invitation.recipient_locale}</small></span>{invitation.status === "pending" && <Button variant="ghost" size="sm" onClick={() => act(`revoke-${invitation.id}`, () => api(`/organization/invitations/${invitation.id}`, { method: "DELETE" }), "Invitation revoked.")}>Revoke</Button>}</div>)}</div>}
        </section>
      )}

      <section className="card p-6">
        <h2 className="text-lg font-semibold mb-2">Join another workspace</h2>
        <p className="text-sm muted mb-4">Paste an invitation token if you received one without opening its link.</p>
        <div className="flex gap-2"><Input value={inviteToken} onChange={(e) => setInviteToken(e.target.value)} placeholder="Invitation token" /><Button disabled={inviteToken.length < 20 || !!busy} onClick={() => act("accept", () => api("/invitations/accept", { method: "POST", body: JSON.stringify({ token: inviteToken }) }), "Invitation accepted.").then((changed) => changed && window.location.reload())}>Join</Button></div>
      </section>
    </Shell>
  );
}
