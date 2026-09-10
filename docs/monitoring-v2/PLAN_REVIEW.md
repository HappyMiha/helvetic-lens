# Monitoring v2 — перевірка плану

Дата: 2026-09-10. Версія плану: 1.2. Перевірено **документацію та цілісність плану**, не реалізацію v2.

## Контроль повноти

- 71 унікальний MV2 ID: 62 required, 9 DEFERRED.
- 126 точних первинних AC збережено: 116 активних (20 CORE, 60 C1/C2/C3/C5/C6/C7, 36 B2/B7/B8), 10 AC-C4 відкладено.
- 79 додаткових груп вимог S-01…S-79, кожна має відповідальну задачу.
- 35 non-DONE legacy HL-пунктів мають MV2 successors; старий текст збережено без зміни статусів.
- Перевірено існування task references, ациклічність залежностей, Markdown paths/anchors, закриті code fences, незмінність вихідної специфікації та legacy content.

## Незалежне рев’ю й виправлення

Окремо перевірено відповідність специфікації та сумісність із поточною архітектурою. До завершення плану усунено такі неоднозначності:

1. MV2-003 може завершити dossier з blocked outcome; credentials одного джерела не зупиняють усі інші.
2. ID відкладених задач нормалізовані до трьох цифр.
3. Калібрування semantic thresholds виконується на training/validation; held-out використовується лише для незалежного gate.
4. Старі read/enqueue budgets збережено окремо від нового time-series workload.
5. Implementation під feature flag відокремлено від model promotion, щоб не створювати приховані цикли приймання.
6. Expiry notice або official link не замінює дозволений retained evidence для історичного порівняння.
7. Metadata-only tender integration не закриває required document/Q&A version-diff acceptance.
8. Auction ending-soon hours налаштовуються; 24h є прикладом. Stop/continue окремого auction не вимикає profile discovery.
9. Today має явні Review / Evidence / Not relevant, IP deadline — days_remaining та verification state.

## Зміна scope за рішенням користувача

C4 «Митні курси» позначено як можливу майбутню реалізацію без поточної розробки. MV2-026/027 перенесено в LATER/P2/DEFERRED; MV2-061 залишається відкладеним. В активних задачах немає залежностей на відкладені задачі. UI має 6 Personal + 3 Business templates, 8 subject types і 4 Source Packs. C4 discovery/licensing, pilot і acceptance виключені; 10 AC-C4 та S-41/42/43 збережені з DEFERRED, змішані S-вимоги мають явні scope notes. Спільний числовий engine залишається активним для C5/C6/C7/B8. Повернення C4 потребує нового явного рішення користувача, не лише доступного API.

## Перша поставка Pollen Watch

За наступним рішенням користувача додані явні MV2-069/070/071, підвищено MV2-030/031 до P0 і змінено їхні залежності на незалежні C5 contracts. Перевіряється, що транзитивні predecessors MV2-071 — тільки MV2-001/069/070/030/031, без full-v2 source/UI/business/pilot gates. Shared parent acceptance зберігається для решти scope. Уточнено contribution semantics трасування: підготовчі MV2-069/070 не потребують передчасно виконати live end-to-end AC, який приймається в MV2-031/071; це усуває неявний цикл приймання. Окремо перевірено відсутність BAZG/C4 rights-вимоги в активному retention/export gate. Повний C5 вимагає official observation **та forecast**; окремо визначені privacy/a11y/language/ops acceptance і готовий протокол першої хвилі ≥5 реальних B2C людей. Тестування ще не проводилося, його майбутні результати не підміняються планом.

## Межі результату

Нові конектори не написано, облікові записи не створено, source terms не прийнято, платні ліцензії не придбано. Код застосунку, migrations, production, модель і release tag MVP не змінено. Усі task implementation evidence поки відсутні; джерела мають власні доступові й функціональні gates.

Значення KPI, pilot samples і нових performance targets — запропоновані критерії цього плану. Вони не є вимогами автора специфікації або виміряними результатами поточного продукту.
