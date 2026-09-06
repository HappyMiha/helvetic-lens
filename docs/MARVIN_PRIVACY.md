# Marvin's pause and context lifecycle

Implemented for HL-083 on HappyDucky02, 6 September 2026.

## Controls people can rely on

Marvin's behaviour settings distinguish muting spontaneous remarks from **Pause
Marvin**. Muting leaves the companion available; pausing removes its active panel
and leaves an **Enable Marvin** control in the top bar (robot icon on a phone),
without a floating control covering the page's actions. Re-enabling is an explicit local
action, not an administrator operation or a model download/start.

The enabled and context-attached choices are saved in this browser. Detached
context stays detached on navigation, reload and pause/resume until the user
attaches it again. Pausing an attached companion retains that attachment choice;
resuming then permits its existing context initialization. These choices are
browser preferences, not organization-wide access controls or per-account settings.
Storage denial keeps the current in-memory choice but cannot promise persistence.

Before preferences are loaded, while paused, or with context detached, the
companion does not initiate context/conversation/model-status requests or subscribe
to its AI job feed. Other product panels may still request their own data. No
personal conversation is initialized for a paused/detached companion. When enabled
and attached, the existing typed context contract and personal conversation API
remain in use; visiting a page can still initialize that personal conversation.
Neither enabling nor attaching triggers a model download or monitoring mutation.

## Pending work and private drafts

Navigation, detachment, pause and unmount invalidate the old request generation
and abort that context's browser requests. Late bootstrap, chat or handoff results
cannot restore old messages, take over the new chat, or speak the old reply.
Pending draft timers are cleared. Voice playback stops when context is discarded;
pause also suspends the companion's procedural audio. This does **not** revoke a
request already accepted by the server, delete saved history, cancel another
panel's durable AI job, or prove that inference stopped on the server.

The shell remounts the companion when the authenticated user or organization
changes, so old private chat state is not reused by the new identity. The
companion's job-feed cache also includes both identity identifiers. Browser-tab
comparison drafts use organization + user + comparison identifiers. Unscoped
legacy tab drafts are not restored or uploaded because their owner cannot be
established. They are not deleted. Saved personal server drafts remain available
under the existing authorized conversation API. Merely loading an unchanged saved
draft no longer sends it back as a redundant PATCH.
Only user edits schedule draft saves, including clearing or undoing an edit;
a late history restore does not replace text the user has already started typing.

Draft transfer to cited Ask still works when personal-history persistence is
unavailable and does not itself run inference. Re-enabling a detached companion
does not reattach it as a side effect. UI labels and explanations cover all five
product locales; independent native-language review is still required.

## Reading and deleting personal history

**My Marvin conversations** is available in the workspace navigation and from the
chat's privacy notice at `/assistant-history`. It works while Marvin is paused or
detached. The companion is not mounted on this reading page: opening history does
not initialize a context, poll a model, submit a draft or run inference. History
waits for the authenticated/development identity; changing user, organization or
locale discards the old page state and aborts its reads. There is no shared client
cache of private conversation bodies.

The list requests 20 metadata records at a time (API maximum 50), newest activity
first, with a timestamp/ID cursor. It transfers counts and labels rather than
message, handoff or draft bodies. Reading a selected conversation uses GET and
does not update its last-activity time. That time reflects the existing open,
draft, handoff and chat operations, not only new messages. The cutoff excludes
later activity; it is not an immutable snapshot. Refresh shows the latest state.
No unbounded total-count query or new database migration is introduced. Large
tenant query plans and index/capacity tuning remain separate measured work.

Each context retains its latest 40 messages (individual messages, not 40 pairs),
20 cited-Ask handoffs and one draft. Older messages/handoffs roll off when writing
new ones. There is currently no time-based expiry for the conversation record.
Users can read and explicitly confirm deletion of their own conversation, even
with a viewer role. Organization administrators have no special access to another
person's private conversation through these APIs. Organization and principal are
checked independently of the cursor; a cursor grants no access. The development
mode without login intentionally uses one shared anonymous principal, so it does
not provide separation between multiple anonymous browser users.

DELETE removes the personal conversation record. Shared Ask/Impact answers,
saved monitoring proposals, topics, watches, documents and their evidence are
independent and remain unchanged. Existing integration/administrative logs and
backups are not erased by deleting a conversation; this is not a comprehensive
data-erasure workflow. Administrative audit records retain the operation and ID,
not a copy of the deleted conversation body. Reopening the context later can
create a new empty record. In-flight chat must look up its original ID again
before saving: after deletion it returns not-found rather than recreating history.
This does not cancel GPU work that was already accepted.

After successful deletion the current tab removes the matching owned comparison
draft. An identifier-only browser storage notification lets other open same-origin
Marvin tabs remove that draft, detach that conversation, stop old speech and abort
pending context requests. This notification is best effort if browser storage is
unavailable. Other browsers/devices, closed/suspended contexts, offline copies,
legacy unowned drafts and manually copied text are not remotely erased; refresh
or remove those copies separately. The notice contains only the latest deletion's
identifiers, not its text. General pause/tone preferences still do not live-sync.

## Verification and remaining work

`npm run check:marvin:lifecycle:browser` runs the production frontend against
intercepted synthetic APIs and a speech spy. It exercises disabled startup,
explicit pause/resume, persisted detachment, navigation/reload, pending responses,
identity changes and tab-draft ownership. The existing comparison, Marvin
monitoring and document-history suites cover adjacent flows; the latter now
rejects the formerly observed disabled-companion startup requests. The new suite
is part of the required accessibility chain, with no rule exclusions.

See the dated [verification record](VERIFICATION.md) for actual completed runs.
`npm run check:marvin:history:browser` exercises the production history page in
all five languages on desktop/mobile, with keyboard navigation, pagination,
read-only loading, deletion confirmation/cancellation/retry, empty/error states
and an identity switch while a private detail read is held. It is also in the
required accessibility chain. API tests exercise tenant/principal ownership,
viewer CSRF enforcement, metadata-only paging, shared-record preservation and
deletion during a model response. `scripts/check_assistant_history_postgres.py`
accepts only explicitly named empty localhost scratch databases for those
PostgreSQL checks. It is not a deployment script.

HL-083–HL-085 still require broader intent execution, explicit record-context
selection, durable in-flight chat and useful-task metrics. Time-based retention,
comprehensive data erasure and cross-device cancellation are not delivered here.
This change does not claim independent privacy certification, real speech quality,
model usefulness, GPU or 100-user capacity, or cross-tab live preference sync.
