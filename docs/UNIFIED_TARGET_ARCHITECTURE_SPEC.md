# Helvetic Lens — Unified Target Architecture
## Development Specification for Codex

**Status:** Target architecture / implementation brief  
**Scope:** Helvetic Lens Core + Legal + Pharma  
**Architecture principle:** One platform, multiple domain packs  
**Primary product object:** Living Dossier  
**Core workflow:** `find → monitor → connect → explain → cite → remember`  
**Human role:** Helvetic Lens prepares evidence, context, provenance and change analysis; the human remains the decision-maker.

---

# 0. Purpose of this document

This document **supersedes the Pharma-only architecture specification**.

Helvetic Lens must not evolve into separate Legal and Pharma products with separate engines.

The target architecture is:

```text
                    HELVETIC LENS
                         CORE
                          │
          ┌───────────────┴───────────────┐
          │                               │
       LEGAL PACK                     PHARMA PACK
          │                               │
  Legal sources / skills          Pharma sources / skills
  Applicability logic             Pharma domain logic
  Legal templates                 Pharma templates
```

The **Core** owns the common product architecture.

Legal and Pharma are **domain packs** that configure and extend the Core.

The Core must not contain hard-coded domain assumptions when the same capability can be expressed through configuration, adapters, skills, schemas or templates.

---

# 1. Codex operating instructions

Before changing production code:

1. Inspect the current Helvetic Lens repository.
2. Document the current architecture as it actually exists.
3. Reuse existing:
   - Dossier models;
   - ingestion;
   - jobs;
   - monitoring;
   - search;
   - citations;
   - snapshots;
   - history;
   - UI components;
   - auth;
   - AI integrations;
   - Apertus integration;
   - database structures.
4. Do **not** assume that target components in this specification already exist.
5. Do **not** rewrite working functionality merely to match terminology in this document.
6. Keep existing general/Legal workflows working during migration.
7. Add Pharma as a domain pack on the same Core.
8. Prefer incremental migration and feature flags over a large rewrite.
9. Prefer deterministic processing, APIs and indexed retrieval before invoking large LLMs.
10. Every user-visible factual AI assertion must be traceable to evidence.
11. Never present an AI output as a guaranteed legal, regulatory, medical, reimbursement or compliance decision.
12. Never claim complete coverage when any configured source is unavailable, delayed or unchecked.

For every target component, classify the current state as:

```text
EXISTS
PARTIAL
TODO
BLOCKED
NOT_NEEDED
```

---

# 2. Product thesis

Helvetic Lens is not:

- a collection of independent AI chatbots;
- five hard-coded lenses;
- a Legal product plus an unrelated Pharma product;
- a replacement for official sources;
- an autonomous decision engine;
- an ERP, planning or document-management replacement.

Helvetic Lens is:

> **A continuously updated, evidence-backed Living Dossier platform.**

A dossier can represent:

```text
Legal:
- a legal question;
- a case;
- a regulation;
- a dispute;
- a policy topic;
- a monitored legislative area.

Pharma:
- a product;
- a molecule;
- an indication;
- a market-access question;
- a regulatory topic;
- a safety topic;
- a competitor/product landscape.
```

The platform continuously:

```text
finds
→ monitors
→ normalizes
→ compares
→ connects
→ explains
→ cites
→ remembers
```

---

# 3. Shared product UX

The Core should answer three universal questions:

1. **What changed?**
2. **Does it matter?**
3. **Why should I trust it?**

Legal adds one domain-specific primary question:

4. **What applies here?**

Therefore:

```text
LEGAL
What applies?
What changed?
Does it matter?
Why should I trust it?

PHARMA
What changed?
Does it matter?
Why should I trust it?
```

The main UI must remain simple even if the architecture underneath is complex.

---

# 4. Target architecture overview

```text
┌─────────────────────────────────────────────────────────────┐
│                       HELVETIC LENS UI                      │
│                                                             │
│  Dossier │ Timeline │ Findings │ Evidence │ Ask │ Coverage  │
│  Review  │ Claims   │ Provenance │ Collaboration            │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    HELVETIC LENS CORE                      │
│                                                             │
│  Dossier Service                                             │
│  Evidence Graph                                              │
│  Claim Ledger                                                │
│  Monitoring / Scheduler                                      │
│  Change Detection                                            │
│  Finding Service                                             │
│  Review Workflow                                             │
│  Source Registry                                             │
│  Skill Registry                                              │
│  Tool Router / AI Gateway                                    │
│  Search / Retrieval                                          │
│  Coverage Manifest                                           │
│  Audit / Provenance                                          │
│  Notifications                                               │
│  Access / Visibility                                         │
│  Collaboration                                               │
└───────────────┬──────────────────────────────┬──────────────┘
                │                              │
      ┌─────────▼─────────┐          ┌────────▼─────────┐
      │    LEGAL PACK      │          │   PHARMA PACK    │
      │                    │          │                  │
      │ Legal Sources      │          │ Pharma Sources   │
      │ Legal Skills       │          │ Pharma Skills    │
      │ Applicability      │          │ Domain schemas   │
      │ Legal templates    │          │ Pharma templates │
      │ Legal claim types  │          │ Market Access    │
      └────────────────────┘          └──────────────────┘
```

---

# 5. Core domain model

The following concepts are platform-wide.

## 5.1 Dossier

A dossier is a long-lived research and monitoring container.

Minimum fields:

```text
id
title
slug
description
domain
template_id
visibility
owner_id
organisation_id
status
monitoring_enabled
monitoring_frequency
created_at
updated_at
```

