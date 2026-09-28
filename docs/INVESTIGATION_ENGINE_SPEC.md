# Helvetic Lens — Investigation Engine

## Task

Implement a real **Research / Investigation Engine** for Helvetic Lens dossiers.

The current dossier monitoring flow is useful for detecting source updates, but it is not sufficient for deep research.

The new engine must allow a user to create a dossier with a simple research question such as:

> Investigate the funding network around George Soros and related foundations, organisations, intermediaries and grant recipients.

The user must NOT be required to manually define:

- search queries
- sources
- agents
- investigation branches
- entity lists
- research steps
- evidence categories
- monitoring rules

Helvetic Lens must dynamically plan, execute, expand and verify the investigation.

---

# Product goal

A Dossier must support two related but separate modes:

```text
DOSSIER
  |
  +-- Monitoring
  |     "What changed?"
  |
  +-- Research / Investigation
        "What is actually going on?"
```

Monitoring continuously watches known topics and sources.

Research actively investigates a question, follows discovered entities and relationships, checks evidence, identifies missing information, creates new research branches and produces a traceable synthesis.

The two modes must share evidence and entities, but they must NOT be implemented as the same pipeline.

---

# Core principle

Do not implement Research as:

```text
question
→ generate keywords
→ search
→ summarize results
```

That is not sufficient.

Implement it as an iterative investigation loop:

```text
Research question
      ↓
Research plan
      ↓
Parallel investigation branches
      ↓
Search / retrieval
      ↓
Candidate relevance gate
      ↓
Evidence extraction
      ↓
Entity resolution
      ↓
Claims + relationships
      ↓
Evidence verification
      ↓
Gap / contradiction detection
      ↓
Generate follow-up questions
      ↓
New investigation branches
      ↺
```

The result of one step must be able to create new research work.

---

# Example acceptance scenario

User creates a dossier:

```text
Title:
Funding network around George Soros

Research question:
Investigate organisations, foundations, intermediaries,
grant recipients, funding flows and documented relationships
connected to George Soros and Open Society structures.
```

The system should autonomously identify research dimensions such as:

```text
- persons
- foundations
- legal entities
- subsidiaries
- affiliated organisations
- grant-making entities
- grant recipients
- intermediary organisations
- projects
- jurisdictions
- amounts
- funding periods
- stated purposes
- annual reports
- financial disclosures
- public registries
- government records
- grant databases
- recipient disclosures
- documented relationships
- contradictions
- missing evidence
```

The user should not need to configure these manually.

---

# High-level architecture

```text
                     DOSSIER
                        |
              +---------+---------+
              |                   |
         MONITORING           INVESTIGATION
              |                   |
        Source watchers       Research Planner
              |                   |
      candidate retrieval     Research Branches
              |                   |
       Jev / Laya gate        Search / Retrieval
              |                   |
          source events       Jev / Laya gate
                                  |
                          Evidence Extraction
                                  |
                           Entity Resolution
                                  |
                          Claim / Edge Builder
                                  |
                          Evidence Verification
                                  |
                     Gap / Contradiction Detector
                                  |
                         Follow-up Generator
                                  |
                                  +----> new branches
                                  |
                           Apertus synthesis
```

Reuse existing Helvetic Lens components where possible.

Do NOT create a completely separate AI stack.

---

# 1. Research mode

Add an explicit dossier capability:

```text
Research
```

A dossier may have:

```text
monitoringEnabled: true | false
researchEnabled: true | false
```

Both can be active at the same time.

Research is an active investigation process.

Monitoring is a continuous change-detection process.

---

# 2. Simple user input

The minimum user input should be:

```text
Title
Research question
```

Optional:

```text
Focus
Jurisdiction
Time range
Languages
Known entities
Excluded topics
```

These are optional constraints, not mandatory setup.

Do not force users through a configuration wizard.

---

# 3. Research Planner

Implement a Research Planner.

Input:

```ts
{
  dossier,
  researchQuestion,
  existingEntities,
  existingClaims,
  existingEvidence,
  priorResearchState
}
```

Output conceptually:

