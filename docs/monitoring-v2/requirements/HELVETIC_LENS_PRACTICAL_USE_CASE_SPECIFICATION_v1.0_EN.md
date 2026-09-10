# HELVETIC LENS — PRACTICAL USE CASE SPECIFICATION — English reading edition

**Version:** 1.0  
**Status:** Final shortlist  
**Scope:** 10 practical use cases  
**Segments:** B2C + B2B  
**Country:** Switzerland  
**Product:** Helvetic Lens  
**Primary principle:** `authoritative source → change → relevance → evidence → decision`

---

# 1. Purpose

The purpose of this specification is to map ten concrete practical scenarios onto the existing functional architecture of **Helvetic Lens**, enabling their implementation without turning the product into ten separate applications.

Helvetic Lens is already built around the core sequence:

```text
source
  → document/data
  → version/state
  → comparison
  → AI-assisted impact
  → review state
```

After a scan, the system can store:

- version history;
- comparison;
- AI history;
- evidence;
- review state;
- severity;
- owner;
- actions;
- digest visibility.

The existing product structure already includes:

- `Today`
- `Monitoring`
- `Topics`
- `Discover`
- `Sources`
- `Impact Inbox`
- `Impact Matrix`
- `Digests`

The backend is already designed to retrieve web/PDF/API sources and support normalization, version storage, diffs and background processing.

Therefore, the task is not to create ten independent verticals.

The target model:

> **10 Monitoring Templates over one Change Intelligence Engine.**

---

# 2. Final Use Case Registry

| ID | Segment | Use Case |
|---|---|---|
| **C1** | B2C | Local Hazard Watch |
| **C2** | B2C | Public Transport Disruption Watch |
| **C3** | B2C | My Route Watch — Gotthard / A2 / A13 |
| **C4** | B2C | Swiss Customs Rate Watch |
| **C5** | B2C | Pollen Exposure Watch |
| **C6** | B2C | River / Lake / Flood Watch |
| **C7** | B2C | Air Quality Watch |
| **B2** | B2B | Public Tender Watch |
| **B7** | B2B | Trademark & IP Watch |
| **B8** | B2B | Public Auction Watch |

---

# 3. Common Functional Model

All ten use cases must follow the same basic functional pattern.

```text
USER DEFINES WHAT MATTERS
        ↓
MONITORING SUBJECT
        ↓
AUTHORITATIVE SOURCE
        ↓
NEW EVENT / NEW STATE / NEW VERSION
        ↓
NORMALIZATION
        ↓
COMPARE WITH PREVIOUS STATE
        ↓
MATERIAL CHANGE?
        ↓
RELEVANT TO THIS USER / ORGANIZATION?
        ↓
TODAY / IMPACT INBOX
        ↓
WHAT CHANGED?
WHY DOES IT MATTER?
WHAT IS THE EVIDENCE?
        ↓
USER DECISION
        ↓
REVIEW HISTORY
        ↓
CONTINUE MONITORING
```

---

# 4. Three Types of Change

Helvetic Lens must handle three types of change consistently.

## 4.1 Event Change

Something new has happened.

Examples:

- an official warning is issued;
- a train is cancelled;
- a road section is closed;
- a tender is published;
- a trademark is registered;
- a new auction appears.

```text
NOT PRESENT
    ↓
NEW EVENT
```

---

## 4.2 State Change

The object existed previously, but its state has changed.

Examples:

```text
Pollen
MODERATE → HIGH

River
1.82 m → 2.31 m

Road
NORMAL → CONGESTED

Customs EUR rate
0.9412 → 0.9547
```

---

## 4.3 Existing Event Updated

An already known event has been updated.

Examples:

```text
Tender deadline:
20 Sep → 27 Sep

Auction end:
14:00 → 18:00

Hazard:
Level 3 → Level 4

Road closure:
one lane → full closure
```

This is where the existing `version history + comparison + evidence` capabilities give Helvetic Lens particularly strong product value.

---

# 5. Common Monitoring Subject

For any use case, the user creates an understandable **Monitoring Subject**, not a technical `source`.

Examples:

```text
My Home
My commute
A2 / Gotthard
EUR customs rate
Birch pollen
Lake Lugano
Air quality Lugano
AI software tenders
ALMORA trademark
Real estate auctions Ticino
```

Basic universal structure:

```yaml
monitoring_subject:
  id:
  name:
  type:
  scope:
  source_pack:
  filters:
  thresholds:
  importance_rule:
  notification_rule:
  owner:
  status:
```

---

# 6. Common Event Lifecycle

Recommended universal lifecycle model:

```text
DISCOVERED
    ↓
MATCHED
    ↓
MATERIAL
    ↓
DELIVERED
    ↓
OPENED
    ↓
REVIEWED
```

After `REVIEWED`:

```text
ACTION_REQUIRED
NO_ACTION
NOT_RELEVANT
MONITOR
RESOLVED
```

If the source changes an event that has already been reviewed:

```text
REVIEWED
   ↓
MATERIAL UPDATE
   ↓
REOPENED
```

This is particularly important for:

- hazards;
- public transport;
- road traffic;
- tenders;
- auctions.

---

# 7. Common Relevance Contract

Every delivered event must answer the question:

> **Why am I seeing this?**

Examples:

```text
Because the warning affects Massagno.

Because this route is part of your saved commute.

Because EUR moved more than your 1% threshold.

Because you monitor birch pollen in Lugano.

Because this tender matches AI + document processing.

Because this new trademark is similar to ALMORA.

Because this auction matches your acquisition profile.
```

`Relevance Reason` must be a required structured field of the event, not optional AI-generated text.

---

# 8. C1 — Local Hazard Watch

## 8.1 Objective

Give a person the ability to say:

> **Tell me when an official warning affects where I live, work or regularly stay.**

The user should not have to check Alertswiss, MeteoSwiss or cantonal resources constantly.

Helvetic Lens must report only changes that intersect with the **user's specific locations**.

---

## 8.2 Primary Actor

Private resident.

Additional variants:

- a second-home owner;
- a family;
- a person who regularly works in another city;
- a person whose children attend school in another location;
- a country-house owner;
- a traveller within Switzerland.

---

## 8.3 User Story

```text
As a resident,
I want Helvetic Lens to monitor official hazard information
for locations important to me,
so that I am notified when the situation materially changes.
```

---

## 8.4 Monitoring Configuration

```yaml
monitor:
  name: Home
  type: LOCATION
  country: CH
  canton: TI
  municipality: Massagno

hazards:
  - flood
  - storm
  - forest_fire
  - heavy_snow
  - power_outage
  - civil_protection_warning

minimum_importance:
  warning_or_higher: true
```

The user can create multiple locations:

```text
Home
Office
Parents
School
Holiday house
```

---

## 8.5 Authoritative Sources

Primary source family:

- Alertswiss / Federal Office for Civil Protection;
- official federal warning feeds;
- relevant cantonal warning feeds.

Source Packs can be extended without changing the use case.

---

## 8.6 Normalized Event Model

```yaml
hazard:
  hazard_id:
  hazard_type:
  title:
  authority:
  publication_time:
  effective_from:
  effective_until:
  status:
  severity:
  certainty:
  geographic_scope:
  canton:
  municipalities:
  instructions:
  source_url:
  source_version:
```

---

## 8.7 Material Change Rules

Material:

```text
new warning
warning level increased
warning level decreased materially
affected geography expanded
affected geography reduced
instructions changed
start/end time changed materially
warning cancelled
all-clear issued
```

Not material:

```text
formatting change
translation correction
metadata refresh
timestamp refresh without substantive change
```

---

## 8.8 Example

Previous state:

```text
Forest fire danger:
HIGH
```

New state:

```text
Forest fire danger:
VERY HIGH

New instruction:
Absolute fire ban.
```

Helvetic Lens:

```text
LOCAL HAZARD UPDATE

Forest fire restrictions changed near Home

Previous:
High fire danger

Now:
Very high fire danger
Absolute fire ban introduced

Why you received this:
The affected area includes one of your monitored locations.

Source:
Official Swiss authority

Action:
Review official instructions
```

---

## 8.9 Severity

### CRITICAL

- immediate danger;
- evacuation;
- shelter instruction;
- major civil protection alert.

### HIGH

- new prohibition;
- significant hazard;
- major escalation.

### MEDIUM

- meaningful advisory;
- situation deteriorating.