Domain:

```text
GENERAL
LEGAL
PHARMA
```

A dossier may evolve over time without recreation.

---

## 5.2 Domain context

Do not force all domain-specific fields into the common Dossier table.

Use a domain-context mechanism.

Example:

```text
Dossier
├── common fields
└── domain_context
    ├── legal_context
    └── pharma_context
```

This can be implemented through:
- JSONB;
- extension tables;
- typed schemas;
- another approach already compatible with the repository.

Codex must choose the smallest compatible change.

---

# 6. Shared Dossier visibility model

Support:

```text
PUBLIC
PRIVATE
SHARED
ORGANISATION
```

## Public dossier

Readable without registration when policy allows.

Registered users may, depending on permissions:

- comment;
- suggest sources;
- upload public evidence;
- suggest claims;
- trigger additional research;
- follow/monitor.

## Private dossier

Visible only to owner/invited users.

Supports:

- private documents;
- correspondence;
- contracts;
- internal evidence;
- notes;
- private review;
- private Ask.

## Organisation dossier

Future/enterprise mode.

Supports:
- teams;
- roles;
- source permissions;
- internal connectors;
- audit requirements.

Do not create separate Dossier implementations for these modes.

---

# 7. Evidence Graph

The core information architecture is an Evidence Graph.

Minimum shared node types:

```text
Dossier
Entity
Event
Evidence
Source
SourceVersion
Claim
Finding
Review
UserNote
```

Typical relations:

```text
ENTITY --mentioned_in--> EVIDENCE
EVENT --supported_by--> EVIDENCE
CLAIM --supported_by--> EVIDENCE
CLAIM --contradicted_by--> EVIDENCE
CLAIM --supersedes--> CLAIM
FINDING --derived_from--> EVIDENCE
FINDING --affects--> ENTITY
SOURCE --has_version--> SOURCE_VERSION
REVIEW --reviews--> FINDING
NOTE --attached_to--> CLAIM / FINDING / EVIDENCE
```

A graph database is **not required**.

Use relational tables/edge tables if sufficient.

Do not introduce Neo4j or another major dependency without demonstrated need.

---

# 8. Evidence model

Minimum:

```text
Evidence
- id
- dossier_id
- source_id
- source_document_id
- source_version_id
- title
- canonical_url
- publication_date
- retrieved_at
- content_hash
- language
- jurisdiction
- document_type
- raw_content_pointer
- normalized_text
- metadata_json
- visibility
```

Requirements:

- evidence must be versioned;
- old versions must remain retrievable;
- evidence must know where it came from;
- evidence visibility must be enforced;
- AI summaries are never the only stored representation of a source.

---

# 9. Source and SourceVersion

Model source identity separately from retrieved document versions.

```text
Source
- id
- name
- provider
- source_type
- authority_level
- domain_tags[]
- jurisdictions[]
- adapter_id
- enabled
```

```text
SourceVersion
- id
- source_id
- external_id
- retrieved_at
- published_at
- effective_from
- effective_to
- hash
- raw_pointer
- normalized_pointer
- metadata
```

Do not silently overwrite old versions.

---

# 10. Claim Ledger

The Claim Ledger is a shared Core capability.

A claim is a structured assertion that can survive outside a generated summary.

```text
Claim
- id
- dossier_id
- text
- normalized_subject
- predicate
- normalized_object
- claim_type
- domain
- status
- confidence
- valid_from
- valid_to
- created_at
- updated_at
- visibility
```

Relations:

```text
Claim
  ├── supported_by → Evidence[]
  ├── contradicted_by → Evidence[]
  ├── derived_from → Finding[]
  ├── supersedes → Claim
  ├── applies_to → Entity[]
  └── reviewed_by → Review[]
```

Statuses:

```text
PROPOSED
ACCEPTED
REJECTED
SUPERSEDED
DISPUTED
UNRESOLVED
```

---

# 11. Domain-specific claim types

The Claim Ledger is shared, but domains can register types.

## Legal

```text
STATUTORY_RULE
CASE_HOLDING
FACT
PARTY_ARGUMENT
INTERPRETATION
EXCEPTION
PROCEDURAL_REQUIREMENT
JURISDICTION_RULE
AI_ANALYSIS
```

## Pharma

```text
REGULATORY_STATUS
MARKET_ACCESS_STATUS
SAFETY_SIGNAL
CLINICAL_RESULT
LABEL_CHANGE
REIMBURSEMENT_CHANGE
SUPPLY_EVENT
COMPETITOR_EVENT
EVIDENCE_INTERPRETATION
AI_ANALYSIS
```

Do not mix source fact and AI interpretation under the same type.

---

# 12. Findings

A Finding is a newly detected or generated item requiring user attention.

```text
Finding
- id
- dossier_id
- title
- summary
- impact_summary
- finding_type
- domain
- status
- materiality
- created_at
- detected_at
```

Relations:

```text
Finding
  ├── derived_from → Evidence[]
  ├── affects → Entity[]
  ├── proposes → Claim[]
  └── reviewed_by → Review[]
```

Statuses:

```text
NEW
PENDING_REVIEW
ACCEPTED
DISMISSED
NEEDS_MORE_EVIDENCE
SUPERSEDED
```

---

# 13. Human Review

Human review is a first-class architecture element.

Do not treat review as a fallback failure.

Review is especially important for:

- legal interpretation;
- regulatory interpretation;
- high-impact findings;
- conflicting evidence;
- generative conclusions;
- low-coverage situations;
- private/internal evidence;
- material updates.