```ts
type ResearchPlan = {
  objective: string;
  subQuestions: ResearchQuestion[];
  branches: ResearchBranch[];
  initialEntityHypotheses: EntityHypothesis[];
  preferredSourceTypes: SourceType[];
  completionCriteria: CompletionCriteria[];
}
```

The planner must decompose the research question into useful independent branches.

Example:

```text
Main question:
How does the funding network operate?

Branches:

1. Identify relevant organisations
2. Identify legal entities
3. Identify grant-making entities
4. Identify recipients
5. Trace grants and amounts
6. Identify intermediaries
7. Verify disclosed relationships
8. Find primary financial records
9. Check conflicting claims
10. Identify unexplained gaps
```

Do not hard-code this specific Soros structure.

The planner must work generically for:

- legal research
- pharma research
- corporate research
- public policy research
- funding networks
- people / organisation relationships
- regulatory dossiers
- technology investigations

---

# 4. Research Branch

A branch is a persistent unit of investigation.

Example:

```ts
type ResearchBranch = {
  id: string;
  dossierId: string;

  question: string;
  purpose: string;

  status:
    | "planned"
    | "searching"
    | "evaluating"
    | "waiting"
    | "complete"
    | "blocked";

  parentBranchId?: string;

  relatedEntityIds: string[];
  relatedClaimIds: string[];

  priority: number;

  createdBy:
    | "planner"
    | "follow_up"
    | "user"
    | "contradiction"
    | "evidence_gap";

  completionReason?: string;
}
```

A branch may generate child branches.

---

# 5. Iterative investigation loop

Each active branch should execute approximately:

```text
branch question
     ↓
query planning
     ↓
source discovery
     ↓
candidate retrieval
     ↓
relevance gate
     ↓
source reading
     ↓
fact / entity / relationship extraction
     ↓
claim generation
     ↓
evidence attachment
     ↓
verification
     ↓
gap detection
     ↓
follow-up questions
```

Do not stop after the first useful source.

---

# 6. Dynamic follow-up generation

This is a critical requirement.

Research results must create new research questions.

Example:

The engine finds:

```text
Foundation A
  funded
Organisation B
```

The system should be able to automatically create follow-up questions such as:

```text
Who legally controls Foundation A?

What primary source proves the funding relationship?

How much was transferred?

In which years?

What was the stated purpose?

Does Organisation B disclose the same grant?

Was the transfer direct?

Were intermediary entities involved?

Are the reported amounts consistent across sources?

Are there additional grants from A to B?

Does B fund other organisations connected to the dossier?
```

These follow-ups become new branches when useful.

Avoid endless recursive expansion.

Use branch priority, duplication detection and completion criteria.

---

# 7. Search strategy

Research search must not depend only on generated keywords.

Support query generation based on:

```text
research question
entities
aliases
relationships
jurisdictions
source types
known claims
missing evidence
contradictions
```

Example entity:

```text
Open Society Foundations
```

Possible search variants may include:

```text
official name
historical names
local legal entities
abbreviations
translated names
known subsidiaries
grant databases
annual reports
registry records
recipient disclosures
```

Query generation must remain dynamic.

---

# 8. Source strategy

The engine should intentionally search different evidence classes.

Examples:

```text
official organisation pages
annual reports
audited financial statements
government registers
commercial registers
tax / charity records where public
official grant databases
parliamentary documents
regulatory documents
court documents
recipient disclosures
academic publications
reputable investigative journalism
reputable news reporting
public archives
```

The system must distinguish source types.

Do not treat all web pages as equal evidence.

---

# 9. Source hierarchy

Add or reuse evidence quality metadata.

Conceptually:

```ts
type SourceQuality = {
  sourceClass:
    | "primary"
    | "official_secondary"
    | "independent_secondary"
    | "commentary"
    | "unknown";

  authorityScore?: number;
  directnessScore?: number;
  freshnessScore?: number;
}
```

This is not a truth score.

It describes characteristics of the source.

Claims must remain connected to the actual evidence.

---

# 10. Jev / Laya role

Reuse the already integrated Jev and Laya components.

They should be used for inexpensive tasks where appropriate, including:

