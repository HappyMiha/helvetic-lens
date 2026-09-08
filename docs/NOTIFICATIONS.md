# In-app notifications

## Reading centre — HL-078, 8 September 2026

The header bell opens an accessible dialog on desktop and mobile. It reads the
existing interest feed through `/api/interest-feed/notifications` with at most five
unread events, rather than copying events or
creating a second delivery store. A card is one eligible persisted event, even
when several topics/laws match it. Its link opens `/?event=<id>` for current
relevance, saved analysis when available, exact evidence and original sources.
Opening the centre or following a link does not mark anything read or call AI.

Read and dismiss buttons explicitly write the existing personal feed state.
Viewers may change their own state; organization relevance and other users are
unchanged. Successful writes invalidate the feed/inbox/digest cache. Failures keep
the visible record, do not pretend the write succeeded, and offer a read-only
refresh before another explicit attempt. No automatic repeat of a failed mutation
is performed. Today exposes read/dismissed items and restores them to unread.

The centre has next, back and latest navigation. Empty candidate batches with a
continuation remain actionable, not an assertion that no older unread events
exist. Page-navigation failure retains the current records; retry uses the failed
cursor. Counts are explicitly **unread on this page**, not a total for the entire
organization. The bell has no invented global badge. Back to the first page and
latest refresh can include newer admissions; the feed's cursor/access contract
still applies, not a frozen snapshot.

The shared resource store polls at 60 seconds only while the centre is mounted,
visible and online. Closing unsubscribes; reopening can show a cached page while
revalidation runs. User/organization/locale identity resets the dialog and page
state. Personal resource keys explicitly include the user and organization IDs,
so cached pages do not depend solely on the normal sign-out/switch cache reset.
Pending navigation cannot reopen a closed/replaced centre. This is not
real-time delivery, a source freshness guarantee or a notifications service that
runs while the browser is closed. Only recorded event detection time is shown;
publication/effective dates remain in event details. Operational failures appear
as errors, never as invented legal developments.

Controls and explanations exist in all five product locales. Modal focus,
Escape/return focus, pointer targets and wrapping are tested in the production
UI. Independent language, real-device and assistive-technology review is still
required; see [verification](VERIFICATION.md).

## Saved relevance briefs — HL-089, 9 September 2026

The notification endpoint composes the same current event feed and saved brief
projection used in digests. One bounded local-runtime metadata observation serves
the entire page, before the SQL read; it does not ask the model to generate,
translate, count tokens or schedule anything. The exact current organization,
input, prompt/configuration, model approval and citation checks still apply.
The selected user's request language controls the variant, independently of the
organization's fallback language. A missing variant never falls back to another
language or starts a new generation. Old clients may still use the unchanged
plain feed endpoint without requesting a brief projection.

Each card shows the short saved development summary and organization importance,
with exact citation links. Expand the relevance control for the current matched
interests, importance explanation, review action (including no-action-now), saved
time, limits and uncertainty. More than three reasons links to the complete event;
the full saved assessment is not truncated or copied into a new notification
record. These are organization relevance conclusions, not an invented private
profile or a claim that each organization interest was personally subscribed to.

Missing, pending, failed, stale, invalid and unverified-runtime states keep the
underlying eligible event and source navigation available without AI prose. The
same event card is enriched on the next ordinary refresh; no second alert or
reading history is created. Revoked evidence removes the ineligible event. A
failed page refresh retains event navigation but hides cached AI text rather than
presenting it as current. Approved conclusions remain snapshots of the checks
performed at retrieval, not continuous attestation while the panel is displayed.

The existing user/organization/locale cache separation and minute cadence remain.
Profile/settings changes invalidate this resource as well. No migration or
production deployment; checks use synthetic model replies and isolated databases.
The page-key bound does not prove bounded total SQL cost for very high interest
fan-out. HL-078/HL-089 still require broader preferences, admission/fairness work,
noise measurement and independent language, accessibility, hardware and user tests.

## Remaining HL-078 work

- An exact durable global unread count with bounded work and verified freshness.
- Personal law/topic/pack/type/importance/channel filters and organization limits.
- Dedicated operational notices, quiet-hours/channel policy and cadence controls.
- Delivery/reconnect/concurrency, notification-noise and independent user tests.

The current centre is the reading/navigation foundation, not completion of
HL-078. Digest settings remain a separate opt-in email/web channel; their filters
do not currently filter this unread-feed centre. No email is sent by this UI.