Review record:

```text
Review
- id
- target_type
- target_id
- reviewer_id
- decision
- comment
- reviewed_at
- source_versions[]
- skill_versions[]
- model_versions[]
```

Accepted findings may create or update claims.

Dismissed findings remain auditable.

---

# 14. Source Registry

The Core owns a Source Registry.

Standard adapter interface:

```text
id
name
domain_tags[]
jurisdictions[]
capabilities[]
auth_type
fetch()
search()
get_document()
get_versions()
health_check()
```

Capabilities:

```text
SEARCH
FEED
API
DOCUMENT
CHANGE_FEED
FULL_TEXT
METADATA
VERSION_HISTORY
```

Source Packs are domain configurations.

They are **not** hard-coded UI products.

---

# 15. Skill Registry

The Core owns a dynamic Skill Registry.

A skill is a reusable task.

Examples:

```text
detect_change
extract_entity
resolve_entity
extract_claim
compare_versions
classify_relevance
summarize_evidence
cross_source_compare
timeline_builder
citation_verification
conflict_detection
```

Metadata:

```text
id
name
domain
version
input_schema
output_schema
cost_class
latency_class
deterministic
requires_llm
supported_providers[]
enabled
```

Domain packs register additional skills.

---

# 16. Tool Router / AI Gateway

The system must not send all tasks to Apertus.

Preferred routing:

```text
1. exact database lookup
2. deterministic parser / rules / diff
3. official/source API
4. indexed retrieval / search
5. lightweight specialized provider
6. Laya / Jev where appropriate
7. Apertus / larger reasoning model
```

The router must consider:

```text
task type
domain
required reliability
source authority
latency
cost
privacy
context size
need for reasoning
need for determinism
```

---

# 17. Provider architecture

Implement provider adapters rather than direct coupling:

```text
ToolProvider
├── DeterministicProvider
├── SearchProvider
├── SourceApiProvider
├── LayaProvider
├── JevProvider
└── ApertusProvider
```

Each run records:

```text
task
provider
model/tool
version
input references
output reference
latency
estimated cost
fallback
timestamp
```

Laya and Jev are optional until their actual interfaces, licenses and capabilities are verified.

Do not implement them purely for branding.

---

# 18. Apertus role

Apertus is a reasoning and synthesis tool, not the centre of Helvetic Lens.

Use for:

- multi-source synthesis;
- contextual explanation;
- evidence comparison;
- conflict explanation;
- grounded Q&A;
- dossier-level reasoning.

Avoid for:

- exact database lookup;
- simple metadata extraction;
- hashes;
- basic diff;
- simple identifier mapping;
- deterministic transformations.

---

# 19. Monitoring

Monitoring is a shared Core capability.

Pipeline:

```text
Scheduler
→ configured Source Pack
→ source adapters
→ retrieve
→ normalize
→ version
→ deduplicate
→ detect change
→ assess materiality
→ map to dossier
→ create finding
→ update evidence graph
→ human review if required
→ notify if meaningful
```

Do not rebuild the whole dossier on every scan.

---

# 20. Change Detection

Primary shared service.

```text
new source version
→ canonicalize
→ hash
→ structural diff
→ semantic diff only if needed
→ classify change
→ map affected entities/claims
→ create finding
```

Change types:

```text
NEW_DOCUMENT
UPDATED_DOCUMENT
REMOVED_DOCUMENT
METADATA_CHANGE
TEXT_CHANGE
STATUS_CHANGE
DATE_CHANGE
TABLE_CHANGE
UNKNOWN_CHANGE
```

Use deterministic diff before AI.

---

# 21. Coverage Manifest

Every monitored dossier must expose what was actually checked.

Example:

```text
Coverage

Fedlex             ✓ checked 11:31
Bundesgericht      ✓ checked 11:29
EMA                ✓ checked 11:28
Swissmedic         ✓ checked 11:27
PubMed             ⚠ delayed
Internal Vault     — not connected
```

Per-source coverage:

```text
source_id
enabled
last_attempt
last_success
last_change_detected
health
coverage_scope
query_strategy
rate_limit_state
error
```

Never show:

> No relevant changes.

when configured coverage is incomplete unless the UI explicitly says:

> No relevant changes found in successfully checked sources; coverage is incomplete.

---

# 22. Source Health

States:

```text
HEALTHY
DELAYED
RATE_LIMITED
AUTH_REQUIRED
FAILED
DISABLED
UNSUPPORTED
```

Source failures must be visible.

They must never silently disappear from a scan.

---

# 23. Audit / Provenance

Every meaningful operation should be auditable.

Record:

```text
actor
action
timestamp
dossier
source version
skill version
provider/model version
input references
output references
```

Audit events include:

- source fetched;
- evidence created;
- source updated;
- scan completed/failed;
- skill executed;
- model invoked;
- finding created;
- review performed;
- claim accepted;
- claim superseded;
- dossier configuration changed;
- visibility changed.

---

# 24. Ask / Search

One universal Ask/Search component should work across all domains.

It must use the dossier as its primary context.

Resolution priority:

```text
accepted claims
→ evidence
→ source versions
→ dossier entities/events
→ configured source search
→ broader search if allowed
→ grounded synthesis
```

Requirements:

1. cite evidence;
2. distinguish source fact from AI interpretation;
3. show uncertainty;
4. surface conflicting evidence;
5. show incomplete coverage;
6. never fabricate evidence;
7. preserve private/public access boundaries.

---

# 25. Dossier memory

The dossier remembers through structured data, not only chat.

