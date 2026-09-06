# Material change reading (HL-096)

Material-first comparison renders five saved change groups at a time, instead of
mounting the entire material list. The page picker reaches every page directly;
previous/next navigation focuses a reading heading below sticky navigation.
Counts explicitly distinguish matching groups from all saved groups. Search scans
the complete saved before/after wording of every group's changes, not only the
visible excerpts. It is normalized literal text matching, not an AI interpretation
or semantic search. Clearing search returns to the first overview.

Each group shows separately labelled before/after excerpts from its first exact
change. They are explicitly labelled excerpts, not generated summaries. Substantive,
structural, formatting and uncertain classifications remain the saved values;
an ambiguous group retains its review warning. Technical unit/group IDs move into
an optional disclosure. Users open the existing complete deterministic diff from
the group or choose another exact change within it. Citation/Ask evidence jumps
continue to reveal and focus the matching row in the full exact-change pager.
Older comparisons without group metadata also keep exact-row pagination beyond
the first 40 material rows. Returning to Material first preserves its search and page; another comparison ID
resets the local reading position. Nothing is saved to legal evidence or AI history.

Text uses semantic card/foreground tokens and 1rem body copy with 1.65 line height;
the before/after grid stacks on narrow screens. Reading controls target at least
44px and wrap long labels. Pagination/search happens in place without another API
request, inference or full page reload. The full comparison is still fetched and
indexed in browser memory: this is a DOM/card rendering limit, not a bounded
network-payload or target-host capacity guarantee. An unusually large group can
still have many exact-change selector options. Search/filter state is local to the
open comparison, not persisted across devices.

Reproduce: `npm run build`, `node scripts/check-comparison-browser.mjs`, and
`npm run check:ai:contrast`. The mandatory synthetic fixture has 200 groups; the
browser checks all 40 pages with no duplicates, a match only in the final group and its second exact change,
empty/clear search, exact-evidence focus and return, 44px controls, localization,
320px reflow with doubled root text size, and existing comparison overlay/citation
journeys. This is Chromium emulation, not a physical-device or screen-reader sign-off.

HL-096 remains in progress. Independent verification of extracted legal-unit labels,
full visual-token/density consolidation, richer concise deltas, all representative
feed/assistant layouts, complete zoom/real-browser coverage and observed user
reading comfort require further work. This slice does not rewrite legacy extraction,
assert useful AI reasoning, or finish the product design audit.


## Saved legal-unit headings (6 September 2026)

Group headings now use the existing saved `diff.legal_units` projection. A unit
must be listed by the group on the correct before/after side and its passage ID
must belong to an exact change on that side. Recognized title/chapter/section/
article/paragraph/letter/number labels come from the saved hierarchy. Anonymous
`passage:87` positions and opaque IDs never become legal article numbers. Missing,
unattached, malformed or unrecognized labels retain the neutral group heading.

Article ancestry and subdivisions are preferred to a long full hierarchy. Repeated
continuations are deduplicated; if the same short article label belongs to different
saved chapter paths, those ancestors remain visible to distinguish them. Different
before/after labels are shown separately with an arrow, preserving renumbering.
Three distinct labels per side are shown with an explicit additional count; search
still covers every saved label, including labels beyond that preview. Labels are
localized in all five UI languages while the saved number is preserved.

The interface explicitly identifies these as extraction labels and links to the
exact evidence. It does not claim independently verified official headings, parse
new document content, rewrite stored diffs, invoke AI or repair historical noise.
The helper tests cover ancestry, absent labels, wrong-side attachment, renumbering,
deduplication, multi-chapter ambiguity, preview limits and malformed input. The
200-group browser fixture checks localized before/after headings and search by
the displayed article label while preserving exact citations, paging and reflow.


## Focused saved-word excerpts (6 September 2026)

Material cards now center their short before/after preview on the first changed
fragment of the first exact change, instead of taking the start of the article.
The existing saved word-diff parts must reconstruct each saved passage exactly
and have aligned equal runs. No second diff or model call is performed. Added words
use insertion markup and removed words use deletion markup, so color alone is not
the indicator. If parts are absent, inconsistent or unchanged, a labelled plain
saved-text excerpt replaces highlighting; the full exact evidence stays available.

Each side contains up to 64 preceding, 120 changed and 64 following Unicode code
points. Explicit ellipses mark skipped text and a notice explains the limit. The
caption counts changed fragments in this first exact change, not the whole group.
Other group changes remain accessible in the exact-change selector. This is neither
an AI summary nor a claim that the first fragment is the most important change.
Source wording, full-text search, stored evidence and report history are unchanged.

Eight helper tests cover late deadlines, insertion/deletion, one-sided passages,
multiple fragments, invalid saved alignment, unchanged/missing data, Unicode bounds
and immutable input. The populated browser fixture requires a 10-to-30-day change
after 900+ unchanged characters to appear as actual del/ins text in all five locales
and all three compact widths. Existing paging, exact evidence, desktop transitions
and text reflow checks remain mandatory. Broader legal significance, extraction
quality, native-language review and actual reading comfort still need independent
verification; HL-096 remains in progress.