### INFORMATIONAL

- warning downgraded;
- resolved;
- non-actionable update.

---

## 8.10 User Actions

```text
View evidence
Open official source
Mark reviewed
Not relevant
Mute this hazard type
Continue monitoring
```

Material escalation:

```text
Previously reviewed
        ↓
Warning materially changed
        ↓
Review reopened
```

---

## 8.11 Existing Helvetic Lens Mapping

| Requirement | Existing HL capability |
|---|---|
| Official source | Sources |
| Automatic monitoring | Scheduler / jobs |
| New event | Today |
| Historical version | Version history |
| Compare warning | Comparison |
| Explain relevance | AI-assisted impact |
| Important unresolved warning | Impact Inbox |
| History | Review state |
| Periodic recap | Digests |

---

## 8.12 Minimal Functional Extensions

### Location Selector

```text
country
canton
municipality
optional coordinates
optional radius
```

### Geographic Match

```text
event geography
INTERSECTS
watched location
```

### Hazard Lifecycle

```text
NEW
UPDATED
ESCALATED
DOWNGRADED
CANCELLED
RESOLVED
```

No major architectural redesign required.

---

## 8.13 Acceptance Criteria

```text
AC-C1-01 User can save at least one Swiss location.
AC-C1-02 System detects a new official hazard affecting that location.
AC-C1-03 Hazard outside monitored area is not delivered.
AC-C1-04 Material severity change produces a new change event.
AC-C1-05 Update is linked to the previous warning.
AC-C1-06 Previous and current state can be compared.
AC-C1-07 Official source is accessible from the alert.
AC-C1-08 User can mark the event reviewed.
AC-C1-09 Cancellation/all-clear closes the active event.
AC-C1-10 Technical refreshes do not create duplicate alerts.
```

---

# 9. C2 — Public Transport Disruption Watch

## 9.1 Objective

The user says:

> **Tell me when something changes on the public transport journeys I regularly use.**

The goal is not to monitor all Swiss public transport, but to track the user's **specific journey, line, stop or commute**.

---

## 9.2 Primary Actor

- commuter;
- student;
- business traveller;
- family;
- person regularly travelling between two cities.

---

## 9.3 User Story

```text
As a commuter,
I want Helvetic Lens to monitor my regular public-transport journey,
so that I know when a disruption can affect my planned travel.
```

---

## 9.4 Monitoring Configuration

```yaml
journey:
  name: Work commute
  origin: Lugano
  destination: Zurich HB

schedule:
  weekdays:
    - MON
    - TUE
    - WED
    - THU
    - FRI

relevant_time:
  from: "06:30"
  to: "09:00"

notify:
  cancellation: true
  station_closure: true
  route_change: true
  replacement_transport: true
  delay_threshold_minutes: 10
```

Other possible Monitoring Subjects:

```text
Line 2
Station Lugano
Bus route X
Train IC2
Lugano → Bellinzona
```

---

## 9.5 Authoritative Source

Official Swiss public transport open-data / realtime feeds.

Preferred structured data:

- GTFS-RT;
- Service Alerts;
- Trip Updates;
- related official transport datasets.

---

## 9.6 Transport Entity Model

```yaml
transport_subject:
  stop:
  line:
  trip:
  route:
  journey:
  direction:
  planned_time_window:
```

---

## 9.7 Monitored Change Types

```text
trip cancellation
partial cancellation
delay
stop closure
platform/boarding-location change
route modification
replacement transport
service disruption
service restored
```

---

## 9.8 Relevance Logic

Step 1:

```text
Does affected trip/line/stop intersect the saved journey?
```

If no:

```text
IGNORE
```

Step 2:

```text
Does disruption overlap user's relevant travel window?
```

If no:

```text
LOW / DIGEST ONLY
```

If yes:

```text
DELIVER
```

---

## 9.9 Noise Reduction

The user must not receive:

```text
Train delayed 1 min
Train delayed 2 min
Train delayed 3 min
Train delayed 4 min
```

A state model is needed:

```text
NORMAL
DELAY_MINOR
DELAY_MATERIAL
MAJOR_DISRUPTION
CANCELLED
RESTORED
```

An alert is created on a meaningful state transition, not on every telemetry update.

---

## 9.10 Example

Initial state:

```text
07:12
Lugano → Zürich HB
NORMAL
```

New state:

```text
07:29
Service disruption
Bellinzona – Arth-Goldau
```

Today card:

```text
YOUR COMMUTE IS AFFECTED

A disruption has been reported on a route
used by your Lugano → Zürich journey.

Current status:
Disrupted

Why you received this:
This event intersects your saved commute.

Official source:
Swiss public transport realtime data
```

---

## 9.11 Event Update

Twenty minutes later:

```text
Previous:
Major disruption

Current:
Services resuming with delays
```

Helvetic Lens must update **the same development**, not create a new independent card.

---

## 9.12 User Actions

```text
Review
Open official transport information
Mute this event
Ignore delays below X minutes
Pause commute monitoring today
Continue monitoring
```

---

## 9.13 Existing HL Mapping

```text
Sources          → public transport feed
Monitoring       → saved journey
Today            → relevant disruptions
Comparison       → previous/current disruption state
Impact Inbox     → severe disruptions
Digest           → disruption history
Review state     → seen/resolved
```

---

## 9.14 Minimal Extensions

Required:

### Transport Entity Model

```text
Stop
Line
Trip
Route
Journey
```

### Time-aware Matching

```text
route match
+
weekday
+
time-window relevance
```

### Ephemeral Event Expiry

Transport events must expire or resolve automatically.

---

## 9.15 Acceptance Criteria

```text
AC-C2-01 User can define a regular journey.
AC-C2-02 Relevant cancellation is detected.
AC-C2-03 Unrelated Swiss transport events are suppressed.
AC-C2-04 User-defined delay threshold is respected.
AC-C2-05 Repeated delay updates are deduplicated.
AC-C2-06 Major status transition creates a material update.
AC-C2-07 Restored service closes the active event.
AC-C2-08 Official evidence/source is retained.
AC-C2-09 Alerts can be filtered by weekday/time.
AC-C2-10 Historical disruption remains available after resolution.
```

---

# 10. C3 — My Route Watch — Gotthard / A2 / A13

## 10.1 Objective

```text
Tell me when the state of the roads I regularly use
changes enough to affect my journey.
```

Primary Swiss examples:

```text
A2
Gotthard road tunnel
Gotthard corridor
A13
```

---

## 10.2 Primary Actor

- private driver;
- cross-cantonal commuter;
- frequent traveller between Ticino and German-speaking Switzerland;
- logistics-oriented private user;
- family planning regular road travel.

---

## 10.3 Monitoring Configuration

```yaml
route:
  name: Lugano - Zurich
  roads:
    - A2
    - Gotthard

direction:
  northbound: true

notify:
  full_closure: true
  lane_closure: true
  accident: true
  heavy_congestion: true
  roadworks: true

minimum_delay:
  minutes: 15
```

Possible subjects:

```text
specific motorway
specific tunnel
specific pass
specific corridor
specific road segment
```

---

## 10.4 Authoritative Sources

Primary source family:

- FEDRO / ASTRA;
- Traffic Data Platform;
- official safety-related traffic messages;
- planned closure notices.

---

## 10.5 Road State Model

```yaml
road_state:
  road_id:
  segment:
  direction:
  timestamp:
  state:
  closure_type:
  congestion_level:
  estimated_delay:
  incident_type:
  planned:
  valid_from:
  valid_until:
  source:
```

---

## 10.6 Change Types

```text
NORMAL → CONGESTED
CONGESTED → HEAVY_CONGESTION
OPEN → PARTIALLY_CLOSED
OPEN → CLOSED
CLOSED → OPEN
new accident
new roadworks
new safety restriction
planned closure announced
planned closure rescheduled
```

---

## 10.7 Example — Planned Closure

Monday:

```text
Gotthard tunnel
Night closure
23:00–05:00
12 Sep
```

Tuesday update:

```text
12 Sep → 13 Sep
```

Helvetic Lens:

```text
PLANNED CLOSURE CHANGED

Gotthard road tunnel

Previous:
12 September, 23:00–05:00

Now:
13 September, 23:00–05:00

Why you received this:
Gotthard is part of your monitored route.
```

---

## 10.8 Example — Live Traffic

