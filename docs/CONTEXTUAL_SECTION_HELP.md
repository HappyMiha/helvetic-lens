# Contextual section help — English first

Each of the 30 application page routes has an inline orientation and a **Page
guide** button. The guide is available without a model and even when the page's
data endpoint fails. The existing authentication gate still applies. Dynamic
document, evidence and comparison routes have their own instructions; unknown
routes do not silently receive Today's instructions.

## Using the guide

- **Start here:** purpose and a short sequence leading to a useful first action.
- **Controls:** searchable explanations of related buttons and fields, their
  consequences, prerequisites and availability in the current view.
- **Data & text:** where the content comes from, distinguishing saved source
  text, user input, deterministic results and separate model outputs.
- **Wait or set up:** background progress, missing prerequisites, configuration
  and the difference between waiting, an empty scope and an error.

**Show me** closes the guide, scrolls to a rendered control, focuses it and briefly
outlines it. It never clicks, submits, enables or navigates through that control.
Missing, disabled or stale targets remain explained without pretending they are
usable. Related controls are grouped: Show me locates the first matching visible
example, rather than claiming to identify every repeated row button. Opening a
collapsed editor or changing a role may expose additional controls; reopen the
guide or use **Check visible controls again**. Search uses English guide text.

F1 opens the guide when another dialog is not active. Escape closes it and returns
focus to its trigger; Show me returns focus to the indicated control. Radix handles
modal focus containment and keyboard tab navigation. On mobile the guide fills
the viewport above navigation/Marvin. Its chapter scrolls independently so the
close control and chapter selector remain accessible.

## Content and scope

The orientation and portalled dialog declare `lang="en"`. Only this feature is
English first, as requested; existing interface translations are retained. Exact
English label matching may not locate controls in another UI language. Stable
selectors still work, and missing-location messages say so explicitly.

The catalogue covers Today, Monitoring, Discover, Topics, Sources, Impact inbox,
Topic match review, Impact matrix, Digests, Organization, Settings, Prompts, Logs,
Administration, Connectors, Models, Deployment history, Relation reprocessing,
monitored documents, saved/native comparisons, both evidence viewers, Assistant
history, Getting started, Basel-Stadt, document operations, Login and Unsubscribe.
Shared explanations cover workspace/navigation/language, notifications, Marvin,
context attachment and handing a draft to cited Ask.

Organization-management and platform permissions are independent. Guide control
lists follow those permissions; restricted sections explain the required role.
The guide cannot grant access. Existing page actions retain their own guards.

Instructions are reviewed static product copy in `apps/web/lib/section-guides.ts`.
They do not report live readiness, collect document contents, persist help usage,
send analytics or call AI. The locator reads control labels, not entered values.
Normal application behavior remains: for example, the unsubscribe route already
submits its URL token on entry, and the assistant can initialize a conversation.
The no-write guarantee applies to help interactions, not every existing page.

## Design rationale

The chosen pattern combines contextual orientation with help on demand, without
requiring a blocking first-run tour. It follows the principles of contextual
onboarding and progressive disclosure described by
[Nielsen Norman Group](https://www.nngroup.com/articles/onboarding-tutorials/).
Its explanations distinguish state and provide task directions, informed by
[NN/g's empty-state guidance](https://www.nngroup.com/articles/empty-state-interface-design/).
The modal follows the
[W3C APG dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/):
initial focus on the heading for structured content, focus containment, Escape
and return focus. The information does not depend on hover-only tooltips.

## Maintenance and verification

Update the catalogue when an action, prerequisite, source or permission changes.
Use stable selectors or reviewed exact accessible labels. Never infer behavior
from an arbitrary button caption. Unit tests discover real `app/**/page.tsx`
routes and fail when a new page lacks a guide or leaves an orphan guide behind.
The localization checker has one explicit file exception for this requested
English-only component; the remaining interface retains its existing gate.

```sh
npm run check:help
npm run build
npm run check:help:browser
npm run check:basel:browser
```

Browser checks use the actual production build, an isolated Chrome profile and
synthetic API responses. They cover 30 routes and all four chapters; 390/1440 px;
viewer/organization-admin and platform access; English inside a localized UI;
F1/Escape, focus containment/return; disabled and vanished targets; safe source
button highlighting; search; and preservation of a login form draft. The eight
full-document axe checkpoints retain incomplete findings in
`test-results/accessibility/section-help.json`; passing automation is not a
complete accessibility certification.

These checks establish software behavior, not independent user comprehension.
The unassisted first-material study and participating-organization pilot gates in
HL-073/HL-090/HL-101 remain open. No production release is implied by a local build.
