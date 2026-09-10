# Helvetic Lens Monitoring v2 — єдиний беклог розробки

**Версія плану:** 1.0 · **Дата:** 10 вересня 2026 · **Baseline коду:** `7109a2891f9c99e53572008cc7c1a86001792a57`

**Статус:** план реалізації; жодна нова можливість v2 не оголошена реалізованою.

**Обсяг:** 10 обов’язкових сценаріїв, 61 обов’язкова задача, 7 відкладених задач.

**Принцип:** authoritative source → material change → personal relevance → evidence → user decision.

## Як користуватися цим беклогом

Це **єдине джерело поточного обсягу, пріоритетів, залежностей і приймання розробки Helvetic Lens**. Кореневий [BACKLOG.md](BACKLOG.md) веде сюди. [Попередній беклог](BACKLOG_V1_ARCHIVE.md) збережений як історія, а не паралельна черга. Уже зроблене з нього перевикористовуємо; 35 незавершених пунктів мають явних наступників у [legacy disposition](docs/monitoring-v2/LEGACY_DISPOSITION.md). Їхні невиконані детальні критерії успадковуються відповідальними задачами v2, а не зникають через короткий переказ.

Вхід — [Practical Use Case Specification v1.0](docs/monitoring-v2/requirements/HELVETIC_LENS_PRACTICAL_USE_CASE_SPECIFICATION_v1.0.md), збережений без змін, SHA-256 `a6f4e7da87a9ae30171164512d16ce4be411f2913c22d90ed7bf7e1bc94ece4c`.
Формулювання документа про вже наявні можливості перевірені за кодом; вони не прийняті як доказ реалізації.
План і архітектурні рішення нижче — результат аналізу; приклади сум, дат, міст, порогів і score зі специфікації не стали прихованими глобальними defaults.

Перед стартом задачі: прочитати її критерії, залежності, source gate та успадковані legacy-зобов’язання; призначити виконавця на вказану роль; завести окрему гілку/worktree. Новий дефект або потрібне уточнення оформити як нову задачу MV2 з acceptance і залежностями **тут**, потім реалізовувати. Не брати старий HL ID як самостійну нову задачу. Поділ L-задачі на підзадачі дозволений лише з явними ID/criteria в цьому документі; coverage батьківського ID зберігається.

Статуси: **PLANNED → READY → IN PROGRESS → VERIFYING → DONE**; **BLOCKED** завжди має конкретну зовнішню залежність/власника/наступну дію; **DEFERRED** не входить у v2.0. READY означає виконані залежності й доступні необхідні контракти/дані. Код у Git, mock, проходження JSON schema або написаний текст не дорівнюють DONE.

**P0** — цілісність, спільна основа або gate перед відповідним зовнішнім pilot. **P1** — обов’язкова функція v2.0. **P2** — явно відкладений scope. Це пріоритет розробки, він не тотожний P1/P2/P3 пріоритету сповіщень у специфікації.
Ролі позначають відповідальність, а не вже призначену команду. S/M/L — відносний розмір невизначеності та роботи, не календарна оцінка. L потребує refinement перед реалізацією.

## Продуктове рішення

Користувач задає **що йому важливо**, а не конструює crawler. Початок — Create Monitor → Personal/Business → зрозумілі поля → preview очікуваних даних/збігу → явне Start. Далі один цикл: Today → What changed → Why received → Evidence → Decision → ongoing monitoring. Жоден звичайний користувач не має вводити API key джерела.

| ID | Користувацький результат | Обов’язкові основні задачі |
|---|---|---|
| C1 | Попередження для Home/Office та інших Swiss locations | MV2-028, MV2-029 |
| C2 | Зміни регулярного journey/line/stop у потрібні дні й час | MV2-037, MV2-038, MV2-039 |
| C3 | A2/Gotthard/A13: напрям, перекриття, затори, планові зміни | MV2-037, MV2-040, MV2-041 |
| C4 | Офіційний митний курс, поріг, історія, digest | MV2-026, MV2-027 |
| C5 | Вибраний пилок біля підтриманої станції; observed і forecast | MV2-030, MV2-031 |
| C6 | Вода/станція: рівень, витрата, температура, офіційна danger state | MV2-032, MV2-033 |
| C7 | PM2.5/PM10/O3/NO2: значуща зміна, поліпшення й обмеження | MV2-034, MV2-035 |
| B2 | Discovery тендерів і зміни вже відстежуваних tender dossiers | MV2-042…045 |
| B7 | Exact/lexical/phonetic IP candidates та register/deadline review | MV2-046…048 |
| B8 | Офіційні аукціони Ticino: актив, бюджет, строки, умови | MV2-049, MV2-050 |

Спільний UI: **Today / Monitoring / Investigate / Workspace / Admin**. Existing Topics, laws, Discover, Impact Inbox/Matrix, Digests і Marvin отримують зрозуміле місце в цій структурі. Нових десяти верхньорівневих застосунків немає. Семантичний AI потрібний для поясненого business ranking, але C1–C7 та числові/часові B8 правила працюють без LLM.

Перевага над звичайною підпискою — одна перевірна історія матеріальних оновлень із причиною саме для цього користувача та повторним review, коли змінився вже переглянутий факт.

## Архітектура та source gates

[Архітектурне рішення](docs/monitoring-v2/ARCHITECTURE.md) фіксує additive generic kernel у чинному FastAPI/PostgreSQL/Celery/Next.js. [Аудит коду](docs/monitoring-v2/BASELINE_AUDIT.md) показує, що legal-only CHECK/FK, connectors, Today grouping і ActionDecision не підтримують ці кейси простим додаванням шаблонів. Зберігаємо стек, jobs/outbox, auth, artifact storage, local models, regulatory domain; додаємо typed entities/states/developments/rules і bridge.

Ключові інваріанти: immutable evidence; idempotent ingestion/delivery; source state ≠ review ≠ decision ≠ delivery; source failure ≠ no change/all-clear; source severity ≠ user relevance ≠ notification priority; UNKNOWN ≠ 0; forecast ≠ observation; matched reasons належать workspace/subject revision, а офіційні дані можуть бути спільними.

[Перевірка джерел](docs/monitoring-v2/SOURCE_FEASIBILITY.md) містить датовані офіційні посилання й межі перевірки. **Документований API не означає готовий конектор чи погоджений доступ.**
MV2-003 можна завершити, коли для всіх десяти кейсів є точний dossier і approved/blocked outcome; він не вимагає одночасно отримати всі credentials. Кожний adapter додатково має власний **G(case)**: дозволений доступ → schema/identity/coverage contract → permitted live sample → lifecycle/quality → rights enforcement. Неготовий G(C4) не блокує дозволений C5.

| Gate | Поточний висновок для планування | Власник / наступна дія |
|---|---|---|
| G(C4) | BAZG/XML містить SIX restriction; права third-party використання не підтверджені | Product/Integration, MV2-026: документувати дозвіл/ліцензію до ingest і distribution |
| G(C1), G(B8) | Офіційні сторінки є; supported API/автоматичне reuse не доведені | Integration, MV2-028/049: supported channel та allowed monitoring contract |
| G(C3) | FEDRO access term та raw-data export restrictions | Integration/Operations, MV2-040: дозволені derived fields, renewal, retention |
| G(B2) | SIMAP API, публікаційні умови й окремі права на attachments | Integration, MV2-042: client contract, publication time/corrections, gated documents |
| G(B7) | IPI API через account/terms; допустимість monitoring emails потребує уточнення | Product/Integration, MV2-046: письмово зафіксувати channel scope |
| G(C2), G(C6) | Є документація, але rate limit/live-window неоднозначні | Integration, MV2-038/032: conservative bounded probe та уточнення контракту |
| G(C5), G(C7) | Pollen OGD придатний для thin slice; air coverage залежить від station/dataset | Integration, MV2-030/034: точні stations/metrics/units/rights |

Це не вилучення сценаріїв. Якщо потрібний source gate не пройдено, обов’язкова задача лишається BLOCKED, а повний v2.0 — не прийнятий. Посилання на зовнішній сайт або mock не закриває автоматичний monitoring AC. UNKNOWN в окремому record є чесною поведінкою; систематична відсутність mandatory capability (наприклад forecast, delay, документи/Q&A або deadline) залишає відповідний AC відкритим. Підписання умов, платний доступ, реєстрація від імені компанії чи зовнішні заявки — окремі явні дії власника/уповноваженого виконавця на етапі виконання.

## Порядок реалізації та контрольні точки

Спочатку виконати MV2-001/002, а source dossiers MV2-003 для всіх десяти джерел вести паралельно. Після мінімальних persistence/rule/delivery contracts будувати **повний C5 slice**, не чекати завершення всіх доменів або «ідеального» generic framework. Довідники/інтерфейси інших джерел досліджуються паралельно; активація лише після їхніх gates. Номер ID не є порядком виконання: наприклад, MV2-060/068 — рання сумісність, а не робота після релізу.

| Checkpoint | Результат і вихідний доказ |
|---|---|
| G0: F0 | Архітектурні контракти, відтворений legacy baseline, досліджені UX journeys, source dossiers; blockers мають owner |
| G1: F1/F2 minimum + C5 | Дозволений pollen source → state → material transition → reason → Today/evidence → review/reopen → notification; працює без LLM |
| G2: F3 | C1/C4/C5/C6/C7 прийняті за власними AC і source gates; спільні numeric/location contracts перевірені |
| G3: F4 | C2/C3 із time/route/expiry, direction, restoration; пояснений cross-source association |
| G4: F5 | B2/B7/B8 із discovery **та** change-monitoring, calibrated semantic candidates, документами, deadlines і рішеннями |
| G5: F6 | 126 AC, inherited regressions, five-language/a11y, target-host capacity/recovery, privacy, pilot; незалежний go/no-go |
| Release | MV2-059: артефакти v2.0, upgrade/rollback runbook; production deployment окремо авторизується |

F2 не означає, що весь UI треба завершити перед першим slice: потрібні лише частини залежних задач, а DONE ставиться після всіх їхніх критеріїв. Як тільки потрібний розріз стає самостійним work item, його додають як підзадачу до цього беклогу з власними залежностями.
MV2-023/043/047 завершують implementation під feature flags після training/validation checks; незалежний held-out gate MV2-051 пізніше дозволяє production promotion. Це не взаємне блокування DONE.

F6 тестові протоколи/fixtures проєктуються від початку; зазначені dependencies — вимоги до фінального виконання і закриття gate.

Поточний critical external path — права/доступ C4, C1, B7, B8 та підтверджене source coverage. Інженерний — entity/state/evidence → rules/development → scoped relevance/outbox → один UI loop → десять adapter+journey slices → quality/recovery/pilot. Поки source gates і команда не оцінені, календарних обіцянок немає.

## Definition of Ready та Definition of Done

**Ready:** задача зрозуміла виконавцю; predecessors завершені або є затверджений versioned interface для явно внесеної підзадачі; source access для залежної реалізації дозволений; є незалежний positive/negative fixture і target acceptance; review owner призначений.

**Done:** виконані всі task AC, mapped source AC та успадковані невиконані legacy acceptance; перевірені API/БД/UI і source path у заявленому обсязі; зафіксовані commit, test command/result, fixture hash, source/schema/rule version, rollout flag, limitations і reviewer. Відсутні критичні дефекти; оновлено цей статус і traceability evidence. Field/human/hardware criterion закривається тільки відповідним evidence, не self-assessment агента.

Для кожного case adapter + workflow вимагається: initial state, new/material update, unrelated/nonmaterial negative, duplicate replay, applicable cancellation/restoration, stale source, history/evidence, personal/team permissions, review/reopen, channel policy. Не кожний numeric series має «офіційний all-clear» — це не вигадувати.
Після source/rule/profile change і after review відтворюваність старого reason зберігається. Джерело, яке дозволяє тільки обмежену evidence representation, не отримує прихований raw export.

## Вимірювання, припущення та відкладений scope

Числові gates нижче — **запропоновані цілі плану**, не дані специфікації й не поточні результати. Їх фіксують до вимірювання; зміна потребує обґрунтованої версії плану, а не підгонки під результат.

