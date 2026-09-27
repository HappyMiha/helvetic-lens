# Helvetic Lens — Dynamic Collaborative Dossier & Investigation Engine

## 1. Goal

Extend the existing Helvetic Lens dossier concept into a collaborative, continuously evolving research workspace.

A dossier must combine:

**knowledge + sources + investigation + collaboration + monitoring**

The system must remain extremely simple for the end user.

A user should NOT have to configure:

- agents;
- number of agents;
- skills;
- models;
- search engines;
- research pipelines;
- source types;
- research depth for every branch;
- workflows;
- investigation topology.

The user works with the dossier.

The system dynamically decides how the research should be performed.

The investigation may change while the dossier develops.

Example:

A dossier starts as:

> Investigate Company X.

During research Helvetic Lens discovers:

- a holding company;
- a court case;
- several directors;
- grants;
- patents;
- a pharmaceutical product.

The Investigation Engine must be able to dynamically create new research branches such as:

- ownership research;
- legal research;
- person research;
- financial research;
- patent research;
- pharmaceutical/regulatory research.

These branches must appear automatically without asking the user to configure the research engine.

---

## 2. Core product principle

Do NOT build a fixed multi-agent workflow.

There must NOT be a hard-coded architecture such as:

```text
Agent 1
Agent 2
Agent 3
Agent 4
Agent 5
Agent 6
Agent 7
```

Instead implement:

```text
Dossier
   ↓
Investigation Coordinator
   ↓
Dynamic Plan
   ↓
Capabilities / Skills / Sources
   ↓
Research Branches
   ↓
Evidence
   ↓
Claims / Entities / Relationships
   ↓
Dossier State
   ↓
Replanning
```

Agents are an implementation detail.

The stable architecture is:

```text
Investigation Coordinator
Skill Registry
Source Registry
Evidence Store
Claim Ledger
Entity Graph
Investigation State
Monitoring
Collaboration
Activity / Provenance Log
```

An investigation can use 1 capability or 20 capabilities depending on the task.

---

## 3. Dossier is the central object

Everything belongs to a Dossier.

Examples:

```text
George Soros / Open Society
Ozempic
Swiss AI regulation
Nestlé
Mads Mikkelsen
Ukraine reconstruction
A specific company
A specific law
A historical event
A scientific topic
```

Do not force every dossier into one predefined domain taxonomy.

The system can infer:

```text
person
company
organisation
law
drug
product
technology
event
scientific topic
political topic
mixed / unknown
```

but this classification must be dynamic and may change.

A dossier can contain many entity types simultaneously.

---

## 4. Dossier visibility

Implement two primary dossier visibility modes.

### PUBLIC DOSSIER

Readable without registration.

Requirements:

```text
anonymous user:
    read dossier
    read findings
    inspect sources
    inspect evidence
    inspect relationships
    inspect investigation progress
    inspect public contributions
```

Public dossiers must:

- have a stable public URL;
- have a human-readable slug;
- be accessible without authentication;
- be searchable inside Helvetic Lens;
- be indexable where appropriate;
- support shareable URLs to individual claims, sources and investigation findings.

Example:

```text
/dossier/open-society-switzerland
```

Registered users can additionally:

```text
comment
submit URL
upload file
suggest correction
add evidence
request additional investigation
start a research branch
participate in discussion
```

Do not treat user-submitted material as verified evidence automatically.

It enters the dossier as:

```text
Candidate Evidence
```

The Investigation Engine evaluates it.

### PRIVATE DOSSIER

Private dossiers use exactly the same research engine and UI.

Difference: access control.

Only invited members can access them.

Support at minimum:

```text
OWNER
EDITOR
CONTRIBUTOR
VIEWER
```

OWNER:
full control including members and dossier settings.

EDITOR:
edit dossier, research, claims, sources and investigations.

CONTRIBUTOR:
comment, upload files, add URLs, propose research and evidence.

VIEWER:
read only.