Persist:

- accepted claims;
- rejected/dismissed findings;
- entities;
- aliases;
- user notes;
- source preferences;
- monitoring scope;
- review decisions;
- important events.

Chat is a view/controller over the dossier.

Chat history is not the dossier database.

---

# 26. Collaboration

Common capabilities:

- comments;
- notes;
- assignments;
- evidence uploads;
- suggested sources;
- suggested claims;
- review requests;
- public contributions where allowed.

Do not build separate collaboration systems for Legal and Pharma.

---

# 27. Shared UI architecture

Most frontend should be shared.

Core pages/components:

```text
Dossier Overview
Timeline
Findings
Evidence Drawer
Claim View
Review Queue
Coverage
Provenance
Ask / Search
Collaboration
Settings
```

Domain packs can add:

- domain-specific labels;
- filters;
- context panels;
- templates;
- entity views;
- applicability/relevance panels.

Avoid forking the frontend.

---

# 28. UI visual direction

Use the current Helvetic Lens visual direction:

- light or near-black background;
- strong typography;
- large data blocks;
- minimal borders;
- glass sidebar where useful;
- floating universal Ask/Search;
- Lens/refraction effect only when the system is actively processing/connecting evidence.

The Lens/refraction effect should represent **analysis**, not decoration.

---

# 29. "Why should I trust it?" panel

One common trust panel should expose:

```text
Source
Authority
Publication date
Retrieved at
Source version
Exact supporting evidence
Confirming evidence
Contradicting evidence
Processing path
Human review status
Coverage status
```

Do not use a generic AI confidence percentage as the primary trust mechanism.

---

# 30. Contradictions

The Core must preserve contradictions.

Example:

```text
Claim A
supported by Source 1 and Source 2

Claim B
supported by Source 3

Conflict:
UNRESOLVED
```

Do not force one generated answer when evidence genuinely conflicts.

---

# 31. Domain Pack contract

A domain pack should be able to register:

```text
domain metadata
context schema
entity types
claim types
source packs
skills
dossier templates
relevance rules
review rules
UI extensions
prompt templates
validation rules
```

Conceptually:

```text
DomainPack
- id
- version
- context_schema
- entity_types[]
- claim_types[]
- source_packs[]
- skills[]
- templates[]
- review_policy
- ui_extensions
```

Core services consume this contract.

---

# 32. LEGAL PACK

Legal is a domain pack over Helvetic Lens Core.

It must not have a separate ingestion, evidence, monitoring, audit or Ask engine.

---

# 33. Legal Dossier context

Optional structured context:

```text
jurisdictions[]
legal_area[]
parties[]
organisations[]
courts[]
authorities[]
laws[]
articles[]
case_ids[]
procedural_stage
relevant_dates[]
tags[]
```

Do not require every field.

The dossier may begin from one simple question.

Example:

```text
Can a landlord prohibit children from playing in the courtyard on Sunday?
```

The system can progressively resolve:

```text
country
canton
municipality
tenancy context
relevant house rules
applicable statutes
case law
```

---

# 34. Legal's additional core question

Legal adds:

> **What applies here?**

This is distinct from:

> What did I find?

The system must reason about applicability, not only retrieval.

---

# 35. Legal Applicability Engine

Legal adds an **Applicability Engine** as a domain service/skill set.

Minimum applicability dimensions:

```text
jurisdiction
territorial_scope
legal_level
subject_scope
effective_from
effective_to
superseded_by
amends
implements
interpreted_by
procedural_context
```

Conceptual chain:

```text
Evidence
→ Legal Source
→ Source Version
→ Applicability
→ Claim
→ Dossier question
```

The system must avoid common Legal AI failures such as:

- correct law, wrong version;
- correct law, wrong canton;
- federal rule applied to municipal issue without analysis;
- repealed rule treated as current;
- secondary commentary presented as binding law.

---

# 36. Legal source packs

Examples for Switzerland may include:

```text
Fedlex
Bundesgericht
admin.ch
SEM
SECO
BAG / FOPH
Swissmedic
cantonal legislation
cantonal courts
municipal rules
official gazettes
parliamentary materials
EUR-Lex when relevant
HUDOC / ECHR when relevant
```

Exact adapters must be verified during implementation.

Official sources should generally outrank secondary sources for primary-law facts.

---

# 37. Legal skills

Register Legal-specific skills such as:

```text
resolve_jurisdiction
find_applicable_law
resolve_law_version
extract_legal_rule
extract_exception
extract_definition
compare_law_versions
find_case_law
extract_case_holding
resolve_precedential_weight
find_supporting_authority
find_conflicting_authority
build_legal_timeline
verify_legal_citation
compare_jurisdictions
analyse_contract_clause
detect_regulatory_change
```

Do not invoke Apertus when an exact source lookup or deterministic version comparison is sufficient.

---

# 38. Legal source authority model

Legal should distinguish:

```text
PRIMARY_BINDING
PRIMARY_NON_BINDING
CASE_LAW
OFFICIAL_GUIDANCE
PARLIAMENTARY_MATERIAL
SECONDARY_COMMENTARY
USER_DOCUMENT
USER_STATEMENT
AI_INTERPRETATION
```

This should influence:

- ranking;
- trust display;
- synthesis;
- review requirements.

Do not treat all web sources equally.

---

# 39. Legal claim separation

Legal must distinguish:

```text
SOURCE FACT
LEGAL RULE
COURT HOLDING
PARTY ARGUMENT
USER FACT
INTERPRETATION
AI ANALYSIS
```