```text
MY ROUTE UPDATE

A2 northbound

Previous:
Normal traffic

Current:
Major congestion

Potential impact:
Your monitored corridor is currently affected.

Evidence:
Official ASTRA traffic data

Action:
Review journey before departure.
```

---

## 10.9 Product Boundary

Helvetic Lens should **not** become Google Maps.

It does not need:

- navigation;
- turn-by-turn instructions;
- consumer route planning engine.

Its role:

```text
monitor known route
detect meaningful state change
explain change
show authoritative evidence
```

---

## 10.10 Existing HL Reuse

```text
Monitoring     → route
Source         → ASTRA
Scheduler      → polling
Version        → traffic-state snapshot
Comparison     → state delta
Today          → relevant event
Impact Inbox   → major closure
Digest         → route developments
```

---

## 10.11 Minimal Extensions

```text
Road/segment entity
direction
location/segment intersection
state thresholds
event expiration
planned vs live event distinction
```

---

## 10.12 Acceptance Criteria

```text
AC-C3-01 User can save one or more monitored road corridors.
AC-C3-02 Closure affecting the corridor generates an alert.
AC-C3-03 Opposite/unrelated corridor events can be filtered.
AC-C3-04 Live status is compared with previous state.
AC-C3-05 Planned closure changes are versioned.
AC-C3-06 Duplicate traffic messages collapse into one development.
AC-C3-07 Reopening/resolution changes event state.
AC-C3-08 Official evidence is retained.
AC-C3-09 User can configure materiality.
AC-C3-10 Historical events remain queryable.
```

---

# 11. C4 — Swiss Customs Rate Watch

## 11.1 Objective

Monitor the **official Swiss customs exchange rate**, rather than a generic FX market price.

The user says:

> **Tell me when the official EUR customs rate changes materially.**

---

## 11.2 Primary Actor

- frequent cross-border shopper;
- person importing higher-value goods;
- online shopper buying abroad;
- individual regularly purchasing in EUR/USD.

---

## 11.3 Why This Is Different from Currency App

Generic currency app:

```text
EUR/CHF market price
```

Helvetic Lens:

```text
official customs conversion rate
used for Swiss import valuation
```

Helvetic Lens monitors an **authoritative state**, not a market ticker.

---

## 11.4 Monitoring Configuration

```yaml
monitor:
  currency: EUR

rule:
  notify_if_change_percent_greater_than: 1.0

optional:
  purchase_value:
    value: 1500
    currency: EUR
```

Other currencies may include:

```text
USD
GBP
JPY
etc.
```

---

## 11.5 State Model

```yaml
customs_rate:
  currency:
  rate:
  effective_date:
  previous_rate:
  absolute_change:
  percentage_change:
  source:
```

---

## 11.6 Example

Previous:

```text
EUR customs rate:
0.9412
```

Current:

```text
EUR customs rate:
0.9547
```

Helvetic Lens calculates:

```text
absolute delta
direction
percentage change
```

Then:

```text
SWISS CUSTOMS RATE CHANGED

EUR

Previous:
0.9412

Current:
0.9547

Change:
+1.43%

Why you received this:
Your alert threshold is 1.0%.

Source:
Federal Office for Customs and Border Security
```

---

## 11.7 Trigger Types

```text
NEW_DAILY_VALUE
THRESHOLD_CROSSED
SIGNIFICANT_DAILY_CHANGE
SIGNIFICANT_WEEKLY_CHANGE
```

Do not alert for:

```text
0.94120 → 0.94121
```

unless the user explicitly asks for every change.

---

## 11.8 Optional Impact Calculation

Not required for first MVP.

Future capability:

```text
Purchase:
EUR 2,000

Previous CHF customs basis:
X

Current:
Y

Difference:
Z CHF
```

Main use case must remain useful **without** a purchase calculator.

---

## 11.9 Existing HL Reuse

```text
Source
Scheduler
Observed state
Version
Comparison
Today
Review history
Digest
```

---

## 11.10 New Generic Capability Created by C4

C4 introduces a reusable capability:

# Numeric State Monitor

```yaml
numeric_state:
  observed_value:
  previous_value:
  delta:
  percentage_delta:
  threshold:
  threshold_crossed:
```

The same capability is reused by:

- C5 Pollen;
- C6 River/Lake/Flood;
- C7 Air Quality;
- parts of B8 Public Auction.

---

## 11.11 Acceptance Criteria

```text
AC-C4-01 User can select currency.
AC-C4-02 Official rate is stored with effective date.
AC-C4-03 Previous rate is retained.
AC-C4-04 Delta is calculated deterministically.
AC-C4-05 User can configure alert threshold.
AC-C4-06 Changes below threshold do not generate alert.
AC-C4-07 Every value links to authoritative evidence.
AC-C4-08 Rate history can be displayed.
AC-C4-09 No generic market FX is presented as customs rate.
AC-C4-10 Digest can summarize material rate changes.
```

---

# 12. C5 — Pollen Exposure Watch

## 12.1 Objective

```text
Tell me when the pollen I care about
changes materially around my location.
```

---

## 12.2 Primary Actor

- person who wants to monitor pollen exposure;
- parent monitoring environmental conditions for a child;
- outdoor worker;
- athlete;
- person planning outdoor activity.

This use case provides environmental information and must not provide diagnosis or treatment advice.

---

## 12.3 Monitoring Configuration

```yaml
location:
  city: Lugano

monitor_allergens:
  - birch
  - grasses

notify:
  when_level_at_least: high
  notify_on_rapid_increase: true
```

---

## 12.4 Monitoring Unit

Not:

```text
all pollen in Switzerland
```

But:

```text
ALLERGEN
+
LOCATION / STATION
```

Examples:

```text
Birch @ Lugano
Grass @ Lugano
```

---

## 12.5 State Model

```yaml
pollen_state:
  station:
  allergen:
  measurement_time:
  concentration:
  category:
  previous_category:
  trend:
  observed_or_forecast:
  source:
```

---

## 12.6 Material Change

Examples:

```text
LOW → MODERATE
MODERATE → HIGH
HIGH → VERY_HIGH
HIGH → LOW
rapid increase
```

Primary trigger should preferably be **category/state transition**, not every numerical fluctuation.

---

## 12.7 Example

```text
POLLEN LEVEL INCREASED

Birch pollen
Lugano area

Previous:
Moderate

Current:
High

Why you received this:
You monitor birch pollen in this area.

Source:
MeteoSwiss / SwissPollen

Suggested action:
Consider this information when planning outdoor activity
and follow your usual allergy-management plan.
```

---

## 12.8 Forecast vs Measurement

Two distinct object types:

### Observed

```text
What is happening now?
```

### Forecast

```text
What is expected?
```

UI must not mix them.

Example:

```text
OBSERVED: Moderate
FORECAST TOMORROW: High
```

---

## 12.9 Existing HL Reuse

```text
Source         → MeteoSwiss / SwissPollen
Monitoring     → allergen + location
Snapshot       → current measurement
Comparison     → state change
Today          → threshold crossing
Digest         → historical changes
```

---

## 12.10 Minimal Extensions

```text
location → monitoring station mapping
numeric/category state
threshold rule
forecast vs observed distinction
```

---

## 12.11 Acceptance Criteria

```text
AC-C5-01 User selects location.
AC-C5-02 User selects one or more pollen types.
AC-C5-03 Current official measurement is stored.
AC-C5-04 Category transitions are detected.
AC-C5-05 User threshold is respected.
AC-C5-06 Measurement and forecast are visually distinct.
AC-C5-07 User receives no medical diagnosis.
AC-C5-08 Evidence identifies source/station/time.
AC-C5-09 Small fluctuations do not create notification spam.
AC-C5-10 Historical state remains available.
```

---

# 13. C6 — River / Lake / Flood Watch

## 13.1 Objective

```text
Monitor the water bodies or measuring stations
that matter to me and tell me when their state changes materially.
```

---

## 13.2 Primary Actors

Possible scenarios:

```text
My house is close to river X.
I own a boat on lake Y.
I regularly fish at location Z.
I want to know when flood danger changes.
I care about water temperature.
```

---

## 13.3 Monitoring Configuration

```yaml
monitor:
  station: X

measurements:
  - water_level
  - discharge
  - water_temperature
  - flood_danger

alert:
  flood_level_change: true
  water_level_threshold: 2.50
```

---

## 13.4 Normalized State

