# Helvetic Lens Monitoring v2 — перевірка здійсненності джерел

Перевірено: **2026-09-10**. Предмет: десять use cases C1–C7, B2, B7, B8. Це перевірка офіційної документації та публічних сторінок для планування, а не успішний end-to-end тест конекторів. Облікових записів не створено, умови від імені власника продукту не прийнято, ключі/API з авторизацією не тестувалися. API-документація підтверджує можливість інтеграції, але не її поточну працездатність з майбутнього середовища Helvetic Lens.

**Зміна scope, версія 1.1:** користувач відніс C4 до можливих майбутніх функцій і виключив із розробки. Нижче збережено попередні факти дослідження десяти кейсів; поточна робота та source gates стосуються лише дев’яти активних. C4 не має поточних discovery, API probe, licensing або delivery tasks.

## Реєстр рішень для беклогу

| Use case | Перевірений стан | Рішення до розробки |
|---|---|---|
| C1 — цивільні небезпеки | Офіційна публікація Alertswiss підтверджена; підтримуваний публічний API/ліцензія автоматичного перевидання не підтверджені | Discovery gate на канал одержання, дозволи і lifecycle повідомлень |
| C2 — громадський транспорт | Документований GTFS-RT API, API key, Protobuf, прив'язка до static GTFS | Реалізація після sandbox contract test; узгодити суперечливі ліміти |
| C3 — автодорожній рух | Документований DATEX II/SOAP API з ключем; спеціальні умови FEDRO | Правила доступу й експорту закласти до платформи, продовження доступу — операційна залежність |
| C4 — митний FX | XML існує, але на сторінці явне обмеження SIX на використання/розповсюдження третіми особами | **DEFERRED — можливо реалізувати; не брати в розробку.** Факт про права збережений лише для майбутнього рішення; gate v2.0 відсутній |
| C5 — пилок | Офіційні CSV через STAC API, вільне використання з атрибуцією | Найкращий кандидат на перший повний вертикальний сценарій |
| C6 — вода | Офіційна GraphQL API, вимірювання, live feed; суперечлива документація довжини live window | Contract spike, watermark/reconciliation; окремо дослідити офіційні flood warnings |
| C7 — повітря | NABEL: 16 станцій; кантональні портали мають дані/API, єдиний live NABEL endpoint не підтверджений | Пілот на конкретному перевіреному наборі; географію не перебільшувати |
| B2 — тендери | Офіційний API, публічні publications/search без user auth; окремий доступ до документів | API-first; окремі правила часу публікації, атрибуції, виправлень і gated documents |
| B7 — IP/торговельні марки | Офіційний IPI API для trademark/patent, підписані умови + account | Почати оформлення доступу; не планувати scraping Swissreg як основний канал |
| B8 — аукціони | Поточний офіційний сайт eGant має публічні listings; API/feed/reuse permission не підтверджені | Обмежений discovery на read-only monitoring, права й статуси; не автоматизувати ставки |

## C1 — Alertswiss / кантональні небезпеки

**Факти.** Alertswiss є каналом конфедерації та кантонів; інфраструктуру веде BABS/FOCP, а повідомлення зазвичай створюють кантональні органи. Рівні: alarm, warning, information; all-clear/expiry/removal завершують актуальність. Покриття включає Швейцарію та Ліхтенштейн. Підтримуються DE/FR/IT/EN, однак видавець не зобов'язаний надати всі переклади. Рішення, чи публікувати подію, ухвалює відповідний орган. [Alertswiss FAQ](https://www.alert.swiss/en/faq.html).

**Непідтверджено.** У перевірених офіційних сторінках не знайдено підтримуваного зовнішнього API contract, умов повторного використання feed, SLA чи дозволеного poll rate. Неофіційний JSON endpoint, навіть якщо його використовує сайт, не є достатнім підтвердженням.

**Планування.** Gate має дати supported endpoint/channel, license/reuse scope, issuer/event identifiers, територіальну геометрію, update/cancel/all-clear semantics та fixtures. Продукт зберігає офіційні інструкції з джерелом і мовою; переклад та пояснення відділяються від тексту органу. Missing/failed source не перетворюється на «небезпек немає». Кантональні додаткові джерела — окремі contracts, а не обіцянка автоматичного повного покриття.

## C2 — opentransportdata GTFS-RT