A generated summary must not collapse these categories.

Example:

```text
Article text:
"X"

Court holding:
"The court interpreted X as ..."

AI analysis:
"This may be relevant to the dossier because ..."
```

These are separate objects/provenance layers.

---

# 40. Legal monitoring

Example:

```text
Dossier:
Swiss Status S — legislation and policy

Monitor:
Fedlex
SEM
Federal Council
Parliament
cantonal guidance
relevant courts
```

When something changes:

```text
What changed?
→ new amendment/guidance/case

What applies?
→ affected group, jurisdiction, effective date

Does it matter?
→ which dossier claims may change

Why should I trust it?
→ official source, exact version, passages
```

---

# 41. Legal public dossiers

Legal is well suited for public collaborative dossiers.

Example:

```text
Swiss Status S — current law and changes
```

Public users may read.

Registered users may, by permission:

- propose sources;
- add documents;
- comment;
- ask questions;
- suggest claims;
- trigger further research.

Every contribution must preserve provenance and moderation/review state.

---

# 42. Legal private dossiers

Examples:

```text
Tenant dispute
Employment issue
Immigration case
Contract review
Litigation preparation
```

Private documents may include:

- contracts;
- letters;
- emails;
- decisions;
- evidence;
- user notes.

Private evidence must never leak into public answers or public dossiers.

---

# 43. Legal product boundary

Do:

- retrieve law;
- resolve versions;
- show authority;
- connect evidence;
- monitor legal changes;
- explain possible relevance;
- show conflicting interpretations;
- produce draft analysis grounded in sources.

Do not present the system as:

- a court;
- a lawyer of record;
- a binding legal authority;
- guaranteed complete legal research;
- autonomous case decision-maker.

---

# 44. PHARMA PACK

Pharma is another domain pack over the same Core.

No separate evidence store, monitoring engine or Ask architecture.

---

# 45. Pharma Dossier context

Optional structured context:

```text
product_names[]
active_substances[]
company_names[]
therapeutic_areas[]
indications[]
countries[]
regulatory_ids[]
market_access_ids[]
trial_ids[]
competitors[]
tags[]
```

Do not require all fields.

The dossier can start from:

```text
product
molecule
company
disease
question
```

---

# 46. Pharma product direction

Pharma should be monitoring-first.

Primary action:

> **Keep this dossier current.**

Not:

> Let AI make the regulatory/reimbursement decision.

Core flow:

```text
Sources
→ detect change
→ build/update dossier
→ explain significance
→ show evidence
→ human decides
```

---

# 47. Pharma source packs

Potential sources include:

```text
Swissmedic
EMA
FDA
BAG / FOPH
Spezialitätenliste
PubMed
ClinicalTrials.gov
company publications
public pricing/reimbursement sources
guidelines
selected official safety feeds
public shortage sources/APIs
```

Exact adapters must be verified.

External services should be used as sources where useful rather than unnecessarily rebuilt.

---

# 48. Pharma skills

Examples:

```text
resolve_product
resolve_active_substance
resolve_indication
detect_label_change
detect_regulatory_status_change
detect_reimbursement_change
compare_product_information
clinical_evidence_extraction
trial_update_detection
safety_signal_extraction
market_access_assessment
competitor_event_detection
cross_market_compare
```

---

# 49. Pharma first vertical slice: Market Access

The first concrete Pharma template should be:

> **Market Access Dossier**

Example:

```text
Product: Wegovy
Market: Switzerland
```

Possible monitored context:

```text
Spezialitätenliste
BAG / FOPH
Swissmedic
EMA
relevant clinical evidence
guidelines
comparators
company publications
```

The goal is not to create a separate "Market Access product".

It is the first validated domain template running on Core.

---

# 50. Pharma review model

Human review should be mandatory/configurable for:

- high-impact changes;
- generative regulatory interpretation;
- conflicting evidence;
- uncertain product/indication match;
- safety findings;
- reimbursement interpretation;
- incomplete coverage.

The system prepares evidence.

The human remains responsible for action.

---

# 51. Pharma coverage

Example:

```text
Swissmedic        ✓ checked 11:31
EMA               ✓ checked 11:28
PubMed            ✓ checked 11:25
ClinicalTrials    ✓ checked 11:22
BAG / FOPH        ✓ checked 11:19
Internal Vault    — not connected
```

Coverage is part of the product.

Do not hide failed scans.

---

# 52. Pharma and existing systems

Do not attempt to replace:

```text
Veeva
SAP
Kinaxis
o9
Salesforce
validated internal planning systems
official regulatory systems
```

Helvetic Lens can:

```text
connect
ingest
correlate
monitor
explain
cite
```

It should sit above/beside these systems as an evidence/context layer.

---

# 53. Supply risk

Do not build another public shortage database if existing sources already expose the data.

Instead:

```text
shortage API/source
+
regulatory evidence
+
clinical evidence
+
manufacturer evidence
+
optional internal customer data
        ↓
Living Dossier
```

Prediction must not be the default product promise.

If experimental prediction is added later, clearly separate:

```text
VERIFIED FACT
OBSERVED SIGNAL
SCENARIO
MODEL PREDICTION
```

---

# 54. Legal and Pharma reuse target

The intended reuse is high.

Shared:

```text
Dossier
Evidence
Sources
Source Versions
Claims
Findings
Review
Monitoring
Coverage
Audit
Ask/Search
Notifications
Collaboration
UI shell
Tool Router
AI Gateway
```

Domain-specific:

