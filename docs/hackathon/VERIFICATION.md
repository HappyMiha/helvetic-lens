# Partner integrations: acceptance evidence

Verification date: 20 September 2026. Development baseline: `8eb4d3b` on main.
See [resource contracts](RESOURCES.md) and the [workstream](../workstreams/HACKATHON_2026.md).

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
