# Pollen station choice and channel overview

MV2-070 C01/C05 contribution to AC-C5-01/02, 11 September 2026.
One setup feature: choose a named station, optionally compare local distances,
inspect the selected allergens' channels, check/save and reopen the settings.

## Dated public directory

`apps/web/lib/pollen-stations.ts` contains only the 15 station names, identifiers
and public coordinates from the retained MV2-069 source proof. The metadata CSV
identity, capture time and SHA-256 are retained with the directory; a regression
compares every field to the proof. No retained concentrations, forecast sample
values or private device coordinates are bundled. Official station names keep
their source spelling. The form defaults to no selection and displays a native
labelled station selector; saved lists/settings also display the station name.

This is a dated directory, not an operational supported-coverage promise. The
source documentation and terms are linked with attribution and the capture date.
The 15-row inventory does not resolve the earlier collection-prose discrepancy
or establish live data at all listed stations. Unknown saved/imported codes are
retained as a selectable option with an explanation, never silently replaced.

## Optional device location

The optional nearby section explains the action before the user presses its
button. Only that button calls the browser geolocation API. The browser decides
permission; manual named selection remains available when access is denied,
unsupported, unavailable or timed out. Requests use a ten-second timeout,
maximum one-minute cached position and no high-accuracy request.

Coordinates live only in the current picker component. Haversine distances are
calculated locally, shown as approximate straight-line distances and used to sort
the 15 options. Nothing automatically selects a station, writes configuration,
requests source data or sends coordinates to the application. No geocoder, map
tile service, address field, browser storage or new API is used. Device/browser
location-provider behavior remains controlled by the browser's permission flow.

Clear location cancels acceptance of outstanding callbacks and removes the local
point without changing the selected station. Component unmount (including the
existing scope/pagehide cleanup) invalidates late callbacks. A fresh form has no
coordinates. The nearest station is not guaranteed to represent conditions at
home; station measurements and near-station model estimates remain distinct.

## Separate documented channels

The allergen table uses the channel facts already recorded in `POLLEN_SOURCES.md`:
seven documented hourly measurement parameters; five documented seasonal forecast
variables. Ragweed has no established automatic hourly parameter, while beech,
ash and oak have no established corresponding forecast variable in this dossier.
Unknown allergens cannot invent a channel. These labels describe documentation,
not current or station-specific availability, freshness, seasonal completeness,
daily aggregation coverage or accepted category scales. The overview explicitly
keeps those checks open and never loads the dated proof as a live fallback.

Changing station or allergens uses the existing configuration-change path, which
invalidates preview and preserves the other numeric/delivery settings. Explicit
server preview and separate idempotent/CAS save remain mandatory. Saved output
contains only the existing station ID, never the device location or distance.
The five-language labels, native selector, keyboard path, mobile table and source
links are also available when reading saved settings. Human language/screen-reader,
source-backed Start, real live coverage and complete user acceptance remain open.