```text
context schemas
source packs
skills
entity types
claim types
relevance rules
applicability/domain logic
templates
UI labels/extensions
```

Do not target a fixed percentage in code, but architect so that domain differences do not require copied Core code.

---

# 55. Dossier templates

Templates configure a dossier without creating a new product.

Examples:

```text
LEGAL:
- Legal Question
- Legislative Monitor
- Case / Dispute
- Immigration
- Tenancy
- Employment
- Contract Analysis

PHARMA:
- Market Access
- Regulatory Monitor
- Clinical Evidence
- Safety
- Competitor Intelligence
- Supply Context
```

Templates may register:

- suggested context fields;
- source packs;
- default monitoring;
- relevant skills;
- UI sections;
- review policy.

---

# 56. No hard-coded lenses

Do not build:

```text
Safety Lens service
Market Access Lens service
Competitor Lens service
Supply Lens service
Divergence Lens service
```

Instead:

```text
Dossier
+ template
+ domain pack
+ sources
+ skills
+ monitoring rules
```

A user may combine multiple capabilities in the same dossier.

Example:

```text
Semaglutide — Switzerland
├── market access
├── regulatory
├── clinical
└── competitor events
```

One evidence graph.

One timeline.

One Ask.

---

# 57. Relevance and materiality

Use explainable relevance.

Shared factors:

```text
entity match
jurisdiction
source authority
novelty
change type
evidence strength
relationship to accepted claims
```

Legal additionally:

```text
applicability
legal level
effective date
procedural relevance
```

Pharma additionally:

```text
product/substance match
indication
market
regulatory status
reimbursement impact
clinical significance
```

Prefer:

```text
High relevance because:
- exact entity match
- applicable jurisdiction
- primary official source
- status changed
```

over opaque:

```text
relevance = 0.91
```

---

# 58. Notifications

Shared modes:

```text
IMMEDIATE
DAILY_DIGEST
WEEKLY_DIGEST
NONE
```

Notify only for meaningful findings.

Include:

- what changed;
- why it may matter;
- evidence;
- dossier link;
- coverage warning when relevant.

Do not notify for every crawl.

---

# 59. Search architecture

Layer search:

```text
existing dossier evidence
→ accepted claims
→ configured official/source APIs
→ configured authoritative sites
→ broader web/search provider if allowed
→ AI synthesis
```

Avoid repeatedly searching the open web for information already in the dossier.

---

# 60. Uploads and internal evidence

Uploaded files are evidence sources.

Requirements:

- preserve original;
- record uploader;
- hash;
- visibility;
- extraction provenance;
- version where applicable;
- access policy;
- link generated claims back to exact evidence.

Private source data must never be exposed through public dossier search.

---

# 61. Access control inheritance

Generated data must never become more public than its supporting evidence unless explicitly sanitised and approved.

Example:

```text
Claim supported by:
PUBLIC source
PRIVATE document

Default claim visibility:
PRIVATE
```

A separate reviewed public claim may be created if appropriate.

---

# 62. API targets

Adapt to existing conventions.

Potential common endpoints:

```text
POST   /dossiers
GET    /dossiers/{id}
PATCH  /dossiers/{id}

POST   /dossiers/{id}/scan
GET    /dossiers/{id}/coverage
GET    /dossiers/{id}/timeline

GET    /dossiers/{id}/findings
POST   /findings/{id}/review

GET    /dossiers/{id}/claims
GET    /claims/{id}
GET    /claims/{id}/evidence

GET    /sources
GET    /sources/{id}/health

POST   /dossiers/{id}/ask

GET    /dossiers/{id}/audit

GET    /domains
GET    /domains/{domain}/templates
GET    /domains/{domain}/skills
GET    /domains/{domain}/source-packs
```

Do not duplicate existing equivalent endpoints.

---

# 63. Backend logical components

Map onto current codebase rather than mechanically creating microservices.

Logical responsibilities:

```text
Dossier Service
Domain Pack Registry
Source Registry
Ingestion / Fetch
Normalization
Evidence Store
Entity Resolution
Versioning
Change Detection
Claim Ledger
Finding Service
Review Service
Monitoring Scheduler
Coverage Service
Skill Registry
Tool Router
AI Gateway
Search / Retrieval
Notification Service
Audit Service
Access Control
Collaboration
```

These may remain modules within a smaller number of deployables.

---

# 64. Suggested domain pack interface

Conceptual pseudocode:

```text
DomainPack {
    id
    version
    contextSchema
    entityTypes
    claimTypes
    sourcePacks
    skills
    templates
    relevancePolicy
    reviewPolicy
    uiExtensions
}
```

Example:

```text
LegalPack implements DomainPack
PharmaPack implements DomainPack
```

Do not over-engineer plugin loading if a clean internal registry is enough.

---

# 65. Versioning and change control

Version:

- sources;
- documents;
- evidence extraction;
- claims;
- findings;
- skills;
- domain pack configuration;
- prompts;
- model/provider configuration;
- applicability metadata;
- monitoring rules.

The system should be able to answer:

> What did this dossier know on date X?

and:

> Which source/skill/model created this conclusion?

---

# 66. Validation and safety boundaries

Shared rule:

> Evidence and provenance first; decision remains with the user.

Do not claim:

- complete legal research;
- guaranteed regulatory coverage;
- compliance certification;
- legal advice as a substitute for professional responsibility;
- autonomous reimbursement decision;
- autonomous regulatory decision;
- deterministic future shortage prediction.

---

# 67. Observability

Track:

