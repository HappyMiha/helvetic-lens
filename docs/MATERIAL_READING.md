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

HL-096 remains in progress. Legal-unit headings where authoritative labels exist,
full visual-token/density consolidation, richer concise deltas, all representative
feed/assistant layouts, complete zoom/real-browser coverage and observed user
reading comfort require further work. This slice does not rewrite legacy extraction,
assert useful AI reasoning, or finish the product design audit.
