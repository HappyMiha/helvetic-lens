# BaselTech and Ukraine pilot verification — 21 September 2026

This records operator preparation of demonstration workspaces with real public
sources. It is not independent pilot feedback or evidence of legal completeness.
Accounts, credentials and private workspace records are not repository artifacts.

## Source recovery

The production symptoms were reproduced against the official services:

- Basel-Stadt dataset 100354 contains a null `version_url_de` and null text for
  version 262305. A valid catalogue page previously failed as a whole. The adapter
  now retains the exact OGD version lookup and explicitly unavailable publisher
  link as metadata-only evidence, while ingesting adjacent valid documents.
  No publisher URL, text or legal effective date is invented.
- Fedlex ELI manifestation URIs redirect to the Casemates metadata application.
  The connector now follows the actual `jolux:isExemplifiedBy` file from the
  official SPARQL response. Both its URL and the final response must belong to the
  same manifestation's filestore prefix. The ELI URI remains in provenance.
- Consultation artifacts used an OPTIONAL join across independent draft,
  attachment and impact properties. That multiplied repeated facts until the
  normal extraction limit rejected the result. Independent UNION fact rows keep
  source task identity and all returned values without that product. Existing
  byte, text and passage limits remain unchanged.

Read-only live probes of the corrected adapters:

| Source sample | Observed result |
| --- | --- |
| Basel-Stadt newest catalogue page | 20 references, including one explicit missing publisher link |
| Fedlex `eli/oc/2026/483` | DE/FR/IT exact official files readable; respectively 272/277/278 extracted characters |
| Fedlex `eli/dl/proj/2021/126/cons_1` | DE/FR/IT source JSON readable; respectively 5,673/5,425/5,755 characters and 187 passages each |

The Fedlex sample concerns a published EDI premium-region amendment. The text's
stated future commencement is preserved and is not confused with retrieval time.
Full original files are retained by normal ingestion. Basel annex coverage remains
excluded by the existing source contract.

Final regression run: 41 tests passed across Basel-Stadt, Fedlex, broad official
connectors, the shared connector runner and the backlog integrity gate. Checks
include rejected foreign files, wrong-language files and redirected evidence, as
well as metadata-only replay. Exact API Ruff gate passed. No frontend code changes
are part of this source-recovery change.

Commands: `services/api/.venv/bin/ruff check services/api deploy/release_manager.py`
and `services/api/.venv/bin/pytest services/api/tests/test_basel_stadt.py services/api/tests/test_fedlex_connector.py services/api/tests/test_broad_official_connectors.py services/api/tests/test_connectors.py services/api/tests/test_monitoring_progress.py::test_actual_backlog_has_complete_unique_sections_and_preserves_customs_deferral -q`.

## Live readiness boundaries

The existing platform diagnostics expose all nine native monitor sections. At the
initial inspection, warnings had a current permitted source; river and air had
public source contracts but old acquisitions. Public SIMAP publications were
configured. Pollen permission, transport credentials/permissions, FEDRO access,
auction source permission and IPI monitoring permission were unavailable.
Configuration presence is not proof of coverage; these gaps must not be hidden or
filled with invented observations.

The two requested Basel accounts share one organization with administrator/viewer
roles. The Ukraine account has a separate personal workspace. Demo setup must use
normal authenticated APIs, explicit subscriptions and real saved official source
material. New demo identities have no platform-wide administrator privileges.

Publication, production activation, scenario testing and independent human
acceptance are separate gates. Broader MV2-052 and MV2-058 acceptance stays open.