Anonymous users must never be able to discover or access private dossiers.

---

## 5. Keep the user experience simple

The primary dossier experience must NOT look like an AI control panel.

Do not expose:

```text
temperature
model selector
agent count
context size
tool selection
search engine selector
prompt editor
vector database options
```

Default interaction:

```text
Ask / Investigate
[________________________________]

[ Investigate ]
```

Examples:

> Who finances this organisation?

> Investigate ownership.

> Why did this law change?

> Check whether this claim is true.

> Research this person's career.

> Find possible connections between these organisations.

The Investigation Engine decides how to execute it.

Advanced technical details can exist in developer/admin diagnostics but must not dominate the normal product UI.

---

## 6. Dynamic Investigation Engine

Create an `InvestigationCoordinator`.

Its job is NOT to answer the question immediately.

It must first inspect:

```text
user request
current dossier state
existing entities
existing sources
existing claims
previous investigations
open questions
contradictions
monitoring observations
new contributions
```

It then creates an internal Investigation Plan.

Example internal representation:

```json
{
  "objective": "Understand financing of Organisation X",
  "branches": [
    {
      "goal": "Identify legal entities",
      "capabilities": [
        "registry_search",
        "entity_resolution"
      ]
    },
    {
      "goal": "Identify funding",
      "capabilities": [
        "financial_document_search",
        "money_extraction",
        "money_flow_analysis"
      ]
    }
  ],
  "open_questions": [],
  "stop_conditions": []
}
```

This structure is internal.

Do not require the user to create it.

---

## 7. Dynamic replanning

Investigation plans are NOT immutable.

The system must support:

```text
PLAN
 ↓
research
 ↓
new evidence
 ↓
new question
 ↓
REPLAN
 ↓
new branch
```

Example:

Initial investigation:

```text
Company A
 └─ ownership
```

Research discovers:

```text
Company A
 ↓
Luxembourg Holding B
 ↓
Person C
```

The system automatically adds:

```text
Branch:
Ultimate Beneficial Ownership
```

Later a court document is discovered.

Automatically add when relevant:

```text
Branch:
Legal Proceedings
```

The original plan must remain in history.

Store:

```text
plan version
reason for change
triggering evidence
timestamp
```

---

## 8. Skill Registry

Implement capabilities as reusable Skills.

Do not make them domain-specific agents.

Conceptual examples:

```text
search.web
search.news
search.registry
search.legal
search.scientific
search.clinical_trials
search.patents
search.financial_documents

extract.person
extract.organisation
extract.money
extract.date
extract.claim
extract.legal_provision
extract.citation

resolve.entity
resolve.company
resolve.person

analyse.timeline
analyse.money_flow
analyse.ownership
analyse.network
analyse.legal_change
analyse.scientific_evidence
analyse.career
analyse.conflict

verify.claim
verify.source
verify.contradiction

synthesize.summary
```

A skill may internally be implemented using:

- deterministic code;
- APIs;
- search;
- parser;
- scraper;
- database lookup;
- lightweight model;
- Apertus;
- another configured model.

The Investigation Coordinator should care about the **capability**, not the implementation.

---

## 9. Dynamic source selection

Do not maintain one universal list of sources used for every dossier.

Create a Source Registry and Source Resolver.

Source selection depends on:

```text
subject
entity type
country
jurisdiction
language
question
previous evidence
reliability requirements
```

Examples.

Pharmaceutical investigation may dynamically prioritize:

```text
Swissmedic
EMA
FDA
PubMed
ClinicalTrials.gov
scientific journals
manufacturer documentation
```

Swiss legal investigation may prioritize:

```text
Fedlex
Bundesgericht
parliamentary documents
cantonal sources
official government publications
```

Company investigation may prioritize:

```text
commercial registry
annual reports
audited reports
regulatory filings
company websites
court records
procurement
patents
```

Actor career investigation may prioritize completely different sources.

The user should not have to select any of them.

---