**Факти.** Feed надає відомі realtime changes у трьохгодинному вікні для операторів, які передають realtime data; він узгоджений зі static GTFS. Потрібен API key. Cookbook документує Protobuf, редиректи, 30-секундний cache і максимум дві заявки за хвилину; JSON призначений для тестування. [GTFS-RT cookbook](https://opentransportdata.swiss/en/cookbook/realtime-prediction-cookbook/gtfs-rt/). Водночас загальна сторінка лімітів вказує п'ять запитів/хвилину для GTFS RT і service alerts — це явна суперечність документації, не підстава мовчки обрати більший ліміт. [Limits and costs](https://opentransportdata.swiss/en/limits-and-costs/).

**Умови.** Загальні Open Data terms дозволяють обробку та публікацію; service-based data потребують реєстрації; слід посилатися на джерело, підтримувати актуальність raw data та публікувати власні аналізи від свого імені. Умови FEDRO застосовуються окремо до дорожніх даних. [Open Data terms](https://opentransportdata.swiss/en/terms-of-use/).

**Планування.** Глобальний спільний fetch/cache для всіх watchlists, Protobuf adapter, версіонування static GTFS, stop/trip/date matching, unknown realtime fallback. Початкова консервативна межа — не частіше 30 секунд на спільний feed; confirm actual grant/429 behavior. Дискретні service alerts та trip updates треба перевіряти окремо. Повнота поїздок не дорівнює повноті realtime даних усіх операторів.

## C3 — ASTRA / FEDRO traffic

**Факти.** Офіційний API передає поточні дорожні situations у DATEX II через SOAP; потрібні API key і SoapAction. Є updates, revocations і planned roadworks. Revoked situation залишається доступною 60 хвилин; history API не надає. [Traffic situations cookbook](https://opentransportdata.swiss/en/cookbook/road-traffic-cookbook/traffic-situations/).

**Умови.** FEDRO terms станом на червень 2026 передбачають реєстрацію, стандартний доступ на шість місяців та можливість продовження за обґрунтуванням. Партнерський доступ має окремі умови. Передавання raw data третім особам через machine-readable interface заборонено. Для публікації результатів обробки встановлено атрибуцію FEDRO TDP; не можна створювати поведінкові профілі або реідентифікувати людей на дорогах. [FEDRO terms](https://opentransportdata.swiss/en/tac-fedro/).

**Планування.** Per-source `allow_raw_export=false`; жодного загального raw JSON/API/export для цього джерела. Підтвердження дозволеного переліку derived fields — gate до user API. Зберігати rights policy разом із source/record, контролювати expiry credentials/access, планувати продовження раніше шести місяців. Локальний event ledger потрібен для історії, за дозволеною retention policy; event identity та revocation reconciliation — обов'язкові.

## C4 — BAZG customs exchange rates (DEFERRED)

**Факти.** Офіційна сторінка пропонує щоденні курси і XML. Прямо вказано copyright SIX Financial Information та заборону використання/подальшого розповсюдження третіми особами; доступність щоденних курсів не гарантується. [BAZG Devisenkurse](https://www.bazg.admin.ch/de/devisenkurse-verkauf).

**Майбутня можливість.** Поточних робіт і блокера v2.0 немає; навіть link-out placeholder не є вимогою. Лише після нового явного рішення користувача повернути C4 потрібна перевірка source rights, яка не є доказом технічної непридатності XML. Майбутній discovery має встановити: право одержання, зберігання, показу, threshold alerts, commercial redistribution, export, history; відповідальний і вартість. Ліцензований альтернативний курс не можна непомітно називати митним курсом BAZG. Після gate потрібні base/quote currency, unit multiplier, value date, effective date та non-trading-day semantics; це різні поняття.

## C5 — MeteoSwiss pollen

**Факти.** Національна мережа має 15 станцій; з 2023 року автоматичні погодинні вимірювання семи груп пилку. Різні методи історичних і автоматичних вимірювань не слід безпосередньо змішувати. Офіційний STAC API надає станційні CSV; OGD можна використовувати з атрибуцією MeteoSwiss. [Pollen stations](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a7-pollen-stations). Changelog від 17.07.2026 підтверджує оновлення погодинних `h_now` файлів кожні 20 хвилин. [Pollen cadence change](https://opendatadocs.meteoswiss.ch/changelog/1.2.0).

**Перший implementation gate MV2-069.** Наведені джерела підтверджують observation dataset; окремий usable official forecast channel, його rights та station/allergen coverage ще не доведені. G(C5-forecast) потребує власного dated contract і дозволеного live sample до приймання повного Pollen Watch. Forecast mock не закриває цей gate; це конкретний ризик першої поставки.

**Планування.** Визначати station applicability, час спостереження та час публікації окремо. 20 хвилин — інтервал оновлення файлу, погодинність — гранулярність вимірювання. Відсутній таксон/значення не означає нуль. Порогові watchlists — за конкретним таксоном, станцією/обґрунтованою областю, unit і rolling window. Не обіцяти персональну медичну оцінку чи точність на кожній вулиці. Перевірити anonymous STAC fetch із deployment environment, метадані одиниць та поточні infrastructure terms.

## C6 — FOEN / BAFU water and floods

**Факти.** Офіційна документація описує GraphQL для hydrological observations, station metadata, aggregates та live feed. Є provisional/validated/definitive releaseState. Запит обмежено 10 000 рядками; перевищення відхиляється, не обрізається. Документація суперечлива: вступ згадує 7-денне live window, примітка — що `data_live` не повертає рядки старші 12 годин. Примітка також вказує затримку появи вимірювання 9–19 хвилин. [Water observations](https://api.data-platform.cloud.bafu.admin.ch/dataproduct-water-observations). Ліцензія платформи дозволяє комерційне й некомерційне використання з автором, назвою та посиланням на набір. [BAFU licence](https://api.data-platform.cloud.bafu.admin.ch/en/lizenz-und-quelle).

**Планування.** Contract test фактичного live window, pagination, timezone UTC, corrections і data freshness — до commitment SLA. Сталі water-level/discharge/temperature thresholds прив'язати до станції, параметра та одиниці. Measurements, flood forecasts і official danger warnings — окремі source types; перший не замінює два останні. Вимірювання температури/стоку не є підтвердженням придатності води для купання. Не робити висновок «безпечно» з відсутності warning feed.

## C7 — NABEL / cantonal air

**Факти.** NABEL вимірює забруднення на 16 станціях, які представляють різні умови; значення поточного року попередні. [NABEL data query](https://www.bafu.admin.ch/en/data-query-nabel). Кантональний портал Basel-Stadt має конкретний dataset Basel-Binningen із API/export tab і полями O3, NO2, PM10, PM2.5 та інших величин. Відкрита таблиця містить також пропуски — наявність timestamp не гарантує значення кожного pollutant. [Basel-Binningen dataset](https://data.bs.ch/explore/dataset/100051/table/).

**Непідтверджено.** Єдиний офіційно документований NABEL live measurements API, актуальна cadence для цього canton dataset, його права та coverage усієї країни не доведені цією перевіркою. Геосервіс із розташуванням станцій не є API поточних вимірювань.

**Планування.** Gate вибирає конкретні station datasets з machine-readable endpoint, ліцензією, pollutant units, interval definitions та freshness contract. Пілотний canton coverage явно показувати користувачеві. Розрізняти numeric observation, short-term air-quality index і regulatory annual limits; threshold має явно визначену тривалість агрегації. Власний екологічний сигнал не подавати як офіційну медичну рекомендацію.

## B2 — SIMAP procurement

**Факти.** Офіційний FAQ посилається на API documentation і заявку API client. Доступ до tender documents у UI потребує login, ролі компанії та interest declaration. [SIMAP FAQ](https://www.simap.ch/de/help/faq). API terms дозволяють publications/search без користувацької автентифікації; доступ до іншого відповідає ролі account. Комерційне повторне використання publication data дозволене, але контент не можна змістовно змінювати, коментарі мають бути візуально відділені; потрібні disclaimer, quality notices і публікація виправлень. Дані дозволено відкривати третім особам від 08:00 дня появи. Умови повинні поширюватися на отримувачів. API наразі безкоштовний, майбутні зміни можливі. [SIMAP legal / API terms](https://www.simap.ch/de/about/legal).

**Непідтверджено.** Swagger page доступна як адреса, але schema не витягнута text browser; точні endpoints, quotas, client setup і scope для protected attachments потребують contract spike. Наявність anonymous publication search не підтверджує anonymous attachments.

**Планування.** Machine-readable source policies: `publication_not_before`, original/commentary separation, correction propagation, access tier. Нормалізувати CPV, canton, buyer, deadline, currency/value якщо вони є, lots, award/cancellation/amendments. Calendar timezone визначити як Europe/Zurich після перевірки провайдера. Не натискати interest declaration від імені користувача автоматично. Gated documents залишаються links до дозволеного доступу, поки не погоджено інший потік.

## B7 — IPI / Swissreg trademarks and patents

**Факти.** IPI офіційно надає trademark та patent records через безкоштовний API після підписання terms; сторінка містить посилання на технічну документацію. [IPI data delivery API](https://www.ige.ch/de/uebersicht-dienstleistungen/digitales-angebot/ip-daten/datenabgabe-api). Умови вимагають account і підписаного прийняття; credentials не передаються третім особам. Використання для mailings заборонено; raw data redistribution переносить обов'язки на отримувача; не можна створювати враження офіційних даних продукту. [IPI data-delivery terms](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/d/Nutzungsbedingungen-Datenabgabe.pdf).

**Coverage.** Swissreg містить активні CH trademarks/applications і певні deleted records, також міжнародні marks з designation CH. Нові CH applications зазвичай з'являються до шести робочих днів; пошук publications обмежений CH marks. База не гарантує вичерпного виявлення схожих/конфліктних marks. [Swissreg trademark coverage](https://www.ige.ch/de/uebersicht-dienstleistungen/digitales-angebot/datenbanken-und-verzeichnisse/swissreg/markendatenbank).

**Планування.** Spike одержує account grant, scopes, quotas, delta/continuation, update cadence та sample fixtures. Зіставлення API scope з UI coverage обов'язкове. Пояснити значення provider restriction «mailings» для user-requested monitoring channels до запуску email alerts; не трактувати самостійно як автоматичний дозвіл. Формувати explainable candidate matches за словом, owner, Nice classes і publication changes; висновок «порушення IP» не автоматизувати. Загальний raw export має наслідувати умови джерела.

## B8 — офіційні Ticino auctions

**Факти.** Поточний офіційний сайт Aste UEF публікує online lots із поточними цінами, кількістю bids і closing time. [Aste UEF listings](https://www.aste.ti.ch/it/). Чинні terms eGant від 09.04.2026 описують реєстрацію для участі, можливість автоматичного bidding agent на самому майданчику, обов'язковість ставки та можливість припинення аукціону разом із провадженням. [Aste UEF terms](https://www.aste.ti.ch/it/condizioni_generali). Старе офіційне повідомлення 2010 року про відсутність онлайн-ставок не можна використовувати як опис нинішнього eGant.

**Непідтверджено.** Supported public API/RSS, reuse permission, допустима cadence, охоплення окремих очних/нерухомих аукціонів і наявність повного архіву. Публічна ціна не є licence для масового отримання.

**Планування.** Discovery має окремо картувати eGant movable lots та офіційні notices нерухомості/очних auctions, якщо вони входять у вимогу. Після rights gate — read-only listing monitor з ID, canton/office, category, place, deadline/status, changed/cancelled/relisted. Власні deadline reminders використовують актуальну версію closing time. Ставки, реєстрація участі та платежі поза monitoring scope. Parser/browser fallback допускається лише після підтвердження права та як contract зі schema-drift detection, без обходу доступу.

## Спільні acceptance gates, що випливають із перевірки

1. **Source registry before ingestion:** publisher, exact dataset/API, purpose, access grant, licence URL/version/check date, polling limit, publication delay, attribution, raw/derived export permission, retention, source timestamp contract, scope/coverage.
2. **Connection proof:** дозволений sample fetch з цільового середовища, schema fixture, auth failure/rate-limit behavior, empty vs failed response, source corrections/removals, latency measurements. Наявність документації цього не замінює.
3. **Rights enforcement end to end:** обмеження діють в UI, alerts, downloads, organisation sharing, API, evidence snapshots, logs і support tooling. ASTRA raw-data restriction та SIMAP publication gate — конкретні regression cases.
4. **No global SLA from scrape cadence:** окремо вимірювати upstream publication lag, ingestion lag, matching lag і delivery lag; user promise не може бути швидшим за джерело. Контрольні приклади: hourly pollen updated every 20 minutes; IP publication може відставати на робочі дні; historical/live window розрізняються.
5. **Closure outcomes:** кожен source discovery закінчується `approved implementation contract`, `approved scoped alternative` або `blocked with named external dependency`; UI має відображати capability availability, а не маскувати source blocker як порожні результати.
