# Codex Task — Helvetic Lens Visual Language Refresh

## Goal

Оновити візуальну мову Helvetic Lens.

Новий інтерфейс має виглядати не як типовий glassmorphism dashboard, а як сучасний серйозний intelligence/research portal:

- світлий або майже чорний фон;
- дуже сильна typography;
- великі data blocks;
- мінімум декоративних рамок;
- glass використовується вибірково;
- sidebar може бути glass/translucent;
- universal Ask / Search має бути floating;
- фірмовий Lens / refraction effect використовується тільки тоді, коли система реально аналізує, порівнює або інтерпретує джерело.

Ключова ідея:

> Glass is not decoration. Glass represents the Lens.

---

# 1. General design direction

Не робити весь портал glassmorphism.

Основний UI повинен бути clean, calm, information-first.

Приблизна пропорція:

- 80% — clean Swiss-style information interface;
- 20% — Lens / glass / refraction visual language.

Пріоритет:

1. інформація;
2. readability;
3. hierarchy;
4. provenance / sources;
5. interaction;
6. visual effects.

Не навпаки.

---

# 2. Background

Підтримати два режими:

## Light

Основний фон:

- off-white;
- very light neutral grey;
- не pure white всюди.

Приклад напрямку:

```css
--background: #F6F6F3;
--surface: #FFFFFF;
--surface-secondary: #EFEFED;
--text-primary: #111111;
--text-secondary: #666666;
```

## Dark

Не використовувати pure black `#000`.

Напрямок:

```css
--background: #0B0C0E;
--surface: #111316;
--surface-secondary: #181A1E;
--text-primary: #F4F4F2;
--text-secondary: #9B9DA2;
```

Dark mode має виглядати як intelligence workspace, а не gaming UI.

Без:

- neon glow everywhere;
- RGB gradients;
- sci-fi dashboard styling.

---

# 3. Typography

Typography повинна стати одним із головних елементів дизайну.

Використовувати сильну hierarchy.

Наприклад:

```text
Page title
42–56 px

Section heading
24–32 px

Large metric / key fact
36–64 px

Body
15–17 px

Metadata / source information
12–14 px
```

Не боятися великих заголовків і великих чисел.

Приклад:

```text
EU Artificial Intelligence Act

27
relevant regulatory changes

4
require immediate review
```

Це краще, ніж показувати 27 маленьких однакових cards.

---

# 4. Layout philosophy

Зменшити кількість:

- borders;
- cards;
- nested cards;
- boxes inside boxes;
- visible containers.

Використовувати:

- whitespace;
- typography;
- grouping;
- alignment;
- subtle surface contrast.

Правило:

> Якщо UI block можна відокремити spacing і typography — не додавати border.

---

# 5. Large Data Blocks

Ключові дані показувати великими information blocks.

Наприклад:

```text
REGULATORY IMPACT

High

This change affects:
Medical AI
Decision Support
Clinical Documentation
```

або:

```text
12
new sources

3
contradictions detected

87%
evidence coverage
```

Не перетворювати кожен показник на окрему dashboard card.

---

# 6. Glass Sidebar

Sidebar може використовувати glass material.

Це одна з головних зон, де glass дозволений постійно.

Characteristics:

- translucent;
- subtle backdrop blur;
- very subtle border;
- minimal shadow;
- background адаптується до light/dark theme.

Приклад:

```css
backdrop-filter: blur(18px) saturate(120%);
background: rgba(...);
border: 1px solid rgba(...);
```

Але sidebar не повинен виглядати як стара macOS-style glass panel.

Glass має бути дуже стриманим.

---

# 7. Floating Universal Ask / Search

Зробити один universal interaction point.

Він повинен замінити розділені:

- search;
- ask AI;
- command palette;
- research query.

Приклад:

```text
┌──────────────────────────────────────────────┐
│ 🔍 Ask Helvetic Lens or search anything…   │
└──────────────────────────────────────────────┘
```

Можливі запити:

```text
Search for “FINMA”
```

```text
What changed in this dossier?
```

```text
Compare these two sources
```

```text
Find contradictions
```

```text
Show primary sources only
```

```text
What supports this claim?
```

Command bar має бути:

- floating;
- доступний з будь-якого екрану;
- keyboard-first;
- `Cmd/Ctrl + K`;
- visually prominent, але не intrusive.

---

# 8. Lens Effect

Це головна фірмова feature дизайну.