## 10. Evidence first

LLM output must not directly become dossier truth.

Implement the basic flow:

```text
SOURCE
  ↓
EXTRACTED EVIDENCE
  ↓
CLAIM
  ↓
VERIFICATION
  ↓
DOSSIER FINDING
```

Every important factual assertion should be traceable to its evidence.

---

## 11. Claim Ledger

Create a first-class `Claim` entity.

Example:

```text
Claim:
Foundation A gave Organisation B CHF 300,000 in 2025.
```

Store at minimum:

```text
id
dossier_id
statement
status
confidence
created_at
updated_at
created_by
investigation_id
```

Suggested statuses:

```text
UNVERIFIED
SUPPORTED
CONTESTED
HYPOTHESIS
DISPROVED
SUPERSEDED
```

Do not silently convert hypotheses into facts.

---

## 12. Evidence links

A Claim can have multiple evidence records.

Evidence relation must include:

```text
claim_id
source_id
relationship
excerpt/reference
page/section/location when available
created_at
```

Relationship:

```text
SUPPORTS
CONTRADICTS
CONTEXT
```

Example:

```text
CLAIM
Foundation X funded Organisation Y.

SUPPORTS
Annual report Foundation X, page 71

SUPPORTS
Organisation Y annual report, page 34

CONTRADICTS
Different amount in audited statement
```

The contradiction must remain visible.

Do not hide inconvenient evidence.

---

## 13. Sources

Create a unified Source entity.

Sources may originate from:

```text
web page
uploaded file
PDF
official document
news article
academic paper
registry record
user contribution
monitoring event
API response
```

Store useful provenance such as:

```text
URL
title
publisher
date
retrieved_at
content_hash
source_type
original contributor
language
metadata
```

Uploaded documents must preserve the original file.

---

## 14. Entity Graph

Create or extend a generic entity/relation graph.

Entity examples:

```text
PERSON
ORGANISATION
COMPANY
FOUNDATION
LAW
REGULATION
DRUG
PRODUCT
PATENT
COURT_CASE
EVENT
PROJECT
PUBLICATION
LOCATION
```

Do not make the schema depend exclusively on those values.

Relationships must be extensible.

Examples:

```text
FOUNDED
OWNS
CONTROLS
FUNDED
RECEIVED_GRANT
BOARD_MEMBER_OF
EMPLOYED_BY
ACTED_IN
DIRECTED_BY
SUBJECT_TO
AMENDS
CITES
PARTNER_OF
CONTRACTED_WITH
RELATED_TO
```

Every important relationship should be traceable to evidence.

---

## 15. Investigation branches

An Investigation can create child branches.

Example:

```text
Investigation:
Open Society Switzerland

├─ Organisation structure
├─ Funding
│  ├─ FOSI Switzerland
│  └─ Grant recipients
├─ People
└─ Legal entities
```

Branches can be created:

```text
by user
by Investigation Coordinator
by new evidence
by monitoring
by contradiction
by another branch
```

Store the reason why the branch exists.

Branches can finish independently.

---

## 16. Research can evolve continuously

A completed investigation does not freeze the dossier.

A dossier may receive:

```text
new source
new file
new comment
new user research request
monitoring update
new official document
changed webpage
new regulatory decision
```

Each event can be evaluated by the Investigation Coordinator.

If the event materially changes the dossier, the coordinator may:

```text
update existing Claim
create new Claim
create Entity
create Relationship
reopen Investigation
create new Investigation Branch
mark contradiction
change dossier summary
```

No user confirmation should be necessary for normal research evolution.

---

## 17. Monitoring integration

Investigation and monitoring must use the same evidence system.

Architecture:

```text
INVESTIGATION
     ↓
DOSSIER
     ↓
MONITORING
     ↓
NEW INFORMATION
     ↓
EVIDENCE
     ↓
CLAIM UPDATE
     ↓
OPTIONAL NEW INVESTIGATION
```

Example:

```text
Claim:
Company X has CEO Y.

Monitoring detects:
Company X announces CEO Z.

Result:

old Claim → SUPERSEDED
new Claim → SUPPORTED
timeline updated
dossier updated
```

Preserve history.

---

## 18. Collaboration

Add a contribution system linked to a dossier.

Registered users can contribute:

```text
COMMENT
URL
FILE
EVIDENCE
CORRECTION
RESEARCH_REQUEST
```

Example:

```text
User:
"This annual report may contain additional payments."

[file.pdf]
```

The file appears immediately as a contribution.

The system may automatically analyse it.

The contributor must be visible.

Machine-derived conclusions from the contribution must be distinguishable from what the user actually submitted.

---

## 19. Public collaboration without destroying trust

User contributions must never automatically become established facts.

UI states should make this obvious:

```text
USER SUBMISSION
UNDER REVIEW
EVIDENCE FOUND
VERIFIED
CONTESTED
```

This verification should normally be automatic.

Do not require an editor to manually approve every contribution before investigation starts.

Editors should retain the ability to:

```text
hide abuse
remove spam
correct metadata
merge duplicates
mark irrelevant content
```

---

## 20. Transparency UI

Dynamic research must be transparent to the user.

Do NOT expose internal chain-of-thought.

Instead expose observable research actions and provenance.

The user should be able to see something similar to:

```text
Research activity

14:21  Started investigation:
       "Who finances Organisation X?"

14:21  Searching organisation registry

14:22  Found legal entity:
       Organisation X AG

14:22  New research branch:
       Ownership

       Reason:
       Registry identifies Holding Y as shareholder.

14:23  Searching annual reports

14:24  Found possible payment:
       CHF 250,000

14:24  Claim created:
       "Foundation Z funded Organisation X"

       Status:
       Unverified

14:26  Second independent source found

14:26  Claim status:
       Supported
```

This is critical.

The system should feel autonomous but never mysterious.

---

## 21. Explain why

For important automatic actions provide a lightweight:

```text
Why?
```

Example:

> Why is Helvetic Lens researching Luxembourg Holding Y?

Answer:

> Company X's registry entry identifies Luxembourg Holding Y as a shareholder. The ownership chain is therefore incomplete.

This must come from stored provenance/state, not hallucinated after the fact.

---

## 22. Dossier UI

Keep the default page simple.

Suggested structure:

```text
┌─────────────────────────────────────┐
│ DOSSIER TITLE                       │
│ Public • Monitoring active          │
│                                     │
│ [ Ask / Investigate ]               │
├─────────────────────────────────────┤
│ WHAT DO WE KNOW?                    │
│ short living summary                │
├─────────────────────────────────────┤
│ KEY FINDINGS                        │
│ supported / uncertain / contested   │
├─────────────────────────────────────┤
│ CONNECTIONS                         │
│ graph / timeline / money flow       │
├─────────────────────────────────────┤
│ ACTIVE RESEARCH                     │
│ what is being investigated now      │
├─────────────────────────────────────┤
│ SOURCES & EVIDENCE                  │
├─────────────────────────────────────┤
│ COMMUNITY                           │
│ comments / files / URLs / requests  │
└─────────────────────────────────────┘
```

Avoid turning the main page into ten technical tabs.

Use expandable sections / drawers for detail.

---

## 23. Three core questions

Where appropriate preserve the Helvetic Lens UX concept:

```text
What did we find?

Why does it matter?

Why should I trust it?
```

`Why should I trust it?` should expose:

```text
sources
evidence
contradictions
source type
dates
provenance
```

---

## 24. Research activity must be live

When an investigation is running, users viewing the dossier should see progress without refreshing the page.

Use the existing project's infrastructure where possible.

Preferred implementation:

```text
WebSocket or Server-Sent Events
```

Events may include:

```text
investigation.started
branch.created
branch.completed
source.discovered
evidence.created
claim.created
claim.updated
relationship.created
plan.changed
investigation.completed
monitoring.update
contribution.created
```