```text
candidate relevance
document classification
domain classification
entity extraction support
relationship candidate extraction
routing
duplicate detection
simple confidence estimation
deciding whether deeper analysis is needed
```

The exact division between Jev and Laya should follow the existing project architecture.

Do not duplicate existing functionality.

---

# 11. Candidate relevance gate

Every discovered source is only a candidate.

Search retrieval does NOT create evidence automatically.

Flow:

```text
search result
    ↓
candidate
    ↓
Jev / Laya relevance evaluation
    ↓
relevant / uncertain / unrelated
```

Only relevant material should enter normal research evidence.

Uncertain material may be escalated.

Unrelated material is discarded but may retain a lightweight debug trace.

---

# 12. Apertus role

Apertus should be used selectively.

Good use cases:

```text
complex document analysis
cross-source synthesis
contradiction analysis
multi-hop reasoning
research-plan refinement
complex follow-up generation
final dossier synthesis
```

Do not call Apertus for every search result.

Desired principle:

```text
cheap operations first
→ Jev / Laya
→ deterministic processing
→ Apertus only when useful
```

---

# 13. Entity model

Research must build a persistent entity graph.

Minimum useful entity classes:

```text
Person
Organisation
Foundation
Company
Government body
Project
Program
Grant
Legal entity
Publication
Law / regulation
Location
Event
```

Keep the model extensible.

Example:

```ts
type Entity = {
  id: string;
  type: string;

  canonicalName: string;
  aliases: string[];

  jurisdiction?: string;
  identifiers?: Record<string, string>;

  sourceIds: string[];
}
```

---

# 14. Entity resolution

Do not create a new entity only because a source uses a different spelling.

Implement entity resolution using:

```text
canonical name
aliases
legal identifiers
domains
addresses
jurisdiction
known relationships
context
```

Example:

```text
Open Society Foundations
OSF
Open Society Institute
local legal entities
```

must not be blindly merged.

The engine must distinguish:

```text
alias
historical name
parent organisation
subsidiary
separate legal entity
possibly same entity
```

Preserve uncertainty.

---

# 15. Relationship graph

Create explicit typed relationships.

Examples:

```text
FOUNDED
CONTROLS
DIRECTOR_OF
FUNDED
GRANT_TO
OWNS
SUBSIDIARY_OF
AFFILIATED_WITH
PARTNER_OF
RECEIVED_GRANT
OPERATES_PROJECT
REGISTERED_IN
MENTIONED_IN
```

Each relationship must be evidence-backed.

Conceptual model:

```ts
type Relationship = {
  id: string;

  fromEntityId: string;
  toEntityId: string;

  type: string;

  claimId: string;

  confidence: number;
  status:
    | "supported"
    | "disputed"
    | "uncertain";

  sourceIds: string[];
}
```

---

# 16. Claim Ledger

This is a core requirement.

Helvetic Lens must not store only generated summaries.

Store atomic research claims.

Example:

```text
CLAIM

Organisation A provided funding to Organisation B.

STATUS

Supported

PERIOD

2024

AMOUNT

CHF 250,000

EVIDENCE

Source 1 — donor annual report
Source 2 — recipient annual report

CONTRADICTIONS

None detected

LAST VERIFIED

2026-09-28
```

Conceptual data model:

```ts
type Claim = {
  id: string;
  dossierId: string;

  statement: string;

  subjectEntityIds: string[];
  objectEntityIds: string[];

  claimType?: string;

  status:
    | "supported"
    | "partially_supported"
    | "uncertain"
    | "disputed"
    | "rejected";

  confidence: number;

  sourceIds: string[];
  contradictingSourceIds: string[];

  amount?: MoneyValue;
  period?: DateRange;

  firstSeenAt: Date;
  lastVerifiedAt: Date;
}
```

Do not expose hidden chain-of-thought.

Store concise evidence-based explanations only.

---

# 17. Evidence object

A source document and evidence extracted from it are not the same thing.

Support evidence references.

Example:

```ts
type Evidence = {
  id: string;

  sourceId: string;

  location?: {
    page?: number;
    section?: string;
    paragraph?: string;
  };

  excerpt?: string;

  supportsClaimIds: string[];
  contradictsClaimIds: string[];

  extractionMethod?: string;
}
```