Lens/refraction effect НЕ використовується постійно.

Він з'являється тільки коли Helvetic Lens виконує intelligence action.

Наприклад:

- source analysis;
- fact extraction;
- comparison;
- contradiction detection;
- claim verification;
- provenance tracing;
- dossier synthesis;
- impact analysis.

---

# 9. Lens analysis state

Коли користувач запускає analysis, UI повинен візуально показати:

> Helvetic Lens is looking through the source.

Приклад flow:

```text
SOURCE
↓
Lens activation
↓
Extraction
↓
Cross-reference
↓
Evidence
↓
Result
```

Візуально це може бути:

- локальний refractive surface;
- optical distortion;
- glass lens moving над document/source area;
- subtle chromatic separation;
- refraction of underlying text;
- animated focal point.

Не використовувати сильний rainbow/chromatic aberration.

Effect має бути:

- sophisticated;
- subtle;
- slow;
- intentional.

---

# 10. Lens must communicate system state

Lens effect має мати semantic meaning.

Наприклад:

### Idle

Lens відсутній.

### Reading source

Subtle circular refraction рухається по source.

### Extracting facts

Lens фокусується на relevant sections.

### Cross-checking

Візуально з'єднуються два або більше джерел.

### Contradiction detected

Lens розділяється / refracts into two directions.

### Evidence confirmed

Lens стабілізується.

### Analysis complete

Glass/refraction animation плавно зникає.

Таким чином користувач розуміє не тільки:

> AI is working.

А:

> що саме система зараз робить.

---

# 11. Sources UI

Sources — first-class object.

Джерела не повинні виглядати як маленький список URL.

Приклад:

```text
SOURCE

European Commission
Artificial Intelligence Act

Primary source
Published 12 Sep 2026

Relevant sections
Article 9
Article 14
Article 26

Used in
3 findings
2 claims
1 contradiction
```

Користувач повинен легко бачити:

- хто джерело;
- primary чи secondary;
- дату;
- що саме з нього використано;
- в яких conclusions воно використано.

---

# 12. Dossier UI

Dossier не повинен виглядати як dashboard із десятками widgets.

Основний dossier layout:

```text
DOSSIER TITLE

Short current summary


KEY QUESTIONS

1. What happened?
2. Who is affected?
3. What evidence supports this?


KEY FINDINGS

large readable blocks


TIMELINE


CLAIMS & EVIDENCE


SOURCES


OPEN QUESTIONS
```

При scroll користувач має відчувати document/research experience, а не BI dashboard.

---

# 13. Cards

Cards використовувати тільки якщо вони реально представляють окремий object.

Наприклад:

- Source
- Person
- Organisation
- Claim
- Event
- Evidence item

Не використовувати card для кожного paragraph або KPI.

Card styling:

- minimal border;
- subtle background difference;
- large internal spacing;
- strong title;
- clear metadata.

---

# 14. Motion

Motion використовувати тільки для:

- state changes;
- Lens analysis;
- opening source context;
- switching dossier sections;
- command/search;
- provenance tracing.

Не додавати hover animation лише тому, що можна.

Duration приблизно:

```text
micro interaction:
120–180 ms

panel transition:
180–280 ms

Lens analysis:
400–1200 ms
```

Lens може мати довші fluid transitions.

---

# 15. Interaction principle

Користувач не повинен конфігурувати AI pipeline.

UI показує:

- що система робить;
- які джерела використовує;
- які tools/skills були задіяні;
- як отримано результат.

Але не вимагає вручну налаштовувати це перед кожним research request.

Default:

```text
User asks
↓
Helvetic Lens determines required actions
↓
System visibly shows the process
↓
User may inspect details
```

Progressive disclosure.

---

# 16. Transparency layer

Для кожного AI result додати можливість відкрити:

```text
How was this produced?
```

Всередині:

```text
Sources used: 7
Primary sources: 4
Secondary sources: 3

Actions:
Search
Source retrieval
Entity extraction
Cross-reference
Contradiction check
Synthesis
```

Optional detailed mode:

```text
Models / tools / skills
```

Але ці технічні деталі не повинні домінувати у default UI.

---

# 17. Components to create/refactor

Створити reusable components:

```text
AppShell
GlassSidebar
TopNavigation

UniversalAskSearch
CommandPalette

LargeMetric
DataBlock
InsightBlock

SourceCard
SourcePreview
SourceMetadata

ClaimBlock
EvidenceBlock
ContradictionBlock

LensOverlay
LensAnalysisState
LensProgress
LensConnection

DossierHeader
DossierSection
DossierTimeline

TransparencyPanel
AnalysisDetails
```