```yaml
hydrology_state:
  station_id:
  water_body:
  location:
  timestamp:
  water_level:
  discharge:
  temperature:
  flood_danger_level:
  quality_status:
  source:
```

---

## 13.5 Change Rules

### Absolute Threshold

```text
water level > 2.5 m
```

### Relative Change

```text
+30 cm within defined period
```

### Official State Transition

```text
flood danger 1 → 2
2 → 3
3 → 4
```

Official danger state should generally outrank a user-defined raw numerical threshold.

---

## 13.6 Example

```text
FLOOD RISK INCREASED

Monitored station:
River X

Previous:
Danger level 2

Current:
Danger level 3

Water level:
1.94 m → 2.38 m

Why you received this:
This is one of your monitored stations
and the official danger level increased.

Source:
FOEN
```

---

## 13.7 Cross-Source Intelligence Opportunity

A core differentiation is not simply duplicating an existing hydrology alert.

Helvetic Lens can potentially correlate:

```text
river danger increased
+
Alertswiss warning issued
+
road near monitored location closed
```

and represent them as one coherent development affecting the same location.

This is substantially more valuable than an isolated threshold notification.

---

## 13.8 Existing HL Reuse

```text
Monitoring
Sources
Numeric snapshots
Versioning
Comparison
Today
Impact Inbox
Review
Digest
```

---

## 13.9 Minimal Extensions

```text
station selector
location mapping
numeric state
official danger-state interpretation
threshold rule
state transition
```

---

## 13.10 Acceptance Criteria

```text
AC-C6-01 User can select a station/water body.
AC-C6-02 System stores current official measurement.
AC-C6-03 New data is compared against previous state.
AC-C6-04 Threshold crossing generates change event.
AC-C6-05 Official flood danger escalation is prioritised.
AC-C6-06 Repeated identical state does not generate duplicate alerts.
AC-C6-07 User can configure custom threshold.
AC-C6-08 Source timestamp is clearly displayed.
AC-C6-09 Reversal/downgrade updates the same development.
AC-C6-10 Historical measurements/change events remain accessible.
```

---

# 14. C7 — Air Quality Watch

## 14.1 Objective

```text
Tell me when official air-quality conditions
around a monitored area materially deteriorate or improve.
```

---

## 14.2 Primary Actor

- resident;
- parent;
- runner;
- cyclist;
- outdoor worker;
- person interested in local environmental conditions.

This use case provides official environmental information. It should not diagnose disease or infer personal medical risk.

---

## 14.3 Monitoring Configuration

```yaml
location:
  city: Lugano

pollutants:
  - PM2.5
  - PM10
  - O3
  - NO2

notify:
  category_change: true
  material_increase: true
```

---

## 14.4 State Model

```yaml
air_quality_state:
  station:
  location:
  timestamp:
  o3_hourly:
  o3_daily_max:
  no2_24h:
  pm10_24h:
  pm25_24h:
  source:
  quality_status:
```

---

## 14.5 Materiality

Prefer meaningful transition rather than raw-change spam.

```text
NORMAL → ELEVATED
ELEVATED → HIGH
HIGH → NORMAL
```

Exact categories should be based on official interpretation where applicable.

Helvetic Lens must not invent medical risk classes from raw measurements.

---

## 14.6 Example

```text
AIR QUALITY CHANGED

Lugano

PM2.5:
Previous state: Normal
Current state: Elevated

Why you received this:
You monitor particulate pollution in Lugano.

Official measurement:
NABEL / FOEN

Note:
Conditions may vary locally from the monitoring/modelled value.
```

---

## 14.7 User Actions

```text
View measurements
View source
Reviewed
Mute pollutant
Adjust threshold
Continue monitoring
```

---

## 14.8 Existing HL Mapping

```text
Source
Monitoring
Observed state
Version
Delta
Today
Review
Digest
```

---

## 14.9 Minimal Extension

No unique major extension is required if C4–C6 are already implemented.

Reuse:

# Numeric State Monitoring Engine

plus:

```text
station/location mapping
pollutant dimensions
threshold semantics
```

---

## 14.10 Acceptance Criteria

```text
AC-C7-01 User can choose a supported location/station.
AC-C7-02 User can choose pollutant(s).
AC-C7-03 Observations preserve source timestamp.
AC-C7-04 Previous/current states can be compared.
AC-C7-05 Materiality rules suppress minor fluctuation.
AC-C7-06 Source limitations are visible.
AC-C7-07 Helvetic Lens does not present medical diagnosis.
AC-C7-08 Relevant change appears in Today.
AC-C7-09 Resolved/improved state updates existing development.
AC-C7-10 Data history is retained.
```

---

# 15. B2 — Public Tender Watch

## 15.1 Business Objective

```text
Tell my company when a Swiss public-sector procurement opportunity
matches what we sell,
and tell us when a tender we are following changes.
```

This use case has to provide more value than a normal keyword subscription.

---

## 15.2 Primary Actors

```text
Sales
Business Development
Bid Manager
CEO of SME
Pre-sales
Legal
```

---

## 15.3 Two Distinct Jobs

### Tender Discovery

```text
Is there a new opportunity relevant to us?
```

### Tender Change Monitoring

```text
Has anything changed in an opportunity we are already pursuing?
```

Both are required.

---

## 15.4 Company Tender Profile

Example:

```yaml
company:
  name: Example AI SA

capabilities:
  - artificial intelligence
  - document processing
  - software development
  - business automation

regions:
  - Ticino
  - Zurich
  - Bern
  - Federal

languages:
  - IT
  - DE
  - EN

excluded:
  - hardware-only procurement
  - construction

minimum_relevance:
  score: 70
```

---

## 15.5 Tender Data Model

```yaml
tender:
  tender_id:
  title:
  contracting_authority:
  publication_date:
  submission_deadline:
  procedure_type:
  location:
  cpv_codes:
  description:
  eligibility_requirements:
  award_criteria:
  documents:
  questions_answers:
  status:
  source:
```

---

## 15.6 New Tender Flow

```text
SIMAP publishes tender
        ↓
Helvetic Lens ingests publication
        ↓
extracts structured information
        ↓
matches against company profile
        ↓
relevance score
        ↓
if relevant:
Today / Impact Inbox
```

---

## 15.7 Example

```text
NEW TENDER MATCH

AI-supported document processing platform

Authority:
Federal organisation

Deadline:
30 September

Match:
HIGH

Why this matches your company:
• document processing
• AI/software
• Swiss implementation
• relevant geography

Potential gaps:
• requirement X not found in company profile

Decision:
BID
NO-BID
REVIEW
MONITOR
```

---

## 15.8 Tender Change Monitoring

This is where Helvetic Lens becomes more valuable than a simple search subscription.

Existing tender:

```text
Deadline:
20 Sep
```

Updated:

```text
Deadline:
27 Sep
```

New document:

```text
Questions & Answers — Version 3
```

Requirement changed:

```text
Previous:
3 references required

Current:
5 references required
```

Helvetic Lens:

```text
MATERIAL TENDER UPDATE

Tender ABC

3 material changes detected

1. Deadline
20 Sep → 27 Sep

2. Reference requirement
3 → 5

3. New document
Q&A v3

Impact:
Your bid preparation should be reviewed.
```

---

## 15.9 Relevance Model

### Deterministic Layer

```text
CPV
location
language
procurement category
deadline
contracting authority
```

### Semantic Layer

Compare:

```text
tender scope
vs
company capabilities
```

### Exclusions

```text
products/services company does not provide
contract-size constraints
geographic exclusions
language constraints
mandatory qualification gaps
```

AI may explain the match, but it must not silently decide to bid.

---

## 15.10 Review States

Full possible lifecycle:

```text
NEW
QUALIFY
BID
NO_BID
MONITOR
SUBMITTED
CLOSED
AWARDED
NOT_AWARDED
```

For Helvetic Lens MVP:

```text
REVIEW
BID
NO_BID
MONITOR
```

is sufficient.

---

## 15.11 Existing HL Mapping

| HL Component | Tender Use |
|---|---|
| Topics | Company procurement interests |
| Sources | SIMAP |
| Today | New relevant tenders |
| Version History | Tender publication versions |
| Comparison | Changed deadline/requirements/docs |
| Impact | Why it matches company |
| Impact Inbox | Opportunities needing decision |
| Digests | New/updated opportunity summary |
| Review State | Bid / no-bid / monitor |

---

## 15.12 Product Differentiation

