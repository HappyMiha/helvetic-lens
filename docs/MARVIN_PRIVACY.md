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

## Verification and remaining work

`npm run check:marvin:lifecycle:browser` runs the production frontend against
intercepted synthetic APIs and a speech spy. It exercises disabled startup,
explicit pause/resume, persisted detachment, navigation/reload, pending responses,
identity changes and tab-draft ownership. The existing comparison, Marvin
monitoring and document-history suites cover adjacent flows; the latter now
rejects the formerly observed disabled-companion startup requests. The new suite
is part of the required accessibility chain, with no rule exclusions.

See the dated [verification record](VERIFICATION.md) for actual completed runs.
HL-083–HL-085 still require the broader intent/retention/deletion UX, explicit
record-context selection contract, durable in-flight chat and useful-task metrics.
This change does not claim independent privacy certification, real speech quality,
model usefulness, GPU or 100-user capacity, or cross-tab live preference sync.