- First value: setup до першого зрозумілого поточного/збереженого source-backed стану ≤5 хвилин; очікування нової природної події вимірюється окремо. Median alert-to-understanding ≤60 секунд.
- Pilot: ≥90% delivered relevance precision, ≥90% material-change precision, ≥90% understandable why, duplicates <1%. Кожний denominator та sample size видимий; aggregate не маскує провал окремого кейсу.
- Candidate evaluation: ≥85% precision / ≥90% recall для business ranking на незалежному held-out наборі, ≥200 labelled pairs з ≥50 B2/B7/B8; не «ймовірність порушення IP».
- Capacity: existing 100-account/10-org gate плюс proposed 1000 subjects/1M observations; legacy read p95≤500ms та enqueue≤1s зберігаються; для нових time-series/history endpoints proposed p95≤2s, post-ingest deterministic processing≤30s. Upstream і delivery lag окремо. Реальна підтримувана cadence залежить від джерела.
- Pilot тривалістю4 тижні: ≥10 B2C людей та ≥5 незалежних organizations. Якщо подій мало — historical replay окремим доказом, а не заміна live sample.
- English-first реалізація, але new v2 five-language closure успадковує EN/DE/FR/IT/RM contract; точна мова офіційного документа зберігається. Незалежна мовна перевірка не замінюється автоперекладом.

MV2-036 свідомо включає source-described correlation opportunity у v2 як bounded explainable association; це рішення цього плану, а не мінімальний AC специфікації. Optional customs calculator, розширена tender lifecycle і national auction expansion — після2.0. Нові vertical use cases, navigation engine, medical treatment, infringement verdicts, autonomous bids/filings, новий identity system і бездоказова заміна стеку не входять у цей план.
П’ять старих conditional directions лишаються явними DEFERRED задачами MV2-063…067, а не прихованою паралельною розробкою.

## Реєстр задач