Helvetic Lens should not be positioned as:

> “We email you when keyword AI appears.”

It should be:

> **A tender relevant to your company appeared. Here is why it matches, what requirements matter, what changed since you last reviewed it, and what decision is currently required.**

---

## 15.13 Minimal Extensions

```text
Tender entity
Company capability profile
Deterministic qualification rules
Semantic relevance scoring
Deadline state
Document-set change detection
Bid / No-bid decision state
```

---

## 15.14 Acceptance Criteria

```text
AC-B2-01 Company can define procurement interest profile.
AC-B2-02 New SIMAP publication can become a candidate.
AC-B2-03 Irrelevant tenders are suppressed.
AC-B2-04 Relevant tender explains why it matched.
AC-B2-05 User can open authoritative tender evidence.
AC-B2-06 Tender updates create new versions.
AC-B2-07 Material deadline change is detected.
AC-B2-08 Added/changed documentation is detected.
AC-B2-09 User can choose Bid / No-bid / Monitor.
AC-B2-10 Previously reviewed tender is reopened on material update.
AC-B2-11 Duplicate publication records do not produce duplicate opportunities.
AC-B2-12 Digest can summarize new and materially updated tenders.
```

---

# 16. B7 — Trademark & IP Watch

## 16.1 Business Objective

```text
Monitor official Swiss trademark publications
and tell us when a new registration or register change
may matter to one of our brands.
```

---

## 16.2 Primary Actors

```text
Founder
CEO
Legal
Brand Manager
Marketing
IP Counsel
Compliance
```

---

## 16.3 Core User Story

```text
As a brand owner,
I want Helvetic Lens to monitor official Swiss trademark publications,
so that I can review potentially relevant new marks or register changes
before I miss an important decision window.
```

---

## 16.4 User Configuration

```yaml
brand:
  name: ALMORA

jurisdiction:
  Switzerland

monitor:
  exact_name: true
  similar_names: true

relevant_classes:
  - class_x
  - class_y

word_variants:
  - optional

owners_of_interest:
  - optional
```

Multiple monitored brands:

```text
ALMORA
PULSANTO
Product A
Product B
```

---

## 16.5 Trademark Entity

```yaml
trademark:
  mark_id:
  mark:
  mark_type:
  owner:
  representative:
  classes:
  goods_services:
  application_date:
  publication_date:
  registration_date:
  status:
  source:
```

---

## 16.6 Candidate Generation

There should be multiple levels.

### Level 1 — Exact

```text
ALMORA
vs
ALMORA
```

### Level 2 — Near Lexical

```text
ALMORA
ALMORE
ALMORA AI
ALMORIA
```

### Level 3 — Phonetic

Potentially similar pronunciation.

### Level 4 — Goods/Services Relevance

Name similarity alone is not enough.

```text
sign similarity
+
goods/services overlap
```

must influence candidate priority.

---

## 16.7 Important Safety Boundary

Helvetic Lens must never automatically conclude:

```text
INFRINGEMENT
```

or:

```text
LEGAL CONFLICT CONFIRMED
```

Correct terminology:

```text
Potentially relevant
Potential similarity
Candidate for IP review
Possible conflict
```

The final legal assessment belongs to the user or qualified IP professional.

---

## 16.8 Example

```text
POTENTIAL TRADEMARK MATCH

Monitored brand:
ALMORA

New publication:
ALMORIA

Similarity:
HIGH

Goods/services overlap:
PARTIAL

Source:
Official Swiss trademark publication

Why you received this:
The new mark is similar to a monitored brand
and overlaps with relevant goods/services.

Decision:
REVIEW
SEND TO IP COUNSEL
NOT RELEVANT
MONITOR
```

---

## 16.9 Deadline Handling

The system should capture:

```yaml
deadline_context:
  official_publication_date:
  applicable_deadline_rule:
  calculated_review_deadline:
  days_remaining:
  verification_required: true
```

For legally sensitive action, UI should explicitly state:

```text
Verify the legal deadline before filing.
```

Deadline computation must remain evidence-linked and auditable.

---

## 16.10 Change Monitoring

Not only new trademarks.

Existing monitored trademark may change:

```text
owner changed
representative changed
renewed
cancelled
goods/services changed
register information changed
status changed
```

Each material register update becomes a new version/state.

---

## 16.11 Review Workflow

```text
NEW CANDIDATE
      ↓
IP REVIEW
      ↓
NOT RELEVANT
or
MONITOR
or
ESCALATE
```

Optional organizational state:

```text
COUNSEL REVIEW REQUIRED
```

Helvetic Lens should not initiate legal proceedings in MVP.

---

## 16.12 Existing HL Reuse

```text
Topic/Profile       → trademark portfolio
Sources             → Swiss trademark publication source
Today               → new candidate
Evidence            → official publication
Comparison          → register changes
AI impact           → explain similarity/relevance
Impact Inbox        → high candidate
Review state        → review/ignore/escalate
Digest              → IP watch summary
```

---

## 16.13 Minimal Extensions

### Trademark Entity

```text
mark
owner
classes
goods/services
publication date
status
```

### Similarity Candidate Generator

```text
exact
lexical
phonetic
class overlap
```

### Generic Deadline Capability

```text
source event date
+
deadline rule
+
calculated deadline
+
verification flag
```

This capability can later be reused by:

- Tender Watch;
- Auction Watch.

---

## 16.14 Acceptance Criteria

```text
AC-B7-01 Organization can register monitored brands.
AC-B7-02 New Swiss trademark publications are ingested.
AC-B7-03 Exact matches are detected.
AC-B7-04 Similarity candidates can be generated.
AC-B7-05 Goods/services relevance affects priority.
AC-B7-06 Source publication is preserved as evidence.
AC-B7-07 System never labels candidate as confirmed infringement.
AC-B7-08 Publication date is stored.
AC-B7-09 Relevant deadline can be displayed with verification warning.
AC-B7-10 Register changes produce a new version/change.
AC-B7-11 Reviewer can classify event as Relevant / Not relevant / Monitor.
AC-B7-12 High-relevance candidates can appear in Impact Inbox.
```

---

# 17. B8 — Public Auction Watch

## 17.1 Business Objective

```text
Tell us when an official Swiss public auction
contains an asset we may want to acquire,
and tell us if the auction conditions later change.
```

For MVP, Ticino is a practical starting geography.

---

## 17.2 Primary Actors

```text
real-estate investor
construction company
vehicle trader
equipment buyer
reseller
asset manager
SME looking for machinery/furniture/equipment
```

---

## 17.3 User Profiles

### Example A — Real Estate

```yaml
auction_watch:
  category: real_estate
  canton: TI

locations:
  - Lugano
  - Mendrisio

maximum_price:
  value: 1500000
  currency: CHF
```

### Example B — Vehicles

```yaml
auction_watch:
  category: vehicles

brands:
  - Mercedes
  - BMW

maximum_price:
  value: 40000
  currency: CHF
```

### Example C — Business Equipment

```yaml
auction_watch:
  category: equipment

keywords:
  - server
  - industrial equipment
  - machinery
```

---

## 17.4 Normalized Auction Model

```yaml
auction:
  auction_id:
  authority:
  title:
  description:
  category:
  asset_type:
  location:
  current_price:
  minimum_price:
  starting_price:
  end_time:
  bid_count:
  documents:
  conditions:
  status:
  source:
  last_observed:
```

Not every source will expose every field.

Missing data should remain:

```text
UNKNOWN
```

and must not be invented.

---

## 17.5 New Auction Flow

```text
Official auction published
        ↓
Helvetic Lens ingests
        ↓
extract auction object
        ↓
match against buyer profile
        ↓
relevance
        ↓
Today / Impact Inbox
```

---

## 17.6 Example

```text
NEW PUBLIC AUCTION MATCH

Commercial property
Lugano

Current / starting value:
CHF X

Auction end:
18 September

Why this matches:
• commercial real estate
• Ticino
• within your configured price range

Source:
Official cantonal auction service

Decision:
INSPECT
BID
NO_BID
MONITOR
```

---

## 17.7 Continuous Change

This use case is especially valuable because auctions are **stateful**.

The same auction may evolve:

```text
current bid:
20,000 → 30,000 → 45,000

end:
15 Sep → 18 Sep

documents:
2 → 3

status:
ACTIVE → CANCELLED

conditions:
updated
```

User should not receive every price increase unless requested.

---

