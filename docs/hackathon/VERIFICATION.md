# Partner integrations: acceptance evidence

Verification date: 20 September 2026. Development baseline: `8eb4d3b` on main.
See [resource contracts](RESOURCES.md) and the [workstream](../workstreams/HACKATHON_2026.md).

## 23 September: saved cloud connections (H26-06)

OpenAI now has an explicit, pinned provider origin. Swisscom accepts the exact
Swiss {ai} Weeks Apertus 1.5 70B endpoint. `/settings/partners` retains separate
encrypted OpenAI/Swisscom profiles with administrator-only save, revision-checked
test and explicit activation. Saving/testing never switches active inference;
activation copies the saved profile. Later profile removal does not revoke the
active copy; change active inference separately in Settings. The controls are
available to every organization, with credentials isolated to their owner.

Verified locally on Linux with Node 24 and Python 3.12:

- 81 API tests passed: inference connections, existing partners, model settings,
  authentication, integration-log redaction and the required backlog invariant.
  These cover restart persistence, encryption, independent credentials, stale
  revisions, pinned destinations, provider-key boundaries, bounded technical
  calls, failed access without retry/fallback, tenant isolation, CSRF, viewer
  denial and revoked membership.
- Exact `ruff check services/api deploy/release_manager.py`, frontend typecheck
  and production build passed, including localization/resource/shell checks.
- Local built UI: disconnected profiles disable testing/activation; saving a
  synthetic Swisscom credential clears the password field, shows saved status
  and leaves inference unchanged. Explicit activation reports success. Desktop
  card layout inspected; no participant credentials were used in browser tests.
- The issued Swisscom credential returned the exact requested status JSON using
  the application's actual ModelClient and `swiss-ai/Apertus-v1.5-70B` on the
  documented 2026 endpoint. This establishes technical access at check time;
  it does not measure lasting authorization, remaining quota or legal quality.

Production activation and release verification are recorded separately after
deployment. The OpenAI promotion still needs redemption in the participant's
intended account/organization and a separate project API key. Supertext's issued
key has not yet been supplied. Neither is claimed connected from public offer
documentation alone. No redemption code, email address or API key is in Git.

## Delivered behavior

- Anthropic Claude uses native Messages with a fixed official origin, version
  header, selected model and existing bounded analysis calls. Partial/refused
  replies fail visibly; only text blocks enter existing schema/citation validation.
- Swisscom uses the documented bearer-authenticated compatible interface at an
  explicitly entered, allowlisted Swisscom `/v1` endpoint. No model or event
  allocation is invented. Model discovery is possible before model selection;
  saving and generation tests still require a model. Provider changes cannot
  silently send another provider's saved or environment credential.
- Supertext and ElevenLabs settings and reviewed-text actions are available at
  `/settings/partners`, linked from Settings, with page guidance and five-language
  labels. A new organization starts with both integrations disabled.
- Credentials are encrypted using the existing server cipher and never returned
  by the settings API. Organization scope, administrator role, CSRF, revision
  checks and rate limits apply to the new endpoints.
- Translation and speech send only explicitly approved text, at most 3,000
  characters. Calls reject redirects, stop at 45 seconds/4 MiB, and do not replay
  a potentially billable request. Logs contain metadata, without submitted text,
  keys or audio. Access tests are labelled separately from generation verification.
- Migration `d0b384adf013` adds one organization-owned table; it enables no
  provider and makes no external calls. Existing monitoring/source configuration
  and the frozen MVP tag are unchanged.

## Executed checks

The checks used Windows, Node 24, Python 3.11, the frozen dependency lockfiles,
isolated SQLite databases and synthetic HTTP responses. No participant key was
available and no billable generation was attempted.

| Check | Evidence |
|---|---|
| `ruff check services/api deploy/release_manager.py` | Passed |
| Partner/settings/workflow/auth/logging/migration/account-erasure suite | 91 tests passed after integration; no failures |
| Final `test_hackathon_partners.py` after additional edge cases | 29 tests passed, including native Messages, saved-evidence citations, invalid envelopes, model discovery, credential boundaries, consent/revisions, limits, role/tenant isolation and provider failures; overlaps the suite above |
| `npm run typecheck` | Passed, including localization, resource/cache, shell/report and contextual-guide checks |
| `npm run build` | Production build passed; partner route prerendered successfully |
| Changed settings components, new route and section guide formatting | Passed Prettier |
| `npm run format:check` across the whole existing frontend | Existing formatting debt remains. Original HEAD versions of `i18n.tsx` and `types.ts` also fail Prettier; numerous untouched files fail. No repository-wide reformat was included. |
| Local browser at `/settings/partners` | Both providers initially disconnected; access/translation/speech disabled; even reviewed text plus consent cannot call a disconnected provider; enabling without a key shows an actionable error. Desktop layout visually inspected. |
| Final built Settings form | Claude selection shows the native endpoint and correct provider label, offers model discovery before selection, and disables unsupported OpenAI sampling/JSON controls. |

There is one upstream Starlette deprecation warning about its HTTPX test client.
The Python tests pass. SQLite migration coverage does not claim a live PostgreSQL
deployment rehearsal, which remains part of the release boundary below.

Reproduce the focused checks with `npm run check:hackathon`, then `npm run build`.
Use a writable, unique pytest `--basetemp` if the machine's default temporary
directory is inaccessible. Do not point test data at a serving database.

## API activation checks for an administrator

1. Obtain the exact issued credentials, models/voices, allowed data types, credits
   and expiry. Enter secrets only in the authenticated configuration interface.
2. In Settings choose Claude or Swisscom, replace the key, select the granted
   model, test and save. The probe requires the requested JSON response. Test
   an actual cited analysis separately and inspect the saved source passages.
3. In Partner tools configure, enable and save Supertext/ElevenLabs. Test saved
   access. A reachable account or voice does not prove generation credits.
4. Submit a short synthetic text after reviewing the named destination. Check the
   translation manually and listen to the speech. Confirm the actual usage in
   the provider console before using additional credits.
5. Remove a partner key by selecting Remove key and disable, then saving. This
   removes the online configuration; it does not revoke the key at the provider
   or erase retained backups/provider-side requests.

## Open acceptance and release boundary

Public documentation does not establish registration, reuse eligibility, private
participant allocations, dataset rights, live provider access, legal accuracy or
native-language quality. These remain explicit participant/organizer checks.
No approval profile was fabricated and existing capability gates remain in force.

Before publication, the main site's public `/api/ready` reported `ready`, database
and Redis available, instance `main`, release `git-8eb4d3b65a08`. A push is not proof
of deployment: compare this endpoint with the pushed commit and inspect the normal
deployment result. No serving checkout, private data, provider key, Monitoring v2
deployment or release tag was changed manually.

Presentation scripts and participant coaching are intentionally delivered outside
Git, following the user's instruction. This directory contains technical integration
contracts and acceptance evidence only.
