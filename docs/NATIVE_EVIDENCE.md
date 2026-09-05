# Saved native-connector evidence

The native connectors already persist raw artifacts and extracted passages in
RegulatoryDocumentVersion. `/corpus-evidence/{id}?passage=<saved-passage-id>` now
uses the existing evidence viewer directly, without manufacturing a Law, legacy
Version, comparison or model job. Today, the event registry and Impact inbox link native-only source versions to
this route; existing legacy evidence routes remain unchanged.

## Access and API

GET `/api/regulatory-versions/{id}` returns saved document metadata, existing
passages, source/language, content hash and an available original-file link.
GET `/api/regulatory-versions/{id}/artifact` serves the original bytes. Both routes
recheck visibility and organization access. The work must be public or owned by
the current organization, with at least one of:

- an organization event admission for this exact version and work;
- a relation-candidate delivery to the organization for this version's event;
- a visible law mapping and document watch (active or paused) for this work.

Topic freshness is not evidence authorization: a rejected/expired match can still
have an admitted source worth inspecting. Removing the admission/delivery revokes
access unless another permitted path remains. Pausing a watch retains history.
An existing legacy-version binding additionally requires both that Version and
its Law to be visible; the new route is not a private-legacy ownership bypass.
Explicit checks also apply to privileged sessions. No personal reading state is
changed by viewing or downloading evidence. Existing authenticated/viewer API
access applies; these routes do not make the application anonymously public.

The artifact handler selects only metadata, not document text/passages. It accepts
only a stored content-addressed filename, resolves it beneath the artifact folder,
rejects traversal/out-of-folder symlinks and checks that the file exists. PDFs use
an inline response; all other content (including HTML) downloads as text/plain.
Responses include sandbox CSP and nosniff. Artifact keys/internal paths never
appear in the document JSON. Source links in the viewer accept HTTP(S) only.

## Viewer behavior and provenance

- Saved passage IDs and PDF page links are retained exactly. A cited passage on
  a later 60-passage display page is brought into view. Missing passage IDs show
  an explicit error and a link to read the complete saved record.
- Missing/unavailable originals never produce a fabricated download link or
  hide retained extracted text. Text without saved passage IDs is displayed as
  unnumbered text, not invented citable passages. Metadata-only records explain
  that there is no extracted text and retain the publisher link if safe.
- Connector records are labelled as saved evidence, not proof of current legal
  status or a fresh website fetch. No official version date is inferred from the
  record's creation/fetch time. An explicit synthetic metadata flag is preserved.
- The source may have changed; the stored original/quoted passage is the evidence.
  The API does not regenerate, re-fetch, analyse or silently repair source content.

This reuses the existing viewer's per-document response and client-side display
pagination. It does **not** introduce server-side passage paging or establish
100-reader/large-document capacity; those HL-099/target-host gates remain open.
The three event surfaces share `corpus_access.event_evidence_links` with the same
SQL access policy as the viewer/original download. Each lookup returns only exact
event/version IDs, never text or passage bodies, and accepts at most 100 distinct
events (an empty batch performs no query). Registry resolves links only after
selecting the displayed page. This removes its per-event full-version load; its
other corpus/filter reads are still not fully bounded SQL paging. An unrelated
newer version is never substituted. Revoked grants, a private work/legacy Law or
Version, and a version expression belonging to another work suppress the link;
no native fallback bypasses an inaccessible legacy binding. A missing original
file does not remove access to saved extracted text. Assistant and other timeline
surfaces remain separate follow-up work. Recorded metadata-only versions are
valid evidence records but do not imply a saved PDF.

## Reproduce verification

- `python -m pytest services/api/tests/test_corpus_evidence.py services/api/tests/test_evidence_navigation.py services/api/tests/test_inbox_context.py -q`
- `npm run build` then `npm run check:native-evidence:browser`
- Empty local PostgreSQL runner `scripts/check_inbox_history_postgres.py` suites
  `native-evidence`, `native-evidence-private`, `native-evidence-relation`,
  `evidence-navigation`, `evidence-navigation-legacy`, `evidence-navigation-private`,
  `evidence-navigation-revoked`.
- `npm run check:registry:browser` and `npm run check:inbox:browser` verify that
  both existing surfaces render the new native source link.

The API fixture runs the actual native connector persistence/extraction pipeline
with synthetic official responses, then reads saved text and original bytes.
Browser APIs are intercepted with synthetic records; five locales × 390/1440px
verify the view, deep citations, navigation, missing originals/text and legacy
viewer compatibility. These checks are not independent/native-language usability
research, physical mobile testing or a real-source/hardware acceptance gate.
No production deployment, data migration, model call or email was performed.