## 17.8 Notification Rules

Example:

```yaml
notify:
  new_matching_auction: true
  price_above_limit: true
  deadline_change: true
  document_change: true
  cancellation: true

  ending_soon:
    hours: 24
```

---

## 17.9 Example — Price State

```text
AUCTION UPDATE

Monitored asset:
Vehicle X

Previous current bid:
CHF 8,500

Current:
CHF 12,700

Your maximum:
CHF 12,000

Result:
The current bid is now above your configured limit.

Decision:
STOP MONITORING
CONTINUE MONITORING
```

This is deterministic and does not require AI.

---

## 17.10 Example — Conditions Changed

```text
MATERIAL AUCTION UPDATE

Commercial Property ABC

New document added:
Updated auction conditions

Auction end:
21 Sep → 28 Sep

Why it matters:
You marked this auction as "Considering bid".

Action:
Review updated conditions.
```

This is classic Helvetic Lens:

```text
version
→ diff
→ impact
→ review
```

---

## 17.11 MVP Geographic Strategy

Do not try to solve all Swiss public auctions on day one.

Recommended:

```text
PHASE 1
Ticino official auctions

PHASE 2
additional cantonal official sources

PHASE 3
Swiss Source Pack / normalized national discovery
```

The core event model should remain stable while Source Packs expand.

---

## 17.12 Existing HL Reuse

```text
Sources             → cantonal auction platform
Topics              → asset interests
Today               → matching new auction
Version history     → auction snapshots
Comparison          → price/date/docs/status changes
Impact              → why it matches buyer profile
Impact Inbox        → high priority / deadline event
Review state        → bid / no-bid / inspect / monitor
Digest              → new auctions + changes
```

---

## 17.13 Minimal Extensions

```text
Auction entity
Asset-interest profile
Price threshold
Deadline state
Ending-soon rule
Auction status lifecycle
Structured + semantic asset matching
```

---

## 17.14 Acceptance Criteria

```text
AC-B8-01 User can create an auction interest profile.
AC-B8-02 New official auction can be ingested.
AC-B8-03 Auction can be matched by category/location/keywords.
AC-B8-04 Price limits can be configured.
AC-B8-05 User sees official source.
AC-B8-06 Current auction state is retained.
AC-B8-07 Deadline change generates material update.
AC-B8-08 Cancellation generates material update.
AC-B8-09 User can request ending-soon notification.
AC-B8-10 User can select Bid / No-bid / Inspect / Monitor.
AC-B8-11 Historical versions remain available.
AC-B8-12 New canton can be added without changing domain workflow.
```

---

# 18. Cross-Use-Case Capability Matrix

| Capability | C1 | C2 | C3 | C4 | C5 | C6 | C7 | B2 | B7 | B8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Authoritative source | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Automatic ingestion | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| New event detection | ✓ | ✓ | ✓ |  |  |  |  | ✓ | ✓ | ✓ |
| State monitoring | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Version history | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Comparison | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Personal/company relevance | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Threshold |  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ |
| Location matching | ✓ | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ |  | ✓ |
| Semantic matching |  |  |  |  |  |  |  | ✓ | ✓ | ✓ |
| Deadline awareness |  |  | ✓ |  |  |  |  | ✓ | ✓ | ✓ |
| Evidence | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Review decision | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

---

# 19. Four Generic Capabilities Needed to Unlock All 10

This is the main result of the use-case analysis.

There is no need to build ten different engines.

The existing Helvetic Lens needs four universal capabilities on top of its existing source/version/diff/review core.

---

## 19.1 CAP-01 — Monitoring Subject

Today, the product primarily models topics/documents/sources.

Add a universal:

> **WHAT DO I CARE ABOUT?**

Types:

```yaml
LOCATION
JOURNEY
ROAD
CURRENCY
ALLERGEN
MEASUREMENT_STATION
TENDER_PROFILE
TRADEMARK
AUCTION_PROFILE
```

Example:

```yaml
monitoring_subject:
  id: MS-001
  type: LOCATION
  name: Home
  definition:
    country: CH
    canton: TI
    municipality: Massagno
```

---

## 19.2 CAP-02 — Observed State

Helvetic Lens must be able to store not only:

```text
Document Version 12
```

but also:

```text
State at T1
State at T2
```

Example:

```yaml
subject: EUR_CUSTOMS_RATE
timestamp: 2026-09-10T12:00:00+02:00

state:
  rate: 0.9547
```

or:

```yaml
subject: A2_GOTTHARD_NORTHBOUND

state:
  condition: CONGESTED
```

This requires a generic `ObservedState` abstraction.

---

## 19.3 CAP-03 — Change Rule

Universal question:

> **What change is meaningful?**

Examples:

```yaml
rule:
  type: threshold
  field: pollen_level
  trigger: HIGH
```

```yaml
rule:
  type: percentage_delta
  field: customs_rate
  threshold: 1.0
```

```yaml
rule:
  type: state_transition
  from: OPEN
  to: CLOSED
```

```yaml
rule:
  type: new_matching_entity
```

Supported rule families should include:

```text
NEW_ENTITY
STATE_TRANSITION
NUMERIC_THRESHOLD
PERCENTAGE_DELTA
FIELD_CHANGED
DEADLINE_CHANGED
DOCUMENT_ADDED
STATUS_CHANGED
SEMANTIC_MATCH
```

---

## 19.4 CAP-04 — Relevance Reason

Every delivered event must contain:

```yaml
relevance:
  matched_subject:
  matched_rule:
  reason:
  evidence:
  deterministic_or_ai:
```

Examples:

```text
Because it affects Massagno.

Because this route is part of your commute.

Because EUR moved more than your 1% threshold.

Because you monitor birch pollen in Lugano.

Because the tender matches AI + document processing.

Because the new trademark resembles ALMORA.

Because this auction matches your property criteria.
```

This must be a first-class product concept.

---

# 20. Common Today Card

All ten use cases can use one UI contract.

```text
┌──────────────────────────────────────────────┐
│ [TYPE]                        [SEVERITY]      │
│                                              │
│ What happened                                │
│                                              │
│ Current state / key change                   │
│                                              │
│ WHY YOU RECEIVED THIS                        │
│ ...                                          │
│                                              │
│ WHAT CHANGED                                 │
│ Previous → Current                           │
│                                              │
│ SOURCE                                       │
│ Official authority                           │
│                                              │
│ [Review] [Evidence] [Not relevant]           │
└──────────────────────────────────────────────┘
```

`Today` should not require ten unrelated card designs.

Domain content changes.

The structural contract remains one.

---

# 21. Common Detail View

```text
TITLE

Current status

────────────────────

WHY THIS MATTERS TO YOU

────────────────────

WHAT CHANGED

Previous
vs
Current

────────────────────

EVIDENCE

Official authority
Publication/update time
Original source
Version

────────────────────

CONTEXT / AI EXPLANATION

────────────────────

DECISION

Reviewed
Action required
Not relevant
Monitor

────────────────────

CHANGE HISTORY
```

---

# 22. AI vs Deterministic Logic

Do not attempt to solve all ten use cases with an LLM.

Most detection logic should remain deterministic.

---

## 22.1 AI Not Required for Primary Detection

### C1

```text
location intersection
severity transition
```

### C2

```text
trip/route match
delay threshold
```

### C3

```text
road segment match
traffic status transition
```

### C4

```text
rate delta
threshold
```

### C5

```text
pollen category transition
threshold
```

### C6

```text
water-level threshold
danger-state transition
```

### C7

```text
pollution-state transition
```

### B8

```text
location
category
price
deadline
status
```

---

## 22.2 AI Very Useful

### B2 — Tender

```text
Does this procurement actually match what we sell?
Why?
What are the likely qualification gaps?
```

### B7 — Trademark

```text
Why might this mark be relevant?
Which semantic similarities matter?
```

### B8 — Auction

For unstructured descriptions:

```text
Does this asset match what we are looking for?
```

---

## 22.3 Correct Architecture

```text
DETERMINISTIC DETECTION
        ↓
DETERMINISTIC FILTERS
        ↓
CANDIDATE
        ↓
AI SEMANTIC ASSESSMENT IF NEEDED
        ↓
USER
```

Not:

```text
RAW INTERNET
    ↓
LLM DECIDES EVERYTHING
```

---

# 23. Source Pack Strategy

The ten use cases create a clean first Source Pack architecture.

## 23.1 Swiss Safety & Environment