Claims should point to precise evidence when possible.

---

# 18. Contradiction detection

The engine must detect conflicting evidence.

Example:

```text
Source A:
Grant amount = CHF 500,000

Source B:
Grant amount = CHF 300,000
```

Do not silently choose one.

Create:

```text
CONTRADICTION
```

and a new research branch:

```text
Resolve conflicting reported grant amounts.
```

Possible output:

```text
Claim status: disputed
```

until resolved.

---

# 19. Evidence gap detection

For each important claim, identify missing evidence.

Examples:

```text
relationship mentioned but no primary source
amount missing
date missing
recipient disclosure missing
legal identity unresolved
ownership unclear
source only repeats another publication
```

An evidence gap may create a new research branch.

Example:

```text
Need primary evidence for A → B funding relationship.
```

---

# 20. Research completion

Research should not mean:

```text
no more search results
```

Use completion criteria.

Possible branch completion conditions:

```text
main factual question answered
primary evidence found
important contradictions resolved
no high-priority evidence gaps remain
new searches produce only duplicates
branch confidence stabilised
search budget reached
```

Some branches may remain:

```text
blocked
unresolved
```

That is acceptable and must be visible.

Do not fabricate closure.

---

# 21. Prevent uncontrolled research loops

Add guardrails for automatic branch expansion.

At minimum:

```text
duplicate question detection
duplicate entity detection
branch depth limit
research budget
per-branch query budget
low-value branch pruning
priority threshold
stagnation detection
```

Do not use a single tiny hard-coded depth limit that makes research shallow.

The limits should be configurable.

---

# 22. Research state

The investigation must be resumable.

Persist:

```text
research plan
active branches
completed branches
blocked branches
queries executed
sources inspected
rejected candidates
entities
relationships
claims
evidence
contradictions
evidence gaps
follow-up questions
research budget usage
```

A research run must not start from zero after a restart.

---

# 23. Incremental research

The user should be able to:

```text
Start research
Pause
Resume
Continue deeper
Ask a follow-up
Add a source
Add an entity
Change focus
```

New research should reuse existing dossier knowledge.

Do not recompute everything unnecessarily.

---

# 24. Monitoring integration

When Research discovers important entities, the system may propose or automatically create appropriate monitoring subjects according to existing product behaviour.

Example:

Research discovers:

```text
Foundation A
Organisation B
Programme C
```

Monitoring can subsequently watch:

```text
new reports
new grants
new filings
regulatory changes
new public documents
```

But Research and Monitoring remain separate execution modes.

---

# 25. Research-to-monitoring lifecycle

Target lifecycle:

```text
Question
   ↓
Investigation
   ↓
Entities + claims + evidence
   ↓
Initial synthesis
   ↓
Continuous monitoring
   ↓
New source discovered
   ↓
Claims re-evaluated
   ↓
Dossier updated
```

This makes a dossier a living research object rather than a static AI response.

---

# 26. UI — Dossier Research view

Keep the UI simple.

The default user view should NOT expose internal agent complexity.

Suggested main structure:

```text
Research question

Status
Researching / Complete / Needs evidence

Key findings

Evidence graph

Claims

Open questions

Latest research activity
```

---

# 27. Research status

Example:

```text
Research status

27 entities found
41 claims
63 evidence items
6 active research branches
3 unresolved questions
2 contradictions
```

Keep these counts meaningful and clickable.

---

# 28. Investigation map

Provide a visual research map.

Example:

```text
                     Person
                        |
                     founded
                        |
                  Foundation A
                    /        \
                funds        controls
                  /              \
        Organisation B       Entity C
              |
           funds
              |
          Project D
```

Clicking an edge must show:

```text
claim
supporting evidence
sources
status
confidence
contradictions
```

Never show a relationship as fact without an evidence path.

---

# 29. Activity trace

Expose a compact transparent processing trace.

Example:

```text
Research branch:
Find grant recipients of Foundation A

Search
✓ 14 candidates

Laya
✓ 9 unrelated removed

Jev
✓ 5 documents classified

Evidence extraction
✓ 3 useful records

Entity resolution
✓ 2 existing entities
✓ 1 new organisation

Claims
✓ 4 added

New follow-up
→ Verify recipient disclosure
```