---

# 18. Design tokens

Не hardcode styles у компонентах.

Створити tokens для:

```text
background
surface
surfaceRaised
textPrimary
textSecondary

glassBackground
glassBorder
glassBlur

lensRefractionStrength
lensDistortion
lensChromaticOffset

borderRadiusSmall
borderRadiusMedium
borderRadiusLarge

spacing
typography

motionFast
motionNormal
motionLens
```

---

# 19. Accessibility

Обов'язково:

- readable contrast;
- keyboard navigation;
- focus states;
- reduced motion;
- Lens effect не повинен бути потрібним для розуміння інформації.

Якщо:

```css
prefers-reduced-motion: reduce
```

Lens animation перетворити на static/subtle highlight state.

---

# 20. Responsive behaviour

Desktop — primary intelligence workspace.

Tablet — sidebar collapses.

Mobile:

```text
Sidebar
→ bottom navigation / drawer

Ask/Search
→ persistent floating control

Large metrics
→ stacked

Source analysis
→ full-screen source view
```

Не намагатися просто стиснути desktop dashboard до 390 px.

---

# 21. Important anti-goals

НЕ робити:

- glass на кожній картці;
- gradients everywhere;
- neon AI visuals;
- purple/blue generic AI branding;
- infinite shadows;
- dashboard із 20 маленьких cards;
- багато borders;
- decorative charts without purpose;
- sci-fi HUD;
- excessive animations;
- old-style frosted glass UI.

Helvetic Lens має виглядати як:

```text
serious research product
+
modern intelligence interface
+
Swiss clarity
+
a unique Lens visual language
```

а не як:

```text
generic AI SaaS dashboard.
```

---

# 22. Implementation approach

Не переписувати весь application stack.

Спочатку:

1. inspect current frontend architecture;
2. identify global layout;
3. identify current theme/tokens;
4. identify reusable UI components;
5. create new design foundation;
6. migrate existing pages incrementally.

Порядок:

```text
Phase 1
Design tokens + typography

Phase 2
App shell + sidebar + navigation

Phase 3
Universal Ask/Search

Phase 4
Core data blocks

Phase 5
Dossier layout

Phase 6
Source UI

Phase 7
Lens animation/state system

Phase 8
Transparency / “How was this produced?”

Phase 9
Responsive + accessibility polishing
```

---

# 23. Lens architecture

Lens повинна бути окремою reusable system, а не animation захардкодженою на одній сторінці.

API component/state приблизно:

```ts
type LensState =
  | "idle"
  | "reading"
  | "extracting"
  | "cross-referencing"
  | "verifying"
  | "contradiction"
  | "synthesizing"
  | "complete";
```

UI:

```tsx
<LensOverlay
  state="cross-referencing"
  target={sourceId}
/>
```

Або через centralized research activity state.

Lens effect має бути прив'язаний до реальної application state.

Не запускати fake animation без relation до backend/research process.

---

# 24. First implementation target

Першим proof-of-concept зробити одну повноцінну сторінку Dossier.

Вона повинна показати одночасно:

- new typography;
- new page layout;
- glass sidebar;
- floating Ask/Search;
- large data blocks;
- sources;
- claims/evidence;
- Lens analysis state;
- transparency panel.

Ця сторінка стане reference implementation для решти Helvetic Lens.

---

# 25. Acceptance criteria

Робота завершена, якщо:

- портал більше не виглядає як generic glass dashboard;
- інформаційна hierarchy зрозуміла за 2–3 секунди;
- sidebar має subtle glass material;
- Ask/Search доступний глобально;
- Lens effect з'являється тільки під час intelligence/research actions;
- Lens animation відображає реальний system state;
- sources і evidence є prominently visible;
- UI однаково добре працює у light та dark mode;
- немає excessive cards/borders;
- components reusable;
- styling базується на design tokens;
- responsive layout працює;
- reduced-motion підтримується;
- existing functionality не повинна бути зламана.

---

# Final principle

Кожного разу перед додаванням UI effect ставити питання:

> Does this help the user understand the information or what Helvetic Lens is doing?

Якщо ні — effect не потрібен.

Lens має стати не просто логотипом або animation.

Lens — це візуальна мова моменту, коли Helvetic Lens перетворює джерело на знання.