```text
Alertswiss
MeteoSwiss / SwissPollen
FOEN Hydrology
FOEN / NABEL
```

Supports:

```text
C1
C5
C6
C7
```

---

## 23.2 Swiss Mobility

```text
Open Transport Data
ASTRA / Traffic Data Platform
```

Supports:

```text
C2
C3
```

---

## 23.3 Swiss Customs

```text
BAZG
```

Supports:

```text
C4
```

---

## 23.4 Swiss Business Opportunities

```text
SIMAP
Cantonal public-auction services
```

Supports:

```text
B2
B8
```

---

## 23.5 Swiss IP

```text
Swiss trademark publication / Swissreg / IPI
```

Supports:

```text
B7
```

---

# 24. Functional Grouping of the Final 10

The ten use cases are not random.

They fall into four product families.

---

## FAMILY A — Where I Am

```text
C1 Local Hazard
C5 Pollen
C6 River / Lake / Flood
C7 Air Quality
```

Common context:

```text
LOCATION
```

Shared capabilities:

```text
location selector
geographic relevance
observed state
threshold/state transition
```

---

## FAMILY B — Where I Go

```text
C2 Public Transport
C3 Road Route
```

Common context:

```text
JOURNEY / ROUTE
```

Shared capabilities:

```text
route entities
time awareness
live state
incident lifecycle
resolution
```

---

## FAMILY C — Numeric State I Care About

```text
C4 Customs Rate
```

Common context:

```text
NUMERIC STATE
```

Reusable engine:

```text
value
previous value
delta
threshold
materiality
history
```

This engine is also reused by C5–C7 and B8.

---

## FAMILY D — What My Business Is Looking For / Protecting

```text
B2 Tender
B7 Trademark
B8 Auction
```

Common context:

```text
COMPANY INTEREST PROFILE
```

Shared capabilities:

```text
entity discovery
semantic relevance
structured filters
deadline
review decision
version/change monitoring
```

---

# 25. Monitoring Templates

Instead of requiring a new user to configure:

```text
Sources
+
Topics
+
keywords
+
rules
+
thresholds
```

Helvetic Lens can expose a simpler flow:

# Create Monitor

Then templates:

```text
PERSONAL

[ Local hazards ]
[ Public transport ]
[ Driving route ]
[ Customs rate ]
[ Pollen ]
[ River / lake ]
[ Air quality ]


BUSINESS

[ Public tenders ]
[ Trademarks ]
[ Public auctions ]
```

---

## 25.1 Example — Pollen Setup

```text
Pollen

Where?
[ Lugano ]

Which pollen?
[x] Birch
[x] Grass

When should I alert you?
[ High or above ]

[ Start monitoring ]
```

Internally:

```text
Monitoring Subject
+
Source Pack
+
Change Rule
+
Relevance Rule
```

The user does not need to understand these technical objects.

---

## 25.2 Example — Tender Setup

```text
Public tenders

What does your company sell?
[ AI software ]
[ Document processing ]
[ Business automation ]

Where?
[x] Federal
[x] Ticino
[x] Zurich

Exclude:
[x] Construction
[x] Hardware-only

Notify me when:
[ A new strong match appears ]
[ A watched tender materially changes ]

[ Start monitoring ]
```

---

## 25.3 Example — Trademark Setup

```text
Trademark Watch

Brand:
[ ALMORA ]

Monitor:
[x] Exact matches
[x] Similar names

Relevant goods/services:
[ Software ]
[ AI ]
[ Business applications ]

Notify:
[ New potentially relevant publication ]

[ Start monitoring ]
```

---

## 25.4 Example — Auction Setup

```text
Public Auctions

Category:
[ Commercial real estate ]

Where?
[ Ticino ]

Maximum price:
[ CHF 1,500,000 ]

Notify:
[x] New match
[x] Deadline changed
[x] Conditions changed
[x] Ending within 24h

[ Start monitoring ]
```

---

# 26. Recommended Product Navigation

The ten use cases should not produce ten top-level modules.

Recommended product mental model:

```text
TODAY
MONITORING
INVESTIGATE
WORKSPACE
ADMIN
```

---

## 26.1 Today

Purpose:

> What changed that needs my attention?

Contains:

```text
new relevant developments
material updates
reopened reviews
ending-soon/deadline events
```

---

## 26.2 Monitoring

Purpose:

> What have I asked Helvetic Lens to watch?

Contains:

```text
Monitoring Subjects
Templates
Status
Thresholds
Locations
Routes
Business profiles
```

Existing `Topics`, watched documents and source configuration can sit behind this abstraction.

---

## 26.3 Investigate

Purpose:

> What exactly changed and what is the evidence?

Contains:

```text
Current state
Previous state
Comparison
Evidence
Official source
AI explanation
History
Ask
```

---

## 26.4 Workspace

Purpose:

> What decisions have we made and what remains unresolved?

Contains:

```text
Impact Inbox
Assignments
Review states
Digests
Decision history
```

---

## 26.5 Admin

Contains:

```text
Sources
Source Sync
Integration Logs
Scan Activity
Local Models
Prompt Settings
Provider Settings
Deployments
Platform Admin
```

These are system capabilities, not primary everyday user jobs.

---

# 27. Cross-Case Shared Domain Objects

Recommended generic objects:

```text
MonitoringSubject
SourcePack
SourceConnection
ObservedEntity
ObservedState
Development
ChangeSet
EvidenceBundle
RelevanceAssessment
ChangeRule
NotificationRule
Review
Decision
Deadline
```

---

## 27.1 MonitoringSubject

```yaml
MonitoringSubject:
  id:
  owner_scope:
  type:
  name:
  configuration:
  status:
  created_at:
```

---

## 27.2 ObservedEntity

Examples:

```text
Hazard Warning
Train Trip
Road Segment
Currency
Pollen Allergen
Hydrology Station
Air Quality Station
Tender
Trademark
Auction
```

---

## 27.3 ObservedState

```yaml
ObservedState:
  entity_id:
  observed_at:
  source_version:
  state_payload:
  evidence_ref:
```

---

## 27.4 Development

A `Development` is the user-facing logical story.

Example:

```text
Gotthard Night Closure — September 2026
```

may have:

```text
v1 closure announced
v2 date changed
v3 closure cancelled
```

The user should see one development with history, not three unrelated events.

---

## 27.5 ChangeSet

```yaml
ChangeSet:
  previous_state_id:
  current_state_id:
  material_changes:
  materiality:
  detected_at:
```

---

## 27.6 RelevanceAssessment

```yaml
RelevanceAssessment:
  monitoring_subject_id:
  development_id:
  relevant:
  score:
  reason:
  method:
  evidence:
```

`method`:

```text
DETERMINISTIC
AI_ASSISTED
HYBRID
```

---

## 27.7 Decision

```yaml
Decision:
  development_id:
  user_or_org:
  state:
  owner:
  comment:
  decided_at:
```

Possible state:

```text
REVIEWED
ACTION_REQUIRED
NO_ACTION
NOT_RELEVANT
MONITOR
RESOLVED
```

Domain-specific decisions may extend this:

```text
BID
NO_BID
INSPECT
ESCALATE_TO_IP_COUNSEL
```

---

# 28. Notification Strategy

Notifications must be based on **meaningful change**, not source refresh.

Bad:

```text
Source refreshed.
Source refreshed.
Source refreshed.
```

Good:

```text
Hazard severity increased.
Your train was cancelled.
Gotthard closure changed.
EUR customs rate crossed your threshold.
Pollen became high.
Flood danger increased.
A tender relevant to you appeared.
A tender deadline changed.
A similar trademark was published.
Auction price crossed your maximum.
```

---

## 28.1 Notification Priority

Recommended:

### P1 — Immediate

```text
critical hazard
route closure
trip cancellation close to travel time
critical state escalation
```

### P2 — Important

```text
material tender update
trademark candidate with deadline
auction deadline/conditions changed
customs threshold crossed
pollen/flood/air material state change
```

### P3 — Digest

```text
low-priority new opportunities
minor resolved events
informational changes
history summaries
```

---

# 29. Deduplication Requirements

This is a core platform requirement.

One real-world development may produce:

```text
multiple source records
multiple language editions
multiple updates
multiple API snapshots
multiple attachments
```

Helvetic Lens should cluster them into:

```text
ONE DEVELOPMENT
+
VERSION / STATE HISTORY
```

