# Public research acceptance — 1 October 2026

**Live answer quality: NOT ACCEPTED.** Controlled worker tests and shipped features
are separate from this judgment. Three neutral questions were selected before the
trials, with independent primary-source expectations. Actual configured Apertus
70B, Jev/Laya and SearXNG/source readers ran in isolated local databases. No model
answers, network responses or conclusions were substituted with fixtures.

## Independent expectations

- Mountain ambiguity: distinguish elevation above sea level, base-to-peak height
  and distance from Earth's centre; do not describe different metrics as factual
  contradiction. Sources: [NOAA highest point](https://oceanservice.noaa.gov/facts/highestpoint.html)
  and [NOAA geoid](https://oceanservice.noaa.gov/facts/geoid.html).
- Sea level: distinguish a long-term rate from a single year's rise, convert
  units explicitly and avoid equating a global mean with a local coast. Sources:
  [NASA altimetry](https://science.nasa.gov/earth/earth-observatory/taking-a-measure-of-sea-level-rise-ocean-altimetry-147435/),
  [NASA 2024 rise](https://sealevel.nasa.gov/news/282/nasa-analysis-shows-unexpected-amount-of-sea-level-rise-in-2024/)
  and [local sea level](https://sealevel.nasa.gov/sea-level-101/local-sea-level-change/the-basics/).
- Definition of the second: distinguish the 1956/1960 astronomical decisions from
  the 1967 atomic definition and later publication dates. Sources:
  [CIPM 1956](https://www.bipm.org/en/committees/ci/cipm/46-1956/resolution-1),
  [CGPM 1960](https://www.bipm.org/en/committees/cg/cgpm/11-1960/resolution-9),
  [CGPM 1967](https://www.bipm.org/en/committees/cg/cgpm/13-1967/resolution-1).
  This source-guided case included the 1960 URL; other cases were unseeded.

## Observed outcomes

| Trial | Initial wall time | Captured portions | Retained claims at final observation | Accepted final answer |
| --- | ---: | ---: | ---: | --- |
| Mountain 1 | 629 s | 15 | 0 | No |
| Mountain 2 | 320 s | 6 | 0 | No |
| Mountain 3 and recovery | 569 s initial; 430 s and 620 s recovery | 8 | 5 | No |
| Sea level | 252 s | 6 | 0 | No |
| Second definition | 508 s | 6 | 0 | No |

Runs span intermediate repair revisions; they are diagnostic evidence, not a
benchmark pass for the exact release revision. Captured portions are not counts
of independent sources. NOAA's relevant original was fully captured; NASA
homepages were largely irrelevant to the numerical question. BIPM originals were
not successfully captured in the second-definition trial, despite discovery.

Failures included invalid/truncated JSON, paraphrased quotations, unsupported
optional metadata, misplaced locators and model 429/timeout responses. One
response introduced an unsupported numerical difference despite citing an exact
source passage; new directly supported claims and observations now reject numbers
absent from their quotations. This conservative check is not a general arithmetic,
unit-conversion or factual-correctness proof. AI source-role classifications remain
proposals; a quoted byline does not prove that an article is primary evidence.

Repairs retain exact-cited siblings, expose rejected proposals as interpretation
gaps, preserve complete-document requirements, prioritize submitted source URLs
and retry final synthesis only after source work. Five claims survived the last
mountain recovery; the run still did not complete a validated final dossier.
Remaining live blockers are provider availability, strict final/whole-document
output reliability and discovery relevance. No successful live answer or full
product readiness is claimed.

Actual token counters are retained when providers return them; billing cost is
unknown, never reported as zero. Detailed counts and local evidence paths are in
the parent `product-completion-public-evaluation.json` and completion checkpoint.
No production dossier or fixture email was created. No further live retry loop is
started merely to turn these failures into a passing report.