Do not expose private chain-of-thought.

The trace shows actions and outcomes only.

---

# 30. Key Findings

Key findings must be generated from Claim Ledger, not directly from raw model output.

Each finding should link to supporting claims and sources.

Example:

```text
Foundation A reported grants to Organisation B
between 2022 and 2024.

[3 claims] [5 sources]
```

The user must be able to inspect the evidence.

---

# 31. Open Questions

Show unresolved research explicitly.

Example:

```text
Open questions

- Legal relationship between Foundation A and Entity C is unresolved.
- 2023 grant amount differs between donor and recipient reports.
- No primary record found for claimed funding to Organisation D.
```

This is better than pretending the dossier is complete.

---

# 32. User intervention

A registered user should be able to add:

```text
source
file
URL
comment
research question
entity
correction
```

User-provided material enters the same evidence pipeline.

Do not automatically treat user input as verified truth.

---

# 33. Provenance

Every important object must retain provenance.

For:

```text
entity
relationship
claim
finding
```

the user should be able to see:

```text
which source
which evidence
when extracted
which engine/process created it
when last verified
```

---

# 34. Research run model

Add a persistent Research Run concept if one does not exist.

Example:

```ts
type ResearchRun = {
  id: string;
  dossierId: string;

  status:
    | "queued"
    | "running"
    | "paused"
    | "complete"
    | "failed";

  objective: string;

  startedAt?: Date;
  completedAt?: Date;

  branchIds: string[];

  budget?: ResearchBudget;
}
```

Multiple runs may contribute to the same dossier.

---

# 35. Cost / resource control

Research must support budgets.

Examples:

```text
max search requests
max documents fetched
max expensive model calls
max research duration
max branch count
```

Use inexpensive processing first.

Do not silently burn Apertus resources.

---

# 36. Failure behaviour

A failed source or model call should not destroy the research run.

Support:

```text
retry
partial branch failure
branch blocked
resume
```

Example:

```text
Registry unavailable
→ branch marked waiting / blocked
→ other branches continue
```

---

# 37. Deduplication

Deduplicate:

```text
URLs
documents
mirrors
entities
claims
research questions
relationship candidates
```

Do not let syndicated articles create five independent pieces of evidence for the same source claim.

---

# 38. Search result independence

Do not count five pages repeating the same original report as five independent confirmations.

Track source dependency when detectable.

Example:

```text
Article B cites Report A
Article C cites Article B

Underlying evidence:
Report A
```

This should not appear as three independent primary confirmations.

---

# 39. Temporal awareness

Relationships and claims may change over time.

Support:

```text
valid from
valid until
reported at
observed at
```

Example:

```text
Person X was director of Organisation Y from 2018–2022
```

Do not collapse all historical relationships into the present.

---

# 40. Research language

Research should work across languages.

A dossier may discover:

```text
English
German
French
Italian
Ukrainian
other supported languages
```

Entity resolution should preserve original names and aliases.

Do not translate legal entity names destructively.

---

# 41. Neutral evidence handling

For politically sensitive, legal or controversial research, the system should separate:

```text
documented fact
source claim
allegation
analysis
inference
unresolved question
```

Do not convert allegations into facts.

Claims must reflect the strength and nature of their sources.

---

# 42. First implementation scope

Do NOT attempt to implement every possible investigative feature in one giant rewrite.

Implement the vertical slice required to prove the engine works end-to-end:

```text
1. Research question
2. Research Planner
3. Branch creation
4. Search
5. Jev/Laya relevance gate
6. Evidence extraction
7. Entity resolution
8. Claim creation
9. Relationship creation
10. Gap/follow-up generation
11. Iterative second research cycle
12. Dossier UI
13. Persisted research state
```

The critical acceptance condition is that the engine performs at least one genuine follow-up cycle based on newly discovered evidence.

---

# 43. End-to-end acceptance test

Create a test dossier:

```text
Research question:

Investigate the funding network around a selected foundation,
including related organisations, grant recipients, intermediaries,
amounts, periods and documentary evidence.
```