Examples:

### Hazard

```text
Warning created
→ severity changed
→ geography expanded
→ cancelled
```

### Tender

```text
Tender published
→ Q&A added
→ deadline changed
→ corrected specification uploaded
```

### Auction

```text
Auction created
→ bid changed
→ conditions updated
→ deadline moved
```

### Trademark

```text
Application/publication
→ status update
→ owner/representative change
```

---

# 30. Evidence Contract

Every delivered development must preserve:

```yaml
evidence:
  authority:
  source:
  source_type:
  fetched_at:
  published_at:
  effective_at:
  original_identifier:
  original_url:
  raw_or_normalized_snapshot:
  previous_snapshot:
  current_snapshot:
```

The user must be able to distinguish:

```text
FACT FROM SOURCE
AI EXPLANATION
SYSTEM CALCULATION
USER DECISION
```

---

# 31. Product Safety Boundaries

## 31.1 Environmental / Hazard Cases

Helvetic Lens may:

```text
report official state
show official instructions
show change
explain why user matched
```

It should not override emergency authorities.

---

## 31.2 Pollen / Air Quality

Helvetic Lens may:

```text
show official environmental data
show state transition
show official/general guidance
```

It must not:

```text
diagnose
change medication
make personalised medical treatment decisions
```

---

## 31.3 Trademark

Helvetic Lens may:

```text
identify candidate similarity
show classes/services overlap
show official publication
surface deadlines for verification
```

It must not:

```text
declare infringement
guarantee opposition success
replace IP counsel
```

---

## 31.4 Tender

Helvetic Lens may:

```text
assess relevance
extract requirements
show gaps
show changes
```

It should not autonomously commit the company to submit a bid.

---

## 31.5 Auction

Helvetic Lens may:

```text
match asset
show price/status/deadline
detect changes
```

It should not autonomously place bids.

---

# 32. Functional Priority

Recommended implementation order based on maximum reuse.

## Phase 1 — Generic Change Foundation

Build:

```text
MonitoringSubject
ObservedState
ChangeRule
RelevanceReason
Development lifecycle
Event deduplication
Threshold engine
```

Unlocks:

```text
C1
C4
C5
C6
C7
```

---

## Phase 2 — Mobility

Build:

```text
route/journey entities
time-aware matching
ephemeral event lifecycle
transport/traffic source adapters
```

Unlocks:

```text
C2
C3
```

---

## Phase 3 — Business Discovery

Build:

```text
business-interest profiles
structured + semantic entity matching
deadline awareness
document-set comparison
```

Unlocks:

```text
B2
B7
B8
```

---

# 33. MVP Acceptance at Platform Level

The platform should not be considered ready for these ten use cases until the following common criteria are met.

```text
AC-CORE-01 Monitoring Subject can be created without manual source configuration.
AC-CORE-02 Every subject resolves to at least one authoritative source.
AC-CORE-03 System can persist current and previous state.
AC-CORE-04 System can distinguish event creation from event update.
AC-CORE-05 System can identify material vs non-material change.
AC-CORE-06 Every delivered change includes a relevance reason.
AC-CORE-07 Every delivered change includes authoritative evidence.
AC-CORE-08 Same logical development is not duplicated on each refresh.
AC-CORE-09 Material update can reopen an already-reviewed development.
AC-CORE-10 User can classify a development as reviewed/not relevant/monitor/action required.
AC-CORE-11 Source failure is distinguishable from "no change".
AC-CORE-12 Source timestamp is visible.
AC-CORE-13 AI output is distinguishable from deterministic facts.
AC-CORE-14 Threshold logic is deterministic and auditable.
AC-CORE-15 Notifications are produced only from configured materiality rules.
AC-CORE-16 Development history remains available after resolution.
AC-CORE-17 Source-specific objects normalize into shared platform contracts.
AC-CORE-18 Adding another source does not require creating another top-level product.
AC-CORE-19 Today can mix multiple domains in one coherent feed.
AC-CORE-20 User can understand in one interaction why each event was delivered.
```

---

# 34. Product KPIs for Pilot

Recommended cross-case pilot metrics:

## Precision

```text
Relevant delivered events
/
All delivered events
```

Target should be high because notification fatigue will destroy the product.

---

## Material Change Precision

```text
Events user considers materially changed
/
Events marked material by system
```

---

## Relevance Explanation Quality

Question:

```text
Did "Why you received this" make sense?
YES / NO
```

---

## Actionability

```text
Events leading to:
review
decision
route change
bid/no-bid
monitor
other action
/
Relevant events
```

---

## Duplicate Rate

```text
Duplicate developments
/
Delivered developments
```

Target:

```text
as close to zero as possible
```

---

## Time-to-Understand

Measure:

```text
alert opened
→
user understands what changed
```

The goal is not maximum reading time.

The goal is:

> **minimal time from change to informed decision.**

---

# 35. Strategic Product Interpretation

The ten use cases materially expand the product abstraction.

Helvetic Lens is not only:

> **Regulatory monitoring platform**

The shared engine now supports:

```text
regulatory publications
official events
realtime disruptions
environmental measurements
numeric states
commercial opportunities
legal publications
public auctions
```

The common denominator is not "law".

The common denominator is:

> **authoritative change that matters to a specific user or company.**

---

# 36. Recommended Positioning

## Option A — Direct

> **Monitor what matters to you in Switzerland.  
> Know when it changes.**

## Option B — Evidence-oriented

> **See what changed. Understand why it matters. Verify the source.**

## Option C — Product Architecture

> **Swiss Change Intelligence**

## Option D — Full Proposition

> **You define what matters. Helvetic Lens watches authoritative Swiss sources, detects meaningful change, filters what is relevant to you, preserves the evidence, and helps you decide what to do.**

---

# 37. Final Product Formula

All ten use cases can be represented by one architecture formula:

```text
MONITORING SUBJECT
        +
AUTHORITATIVE SOURCE
        +
CURRENT STATE
        +
PREVIOUS STATE
        +
CHANGE RULE
        +
RELEVANCE RULE
        =
MEANINGFUL DEVELOPMENT
```

The user-facing formula is even simpler:

```text
WHAT I CARE ABOUT
        ↓
WHAT CHANGED
        ↓
WHY IT MATTERS TO ME
        ↓
SHOW ME THE EVIDENCE
        ↓
WHAT DO I WANT TO DO
```

This is the shared functional core for:

```text
C1 Local Hazard Watch
C2 Public Transport Disruption Watch
C3 My Route Watch
C4 Swiss Customs Rate Watch
C5 Pollen Exposure Watch
C6 River / Lake / Flood Watch
C7 Air Quality Watch
B2 Public Tender Watch
B7 Trademark & IP Watch
B8 Public Auction Watch
```

---

# 38. Source Families Referenced

The implementation should be grounded in authoritative Swiss sources appropriate to each use case, including:

- Alertswiss / Federal Office for Civil Protection
- MeteoSwiss / SwissPollen
- Federal Office for the Environment (FOEN/BAFU)
- Swiss public transport open-data infrastructure
- FEDRO / ASTRA
- Federal Office for Customs and Border Security (BAZG)
- SIMAP
- Swiss Federal Institute of Intellectual Property / Swissreg
- official cantonal auction platforms, beginning with Ticino for the proposed MVP

Exact connector/API contracts, update cadence and data licences should be validated during source-adapter implementation.

---

# 39. Final Scope Statement

**Helvetic Lens Practical Use Cases v1 contains exactly 10 use cases:**

```yaml
B2C:
  - C1 Local Hazard Watch
  - C2 Public Transport Disruption Watch
  - C3 My Route Watch — Gotthard / A2 / A13
  - C4 Swiss Customs Rate Watch
  - C5 Pollen Exposure Watch
  - C6 River / Lake / Flood Watch
  - C7 Air Quality Watch

B2B:
  - B2 Public Tender Watch
  - B7 Trademark & IP Watch
  - B8 Public Auction Watch
```

Any additional use case should be treated as outside this v1 scope unless explicitly approved.

---

# 40. Final Principle

> **Helvetic Lens should not become ten separate vertical applications.**

It should become one configurable **Swiss Change Intelligence platform** where each use case is primarily:

```text
Monitoring Template
+
Source Pack
+
Observed State Model
+
Change Rules
+
Relevance Rules
+
Decision Contract
```

The engine remains shared.

The user experience changes according to what the user cares about.
