# Helvetic Lens Brandbook v1.0

**Version:** 1.0  
**Date:** September 2026  
**Core line:** **See. Understand. Go further.**

## 1. Brand essence

Helvetic Lens turns fragmented sources into a transparent, navigable understanding of a subject.

### Principles
- **Clarity before decoration.** Every visual effect must improve orientation or understanding.
- **Evidence before assertion.** Show where information comes from and what remains uncertain.
- **Depth on demand.** Simple first view; detail appears when the user asks for it.
- **Swiss precision, human tone.** Disciplined hierarchy without bureaucratic coldness.
- **Technology reveals itself when useful.** AI is visible through its contribution, not generic sci-fi styling.

## 2. Visual language: the Lens

The Lens/refraction effect is a **functional visual signal**, not decoration.

Use it when Helvetic Lens is:
- analyzing a source;
- cross-checking claims;
- comparing evidence;
- tracing provenance;
- surfacing contradictions;
- synthesizing evidence.

Do **not** use refraction on ordinary navigation, every card, every button, or as a permanent animated background.

## 3. Logo system

Primary lockup: geometric **H** monogram + **Helvetic Lens** wordmark.

- White/frost on dark backgrounds.
- Obsidian on light backgrounds.
- Minimum wordmark size: **120 px digital / 32 mm print**.
- Minimum monogram size: **24 px digital / 7 mm print**.
- Keep clear space around the mark equal to at least the H crossbar height.
- No bevel, glow, gradients inside the wordmark, distortion or stretching.

## 4. Color system

### Core colors
| Token | Hex | Use |
|---|---|---|
| Carbon | `#090B0E` | Deep background |
| Obsidian | `#111418` | Primary surface |
| Slate | `#343A44` | Structure / borders |
| Graphite | `#55575C` | Secondary UI |
| Steel | `#768798` | Metadata / cool accent |
| Frost | `#E6E3E1` | Primary text |
| Signal Red | `#E63B32` | Critical states / restrained Swiss cue |

### Refraction-only colors
- Cyan `#72E0FF`
- Violet `#8C7BFF`
- Amber `#FFD27A`
- Coral `#FF8B7A`

These colors should appear as optical events, short spectral lines, edge refraction or analysis transitions - not as large rainbow backgrounds.

## 5. Typography

Preferred family: **Inter / Inter Display** in product implementation. If unavailable, use a modern neutral grotesk with comparable metrics.

Suggested scale:
- Display: **48/52**
- H1: **36/42**
- H2: **26/32**
- Body: **16/26**
- Label: **11/16**, uppercase allowed with tracking

Rules:
- Strong typography should carry most of the visual identity.
- Keep headlines short.
- Body copy stays sentence case.
- Avoid ultra-light long-form copy.
- Avoid using more than three font weights in one view.

## 6. Layout

- Desktop grid: **12 columns**.
- Maximum content width: **1440 px**.
- Gutters: **24-32 px**.
- Primary radius: **20-28 px**.
- Preferred text measure: **60-75 characters**.
- Use large data blocks and generous negative space.
- Borders separate function; they should not frame every element.

## 7. Glass material

Glass is structural, not wallpaper.

Use it for:
- sidebar/navigation layer;
- command surfaces;
- source inspection;
- transient overlays;
- focused contextual panels.

Baseline:
- white fill: roughly **4-9%**;
- border: roughly **16-34%**;
- blur: **24-36 px**;
- soft edge reflections;
- restrained shadows.

Avoid milky panels, neon borders, large drop shadows and glass cards nested inside glass cards.

## 8. Refraction states

1. **Analyzing a source** - narrow spectral sweep travels across the active source surface.
2. **Comparing evidence** - two light paths converge toward a shared focal point.
3. **Contradiction found** - subtle split/refraction exposes competing claim paths.
4. **Synthesis ready** - refraction resolves into a clean stable highlight.

## 9. Product UI

The product shell should remain calm around the evidence.

- Near-black canvas.
- One persistent glass sidebar.
- Large typography and data blocks.
- Minimal framing.
- Floating universal **Ask / Search** entry point.
- Lens/refraction appears locally around the active source, claim or synthesis event.
- Relevant settings remain available from the product UI; users should not need hidden configuration.

## 10. Evidence language

Do not collapse uncertainty into a single magic truth score.

Prefer:
- “3 independent sources support this claim.”
- “2 sources disagree on the date.”
- “We could not verify this from a primary source.”

Avoid:
- “AI says this is true.”
- “Truth score: 87%.”
- Absolute labels without visible evidence.

Useful evidence states:
- Verified source
- Claim
- Contradiction
- Unverified
- Primary document

## 11. Motion

- Hover/focus: **150-220 ms**.
- Panel reveal: **280-360 ms**.
- Lens analysis sweep: **450-700 ms**.
- Lens sweep should normally happen once, not loop indefinitely.
- Prefer progress and source activity over generic spinning AI particles.
- Respect `prefers-reduced-motion`; preserve state without animation.

## 12. Imagery / 3D direction

Use:
- alpine or architectural geometry;
- optical glass and lens materials;
- dark water, steel and reflective physical surfaces;
- macro detail;
- real working environments;
- real documentary source material;
- low-key light with cool ambient tones and restrained warm reflections.

Avoid:
- stock “AI brains”;
- neon circuit boards;
- anonymous robots;
- cyberpunk dashboards;
- saturated blue-gradient AI clichés.

## 13. Tone of voice

Helvetic Lens should sound like a capable research partner.

**Do:** state evidence first, use plain verbs, name uncertainty, separate fact from interpretation, make next actions obvious.

**Do not:** write “revolutionary AI”, anthropomorphize the model, hide caveats, use legalistic filler, or overpromise certainty.

## 14. System states

Even failure states must belong to the brand.

### Maintenance
> Temporarily unavailable. We’re improving the experience. Please check back soon.

### No evidence yet
> No reliable source has been added yet.

Always pair empty/error states with one clear next action where possible.

## 15. Core guardrails

### Do
- Let typography lead.
- Use glass only for functional layers.
- Reserve spectrum for analysis.
- Show sources and uncertainty.
- Keep dark space generous.

### Don’t
- Turn every panel into frosted glass.
- Use rainbow gradients as backgrounds.
- Add neon glows to normal controls.
- Create decorative AI particles.
- Score truth with one magic number.

## 16. Frontend tokens

```css
:root {
  --hl-bg: #090B0E;
  --hl-surface: #111418;
  --hl-slate: #343A44;
  --hl-text: #E6E3E1;
  --hl-muted: #A7ADB5;
  --hl-steel: #768798;
  --hl-signal: #E63B32;

  --hl-glass-fill: rgba(255,255,255,.055);
  --hl-glass-border: rgba(230,227,225,.24);
  --hl-radius: 24px;
  --hl-blur: 30px;
  --hl-ease: cubic-bezier(.2,.8,.2,1);
  --hl-lens-duration: 560ms;
}
```

## Brand system in one sentence

**Calm interface. Visible evidence. Refraction when perspective changes.**

Helvetic Lens should look intelligent because it makes complexity legible - not because it looks futuristic.