| ID | Задача | Фаза | Пріоритет | Розмір | Статус | Залежності |
|---|---|---|---|---|---|---|
| [MV2-001](#mv2-001) | Зафіксувати контракти розширення та сумісність із MVP | F0 | P0 | M | PLANNED | — |
| [MV2-002](#mv2-002) | Перевірити сценарії першої цінності та спільну навігацію | F0 | P0 | M | PLANNED | — |
| [MV2-003](#mv2-003) | Перевірити права, покриття та контракти всіх десяти джерел | F0 | P0 | L | PLANNED | [MV2-001](#mv2-001) |
| [MV2-004](#mv2-004) | Особистий workspace і командні права моніторингу | F1 | P0 | M | PLANNED | [MV2-001](#mv2-001) |
| [MV2-005](#mv2-005) | MonitoringSubject і версійні Monitoring Templates | F1 | P0 | L | PLANNED | [MV2-001](#mv2-001), [MV2-004](#mv2-004) |
| [MV2-006](#mv2-006) | ObservedEntity: стабільна ідентичність джерела | F1 | P0 | M | PLANNED | [MV2-001](#mv2-001), [MV2-003](#mv2-003) |
| [MV2-007](#mv2-007) | ObservedState та незмінні докази | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006) |
| [MV2-008](#mv2-008) | Детерміновані ChangeRule, ChangeSet і числові пороги | F1 | P0 | L | PLANNED | [MV2-005](#mv2-005), [MV2-007](#mv2-007) |
| [MV2-009](#mv2-009) | Development, deduplication і lifecycle | F1 | P0 | L | PLANNED | [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-008](#mv2-008) |
| [MV2-010](#mv2-010) | Структурна релевантність із доказом кожного збігу | F1 | P0 | L | PLANNED | [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-009](#mv2-009) |
| [MV2-011](#mv2-011) | Надійний збір станів, черги та свіжість | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-009](#mv2-009) |
| [MV2-012](#mv2-012) | Notification policy та transactional outbox | F1 | P0 | L | PLANNED | [MV2-004](#mv2-004), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-011](#mv2-011) |
| [MV2-013](#mv2-013) | Review, Decision та призначення відповідального | F1 | P0 | M | PLANNED | [MV2-004](#mv2-004), [MV2-009](#mv2-009) |
| [MV2-014](#mv2-014) | API та read projections спільної стрічки | F1 | P0 | L | PLANNED | [MV2-004](#mv2-004), [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-013](#mv2-013) |
| [MV2-015](#mv2-015) | Каталог географії, станцій та зон покриття | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006) |
| [MV2-016](#mv2-016) | Часові вікна, строки та нагадування | F1 | P0 | L | PLANNED | [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-012](#mv2-012) |
| [MV2-060](#mv2-060) | Legacy bridge для Topics, watches та legal events | F1 | P0 | L | PLANNED | [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-014](#mv2-014) |
| [MV2-068](#mv2-068) | Завершити перевірку legacy coverage та repair старих артефактів | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-060](#mv2-060) |
| [MV2-017](#mv2-017) | Create Monitor: десять зрозумілих шаблонів | F2 | P1 | L | PLANNED | [MV2-002](#mv2-002), [MV2-005](#mv2-005), [MV2-010](#mv2-010), [MV2-015](#mv2-015) |
| [MV2-018](#mv2-018) | Monitoring: керування збереженими subjects | F2 | P1 | M | PLANNED | [MV2-005](#mv2-005), [MV2-011](#mv2-011), [MV2-017](#mv2-017) |
| [MV2-019](#mv2-019) | Today: одна картка для всіх доменів | F2 | P1 | L | PLANNED | [MV2-014](#mv2-014), [MV2-017](#mv2-017) |
| [MV2-020](#mv2-020) | Investigate: стани, diff, докази та історія | F2 | P1 | L | PLANNED | [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-014](#mv2-014) |
| [MV2-021](#mv2-021) | Workspace: Impact Inbox, рішення та Impact Matrix | F2 | P1 | M | PLANNED | [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-019](#mv2-019), [MV2-020](#mv2-020) |
| [MV2-022](#mv2-022) | Сповіщення та Digests із тих самих developments | F2 | P1 | L | PLANNED | [MV2-012](#mv2-012), [MV2-014](#mv2-014), [MV2-019](#mv2-019) |
| [MV2-023](#mv2-023) | Ask і Marvin у контексті доказів v2 | F2 | P1 | M | PLANNED | [MV2-010](#mv2-010), [MV2-020](#mv2-020) |
| [MV2-024](#mv2-024) | Зрозумілі підказки, доступність і п’ять мов | F2 | P0 | L | PLANNED | [MV2-002](#mv2-002), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022) |
| [MV2-025](#mv2-025) | Admin: правдиві source capabilities і керування доступом | F2 | P0 | M | PLANNED | [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-018](#mv2-018) |
| [MV2-026](#mv2-026) | C4: дозволений конектор офіційних митних курсів | F3 | P1 | M | BLOCKED — права BAZG/SIX не підтверджені | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011) |
| [MV2-027](#mv2-027) | C4: валюта, пороги, історія і digest | F3 | P1 | M | PLANNED | [MV2-008](#mv2-008), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-022](#mv2-022), [MV2-026](#mv2-026) |
| [MV2-028](#mv2-028) | C1: офіційні попередження і географія небезпеки | F3 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015) |
| [MV2-029](#mv2-029) | C1: Home/Office locations і повний warning workflow | F3 | P1 | L | PLANNED | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-028](#mv2-028) |
| [MV2-030](#mv2-030) | C5: офіційні pollen observations і forecasts | F3 | P1 | M | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015) |
| [MV2-031](#mv2-031) | C5: Pollen — перший наскрізний користувацький сценарій | F3 | P1 | L | PLANNED | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-013](#mv2-013), [MV2-017](#mv2-017), [MV2-018](#mv2-018), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-022](#mv2-022), [MV2-030](#mv2-030) |
| [MV2-032](#mv2-032) | C6: гідрологічні станції, показники та офіційна небезпека | F3 | P1 | M | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015) |
| [MV2-033](#mv2-033) | C6: River / Lake thresholds, escalation та історія | F3 | P1 | M | PLANNED | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-032](#mv2-032) |
| [MV2-034](#mv2-034) | C7: офіційні air-quality ряди та інтерпретація | F3 | P1 | M | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015) |
| [MV2-035](#mv2-035) | C7: Air Quality — показники, зміни та поліпшення | F3 | P1 | M | PLANNED | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-034](#mv2-034) |
| [MV2-036](#mv2-036) | Пов’язані developments із кількох джерел | F4 | P1 | M | PLANNED | [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-029](#mv2-029), [MV2-033](#mv2-033), [MV2-041](#mv2-041) |
| [MV2-037](#mv2-037) | Довідники Journey/Trip/Route/Stop і Road Corridor | F4 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-015](#mv2-015), [MV2-016](#mv2-016) |
| [MV2-038](#mv2-038) | C2: Service Alerts і Trip Updates | F4 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037) |
| [MV2-039](#mv2-039) | C2: регулярний commute і тихі транспортні alerts | F4 | P1 | L | PLANNED | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-038](#mv2-038) |
| [MV2-040](#mv2-040) | C3: ASTRA traffic і заплановані перекриття | F4 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037) |
| [MV2-041](#mv2-041) | C3: My Route Watch для A2 / Gotthard / A13 | F4 | P1 | L | PLANNED | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-040](#mv2-040) |
| [MV2-042](#mv2-042) | B2: SIMAP discovery та відстеження публікацій | F5 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011) |
| [MV2-043](#mv2-043) | B2/B7/B8: структурні профілі й semantic candidate ranking | F5 | P1 | L | PLANNED | [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-010](#mv2-010) |
| [MV2-044](#mv2-044) | Версії наборів документів та умов | F5 | P1 | L | PLANNED | [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009) |
| [MV2-045](#mv2-045) | B2: Tender discovery → review → material update | F5 | P1 | L | PLANNED | [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-042](#mv2-042), [MV2-043](#mv2-043), [MV2-044](#mv2-044) |
| [MV2-046](#mv2-046) | B7: офіційні trademark publications і register updates | F5 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011) |
| [MV2-047](#mv2-047) | B7: exact, lexical і phonetic candidates | F5 | P1 | L | PLANNED | [MV2-043](#mv2-043), [MV2-046](#mv2-046) |
| [MV2-048](#mv2-048) | B7: IP review, строк перевірки та зміни реєстру | F5 | P1 | L | PLANNED | [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-046](#mv2-046), [MV2-047](#mv2-047) |
| [MV2-049](#mv2-049) | B8: офіційні аукціони Ticino | F5 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011) |
| [MV2-050](#mv2-050) | B8: Auction profile, price limit і ending-soon | F5 | P1 | L | PLANNED | [MV2-008](#mv2-008), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-043](#mv2-043), [MV2-044](#mv2-044), [MV2-049](#mv2-049) |
| [MV2-051](#mv2-051) | Незалежна перевірка matching та локального AI | F6 | P0 | L | PLANNED | [MV2-023](#mv2-023), [MV2-043](#mv2-043), [MV2-047](#mv2-047) |
| [MV2-052](#mv2-052) | Операційні метрики, degraded mode і відновлення джерел | F6 | P0 | M | PLANNED | [MV2-011](#mv2-011), [MV2-012](#mv2-012), [MV2-025](#mv2-025) |
| [MV2-053](#mv2-053) | Приватність персональних locations і контроль доступу | F6 | P0 | M | PLANNED | [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-023](#mv2-023) |
| [MV2-054](#mv2-054) | Ємність одного сервера і черги з різними пріоритетами | F6 | P0 | L | PLANNED | [MV2-011](#mv2-011), [MV2-014](#mv2-014), [MV2-043](#mv2-043), [MV2-052](#mv2-052) |
| [MV2-055](#mv2-055) | Зберігання історії, retention та дозволений export | F6 | P0 | M | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-020](#mv2-020), [MV2-044](#mv2-044) |
| [MV2-056](#mv2-056) | Міграція, сумісність і rollback rehearsal | F6 | P0 | L | PLANNED | [MV2-001](#mv2-001), [MV2-053](#mv2-053), [MV2-055](#mv2-055), [MV2-060](#mv2-060) |
| [MV2-057](#mv2-057) | Виконуваний набір 126 AC та adversarial regression | F6 | P0 | L | PLANNED | [MV2-027](#mv2-027), [MV2-029](#mv2-029), [MV2-031](#mv2-031), [MV2-033](#mv2-033), [MV2-035](#mv2-035), [MV2-036](#mv2-036), [MV2-039](#mv2-039), [MV2-041](#mv2-041), [MV2-045](#mv2-045), [MV2-048](#mv2-048), [MV2-050](#mv2-050), [MV2-024](#mv2-024), [MV2-051](#mv2-051), [MV2-053](#mv2-053), [MV2-056](#mv2-056), [MV2-068](#mv2-068) |
| [MV2-058](#mv2-058) | Виміряний B2C/B2B pilot | F6 | P0 | L | PLANNED | [MV2-002](#mv2-002), [MV2-024](#mv2-024), [MV2-051](#mv2-051), [MV2-054](#mv2-054), [MV2-057](#mv2-057) |
| [MV2-059](#mv2-059) | Приймання і реліз Helvetic Lens Monitoring v2.0 | F6 | P0 | M | PLANNED | [MV2-025](#mv2-025), [MV2-052](#mv2-052), [MV2-054](#mv2-054), [MV2-055](#mv2-055), [MV2-056](#mv2-056), [MV2-057](#mv2-057), [MV2-058](#mv2-058) |
| [MV2-061](#mv2-061) | Після v2.0: опційний customs purchase calculator | LATER | P2 | S | DEFERRED | [MV2-027](#mv2-027) |
| [MV2-062](#mv2-062) | Після v2.0: нові кантони аукціонів і розширений tender workflow | LATER | P2 | L | DEFERRED | [MV2-045](#mv2-045), [MV2-050](#mv2-050) |
| [MV2-063](#mv2-063) | Умовно: pgvector після доведеного recall gap | LATER | P2 | M | DEFERRED | [MV2-051](#mv2-051), [MV2-054](#mv2-054) |
| [MV2-064](#mv2-064) | Умовно: relation graph після перевірки користі | LATER | P2 | M | DEFERRED | [MV2-021](#mv2-021), [MV2-036](#mv2-036), [MV2-058](#mv2-058) |
| [MV2-065](#mv2-065) | Умовно: кілька серверів / HA за виміряною потребою | LATER | P2 | M | DEFERRED | [MV2-054](#mv2-054), [MV2-056](#mv2-056) |
| [MV2-066](#mv2-066) | Умовно: наступні два кантональні regulatory packs | LATER | P2 | M | DEFERRED | [MV2-068](#mv2-068) |
| [MV2-067](#mv2-067) | Поза десятьма кейсами: opt-in public-discourse pilot | LATER | P2 | M | DEFERRED | [MV2-058](#mv2-058) |

## F0 — Рішення, джерела та перевірка потреби

<a id="mv2-001"></a>

### MV2-001 — Зафіксувати контракти розширення та сумісність із MVP

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Architect + Backend · **Розмір:** M

**Залежності:** —. **Вимоги:** §§1–7,19,27,30.

**Результат для користувача:** Розробка починається від перевіреної основи.

**Робота:** Затвердити ADR для generic kernel; інвентар API, схем, маршрутів, jobs та 35 відкритих legacy-пунктів; feature flags за template і workspace.

**Критерії приймання:**

1. Baseline — 7109a28; тег MVP незмінний; усі 35 відкритих HL мають disposition.
2. Нові сутності не обходять legal CHECK constraints; описані additive migrations, bridge і повернення на старі читачі.
3. Розмежовані факт джерела, системний розрахунок, AI та рішення; погоджені контракти з ARCHITECTURE.md.

**Перевірка:** Рев’ю схем і матриці сумісності; characterization-набір на ізольованій копії БД.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-002"></a>

### MV2-002 — Перевірити сценарії першої цінності та спільну навігацію

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Product + UX · **Розмір:** M

**Залежності:** —. **Вимоги:** §§20–21,25–26,34.

**Результат для користувача:** Людина створює спостереження без знання Sources/Topics.

**Робота:** Прототип Create Monitor → preview → Today → evidence → decision; особистий і командний режими; сценарії всіх десяти шаблонів.

**Критерії приймання:**

1. Щонайменше 5 B2C учасників і 5 представників B2B проходять релевантні їм задачі; протокол помилок збережений.
2. Прототип явно показує недоступне покриття, очікування першого стану та брак свіжих даних.
3. Навігація Today / Monitoring / Investigate / Workspace / Admin; збережено шлях до старих законів, Topics, Discover та Impact Matrix.

**Перевірка:** Спостереження за користувачем без підказок; результати уточнюють тексти та конфігурацію, не розширюють десять кейсів.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-003"></a>

### MV2-003 — Перевірити права, покриття та контракти всіх десяти джерел

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Integration + Product · **Розмір:** L

**Залежності:** [MV2-001](#mv2-001). **Вимоги:** §§23,38; усі authoritative source розділи.

**Результат для користувача:** Обіцяються лише дані, які можна отримувати й показувати.

**Робота:** Окремий dossier C1…B8: endpoint, auth, terms, licence, поля, території, мови, cadence, історія, correction/delete, evidence retention/export; каталог capabilities.

**Критерії приймання:**

1. Для кожного кейсу є датований dossier з URL/версією умов, exact capability inventory, відповідальним і outcome approved або blocked. Якщо доступ заблокований, достатній документований blocker; successful response sample потрібний лише для власного G(case), не для DONE MV2-003.
2. C4 заблокований до врегулювання прав BAZG/SIX; C3 має контроль строку доступу та заборони raw redistribution; SIMAP враховує час публікації.
3. Недоступний обов’язковий кейс лишається BLOCKED; його не оголошують DONE через mock або підміну стороннім джерелом.

**Перевірка:** Документальне рев’ю десяти source dossiers; successful bounded API probe та conformance fixtures виконуються в G(case) кожного adapter після дозволеного доступу.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.


## F1 — Спільні контракти й сумісність

<a id="mv2-004"></a>

### MV2-004 — Особистий workspace і командні права моніторингу

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend + UX · **Розмір:** M

**Залежності:** [MV2-001](#mv2-001). **Вимоги:** §§5,27.1,27.7.

**Результат для користувача:** B2C не потребує вигаданої компанії; командні дані залишаються командними.

**Робота:** Повторно використати Organization/personal workspace і auth; subject owner_scope, автор, доступ, членство, видалення/передача власника.

**Критерії приймання:**

1. Особистий workspace за замовчуванням ізольований; адресу Home не бачить інша організація.
2. Admin керує shared monitors; viewer має тільки дозволені read/особисті acknowledgement дії; спільне рішення потребує права.
3. Перемикання workspace, відкликання доступу й старі посилання не розкривають стан або AI-висновок.

**Перевірка:** API role-matrix, cross-tenant негативні тести, browser switch/revocation.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-005"></a>

### MV2-005 — MonitoringSubject і версійні Monitoring Templates

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend + Frontend · **Розмір:** L

**Залежності:** [MV2-001](#mv2-001), [MV2-004](#mv2-004). **Вимоги:** §§5,19.1,25,27.1.

**Результат для користувача:** Одна конфігурація описує те, що користувач хоче відстежувати.

**Робота:** 9 типів subject, 10 template_id; schema_version; конфігурація, filters/thresholds/rules, source bindings, draft/active/paused/archived, revision і preview.

**Критерії приймання:**

1. Кожен тип із §19.1 валідований; C6/C7 мають різні шаблони над MEASUREMENT_STATION.
2. Активація вимагає доступного source capability; немає прихованої активації після preview.
3. Редагування зберігає revision та actor; повторний create з тим самим idempotency key не дублює monitor.

**Перевірка:** Schema/API tests для валідних і несумісних параметрів усіх десяти шаблонів.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-006"></a>

### MV2-006 — ObservedEntity: стабільна ідентичність джерела

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend + Integration · **Розмір:** M

**Залежності:** [MV2-001](#mv2-001), [MV2-003](#mv2-003). **Вимоги:** §§4,27.2,29.

**Результат для користувача:** Повторне отримання запису не створює нову реальну сутність.

**Робота:** Identity = source_namespace + entity_type + external_id; aliases для підтверджених перевидань і мовних версій; provenance та domain extensions.

**Критерії приймання:**

1. Одна сутність має стабільний ID між polling, мовами й перезапуском; namespace не зливає чужі ідентифікатори.
2. Немає надійного ID — версійна fallback strategy з collision tests і позначкою невпевненості.
3. Зміна назви, власника або URL не видаляє історію; merge/split аудитується та може бути виправлений.

**Перевірка:** Replay duplicated/renamed records, collision та split fixtures.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-007"></a>

### MV2-007 — ObservedState та незмінні докази

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-006](#mv2-006). **Вимоги:** §§19.2,27.3,30.

**Результат для користувача:** Кожен стан можна перевірити і порівняти з попереднім.

**Робота:** Typed payload, units, measurement/forecast, quality, fetched/published/effective/observed/valid times; schema_version, checksum, evidence locators і source retention policy.

**Критерії приймання:**

1. Повторний snapshot ідентичний за змістом не створює матеріальної зміни; transport fetch log зберігається окремо.
2. Пізня/виправлена відповідь зберігає history, але не відкочує current без правила revision ordering.
3. UNKNOWN, missing, zero, stale, forecast і provisional розрізняються; evidence access/export відповідає правам джерела.

**Перевірка:** Round-trip snapshots; out-of-order, correction, missing і rights-filter tests.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-008"></a>

### MV2-008 — Детерміновані ChangeRule, ChangeSet і числові пороги

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend · **Розмір:** L

**Залежності:** [MV2-005](#mv2-005), [MV2-007](#mv2-007). **Вимоги:** §§4,19.3,22,33.

**Результат для користувача:** Сповіщення виникає через значущу зміну, а не оновлення часу.

**Робота:** NEW_ENTITY, STATE_TRANSITION, NUMERIC_THRESHOLD, PERCENTAGE_DELTA, FIELD_CHANGED, DEADLINE_CHANGED, DOCUMENT_ADDED, STATUS_CHANGED; SEMANTIC_MATCH підключається як candidate assessment у MV2-043.

**Критерії приймання:**

1. Обчислення використовує Decimal, unit/basis/aggregation-period; zero baseline не дає вигаданий percentage.
2. Зафіксовані > проти ≥, previous-effective/daily/weekly baseline, crossing direction, hysteresis, cooldown та reset.
3. Кожна оцінка зберігає rule revision, input state IDs, reason і результат; preview та worker використовують той самий evaluator.
4. Перший стан є baseline; активна офіційна небезпека може дати initial alert, але числовий delta без бази — ні.

**Перевірка:** Boundary/property/replay tests: рівність, нуль, null, flapping, пропуски, одиниці, щотижневий baseline.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-009"></a>

### MV2-009 — Development, deduplication і lifecycle

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend · **Розмір:** L

**Залежності:** [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-008](#mv2-008). **Вимоги:** §§6,27.4,29.

**Результат для користувача:** Користувач бачить одну історію з оновленнями.

**Робота:** Development + immutable revisions; source lifecycle окремо від review/delivery; correlation keys за доменом; manual split audit.

**Критерії приймання:**

1. Той самий incident/announcement і мовні копії дають одну development; новий trip service date або новий warning ID не зливаються.
2. Матеріальна revision повторно відкриває review; незмінний refresh не відкриває і не надсилає.
3. CANCELLED/RESOLVED/EXPIRED мають різні причини; зникнення з feed або timeout не означає офіційний all-clear.
4. Оновлення та re-open після перезапуску обробляються ідемпотентно.

**Перевірка:** State-machine і concurrent-ingestion tests; manual correction/merge/split replay.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-010"></a>

### MV2-010 — Структурна релевантність із доказом кожного збігу

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend · **Розмір:** L

**Залежності:** [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-009](#mv2-009). **Вимоги:** §§7,19.4,22,27.6.

**Результат для користувача:** На «чому я це бачу?» є точна відповідь.

**Робота:** RelevanceAssessment на subject revision × development revision; rule IDs, matched fields, source anchors, method; одна development може мати кілька причин.

**Критерії приймання:**

1. Delivery без reason і evidence блокується; AI-текст не підміняє структурний match.
2. Зміна профілю переоцінює поточну релевантність, але не переписує історичну причину.
3. Exclusions переважають semantic score; UNKNOWN не трактується як підтверджена відповідність.
4. Одна development для кількох monitors не створює кілька сповіщень одному одержувачу.

**Перевірка:** Golden match/nonmatch cases, preview/worker parity, cross-profile replay.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-011"></a>

### MV2-011 — Надійний збір станів, черги та свіжість

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend + Operations · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-009](#mv2-009). **Вимоги:** §§3,23,28,33.

**Результат для користувача:** Монітор має правдивий стан навіть під час збоїв.

**Робота:** Розширити PostgreSQL jobs + Celery; scheduled connector ingest окремо від bounded match fan-out; source leases, cursors, backoff, Retry-After, priority queues.

**Критерії приймання:**

1. Одна shared source fetch обслуговує багато subjects; quota чи 429 не запускає нескінченний retry.
2. Restart/replay не губить watermark і не дублює revisions; reprocess історії за замовчуванням не надсилає сповіщення.
3. Fresh/late/stale/failed/no-data відрізняються від no-change; next expected update походить із capability.
4. Термінові deterministic jobs не стоять за LLM; один tenant не монополізує чергу.

**Перевірка:** Kill/restart, duplicate worker, 429/partial feed і overload tests; queue lag telemetry.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-012"></a>

### MV2-012 — Notification policy та transactional outbox

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend · **Розмір:** L

**Залежності:** [MV2-004](#mv2-004), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-011](#mv2-011). **Вимоги:** §§28–29,33.

**Результат для користувача:** Канал доставки виконує налаштування, не створює спам.

**Робота:** Розширити наявний outbox; recipient + development revision + channel policy revision; immediate/important/digest, mute, quiet hours, user timezone, opt-in.

**Критерії приймання:**

1. Матеріальна revision і права одержувача перевіряються до enqueue та send; відкликані/paused/muted monitors не отримують доставку.
2. Матеріальне посилення може обійти cooldown лише за явним template rule; не ігнорує відмову користувача від каналу.
3. Retry, send-timeout і перезапуск не дають повторну in-app подію; зовнішнє email підтвердження не видається за гарантовану доставку.
4. Термінове означає пріоритет обробки після отримання джерела, без обіцянки заміни аварійної системи.

**Перевірка:** Outbox race/retry/revocation tests, quiet hours/DST, send ambiguity і dedup.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-013"></a>

### MV2-013 — Review, Decision та призначення відповідального

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend + Frontend · **Розмір:** M

**Залежності:** [MV2-004](#mv2-004), [MV2-009](#mv2-009). **Вимоги:** §§6,21,27.7,31.

**Результат для користувача:** Рішення користувача зберігається разом із версією доказів.

**Робота:** Особистий read state, workspace Review, append-only Decision; REVIEWED/ACTION_REQUIRED/NO_ACTION/NOT_RELEVANT/MONITOR/RESOLVED і domain decisions.

**Критерії приймання:**

1. Рішення містить development revision, actor, owner, comment, timestamp; конкурентний запис не затирає інший.
2. Новий material update позначає попереднє рішення як прийняте на старій revision; його текст залишається в історії.
3. BID/NO_BID/INSPECT/ESCALATE_TO_IP_COUNSEL — внутрішні рішення; зовнішня подача чи надсилання не виконується.
4. Деактивація owner не губить unresolved review; дозволена передача іншому member.

**Перевірка:** Optimistic concurrency, roles, reopen, reassignment і personal/shared-state tests.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-014"></a>

### MV2-014 — API та read projections спільної стрічки

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend · **Розмір:** L

**Залежності:** [MV2-004](#mv2-004), [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-013](#mv2-013). **Вимоги:** §§20–21,26,33.

**Результат для користувача:** Today і історія залишаються швидкими зі змішаними даними.

**Робота:** Нові versioned API contracts; projections, cursor pagination, unseen revision count, filters template/status/subject/severity; evidence lazy load.

**Критерії приймання:**

1. Today не виконує cross-join усіх станів, AI або генерацію; max page/period/enrichment bounded.
2. Unread count ґрунтується на видимій revision і не залежить від поточної сторінки.
3. Stable cursors не гублять записи під час нових revisions; archived/resolved history доступна.
4. Endpoint authorization перевіряє workspace для кожної development, evidence і decision.

**Перевірка:** SQL query-count/plan checks, pagination under updates, serialization contract.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-015"></a>

### MV2-015 — Каталог географії, станцій та зон покриття

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Integration + Backend + UX · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-006](#mv2-006). **Вимоги:** §§8,12–14,19.1.

**Результат для користувача:** Вибрана локація відповідає реальному покриттю.

**Робота:** Офіційні municipality/station IDs, coordinates, CRS, polygon/radius, station metrics та validity; reuse pack metadata.

**Критерії приймання:**

1. Boundary intersection, overlapping canton/municipality, radius і CRS перевірені на fixtures.
2. Найближча станція не оголошується виміром у домі; показані distance, representativeness, доступні показники та обмеження.
3. Непокрита локація не активує fictitious monitor; недоступний параметр не замінюється іншим.
4. Перенесена/закрита станція отримує явний remap з історією, не безшумну заміну.

**Перевірка:** Geo boundary/CRS tests, station gap/change fixtures, keyboard selector UX.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-016"></a>

### MV2-016 — Часові вікна, строки та нагадування

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend · **Розмір:** L

**Залежності:** [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-012](#mv2-012). **Вимоги:** §§9–10,15–17,27,28.

**Результат для користувача:** Зміна строку й запланована поїздка обробляються правильно.

**Робота:** UTC storage + Europe/Zurich display, overnight windows, service date >24h, weekdays; explicit vs calculated deadline, evidence rule version, reschedule jobs.

**Критерії приймання:**

1. DST gap/fold і 23:00–05:00 працюють із визначеною політикою; source timezone збережений.
2. Невідомий/неоднозначний deadline не вигадується; calculated legal deadline завжди має verification_required.
3. Перенесення/скасування auction чи tender скасовує старі ending-soon jobs; reminder idempotent per deadline revision.
4. Документована відмінність official resolution від system expiry; минулі події лишаються в історії.

**Перевірка:** Fake-clock tests для DST, midnight, delay, reschedule, expiry, source correction.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-060"></a>

### MV2-060 — Legacy bridge для Topics, watches та legal events

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend + Frontend · **Розмір:** L

**Залежності:** [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-014](#mv2-014). **Вимоги:** §§1,26–27; legacy HL-073,076–080,089,098–100.

**Результат для користувача:** Чинні можливості Helvetic Lens лишаються доступними в новій моделі.

**Робота:** Bridge references old Topic/RegulatoryEvent/Watch IDs → generic Subject/Entity/Development; compatibility read adapters, no blanket FK rewrite.

**Критерії приймання:**

1. Legal records лишаються в існуючих таблицях; generic contracts не вимагають AI analysis/comparison для numeric decision.
2. Backfill не робить старі reviewed events новими unread; дві fan-out системи не надсилають дублікати.
3. Topics/watch settings, locales, citations і user decisions збережені; old links resolve до відповідного evidence.
4. Legacy-only unsupported record видимий через старий reader із причиною, а не silently dropped; repair audited.

**Перевірка:** Golden production-shaped legacy corpus, bridge replay, read parity і notification suppression.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-068"></a>

### MV2-068 — Завершити перевірку legacy coverage та repair старих артефактів

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Integration + Backend + QA · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-060](#mv2-060). **Вимоги:** legacy HL-080,098,100; §§1,26,30.

**Результат для користувача:** Нові домени не приховують незавершену якість чинного legal monitoring.

**Робота:** Перенести remaining HL-080/098: exact source coverage federal/cantonal streams, Basel pilot evidence, bounded versioned re-extraction/repair із preview; unchanged immutable originals.

**Критерії приймання:**

1. Заявлене старе покриття має перевірені види/мови/географію/час/історію і відомі gaps; Ticino auction не закриває Basel regulatory gate.
2. Repair має нову normalization revision і пояснення, старий hash/доказ не перезаписується.
3. Повторний repair/resume не створює фальшивих amendments або дубльованих notifications; affected comparisons і cached briefs superseded контрольовано.
4. Після repair old URLs/citations/review/read state та legal relation evidence проходять regression.

**Перевірка:** Representative legacy corpus до/після з hashes, legal/cantonal live permitted samples, re-extract/cancel/retry і user journey evidence.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.


## F2 — Єдиний користувацький шлях

<a id="mv2-017"></a>

### MV2-017 — Create Monitor: десять зрозумілих шаблонів

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + UX · **Розмір:** L

**Залежності:** [MV2-002](#mv2-002), [MV2-005](#mv2-005), [MV2-010](#mv2-010), [MV2-015](#mv2-015). **Вимоги:** §§5,25,33.

**Результат для користувача:** Користувач налаштовує мету, а джерело система підбирає сама.

**Робота:** Personal/Business template picker; guided form, capability availability, preview why-match/no-match, defaults, explicit start.

**Критерії приймання:**

1. Усі 10 template IDs присутні; unsupported/blocked пояснюють причину й не активуються.
2. Форма збирає domain configuration з requirements, без вимоги вводити URL, API key чи технічний source ID.
3. Preview позначає sample/baseline та не створює реальних alerts; double-click Start не дублює.
4. Помилки зберігають draft, підказують виправлення; перший стан має expected wait, джерело й наступний крок.

**Перевірка:** Browser journeys створення/редагування/недоступності для десяти templates.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-018"></a>

### MV2-018 — Monitoring: керування збереженими subjects

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend · **Розмір:** M

**Залежності:** [MV2-005](#mv2-005), [MV2-011](#mv2-011), [MV2-017](#mv2-017). **Вимоги:** §§9.12,25–26.

**Результат для користувача:** Видно, що саме відстежується і чи працює збір.

**Робота:** Список personal/shared subjects; стан, джерело, last observation/success/next expected, пороги, pause/resume/archive, contextual Monitor this.

**Критерії приймання:**

1. Редагування й pause/resume видимі після reload; archive не видаляє історію.
2. No change, first data pending, stale, source unavailable і disabled відрізняються словами та дією.
3. Pause commute today автоматично відновлюється за timezone й показує час; archive без auto resume.
4. Поточні Topics і watched documents доступні через bridge; нова навігація не дублює керування.

**Перевірка:** Browser persistence, realtime status update, stale recovery і legacy link tests.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-019"></a>

### MV2-019 — Today: одна картка для всіх доменів

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + UX · **Розмір:** L

**Залежності:** [MV2-014](#mv2-014), [MV2-017](#mv2-017). **Вимоги:** §§20,26.1,33.

**Результат для користувача:** Змішані події читаються однаково зрозуміло.

**Робота:** Спільний card shell: type, authority severity, state/delta, why, timestamps, evidence, review; domain-specific fields усередині shell.

**Критерії приймання:**

1. Картка має факт, previous→current, source/time, структурне why і явний CTA; перший baseline не показує вигадане previous. На картці явні Review / Evidence / Not relevant.
2. Observed, forecast, stale і system calculation мають видимі підписи; source severity відокремлена від user priority.
3. Одне development агрегує кілька subjects; material updates/reopened позначені без другої незалежної картки.
4. Legacy legal і всі 10 v2 templates сумісні з filters, accessible empty/loading/error і global unread.

**Перевірка:** Populated mixed-feed browser replay; keyboard, narrow viewport та live revision updates.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-020"></a>

### MV2-020 — Investigate: стани, diff, докази та історія

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** L

**Залежності:** [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-014](#mv2-014). **Вимоги:** §§21,30.

**Результат для користувача:** Можна перевірити, що змінилося від моменту свого рішення.

**Робота:** Typed numeric/state diff, document-set diff plug-in, pinned evidence, current/historical revisions, provenance та AI section.

**Критерії приймання:**

1. Історична картка відкриває саме старий доказ; today/current response не підміняє його.
2. Fact / AI / calculation / decision явно розділені; numeric value містить unit, period і quality.
3. Raw download/export доступний лише за source policy; інакше дозволений normalized evidence + official link + пояснення меж.
4. Великі документи й timeline завантажуються частинами; broken/live source не руйнує збережені дозволені докази.

**Перевірка:** Evidence-version navigation, permissioned export, long-text/large-history browser checks.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-021"></a>

### MV2-021 — Workspace: Impact Inbox, рішення та Impact Matrix

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** M

**Залежності:** [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-019](#mv2-019), [MV2-020](#mv2-020). **Вимоги:** §§15–17,26.4,27.7.

**Результат для користувача:** Незавершена робота має відповідального і контекст.

**Робота:** Фільтри unresolved/reopened/assigned, notes, decisions, safe batch review; зберегти existing Matrix у regulatory контексті без вигаданих cross-domain impact scores.

**Критерії приймання:**

1. Високий hazard, relevant IP candidate й tender update можуть мати Inbox review; source state не змішується з рішенням.
2. Batch review прив’язана до видимих revisions; нова revision під час дії не вважається переглянутою.
3. BID/NO_BID/INSPECT/escalate мають доменні labels і не надсилають нічого назовні.
4. Призначення owner і decision history видимі лише в дозволеному scope; Matrix та старі inbox links працюють.

**Перевірка:** Concurrent revision/decision браузерні сценарії, owner filters, legacy Matrix regression.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-022"></a>

### MV2-022 — Сповіщення та Digests із тих самих developments

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** L

**Залежності:** [MV2-012](#mv2-012), [MV2-014](#mv2-014), [MV2-019](#mv2-019). **Вимоги:** §§28,33; AC-C4-10,AC-B2-12.

**Результат для користувача:** Користувач керує шумом в одному місці.

**Робота:** In-app center і opt-in email digest; monitor/type/event/channel mute, priority, frequency, quiet hours; review/evidence deep links.

**Критерії приймання:**

1. Immediate та digest не дублюють ту саму revision без явно вибраної recap policy.
2. Digest містить тільки material changes дозволеного періоду та позначає source gaps; preview = sending rules.
3. Налаштування збережені per user/workspace; unsubscribe та права застосовані перед відправленням.
4. Покращення/скасування посилаються на попередній development; непрочитане синхронізується між Today й center.

**Перевірка:** Send-preview parity, race/unsubscribe, multi-monitor dedup, bounded period queries.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-023"></a>

### MV2-023 — Ask і Marvin у контексті доказів v2

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** AI + Frontend · **Розмір:** M

**Залежності:** [MV2-010](#mv2-010), [MV2-020](#mv2-020). **Вимоги:** §§21–22,26.3,31; legacy HL-083–087,089.

**Результат для користувача:** Питання про подію не запускає зайву генерацію й не змінює monitor.

**Робота:** Reuse cached briefs; entity-aware read context, cited answers; follow-up intent, explicit draft/preview for monitor changes.

**Критерії приймання:**

1. C1–C7 core works with LLM offline; unavailable model показує evidence/extractive mode.
2. Збережений висновок прив’язаний до state/profile/model/prompt/locale revisions; stale answer не видається як актуальний.
3. Ask не обіцяє medical treatment, infringement або гарантований legal deadline; official instructions цитуються точно.
4. Natural-language config створює draft для перегляду; жодної автономної активації, bid чи зовнішнього повідомлення.

**Перевірка:** Context revocation, stale brief, prompt-injection fixtures та cited-answer checks під feature flag. DONE означає інтеграцію з manual/extractive fallback; production model enablement окремо проходить MV2-051.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-024"></a>

### MV2-024 — Зрозумілі підказки, доступність і п’ять мов

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** UX + Frontend + Language reviewers · **Розмір:** L

**Залежності:** [MV2-002](#mv2-002), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022). **Вимоги:** §§20–21,25–26; legacy HL-057,073,095–097.

**Результат для користувача:** Нові можливості доступні з клавіатури, телефона й підтриманою мовою.

**Робота:** English-first реалізація з existing i18n contracts; EN/DE/FR/IT/RM release strings і human review; F1/Page guide/Show me для нових дій.

**Критерії приймання:**

1. У нових розділах пояснені походження даних, кожна дія, waiting/configuration та наслідки mute/review.
2. Keyboard/focus/contrast/reader checks проходять populated/error/stale flows; колір не є єдиним сигналом.
3. Нові v2 потоки всіх п’яти мов перевірені незалежними fluent reviewers; неперевірена мова не оголошується готовою.
4. Primary actions прості; provider/queue/debug поля лишаються Admin, units/dates/number formats локалізовані.

**Перевірка:** Browser/axe + screen-reader/device review + language sign-off; автоматичні checks не замінюють human acceptance.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-025"></a>

### MV2-025 — Admin: правдиві source capabilities і керування доступом

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Integration + Frontend · **Розмір:** M

**Залежності:** [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-018](#mv2-018). **Вимоги:** §§23,26.5,38.

**Результат для користувача:** Адміністратор розуміє, чому шаблон доступний чи заблокований.

**Робота:** Каталог 5 source packs, conformance version, access expiry, supported fields/location/history, quotas, freshness, reprocess controls.

**Критерії приймання:**

1. Заборона export, строк доступу, correction requirements і licence version виконуються політикою, а не лише записані в docs.
2. Відсутній доступ показує actionable state; viewer не бачить секретів або credentials.
3. Reprocess має preview, bounded scope, progress/cancel/resume; історичний replay не створює alert burst.
4. Зміна terms/capability вимикає залежну функцію та повідомляє адміністратора; без тихого стороннього fallback.

**Перевірка:** API permission tests, licence-expiry clock, source fail/recover і reprocess browser checks.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.


## F3 — Числові стани, середовище та небезпеки

<a id="mv2-026"></a>

### MV2-026 — C4: дозволений конектор офіційних митних курсів

**Статус:** BLOCKED — права BAZG/SIX не підтверджені · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** M

**Залежності:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011). **Вимоги:** §11; AC-C4-02,03,07,09.

**Результат для користувача:** Зберігається саме офіційний customs rate.

**Робота:** Отримати/зафіксувати право повторного використання BAZG/SIX, перевірити XML, currency unit/basis, effective day, correction/weekend semantics.

**Критерії приймання:**

1. Письмово або у чинній ліцензії підтверджено дозволений сценарій; до цього production ingest/distribution не активується.
2. Курс зберігає валюту, nominal units, CHF basis, effective date і джерело; JPY/100 не читається як JPY/1.
3. Вихідний/відсутня публікація не створює нульового курсу; виправлення дати versioned.
4. Жодного market FX fallback під назвою customs.

**Перевірка:** Licensed sample replay і 1/100-unit fixtures; source-contract report.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-027"></a>

### MV2-027 — C4: валюта, пороги, історія і digest

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** M

**Залежності:** [MV2-008](#mv2-008), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-022](#mv2-022), [MV2-026](#mv2-026). **Вимоги:** §11; AC-C4-01…10.

**Результат для користувача:** Користувач отримує значущу зміну обраного курсу.

**Робота:** Currency selector; daily/weekly/absolute crossing/every-change rules; previous/current/delta/chart/digest. Purchase calculator відокремлений у MV2-061.

**Критерії приймання:**

1. Виконано AC-C4-01…10; 0.9412→0.9547 дає +1.43434…%, показано +1.43% із точним underlying value.
2. Strict greater-than 1% не спрацьовує на рівно1%; weekly baseline і відсутній baseline пояснені.
3. Поріг перевіряється на unrounded Decimal; every-change — явний opt-in; history та evidence доступні.
4. Без purchase value шаблон повністю корисний.

**Перевірка:** End-to-end licensed source→state→rule→Today→digest; below/exact/above threshold, weekend/correction fixtures.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-028"></a>

### MV2-028 — C1: офіційні попередження і географія небезпеки

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015). **Вимоги:** §8.4–8.9; AC-C1-02,04,05,07,09.

**Результат для користувача:** Офіційне попередження має стабільну історію й зону дії.

**Робота:** Alertswiss/federal/cantonal capability-specific adapter; authority ID, severity scale, certainty, instructions, publication/effective/valid times, cancellation.

**Критерії приймання:**

1. Доступ і дозволена географія підтверджені; категорії hazards показують реальне source coverage, включно з outage, якщо джерело її дає.
2. Instructions і authority severity збережені без AI-переписування; кілька мов не дублюють warning.
3. Polygon/municipality expansion/reduction зберігається як update; cancellation/all-clear відрізняється від пропуску feed.
4. Відсутні типи чи кантональні дані позначені недоступними, а не «немає небезпеки».

**Перевірка:** Source fixture creation/update/instructions/geography/cancel; controlled live fetch з дозволом.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-029"></a>

### MV2-029 — C1: Home/Office locations і повний warning workflow

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** L

**Залежності:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-028](#mv2-028). **Вимоги:** §8; AC-C1-01…10.

**Результат для користувача:** Попередження отримує лише людина, якої стосується зона.

**Робота:** Multiple saved locations, hazards/minimum importance, Review/View official/Not relevant/Mute type; active and historical warning state.

**Критерії приймання:**

1. Виконано AC-C1-01…10; Home усередині affected geometry отримує warning, поза нею — ні.
2. Нові instructions, severity, geography, time або cancellation створюють material revision; formatting/timestamp refresh — ні.
3. Material escalation reopen перевірено після reviewed; all-clear закриває active source event, зберігаючи review history.
4. Critical source instructions видно без AI; поруч official source і актуальність; no-data не показується як all-clear.

**Перевірка:** E2E multi-location, boundary, changed instruction, reviewed→reopened→all-clear, mute і offline model.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-030"></a>

### MV2-030 — C5: офіційні pollen observations і forecasts

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** M

**Залежності:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015). **Вимоги:** §12.3–12.8; AC-C5-03,06,08.

**Результат для користувача:** Є перевірений часовий ряд allergen × station.

**Робота:** MeteoSwiss/SwissPollen dataset contract, parameter list, categories, units, station capability; окремі observation та forecast series.

**Критерії приймання:**

1. Підтримка birch/grasses доведена для обраної станції; unavailable аллерген не вважається нулем.
2. Observation_time, issue_time і forecast_valid_time не змішуються; revised forecast не перезаписує measurement.
3. Official categories/scales збережені з версією; provisional/corrected readings відрізняються.
4. Polling відповідає перевіреному source cadence; 20-minute refresh не означає окремий alert.

**Перевірка:** Official dataset sample, missing station/allergen, revision and forecast-vs-observation conformance.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-031"></a>

### MV2-031 — C5: Pollen — перший наскрізний користувацький сценарій

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend + UX · **Розмір:** L

**Залежності:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-013](#mv2-013), [MV2-017](#mv2-017), [MV2-018](#mv2-018), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-022](#mv2-022), [MV2-030](#mv2-030). **Вимоги:** §12; AC-C5-01…10.

**Результат для користувача:** Location + pollen type + поріг дають зрозуміле спостереження.

**Робота:** Створити один цілісний delivery slice на справжньому дозволеному джерелі: setup, initial state, category crossing, review, improvement, history.

**Критерії приймання:**

1. Виконано AC-C5-01…10; одна й кілька pollen types, threshold/high-or-above і rapid-increase window.
2. HIGH fluctuation не спамить; improvement оновлює ту саму development після configured reset.
3. Observed та Forecast tomorrow мають різні labels/час; пояснені station coverage і локальні обмеження.
4. Немає діагнозу/дозування; перша цінність доступна з вимкненим LLM.

**Перевірка:** Golden + live permitted E2E, reviewed update, flapping, station gap, email opt-in; записане демо.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-032"></a>

### MV2-032 — C6: гідрологічні станції, показники та офіційна небезпека

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** M

**Залежності:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015). **Вимоги:** §13.3–13.5; AC-C6-01,02,05,08.

**Результат для користувача:** Рівень води, витрата, температура й danger не змішуються.

**Робота:** FOEN station/waterbody mapping; parameter units/reference datum/aggregation/quality; explicit source danger vs locally calculated threshold.

**Критерії приймання:**

1. Покриття кожної величини перевірене; відсутній station parameter = UNKNOWN.
2. Water level з різними datum не порівнюється як один ряд; discharge/temperature мають власні units.
3. Офіційний danger level походить із офіційного продукту й зони, а не вигадується з water level.
4. Підтверджено live/history window та recovery watermark, врахована суперечність документації.

**Перевірка:** Metric/datum/quality fixtures і source contract probe; hydrology sample review.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-033"></a>

### MV2-033 — C6: River / Lake thresholds, escalation та історія

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** M

**Залежності:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-032](#mv2-032). **Вимоги:** §13; AC-C6-01…10.

**Результат для користувача:** Користувач стежить за потрібною водоймою чи станцією.

**Робота:** Station/waterbody picker, water-level/discharge/temperature/danger selection; absolute/rate-of-change window; escalation/downgrade.

**Критерії приймання:**

1. Виконано AC-C6-01…10; абсолютний >2.5m і +30cm за заданий час використовують відповідні одиниці/вікно.
2. Офіційна danger escalation має вищий пріоритет, не пригнічується нижчим custom threshold.
3. Downgrade змінює існуючу development; unchanged readings не створюють duplicates.
4. History measurements відокремлена від change history; source timestamp/quality видно.

**Перевірка:** E2E threshold/window/danger override/reversal/duplicate/missing reading.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-034"></a>

### MV2-034 — C7: офіційні air-quality ряди та інтерпретація

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** M

**Залежності:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015). **Вимоги:** §14.3–14.6; AC-C7-01,03,06,07.

**Результат для користувача:** Користувач бачить відомий показник із правильним періодом.

**Робота:** FOEN/NABEL та дозволені кантональні adapters; PM2.5/PM10/O3/NO2, station/model distinction, hourly/daily/24h fields.

**Критерії приймання:**

1. Station and parameter support підтверджено, зокрема для вибраної Lugano локації; відсутнє покриття видно.
2. O3 hourly і daily-max, NO2/PM 24h не порівнюються напряму; source measurement time відрізняється від fetch time.
3. Категорії мають офіційну шкалу/джерело; без неї показано числовий стан і user rule, без вигаданих medical risk classes.
4. Provisional/invalid/corrected data і local representativeness позначені.

**Перевірка:** Unit/aggregation/category source conformance; provisional/missing/corrected data cases.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-035"></a>

### MV2-035 — C7: Air Quality — показники, зміни та поліпшення

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** M

**Залежності:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-034](#mv2-034). **Вимоги:** §14; AC-C7-01…10.

**Результат для користувача:** Забруднення відстежується без сповіщень про кожну флуктуацію.

**Робота:** Location/station, pollutant multiselect, category/material increase, mute pollutant, adjust threshold, compare/history.

**Критерії приймання:**

1. Виконано AC-C7-01…10; релевантна зміна входить у Today і пояснює station/area match.
2. Категорійний поріг та cooldown не змішують різні aggregation periods.
3. Improved/resolved state оновлює той самий development; source unavailable не означає normal.
4. UI не робить висновок про здоров’я конкретного користувача; limitations/evidence доступні.

**Перевірка:** E2E pollutants/periods, improvement, noise suppression, unsupported station і history.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.


## F4 — Мобільність і зв’язок подій

<a id="mv2-036"></a>

### MV2-036 — Пов’язані developments із кількох джерел

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Backend + UX · **Розмір:** M

**Залежності:** [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-029](#mv2-029), [MV2-033](#mv2-033), [MV2-041](#mv2-041). **Вимоги:** §§13.7,29.

**Результат для користувача:** Повінь і закриття дороги можна розглядати разом.

**Робота:** Cross-source association за verified identifiers/geography/time; grouped overview, evidence per event, explainable linkage й reversible split.

**Критерії приймання:**

1. River danger + Alertswiss + road closure можна зв’язати з однією location story без втрати окремих authority IDs.
2. Проста близькість у часі не доводить спільну причину; непідтверджений зв’язок позначено можливим.
3. Conflicting sources показані окремо; скасування одного не закриває решту.
4. Merge/split не дублює delivery і не переносить автоматично чужі review decisions.

**Перевірка:** Three-source fixture плюс unrelated near-location negative і correction/split replay.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-037"></a>

### MV2-037 — Довідники Journey/Trip/Route/Stop і Road Corridor

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Integration + Backend · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-015](#mv2-015), [MV2-016](#mv2-016). **Вимоги:** §§9.4–9.8,10.3–10.5.

**Результат для користувача:** Транспортний subject зіставляється за стабільною сутністю.

**Робота:** GTFS/static identifiers, timetable service dates, stop/line/trip/route/journey/direction; saved road segments/corridor geometry. Без turn-by-turn routing.

**Критерії приймання:**

1. Origin/destination можуть вибрати підтверджений journey чи explicit legs; keyword city match не видається за route intersection.
2. Trip ID пов’язаний із service date, stop IDs cross-feed mapping версійний; >24h timetable підтриманий.
3. Road direction, segment і corridor IDs зіставляються окремо від railway route.
4. Reference-data refresh не губить monitors; unresolved mapping повідомляє користувача.

**Перевірка:** Static↔realtime ID fixtures, replaced timetable, overnight trip, opposite road direction.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-038"></a>

### MV2-038 — C2: Service Alerts і Trip Updates

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037). **Вимоги:** §9; AC-C2-02,06,07,08.

**Результат для користувача:** Регулярна поїздка отримує офіційний disruption state.

**Робота:** Official GTFS-RT alerts/trip updates; cancellation, partial cancel, stop/platform change, replacement, restoration; documented full/differential feed semantics.

**Критерії приймання:**

1. Усі заявлені типи зіставлені з реально доступними feed fields; відсутні platform/delay дані не вигадуються.
2. GTFS service date, entity ID, validity, delay minutes і language editions збережені.
3. Повторна відповідь, entity disappearance і expired alert мають різні семантики; deletion не гарантує restoration.
4. Auth/rate-limit контракт уточнений у джерела; технічна суперечність 2/5 req/min не вирішена здогадкою.

**Перевірка:** Protocol replay: full/differential/delete/stale, cancellation, changed stop, replacement/restoration.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-039"></a>

### MV2-039 — C2: регулярний commute і тихі транспортні alerts

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** L

**Залежності:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-038](#mv2-038). **Вимоги:** §9; AC-C2-01…10.

**Результат для користувача:** Сповіщення стосується маршруту й часу поїздки.

**Робота:** Journey/line/stop/trip selector, weekdays/window, threshold minutes, pause today, mute event; state transition NORMAL→…→RESTORED.

**Критерії приймання:**

1. Виконано AC-C2-01…10; cancellation поза route не доставляється; overlap time необхідний для immediate.
2. Поза вікном — ignore або opt-in digest за видимою policy; 1/2/3/4 minutes не спамлять за threshold10.
3. Restoration/partial resumption змінює ту саму service-day development, historical disruptions доступні.
4. Near-departure cancellation пріоритетна в deterministic queue; source stale видно до планування поїздки.

**Перевірка:** E2E commute weekdays, time/DST, threshold, partial restore, pause today і historical replay.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-040"></a>

### MV2-040 — C3: ASTRA traffic і заплановані перекриття

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037). **Вимоги:** §10; AC-C3-02,04,05,07,08.

**Результат для користувача:** Відомі дороги мають source-backed стан і планові зміни.

**Робота:** ASTRA/FEDRO permitted feed(s); DATEX/інший підтверджений формат; segment/direction, lane/full closure, incident, congestion/delay, planned windows.

**Критерії приймання:**

1. Доступ і шестимісячний строк/продовження відстежені; raw machine-readable redistribution заборонено відповідно до source policy.
2. Закриття й measured congestion/delay — різні capabilities: одного safety feed недостатньо для заяви про всі дорожні стани.
3. Planned/live events, reschedule і reopening нормалізовані; source instructions/evidence збережені в дозволеній формі.
4. A2/Gotthard/A13 coverage і напрям підтверджені; estimated_delay UNKNOWN, якщо feed його не дає.

**Перевірка:** Contract probe і replay full/lane closure, roadwork, delay missing, planned reschedule, reopened.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-041"></a>

### MV2-041 — C3: My Route Watch для A2 / Gotthard / A13

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** L

**Залежності:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-040](#mv2-040). **Вимоги:** §10; AC-C3-01…10.

**Результат для користувача:** Людина знає про значущу зміну на збереженому коридорі.

**Робота:** Multi-corridor selection, direction, event types, minimum delay, planned closures overnight, compare/source/review/history.

**Критерії приймання:**

1. Виконано AC-C3-01…10; northbound filter виключає southbound і непов’язані segment events.
2. OPEN→CLOSED, lane restriction, roadwork/accident і rescheduled closure коректно відображені.
3. Повторні traffic records однієї події об’єднуються; reopening зберігає history.
4. 15-minute threshold використовується лише за валідним delay; відсутній delay не пригнічує explicit full closure.

**Перевірка:** E2E opposite direction, planned date shift, no delay value, closure/reopen, duplicate languages.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.


## F5 — Бізнес-сценарії

<a id="mv2-042"></a>

### MV2-042 — B2: SIMAP discovery та відстеження публікацій

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011). **Вимоги:** §15; AC-B2-02,05,06,11.

**Результат для користувача:** Публічні закупівлі надходять як нові й змінені сутності.

**Робота:** Official SIMAP API/client registration, pages/cursors, publication IDs, tender dossier linking; authority/CPV/region/language/deadline/documents/Q&A.

**Критерії приймання:**

1. Публікація не поширюється до дозволеного source часу 08:00; original/commentary і required notice розділені.
2. Access to public publications не дає автоматичного доступу до restricted tender attachments; coverage кожного поля явне.
3. Corrections, cancellations, award/status і multilingual publications versioned без duplicate opportunity.
4. Backfill bounds/watermark не втрачають late publication; заборонені документи не витягуються обхідним шляхом.

**Перевірка:** Contract/API fixtures pagination, publication gate clock, corrections і public-vs-restricted attachments.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-043"></a>

### MV2-043 — B2/B7/B8: структурні профілі й semantic candidate ranking

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Backend + AI · **Розмір:** L

**Залежності:** [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-010](#mv2-010). **Вимоги:** §§15.4,15.9,16.6,17.3,19.3,22.

**Результат для користувача:** Business match кращий за слово в заголовку і зрозумілий людині.

**Робота:** Typed capability/brand/asset profiles, deterministic includes/excludes; lexical candidates then bounded optional semantic assessment; match facets and unknown gaps.

**Критерії приймання:**

1. Tender profile зберігає CPV/capabilities, regions/languages/exclusions, size/qualification constraints; score70 з прикладу не стає неперевіреним default.
2. Asset profile має category/location/keywords/brands/price; UNKNOWN price не дає «within budget».
3. SEMANTIC_MATCH має versioned score/model/evidence; hard exclusions не обходяться LLM.
4. Відсутня qualification в профілі = unknown gap, а не доведена невідповідність. DONE: implement/schema/bounded evaluation на training/validation під disabled semantic flag; independent promotion MV2-051 не є зворотною залежністю.

**Перевірка:** Independent structured/semantic match set, hard exclusion, unknown field, profile revision і preview parity.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-044"></a>

### MV2-044 — Версії наборів документів та умов

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Backend + Frontend · **Розмір:** L

**Залежності:** [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009). **Вимоги:** §§15.5,15.8,17.4,17.7,17.10.

**Результат для користувача:** Зміна файлу, вимоги чи Q&A видима після попереднього review.

**Робота:** DocumentSetManifest: stable item ID, type, URL, hash, retrieved/version time, access status; add/replace/remove; link existing exact/legal diff where applicable.

**Критерії приймання:**

1. Нове Q&A, змінений файл за тим самим URL, видалення/withdrawal документа та зміна conditions дають різні deltas.
2. Зміна порядку списку чи signed URL не створює false material update.
3. Історичний комплект і changed requirements мають посилання на точні дозволені snapshots/locators; denied attachment = unavailable, не removed.
4. Невдалий OCR/parse не створює вигаданий зміст; UI пропонує official evidence і позначає неповноту.

**Перевірка:** Golden add/replace/remove/reorder/403 documents, deadline vs body diff, historical view.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-045"></a>

### MV2-045 — B2: Tender discovery → review → material update

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** L

**Залежності:** [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-042](#mv2-042), [MV2-043](#mv2-043), [MV2-044](#mv2-044). **Вимоги:** §15; AC-B2-01…12.

**Результат для користувача:** Компанія вирішує Bid/No-bid/Monitor і бачить зміни умов.

**Робота:** Tender profile wizard, discovery candidates, follow tender, explain matched capabilities/gaps, explicit deadline, Q&A/doc changes, owner.

**Критерії приймання:**

1. Виконано AC-B2-01…12; discovery та follow/update — обидва доступні.
2. Deadline20→27, references3→5 і Q&A v3 відкривають старий review з тим самим tender ID.
3. Irrelevant opportunities suppressed; explanatory match/gaps evidence-linked і не обіцяють eligibility.
4. BID/NO_BID/MONITOR зберігає внутрішнє рішення; жодного submit bid; digest включає нові й material updates.
5. Без дозволеного capture/version/diff потрібних документів і Q&A AC-B2-08 та відповідна частина AC-B2-06 лишаються BLOCKED; metadata-only або unavailable badge не закриває цей кейс.

**Перевірка:** E2E profile→publication→review→3-field revision→reopen→digest; negatives і unavailable attachment.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-046"></a>

### MV2-046 — B7: офіційні trademark publications і register updates

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011). **Вимоги:** §16; AC-B7-02,06,08,10.

**Результат для користувача:** Є source-backed публікації й версії реєстрацій.

**Робота:** IPI/Swissreg official API після terms/account; mark/owner/representative/classes/goods-services/application/publication/registration/status.

**Критерії приймання:**

1. Автоматичний доступ, retention та допустимі in-app/email uses погоджені; search UI не використовується як доказ API licence.
2. Application, publication і registration dates не взаємозамінні; Swiss jurisdiction/rights coverage явні.
3. Owner/representative/goods-services/renewal/cancel/status updates зберігають попередній стан.
4. Відсутні mark fields не домислюються; publication evidence має стабільний official ID.

**Перевірка:** Official API contract fixtures, multilingual goods/services, status/owner corrections і rights-policy test.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-047"></a>

### MV2-047 — B7: exact, lexical і phonetic candidates

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Backend + AI/domain reviewer · **Розмір:** L

**Залежності:** [MV2-043](#mv2-043), [MV2-046](#mv2-046). **Вимоги:** §16.4–16.7; AC-B7-01,03,04,05,07.

**Результат для користувача:** Подібні назви можна знайти з поясненням підстав.

**Робота:** Multi-brand portfolio, optional word variants/owners, Unicode normalization, exact/near lexical/phonetic, class та goods/services overlap.

**Критерії приймання:**

1. ALMORA/ALMORA exact, ALMORE/ALMORIA lexical і phonetic cases відтворюються; normalization/version збережені.
2. Goods/services overlap впливає на пріоритет; однаковий class code сам собою не доводить similarity/conflict.
3. False positives по мовах виміряні; thresholds калібровані на training/validation, потім frozen. Held-out evaluation виконує MV2-051; дані held-out не використовуються для налаштування.
4. Результат candidate for IP review; немає confirmed infringement, навіть за perfect score.

**Перевірка:** Independent exact/near/phonetic/goods-services cases; accents/transliterations і unrelated class negatives.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-048"></a>

### MV2-048 — B7: IP review, строк перевірки та зміни реєстру

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** L

**Залежності:** [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-046](#mv2-046), [MV2-047](#mv2-047). **Вимоги:** §16; AC-B7-01…12.

**Результат для користувача:** Власник бренду отримує кандидат і контрольований review workflow.

**Робота:** Portfolio wizard, candidate evidence, deadline context/rule, review/relevant/not relevant/monitor/escalate decision; register updates.

**Критерії приймання:**

1. Виконано AC-B7-01…12; високий candidate доступний у Impact Inbox.
2. Calculated review deadline має source date, approved applicable rule/version, calculation trace і verification warning; unknown rule → deadline unavailable. Показано days_remaining на основі тієї самої timezone/rule revision.
3. Матеріальна зміна owner/status/goods-services відкриває review, зберігаючи минуле рішення.
4. Send to counsel у v2 — позначити/підготувати дозволений evidence export; зовнішнє надсилання потребує окремої дії користувача.

**Перевірка:** E2E multi-brand→candidate→review→register update; missing date/rule, deadline change, export rights.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-049"></a>

### MV2-049 — B8: офіційні аукціони Ticino

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Integration · **Розмір:** L

**Залежності:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011). **Вимоги:** §17.3–17.7,17.11; AC-B8-02,05,06,11.

**Результат для користувача:** Офіційна пропозиція має перевірені поля і джерело.

**Робота:** Ticino official auction source contract; real estate/vehicles/equipment capability; auction/lot IDs, dates, documents, conditions, price type, status.

**Критерії приймання:**

1. Підтверджено автоматичний доступ/повторне використання; HTML availability не оголошується API licence.
2. Current bid, estimate, starting/minimum price зберігаються як різні типи; missing bid_count/price/end = UNKNOWN.
3. Auction і lot не зливаються; cancellation/postponement/conditions/doc updates versioned.
4. Coverage категорій у Ticino перевірена; непідтримані категорії/території чесно показані, без неофіційного fallback.

**Перевірка:** Bounded official sample + multi-lot/unknown fields/cancel fixtures; parser drift tests.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-050"></a>

### MV2-050 — B8: Auction profile, price limit і ending-soon

**Статус:** PLANNED · **Пріоритет:** P1 · **Власник:** Frontend + Backend · **Розмір:** L

**Залежності:** [MV2-008](#mv2-008), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-043](#mv2-043), [MV2-044](#mv2-044), [MV2-049](#mv2-049). **Вимоги:** §17; AC-B8-01…12.

**Результат для користувача:** Покупець бачить релевантний актив і важливі зміни торгів.

**Робота:** Category/location/keywords/brand/budget, new match, price crossing, end shift, documents/conditions, cancellation; Bid/No-bid/Inspect/Monitor.

**Критерії приймання:**

1. Виконано AC-B8-01…12; supported category/location/keywords працюють; новий canton adapter не змінює domain workflow. Розширюваність підтверджена другим canton adapter conformance fixture; live rollout інших кантонів не заявляється.
2. CHF8500→12700 при limit12000 дає crossing; кожен bid increment не спамить без opt-in.
3. Ending-soon має налаштовувану кількість годин до end;24h — приклад. Перенесення строку переобчислює reminder; cancelled/unknown end не надсилається.
4. UNKNOWN ціна не проходить budget filter як нуль; action Bid не виконує ставку; історія доступна.
5. Можна stop/continue following конкретного auction, не зупиняючи discovery всього profile; історичні рішення лишаються.

**Перевірка:** E2E new auction→inspect→price/conditions/end change→reminder→cancel; unknown fields, adapter swap fixture.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.


## F6 — Докази якості, pilot та реліз

<a id="mv2-051"></a>

### MV2-051 — Незалежна перевірка matching та локального AI

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** AI + Independent domain reviewers · **Розмір:** L

**Залежності:** [MV2-023](#mv2-023), [MV2-043](#mv2-043), [MV2-047](#mv2-047). **Вимоги:** §§7,22,31,34; legacy HL-064,089,091–094,100.

**Результат для користувача:** Semantic match не отримує довіру лише через успішну схему JSON.

**Робота:** Independent gold set, held-out partition, per-case/language/negative evaluation; local model/task/locale profile approvals; semantic benchmark before feature promotion.

**Критерії приймання:**

1. Щонайменше 200 незалежно розмічених match/nonmatch пар, ≥50 для кожного B2/B7/B8; held-out split і disagreements/adjudication збережені.
2. Для calibrated business candidate ranking виміряні precision/recall per case; proposed gates ≥85% precision та ≥90% recall, без claim legal conflict accuracy.
3. 100% перевірених цитат посилаються на дозволений snapshot/field; zero invented facts/deadlines у release critical fixture set.
4. Без схваленого profile семантичний режим unavailable/extractive; deterministic results не блокуються; measured score не подається як probability без калібрування.

**Перевірка:** Повторюваний offline benchmark з report/hash/config; незалежний review без авторства тих самих очікуваних відповідей.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-052"></a>

### MV2-052 — Операційні метрики, degraded mode і відновлення джерел

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Operations + Backend · **Розмір:** M

**Залежності:** [MV2-011](#mv2-011), [MV2-012](#mv2-012), [MV2-025](#mv2-025). **Вимоги:** §§23,28,33.11–12,34; legacy HL-094,099.

**Результат для користувача:** Адміністратор бачить пропущені дані й причину затримки.

**Робота:** Per-source ingest/match/delivery lag, last-good state, error taxonomy, coverage gaps; alert on actionable source failure; renew access reminders.

**Критерії приймання:**

1. На графіках розділені source publication lag, ingest lag, processing lag і channel delivery; нуль не заміняє unknown.
2. При stale/expired licence UI й jobs виконують policy; відновлення backfills gaps без flood старих alerts.
3. AI utilization/budget/reuse та fairness measured; diagnostics має короткий timeout і не затримує відповідь.
4. Logs не містять секретів, Home coordinates чи повних user prompts; correlated job IDs достатні для підтримки.

**Перевірка:** Failure injection source/queue/provider/email/DB telemetry; bounded diagnostic lock regression.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-053"></a>

### MV2-053 — Приватність персональних locations і контроль доступу

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend + Security reviewer · **Розмір:** M

**Залежності:** [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-023](#mv2-023). **Вимоги:** §§5,27,31; inherited personal/organization access contract.

**Результат для користувача:** Приватний Home, commute і бізнес-інтерес не потрапляють у чужий простір.

**Робота:** Consent/minimization, owner-only personal scope, retention/delete/export user config, cache isolation, role checks; secrets remain current provider store.

**Критерії приймання:**

1. Session/CSRF/current role checks покривають нові endpoints, jobs, exports і evidence; IDOR tests негативні.
2. Personal coordinate precision мінімальна для matching; public corpus не містить private subject definitions.
3. Delete account/monitor виконує policy для private state/decisions, не руйнує shared official history інших workspace.
4. Cloud AI disabled by default; explicit opt-in показує які дані передаються, без прихованого location/profile disclosure.

**Перевірка:** API privacy boundary tests, deletion/export workflow, revocation during job and browser context switch.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-054"></a>

### MV2-054 — Ємність одного сервера і черги з різними пріоритетами

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Operations + Backend + AI · **Розмір:** L

**Залежності:** [MV2-011](#mv2-011), [MV2-014](#mv2-014), [MV2-043](#mv2-043), [MV2-052](#mv2-052). **Вимоги:** §§22,28,34; legacy HL-032,048,049,084,099.

**Результат для користувача:** Realtime monitoring не витісняється document ingestion або LLM.

**Робота:** Target i7/32GB/2×GTX1080 measured workload; independent deterministic/source/matching/AI queues; data growth and DB indexes; no infrastructure rewrite without evidence.

**Критерії приймання:**

1. Відтворено inherited gate:100 акаунтів,300 reads,10–20 concurrent users,20 AI jobs, parallel sync, restart і recovery. Збережено оригінальну матрицю 10 organizations,100k legal corpus/20 readers та 50-run assistant stability.
2. Додано запропонований v2 workload:1000 active subjects,10 templates, 1M observation rows; budget model і actual measurements опубліковані.
3. Збережено inherited thresholds: legacy reads p95≤500ms і enqueue≤1s на відповідному baseline workload. Proposed нові history/time-series endpoints p95≤2s, post-ingest deterministic ready≤30s вимірюються окремо; старі бюджети не послаблюються.
4. GPU OOM/degraded/offline не ламає C1–C7; 8B default дозволено лише після target hardware gate, pgvector/HA — лише за доказом потреби.

**Перевірка:** Load/restart benchmark на цільовому host або позначено BLOCKED; synthetic workstation report не закриває gate.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-055"></a>

### MV2-055 — Зберігання історії, retention та дозволений export

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend + Operations · **Розмір:** M

**Залежності:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-020](#mv2-020), [MV2-044](#mv2-044). **Вимоги:** §§27,29–30,38.

**Результат для користувача:** Історія залишається перевірною за контрольованого обсягу даних.

**Робота:** Retention per source/data class, raw/normalized states, compaction/downsampling policy, evidence pinning for delivered revisions, export manifests.

**Критерії приймання:**

1. Delivered development/decision evidence не губиться через telemetry compaction; old/new потрібні для diff залишаються доступні в дозволеній формі.
2. Retention/rights conflict потребує durable permitted raw або normalized snapshot із provenance, достатнього для historical compare. Expiry notice/link не замінює доказ; якщо достатню форму не можна зберігати, G(case) і affected AC лишаються BLOCKED.
3. ASTRA raw export/API заблокований, SIMAP originals/commentary відділені, BAZG/IP permissions застосовані.
4. History export відтворює provenance/state/rule/decision revisions; персональні дані доступні тільки авторизованому scope.

**Перевірка:** Retention time travel, restore archived evidence, forbidden raw export і cross-tenant export negatives.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-056"></a>

### MV2-056 — Міграція, сумісність і rollback rehearsal

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Backend + Operations + QA · **Розмір:** L

**Залежності:** [MV2-001](#mv2-001), [MV2-053](#mv2-053), [MV2-055](#mv2-055), [MV2-060](#mv2-060). **Вимоги:** §§1,26–27,30; legacy HL-048,049,098.

**Результат для користувача:** Перехід на v2 зберігає чинних користувачів і MVP-докази.

**Робота:** Additive Alembic migrations, resumable bridge backfill, dry-run/checkpoints, dual-read/shadow comparison, feature flag rollout; backup→restore in isolated env.

**Критерії приймання:**

1. До/після збережені organization/member/session/watch/topic IDs, review/unread/preferences, source packs, artifact hashes, analyses/citations.
2. Повторна міграція, interruption і частковий backfill не дублюють records або notifications.
3. Legacy API/URLs/Ask/Today/Basel journey/Page guide працюють; shadow parity report фіксує deliberate differences.
4. Rollback flags + compatible code/schema та verified DB restore відпрацьовані; тег MVP без відповідного backup не вважається rollback БД.

**Перевірка:** Production-shaped sanitized snapshot rehearsal, row/hash counts, restart/resume, rollback та regression report.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-057"></a>

### MV2-057 — Виконуваний набір 126 AC та adversarial regression

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** QA + Domain reviewers · **Розмір:** L

**Залежності:** [MV2-027](#mv2-027), [MV2-029](#mv2-029), [MV2-031](#mv2-031), [MV2-033](#mv2-033), [MV2-035](#mv2-035), [MV2-036](#mv2-036), [MV2-039](#mv2-039), [MV2-041](#mv2-041), [MV2-045](#mv2-045), [MV2-048](#mv2-048), [MV2-050](#mv2-050), [MV2-024](#mv2-024), [MV2-051](#mv2-051), [MV2-053](#mv2-053), [MV2-056](#mv2-056), [MV2-068](#mv2-068). **Вимоги:** Усі AC-CORE/C1–C7/B2/B7/B8; §§29–34.

**Результат для користувача:** Повнота v2 доведена конкретними сценаріями, а не кількістю комітів.

**Робота:** AC-linked integration/browser tests, versioned official fixtures with licence/provenance; positive/negative/material/nonmaterial/history/roles for each template.

**Критерії приймання:**

1. Кожний із126 source AC має виконуваний check або reviewer protocol і evidence reference; supplemental coverage також перевірена.
2. Replay same batch twice/restart/out-of-order/translation duplicate/429/source disappearance/model offline не порушує invariants.
3. Нуль critical defects: cross-tenant leak, false official all-clear, invented numerical/legal fact, duplicate internal delivery, lost review.
4. Немає tests які лише повторюють implementation; gold fixtures незалежні, live freshness contract перевіряється окремо.
5. Постійна відсутність required source capability (forecast, delay, docs/Q&A або deadline) залишає affected AC відкритим. UNKNOWN — правильна поведінка окремого record, не заміна обов’язкової функції всього template.

**Перевірка:** Full suite plus ten domain demo recordings, contract reports і independent evidence spot-check.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-058"></a>

### MV2-058 — Виміряний B2C/B2B pilot

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Product + QA + Operations · **Розмір:** L

**Залежності:** [MV2-002](#mv2-002), [MV2-024](#mv2-024), [MV2-051](#mv2-051), [MV2-054](#mv2-054), [MV2-057](#mv2-057). **Вимоги:** §34; legacy HL-088,090,101.

**Результат для користувача:** Підтверджено, що люди розуміють зміни й повертаються до моніторингу.

**Робота:** Proposed four-week pilot:≥10 B2C учасників і≥5 organizations; representative coverage усіх десяти cases; sparse events supplement by labelled historical replay.

**Критерії приймання:**

1. Для кожного template зафіксовані eligible sample, precision/materiality/duplicates, explanation helpfulness, decisions і time-to-understand.
2. Proposed targets: delivered relevance≥90%, material-change precision≥90%, understandable why≥90%, duplicate rate<1%, first value≤5min setup та median understand≤60s.
3. Actionability вимірюється без мінімуму, що змушує вигадувати дії; no-action може бути корисним рішенням.
4. Недостатній sample або blocked source = explicit incomplete evidence; replay не видається за live pilot, thresholds не видаються за досягнуті.

**Перевірка:** Анонімізований pilot report з denominators, confidence/limitations, defects та рішенням expand/fix/hold.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-059"></a>

### MV2-059 — Приймання і реліз Helvetic Lens Monitoring v2.0

**Статус:** PLANNED · **Пріоритет:** P0 · **Власник:** Release owner + Product + Operations · **Розмір:** M

**Залежності:** [MV2-025](#mv2-025), [MV2-052](#mv2-052), [MV2-054](#mv2-054), [MV2-055](#mv2-055), [MV2-056](#mv2-056), [MV2-057](#mv2-057), [MV2-058](#mv2-058). **Вимоги:** §§33,39–40; full v2 scope.

**Результат для користувача:** Версія v2 може бути відновлена, перевірена і підтримувана.

**Робота:** Release checklist, immutable source/tag, manifest/checksums/build versions, migrations/backup/restore, source credentials/licence renewal runbook, release notes.

**Критерії приймання:**

1. Усі required задачі цього беклогу DONE, усі126 AC accepted, усі10 templates мають allowed source та end-to-end evidence; MV2-059 закривається фінальним release evidence.
2. Жоден required кейс не пропущений заради назви2.0; часткові milestones маркуються preview/limited pilot.
3. Перевірено fresh install і upgrade, rollback restore, підтримані мови, source/export policy; критичні дефекти відсутні.
4. MVP tag незмінний; production rollout окрема явно погоджена операція з health/rollback checks.

**Перевірка:** Independent go/no-go checklist, release artifact restore/build verification і post-deploy checks лише після deployment authorization.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.


## Відкладений обсяг — не входить до v2.0

<a id="mv2-061"></a>

### MV2-061 — Після v2.0: опційний customs purchase calculator

**Статус:** DEFERRED · **Пріоритет:** P2 · **Власник:** Product + Backend · **Розмір:** S

**Залежності:** [MV2-027](#mv2-027). **Вимоги:** §11.8 — explicitly future.

**Результат для користувача:** Можна оцінити зміну CHF valuation для заданої покупки.

**Робота:** Optional purchase amount/currency, official rate basis і deterministic delta; не загальний розрахунок мита/податку.

**Критерії приймання:**

1. Source rights дозволяють розрахунок; optional amount не потрібна для primary rate watch.
2. Previous/current CHF basis та delta пояснюють rate/nominal units/rounding; не дають tax liability claim.

**Перевірка:** Decimal/unit calculation та optional form checks.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-062"></a>

### MV2-062 — Після v2.0: нові кантони аукціонів і розширений tender workflow

**Статус:** DEFERRED · **Пріоритет:** P2 · **Власник:** Product + Integration · **Розмір:** L

**Залежності:** [MV2-045](#mv2-045), [MV2-050](#mv2-050). **Вимоги:** §§15.10,17.11 — explicitly future.

**Результат для користувача:** Розширення охоплення відбувається без другої архітектури.

**Робота:** Additional cantonal source packs після окремого source gate; за підтвердженою потребою QUALIFY/SUBMITTED/CLOSED/AWARDED/NOT_AWARDED.

**Критерії приймання:**

1. Кожне джерело має власний rights/coverage dossier; це не автоматична обіцянка national coverage.
2. Нові decision states не змінюють стару history і не виконують bid submission; пріоритет уточнюється лише через canonical backlog.

**Перевірка:** Adapter conformance і backward-compatible decision tests.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-063"></a>

### MV2-063 — Умовно: pgvector після доведеного recall gap

**Статус:** DEFERRED · **Пріоритет:** P2 · **Власник:** Product + Architect · **Розмір:** M

**Залежності:** [MV2-051](#mv2-051), [MV2-054](#mv2-054). **Вимоги:** legacy HL-024.

**Результат для користувача:** Збережено відкладене зобов’язання без розширення поточного release scope.

**Робота:** Зберегти HL-024: спершу виміряти direct-context retrieval; pgvector в existing PostgreSQL лише якщо покращення доведене.

**Критерії приймання:**

1. Немає v2 prerequisite на vector DB; benchmark порівнює citations/recall/latency/cost.
2. Exact version context і direct fallback зберігаються.

**Перевірка:** Окремий evidence report за умовою активації; реалізація лише після внесення рішення й пріоритету в цей беклог.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-064"></a>

### MV2-064 — Умовно: relation graph після перевірки користі

**Статус:** DEFERRED · **Пріоритет:** P2 · **Власник:** Product + Architect · **Розмір:** M

**Залежності:** [MV2-021](#mv2-021), [MV2-036](#mv2-036), [MV2-058](#mv2-058). **Вимоги:** legacy HL-053.

**Результат для користувача:** Збережено відкладене зобов’язання без розширення поточного release scope.

**Робота:** Зберегти HL-053: list-vs-graph user experiment; існуючий relation review лишається доступний.

**Критерії приймання:**

1. No-benefit результат завершує експеримент без обов’язкової побудови графа.
2. Граф не замінює доказовий список і не змінює статус непідтверджених зв’язків.

**Перевірка:** Окремий evidence report за умовою активації; реалізація лише після внесення рішення й пріоритету в цей беклог.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-065"></a>

### MV2-065 — Умовно: кілька серверів / HA за виміряною потребою

**Статус:** DEFERRED · **Пріоритет:** P2 · **Власник:** Product + Architect · **Розмір:** M

**Залежності:** [MV2-054](#mv2-054), [MV2-056](#mv2-056). **Вимоги:** legacy HL-056.

**Результат для користувача:** Збережено відкладене зобов’язання без розширення поточного release scope.

**Робота:** Зберегти HL-056: перейти до scale/HA design лише за зафіксованим bottleneck або recovery requirement.

**Критерії приймання:**

1. Є measured necessity і resource plan; не додається Kubernetes/microservices заради шаблонів.
2. Дотримані job identity, storage, tenancy, backup/restore та Git host contracts.

**Перевірка:** Окремий evidence report за умовою активації; реалізація лише після внесення рішення й пріоритету в цей беклог.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-066"></a>

### MV2-066 — Умовно: наступні два кантональні regulatory packs

**Статус:** DEFERRED · **Пріоритет:** P2 · **Власник:** Product + Architect · **Розмір:** M

**Залежності:** [MV2-068](#mv2-068). **Вимоги:** legacy HL-081.

**Результат для користувача:** Збережено відкладене зобов’язання без розширення поточного release scope.

**Робота:** Зберегти HL-081: два окремо названі й перевірені пакети законодавства після Basel; не плутати з C1 coverage або B8 Ticino.

**Критерії приймання:**

1. Кожний pack має незалежні rights/parser/drift/localization/history/acceptance докази.
2. Автоматично не активується лише через завершення new-domain connectors.

**Перевірка:** Окремий evidence report за умовою активації; реалізація лише після внесення рішення й пріоритету в цей беклог.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

<a id="mv2-067"></a>

### MV2-067 — Поза десятьма кейсами: opt-in public-discourse pilot

**Статус:** DEFERRED · **Пріоритет:** P2 · **Власник:** Product + Architect · **Розмір:** M

**Залежності:** [MV2-058](#mv2-058). **Вимоги:** legacy HL-082.

**Результат для користувача:** Збережено відкладене зобов’язання без розширення поточного release scope.

**Робота:** Зберегти HL-082 як поза v2.0: щонайбільше два джерела commentary після окремого рішення про зміну scope.

**Критерії приймання:**

1. Окремі source rights, expiry/diversity/noise/usefulness/corrections/removal gates.
2. Неофіційне commentary ніколи не змішується з authoritative facts; explicit org opt-in до alerts.

**Перевірка:** Окремий evidence report за умовою активації; реалізація лише після внесення рішення й пріоритету в цей беклог.

**Evidence виконання:** ще немає; записати commit, tests/protocol, source/fixture version, reviewer та limitations при закритті.

## Трасування та зміни плану

[126 AC + 79 додаткових вимог](docs/monitoring-v2/REQUIREMENTS_TRACEABILITY.md) · [Legacy disposition](docs/monitoring-v2/LEGACY_DISPOSITION.md) · [Архітектура](docs/monitoring-v2/ARCHITECTURE.md) · [Офіційні джерела](docs/monitoring-v2/SOURCE_FEASIBILITY.md).

| Версія | Дата | Зміна |
|---|---|---|
| 1.0 | 2026-09-10 | Повний план десяти сценаріїв, source gates, generic extension, MVP compatibility, 126 AC/79 supplemental, 35 legacy dispositions; нові фічі не реалізовано |