Expected behaviour:

```text
1. Planner decomposes the question.

2. Multiple research branches are created.

3. Search discovers candidate sources.

4. Irrelevant sources are filtered by Jev/Laya.

5. Relevant documents are processed.

6. Entities are created/resolved.

7. Evidence-backed claims are created.

8. Relationships are added to the graph.

9. The engine notices at least one missing piece of evidence
   or unresolved relationship.

10. A follow-up research question is generated automatically.

11. A new branch executes that follow-up.

12. New evidence updates or strengthens an existing claim.

13. The dossier displays:
    - findings
    - entities
    - evidence
    - claims
    - graph
    - open questions
    - research activity
```

A one-pass search + summary does NOT pass this test.

---

# 44. Specific regression: weak keyword research

Do not allow this:

```text
Research topic:
Swiss cantonal health regulation

Document:
Vaud motorway deforestation

Match:
"canton"

→ evidence
```

Expected:

```text
candidate discovered
→ Jev/Laya relevance check
→ unrelated
→ rejected
```

Research and monitoring should use the same relevance principle.

---

# 45. Comparative quality test

Add an internal evaluation scenario where the initial question has multi-hop relationships.

The resulting research should be checked for:

```text
coverage
source diversity
primary-source usage
entity resolution
relationship traceability
follow-up depth
contradiction handling
evidence gaps
citation/provenance completeness
```

Do not implement a fake numeric "truth score".

Use concrete quality signals.

---

# 46. Do NOT implement

Do not solve this task by:

```text
adding more keywords
adding a giant static prompt
calling Apertus on every page
creating 20 fixed agents
hard-coding Soros-specific logic
hard-coding health-specific logic
hard-coding legal-specific logic
forcing users to configure all sources
showing generated relationships without evidence
generating a single large summary and calling it research
```

---

# 47. Required code investigation before implementation

Before changing architecture, inspect the existing repository and report:

```text
current dossier data model
current monitoring pipeline
current search adapters
current Jev integration
current Laya integration
current Apertus routing
current source/evidence model
current entity model if present
current job/worker architecture
current UI dossier components
```

Reuse existing code where sensible.

Do not create duplicate systems under new names.

---

# 48. Migration strategy

Prefer additive evolution.

Existing dossiers must continue to work.

If schema changes are necessary:

```text
make migrations backwards-compatible
preserve existing monitoring events
do not delete source history
do not reinterpret old evidence silently
```

---

# 49. Observability

Add structured telemetry for research execution.

Useful events:

```text
research_run_started
research_plan_created
research_branch_created
search_started
search_completed
candidate_rejected
candidate_accepted
entity_created
entity_resolved
claim_created
claim_updated
contradiction_detected
evidence_gap_created
follow_up_created
branch_completed
research_run_completed
```

Do not log sensitive source contents unnecessarily.

---

# 50. Debug view

Provide an internal/debug view of a branch:

```text
Question

Queries generated

Candidates
- accepted
- rejected
- uncertain

Jev/Laya routing

Documents processed

Entities extracted

Claims created

Follow-ups generated

Reason branch was completed / blocked
```

This will be critical for tuning the system.

---

# 51. Definition of Done

The task is complete when Helvetic Lens can take a simple research question and autonomously perform a multi-step investigation where:

```text
a discovery creates a new question,
the new question creates another search,
the search produces new evidence,
the evidence updates the dossier,
and every important finding is traceable to evidence.
```

The user should be able to understand:

```text
what was found
why it matters
which evidence supports it
what remains uncertain
what Helvetic Lens investigated next
```

without manually designing the research workflow.

---

# Final implementation report

After implementation, provide:

1. Existing architecture discovered.
2. Components reused.
3. New components added.
4. Database/schema changes.
5. Actual Jev role.
6. Actual Laya role.
7. Actual Apertus role.
8. Research execution flow.
9. Follow-up generation logic.
10. Loop/duplication safeguards.
11. UI changes.
12. Tests added.
13. End-to-end test result.
14. Known limitations.
15. Next recommended iteration.

Do not only state that the feature is implemented.

Show the exact execution path of one real research run.