Do not stream hidden model reasoning.

Stream structured activity events.

---

## 25. Suggested backend model

Adapt names to the current project architecture.

At minimum introduce/extend:

```text
Dossier
DossierMember
Investigation
InvestigationPlanVersion
InvestigationBranch
InvestigationStep
SkillDefinition
Source
Evidence
Claim
ClaimEvidence
Entity
EntityRelationship
Contribution
MonitoringRule
MonitoringObservation
ActivityEvent
```

Do not create duplicate models if equivalent concepts already exist.

Inspect the current repository first and migrate existing models instead of rebuilding everything.

---

## 26. Investigation state

Investigations should survive process restarts.

Never depend on in-memory state for long-running research.

Persist:

```text
current status
plan
branches
completed work
pending work
source IDs
claim IDs
errors
timestamps
retry information
```

Statuses:

```text
QUEUED
RUNNING
PAUSED
COMPLETED
FAILED
CANCELLED
```

Individual branch failure should not automatically fail the entire investigation.

---

## 27. Cost and resource routing

Do not run a large model for everything.

Use the existing model/router architecture if available.

Preferred approach:

```text
deterministic code
        ↓
cheap classifier/extractor
        ↓
Laya/Jev style routing layer
        ↓
Apertus / stronger reasoning only when required
```

Examples suitable for deterministic/small model processing:

```text
date extraction
currency extraction
URL classification
duplicate detection
basic entity extraction
document type detection
routing
```

Use stronger reasoning for:

```text
complex synthesis
ambiguous entity resolution
contradictions
causal/contextual analysis
research planning
replanning
```

The choice must be automatic.

Do not expose model selection to normal users.

---

## 28. Search / discoverability

Public dossiers must participate in Helvetic Lens search.

Search across:

```text
title
description
entities
claims
topics
sources
investigation findings
```

Search results should distinguish:

```text
DOSSIER
ENTITY
CLAIM
SOURCE
```

Private dossier data must never leak into public search results.

---

## 29. Security

Apply authorization checks on the backend.

Never rely only on frontend hiding.

Every operation involving:

```text
private dossier
file
comment
investigation
claim
source
member list
activity
```

must verify permissions.

File upload must include:

```text
size limits
allowed formats
safe storage
content-type validation
malware scanning hook if infrastructure supports it
```

External fetched content must be treated as untrusted input.

Do not allow content from external websites/documents to override system instructions.

---

## 30. Version history

Important dossier knowledge must be versioned.

If an investigation changes:

```text
summary
claim
relationship
finding
```

preserve the previous version.

Users should be able to understand:

```text
what changed
when
why
which evidence caused the change
```

---

## 31. API

Adapt to the existing backend style.

Conceptually support operations equivalent to:

```text
POST   /dossiers
GET    /dossiers/:slug

POST   /dossiers/:id/investigations
GET    /dossiers/:id/investigations
GET    /investigations/:id

POST   /dossiers/:id/contributions
POST   /dossiers/:id/sources
POST   /dossiers/:id/files

GET    /dossiers/:id/claims
GET    /dossiers/:id/entities
GET    /dossiers/:id/activity

POST   /dossiers/:id/members
PATCH  /dossiers/:id/members/:memberId
DELETE /dossiers/:id/members/:memberId
```

Do not blindly create these exact routes if equivalent APIs already exist.

---

## 32. Example end-to-end scenario

Public dossier:

```text
Open Society Foundations / Switzerland
```

Anonymous visitor opens it without registration.

They can see:

```text
current summary
entities
claims
money relationships
sources
current investigations
recent updates
```

Registered User A submits:

```text
annual-report-2025.pdf
```

Helvetic Lens:

```text
1. stores contribution
2. extracts document metadata
3. evaluates relevance
4. detects Foundation X
5. detects CHF 420,000 payment
6. links existing entities if possible
7. creates candidate evidence
8. checks whether an existing claim is affected
9. creates a new investigation branch if necessary
10. searches for independent confirmation
11. updates claim status
12. adds activity entries
13. updates dossier summary when materially relevant
```

No agent configuration.

No source configuration.

No confirmation dialog asking:

> Should I research Foundation X?

The system does it automatically when relevant.

The activity feed makes the decision transparent.

---

## 33. Another end-to-end scenario

Dossier:

```text
Actor X
```

User asks:

> Investigate the development of his career.

Coordinator may dynamically use:

```text
filmography
awards
timeline
interviews
collaborations
critical reception
```

During research a major legal dispute becomes relevant.

The coordinator may create:

```text
Legal history branch
```

and activate legal research capabilities.

No actor-specific hard-coded workflow should be necessary.

---

## 34. Definition of Done

The feature is complete when the following scenario works end to end:

```text
1. Create PUBLIC dossier.
2. Anonymous visitor can read it.
3. Registered user can add URL/file/comment/research request.
4. User can enter one natural-language investigation question.
5. Investigation Coordinator automatically creates research plan.
6. Coordinator dynamically chooses capabilities/sources.
7. Investigation creates evidence, claims, entities and relationships.
8. Investigation can create a new branch because of newly discovered evidence.
9. Investigation plan can change while running.
10. User can see why the new branch was created.
11. Claims show supporting/contradicting evidence.
12. Research activity updates live.
13. New monitoring information can reopen/update research.
14. Historical claim versions remain accessible.
15. Create PRIVATE dossier.
16. Anonymous and unauthorized users cannot discover/read it.
17. Invited VIEWER can read it.
18. CONTRIBUTOR can add material.
19. EDITOR can modify dossier/research.
20. Public and private dossiers use the same investigation engine.
```

---

## 35. Tests

Add automated tests for at least:

```text
public anonymous access
private access rejection
member roles
file/source contribution
investigation creation
branch creation
dynamic replanning
claim/evidence linking
contradicting evidence
plan history
activity events
monitoring → investigation trigger
public search visibility
private search isolation
```

Also add one integration test demonstrating an investigation that changes its plan after discovering a new entity.

---

## 36. Implementation strategy

Before coding:

Inspect the current Helvetic Lens repository.

Identify and reuse:

```text
existing Dossier model
authentication
permissions
database
background jobs
monitoring
search
model routing
Apertus integration
Laya/Jev integration if already present
frontend components
WebSocket/SSE infrastructure
file storage
```

Do NOT replace working infrastructure without a strong reason.

Implement the feature incrementally but keep the architecture compatible with the complete design.

Prefer extending existing concepts over creating parallel systems.

---

## 37. Important product constraint

The final product must not feel like:

> Configure an AI research workflow.

It must feel like:

> Open a dossier and investigate something.

The complexity belongs under the hood.

The intelligence of Helvetic Lens is that the system can decide:

```text
what to investigate
what is missing
where to search
which capability to use
when to create a new research branch
when existing evidence is insufficient
when evidence conflicts
when an old conclusion must change
```

while always showing the user enough provenance to understand **what happened and why**.

---

## 38. Desired product loop

The finished architecture should support this continuous loop:

```text
                 ┌───────────────┐
                 │    DOSSIER    │
                 └───────┬───────┘
                         │
                  Ask / Investigate
                         │
                         ▼
                Dynamic Investigation
                         │
             ┌───────────┴───────────┐
             │                       │
         Evidence                New questions
             │                       │
             ▼                       │
        Claims + Graph               │
             │                       │
             └───────────┬───────────┘
                         ▼
                    Living Dossier
                         │
                         ▼
                     Monitoring
                         │
                    new evidence
                         │
                         └──────────────► Replan
```

The Dossier is never merely a generated report.

It is a **living shared knowledge object** that can be researched, challenged, expanded, monitored and continuously improved by both humans and Helvetic Lens.