```text
scan duration
sources attempted
sources successful
source failures
documents fetched
documents changed
duplicates removed
findings generated
findings reviewed
claims accepted/rejected
AI calls by provider/model
AI latency
estimated AI cost
retrieval latency
notifications
```

Separate technical observability from user-facing Coverage.

---

# 68. Performance

Principles:

- incremental processing;
- deduplicate before AI;
- hash before semantic comparison;
- batch work where possible;
- do not rerun synthesis when evidence did not change;
- keep Dossier UI responsive while background jobs continue;
- cache stable source responses according to source rules.

---

# 69. Migration strategy

Existing Helvetic Lens functionality must remain operational.

If current code is Legal-oriented, do not throw it away.

Instead:

```text
existing Legal/general functionality
→ identify reusable Core
→ move domain assumptions behind LegalPack
→ preserve behaviour
→ add PharmaPack
```

Migration rules:

1. backward-compatible schema first;
2. migrate existing dossiers to domain=`LEGAL` or `GENERAL` where appropriate;
3. preserve old URLs/API contracts where practical;
4. avoid mandatory full migration in one deployment;
5. document breaking changes before applying them.

---

# 70. Repository audit deliverables

Before major refactor, Codex must create:

```text
/docs/architecture/current-state.md
/docs/architecture/target-architecture.md
/docs/architecture/core-gap-analysis.md
/docs/domains/legal-current-state.md
/docs/domains/pharma-implementation-plan.md
```

`current-state.md` must describe reality, not this specification.

`target-architecture.md` should map the codebase to the architecture defined here.

`core-gap-analysis.md` should classify each target capability:

```text
EXISTS
PARTIAL
TODO
BLOCKED
NOT_NEEDED
```

---

# 71. Implementation phases

## Phase 0 — Audit

No major refactor.

Identify:

- current Dossier model;
- evidence representation;
- sources;
- monitoring;
- snapshots;
- search;
- citations;
- auth;
- collaboration;
- AI providers;
- Apertus;
- domain-specific coupling.

---

## Phase 1 — Extract/strengthen Core

Create or formalize:

- Domain Pack Registry;
- Source Registry;
- Evidence/SourceVersion;
- Claim Ledger;
- Finding;
- Review;
- Coverage;
- Audit.

Do not duplicate existing models if they can be extended.

---

## Phase 2 — LegalPack

Move existing Legal-specific assumptions behind LegalPack where useful.

Add missing:

- applicability metadata;
- legal claim types;
- legal source authority classification;
- Legal skills;
- Legal templates.

Preserve current Legal behaviour.

---

## Phase 3 — Shared monitoring + coverage

Implement/standardize:

- source health;
- incremental scan lifecycle;
- visible incomplete coverage;
- change detection;
- source versioning.

Use for both Legal and Pharma.

---

## Phase 4 — Human review + Claim Ledger

Implement:

- Review Queue;
- finding decisions;
- claim creation;
- contradictions;
- supersession;
- provenance.

---

## Phase 5 — Shared Ask

Ground answers in:

```text
claims
→ evidence
→ source versions
```

Add domain-aware interpretation through the active Domain Pack.

---

## Phase 6 — Tool Router

Implement:

```text
deterministic
→ API/retrieval
→ lightweight tools
→ Laya/Jev where validated
→ Apertus
```

Expose actual processing path in provenance.

---

## Phase 7 — PharmaPack

Add:

- Pharma context schema;
- Pharma entity/claim types;
- initial source adapters/source pack;
- Pharma skills;
- Market Access template;
- Pharma UI labels/extensions.

---

## Phase 8 — First Pharma vertical slice

Demonstrate:

```text
Semaglutide — Switzerland
Market Access Dossier
```

with:

- creation;
- source pack;
- initial evidence;
- monitoring;
- coverage;
- change detection;
- finding;
- review;
- accepted claim;
- Ask with citations;
- source failure transparency.

---

# 72. Acceptance criteria — Core

## Dossier

- [ ] One common Dossier implementation supports Legal and Pharma.
- [ ] Domain behaviour is selected via domain pack/template, not copied services.
- [ ] Public/private/shared visibility works.

## Evidence

- [ ] Every finding can open supporting evidence.
- [ ] Every evidence item points to a source/version.
- [ ] Historical versions remain retrievable.

## Claims

- [ ] Claims are structured objects.
- [ ] Claims can have supporting and contradicting evidence.
- [ ] Claims can be superseded.
- [ ] Source facts and AI interpretation are distinguishable.

## Monitoring

- [ ] Scans are incremental.
- [ ] Duplicate evidence does not create duplicate findings.
- [ ] Failed sources remain visible.

## Coverage

- [ ] User can see what was checked.
- [ ] User can see last successful check per source.
- [ ] Incomplete coverage is explicit.

## AI

- [ ] Deterministic tasks do not call large LLMs.
- [ ] Provider/model/skill versions are logged.
- [ ] User-visible factual AI output is evidence-grounded.

## Human review

- [ ] Findings can be accepted/dismissed.
- [ ] Reviews are auditable.
- [ ] Accepted findings can create/update claims.

---

# 73. Acceptance criteria — Legal

- [ ] Existing Legal workflows still work.
- [ ] Legal sources can be represented through Source Registry.
- [ ] Legal version/effective-date metadata is preserved.
- [ ] Applicability can be attached to claims/evidence.
- [ ] Legal claim types distinguish rule/holding/fact/argument/analysis.
- [ ] Ask can show source authority and applicable version.
- [ ] Monitoring can detect a legal/source change.
- [ ] A historical legal claim can be superseded without deletion.

---

# 74. Acceptance criteria — Pharma

- [ ] Pharma uses the same Core Dossier implementation.
- [ ] A Market Access template can be created.
- [ ] Pharma source pack is configurable.
- [ ] Monitoring can detect a relevant public-source change.
- [ ] Coverage shows Pharma source health.
- [ ] Human review can accept a Pharma finding.
- [ ] Accepted finding creates/updates a Claim.
- [ ] Ask answers from dossier evidence with citations.
- [ ] Source failure prevents a misleading "complete" status.

---

# 75. Tests

Add unit/integration/e2e tests.

## Shared

```text
same content → no new version
changed content → new version
prior version retrievable
duplicate source → no duplicate finding
failed source → incomplete coverage
finding accepted → claim created/updated
finding dismissed → preserved in audit
contradicting evidence → conflict preserved
private evidence → no public leakage
deterministic task → no LLM call
provider failure → fallback/audit
```

## Legal

```text
law version changes
effective date changes
superseded rule
wrong jurisdiction rejected/flagged
primary vs secondary authority
court holding separate from AI interpretation
```

## Pharma

```text
product alias resolution
exact substance match
regulatory document update
reimbursement status update
source delay
duplicate clinical source
high-impact finding requires review
```

---

# 76. Example Legal user journey

```text
1. User creates:
   "Children playing in a residential courtyard — Basel"

2. LegalPack resolves:
   Switzerland
   Basel-Stadt
   tenancy / house rules context

3. Source pack proposes:
   federal law
   cantonal rules
   municipal rules if applicable
   relevant case law

4. Evidence is collected.

5. Applicability Engine maps:
   jurisdiction
   effective date
   authority level

6. Claims are created/proposed:
   statutory rules
   relevant holdings
   exceptions

7. User asks:
   "Can house rules prohibit this at 12:00 on Sunday?"

8. Answer:
   - separates law from interpretation;
   - cites sources;
   - shows applicable versions;
   - surfaces uncertainty/conflict.

9. Monitoring remains active.

10. If relevant law/guidance changes:
    new Finding → human review → claim updated.
```

---

# 77. Example Pharma user journey

```text
1. User creates:
   "Semaglutide — Switzerland"

2. Chooses:
   Market Access template

3. PharmaPack proposes:
   BAG/FOPH
   Spezialitätenliste
   Swissmedic
   EMA
   clinical sources

4. Initial evidence is collected.

5. Coverage shows:
   what was checked
   what failed
   when

6. A reimbursement/source document changes.

7. Change Detection creates a Finding.

8. System explains:
   what changed
   why it may matter
   exact evidence

9. Human accepts the Finding.

10. Claim Ledger updates.

11. User asks:
    "What changed in Switzerland this month?"

12. Answer is grounded in accepted claims/evidence.

13. Monitoring continues.
```

---

# 78. Explicit non-goals

Do not spend the first cycles on:

- separate Legal and Pharma codebases;
- five separate Pharma "lens" services;
- autonomous legal decisions;
- autonomous regulatory decisions;
- replacing SAP/Kinaxis/Veeva/Salesforce;
- building duplicate public-source databases;
- global coverage before one vertical slice works;
- graph database migration without need;
- complex multi-agent choreography for deterministic tasks;
- Laya/Jev integration purely for presentation;
- dashboards that do not improve the core questions.

---

# 79. Target product language

Avoid architecture/product language like:

> AI decides.

Prefer:

> Helvetic Lens detects, connects and explains evidence.

Avoid:

> Complete coverage.

Prefer:

> 16 of 17 configured sources successfully checked.

Avoid:

> This is the legal/regulatory answer.

Prefer:

> Based on the cited sources and their applicable versions, the dossier currently supports the following interpretation.

---

# 80. Target architecture principle

The centre of the platform is:

```text
                         HELVETIC LENS CORE
                                │
                    ┌───────────▼───────────┐
                    │     LIVING DOSSIER    │
                    │                       │
                    │  Evidence Graph       │
                    │  Claim Ledger         │
                    │  Timeline / History   │
                    └───────────┬───────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
       Sources                Skills              Monitoring
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                         Tool / AI Router
                                │
                  ┌─────────────┴─────────────┐
                  │                           │
              LEGAL PACK                 PHARMA PACK
                  │                           │
            Applicability                Domain logic
            Legal sources                Pharma sources
            Legal skills                 Pharma skills
            Legal templates              Pharma templates
```

Apertus, Laya, Jev, search engines, APIs and parsers are **tools around the dossier**.

They are not the product.

Legal and Pharma are **domain packs around the same Core**.

They are not separate architectures.

---

# 81. First Codex action

Before implementation, produce:

```text
/docs/architecture/current-state.md
/docs/architecture/target-architecture.md
/docs/architecture/core-gap-analysis.md
/docs/domains/legal-current-state.md
/docs/domains/pharma-implementation-plan.md
```

Then produce a concise implementation proposal answering:

1. Which existing modules already belong to Core?
2. Which current Legal assumptions are embedded in shared code?
3. What is the smallest safe way to introduce `DomainPack`?
4. Which existing database models can be extended instead of replaced?
5. Which existing UI components can remain shared?
6. What must be added for Legal Applicability?
7. What must be added for Pharma Market Access?
8. Which Laya/Jev integrations are actually useful after verifying real interfaces?
9. What is the smallest end-to-end vertical slice that proves both:
   - shared Core works for Legal;
   - Pharma can run on the same Core?

**Do not begin a large refactor until these documents are complete and the migration path is explicit.**
