// Small native reader contracts, synthetic accounts and retained source states.
// No external calls or production credentials. API permission tests are separate.
const id = "00000000-0000-4000-8000-000000000011";
const item = "00000000-0000-4000-8000-000000000022";
const reference = "00000000-0000-4000-8000-000000000033";
const time = "2026-09-14T08:00:00Z";
const page = (items = []) => ({
  items,
  next_cursor: null,
  next_before: null,
  next: null,
});
const basic = {
  id,
  version: 2,
  revision: 1,
  status: "active",
  health: "ready",
  state: {},
  last_check_at: time,
  last_poll_at: time,
};
const email = {
  revision: 0,
  monitor_version: 2,
  configuration: {
    timezone: "Europe/Zurich",
    delivery: { email: "off", digest_at: null, quiet_hours: null },
  },
  consent_active: false,
  email_verified: true,
};
const labels = [
  {
    id: reference,
    label: "Tram 8: Basel SBB → Claraplatz",
    name: "Synthetic Basel corridor",
    enabled: true,
    flow: "north",
    attribution: "Synthetic topology",
  },
];
export function personalFixture(domain) {
  let monitor, detail, route, query, sample;
  const config = {
    template_version: 1,
    name: "Private Basel history",
    timezone: "Europe/Zurich",
  };
  if (domain === "air" || domain === "river") {
    route = `${domain}-watch`;
    query = `monitor=${id}&change=${item}`;
    sample = {
      source: "Synthetic official station",
      metric: domain === "air" ? "O3" : "W",
      timestamp: time,
      value: "60",
      unit: domain === "air" ? "µg/m³" : "m",
      quality: "provisional",
      period: "hourly_mean",
      datum: "FOEN:2289:m ü.M.",
      aggregation: "live_observation",
      source_url: "https://example.invalid/source",
      license_url: "https://example.invalid/terms",
      revision: 1,
    };
    monitor = {
      ...basic,
      configuration: {
        ...config,
        template_id: route,
        station_id: domain === "air" ? "BAS" : "2289",
        metrics: [sample.metric],
        muted_metrics: [],
        rules: [],
        official_danger: true,
      },
      state: { coverage: { [sample.metric]: { status: "current", sample } } },
    };
    detail = {
      event: {
        id: item,
        development_id: reference,
        sequence: 1,
        revision: 1,
        kind: "threshold_crossed",
        priority: 2,
        review_version: 0,
        decision: null,
        evidence: { sample, baseline: null, rule: null, recovered: false },
      },
      newer_available: true,
      current_configuration: false,
    };
  } else if (domain === "traffic") {
    route = "road-watch";
    query = `monitor=${id}&event=${item}&sequence=1`;
    monitor = {
      ...basic,
      configuration: {
        ...config,
        template_id: route,
        corridor_reference_ids: [reference],
        materiality: {
          event_kinds: ["road_closure"],
          minimum_delay_seconds: 900,
          include_planned: true,
        },
      },
    };
    const payload = {
      state: "active",
      corridors: {
        [reference]: {
          state: "active",
          coverage: "verified",
          facts: [
            {
              kind: "road_closure",
              phase: "active",
              probability: "certain",
              valid_from: time,
              valid_until: null,
            },
          ],
        },
      },
    };
    const event = {
      id: item,
      monitor_id: id,
      version: 2,
      sequence: 2,
      reviewed_sequence: 0,
      muted: false,
      updated_at: time,
      availability: "available",
      attribution: "Synthetic official traffic source",
      payload,
    };
    detail = {
      event,
      snapshot: {
        sequence: 1,
        payload,
        availability: "available",
        attribution: event.attribution,
        created_at: time,
      },
      previous: null,
      corridors: labels,
      newer_available: true,
      current_configuration: false,
    };
  } else if (domain === "commute") {
    route = "commute-watch";
    query = `monitor=${id}&event=${item}&sequence=1`;
    monitor = {
      ...basic,
      paused_on: null,
      reference_labels: labels,
      configuration: {
        ...config,
        template_id: route,
        leg_reference_ids: [reference],
        weekdays: [1, 2, 3, 4, 5],
        window_start: "07:00",
        window_end: "09:00",
        delay_threshold_minutes: 5,
        delay_reset_minutes: 2,
        cancellations: true,
        skipped_boarding_or_alighting: true,
        service_notices: true,
        outside_window: "digest",
      },
    };
    const current = {
      states: {
        [reference]: {
          condition: "cancelled",
          availability: "present",
          reason: "material",
          observed_at: time,
          delay_seconds: null,
        },
      },
      editions: {},
    };
    const event = {
      id: item,
      available: true,
      monitor_id: id,
      source: "swiss_gtfs_trip_updates",
      version: 2,
      sequence: 2,
      reviewed_sequence: 0,
      configuration_revision: 1,
      service_day: "2026-09-14",
      muted: false,
      current,
      reference_labels: labels,
    };
    detail = {
      event,
      snapshot: {
        id: reference,
        sequence: 1,
        created_at: time,
        evidence_hash: "c".repeat(64),
        evidence: {
          current,
          source: event.source,
          feed_sha256: "a".repeat(64),
          entity_sha256: "b".repeat(64),
          feed_observed_at: time,
          recorded_at: time,
          service_day: event.service_day,
          configuration_revision: 1,
          legs: {
            [reference]: {
              route_name: "Tram 8",
              boarding_name: "Basel SBB",
              alighting_name: "Claraplatz",
            },
          },
        },
      },
      newer_available: true,
      current_configuration: false,
    };
  } else if (domain === "warnings") {
    route = "hazard-watch";
    query = `monitor=${id}&event=${item}&revision=1`;
    monitor = {
      ...basic,
      configuration: {
        ...config,
        template_id: route,
        location: {
          kind: "point",
          country: "CH",
          canton: "BS",
          latitude: 47.56,
          longitude: 7.59,
          radius_km: 0,
        },
        hazards: ["storm"],
        minimum_importance: "warning",
      },
    };
    detail = {
      id: item,
      monitor_id: id,
      version: 2,
      revision: 1,
      historical: true,
      state: "active",
      material_sequence: 1,
      reviewed: false,
      dismissed: false,
      needs_review: true,
      muted: false,
      decision: {
        hazards: ["storm"],
        importance: "warning",
        certainty: "Observed",
        match: { basis: "explicit_geometry" },
      },
      source: {
        attribution: "Synthetic warning authority",
        last_seen_at: time,
        message: {
          identity: { sent: time },
          infos: [
            {
              language: "en-CH",
              event: "Synthetic storm",
              headline: "Saved warning for Basel",
              description: "Retained source description",
              instruction: "Stay indoors.",
              web: "https://example.invalid/warning",
              effective: time,
              expires: "2026-09-15T09:00:00Z",
            },
          ],
        },
      },
    };
  } else {
    route = "pollen-watch";
    query = `subject=${id}&entry=${item}`;
    const configuration = {
      station_id: "PBS",
      selections: [
        {
          allergen: "birch",
          rules: [
            {
              period: "observation_hourly",
              unit: "number/m3",
              threshold: { trigger_at_or_above: "20", reset_at_or_below: "5" },
              rapid_increase: null,
              category_change: false,
            },
          ],
        },
      ],
      timezone: "Europe/Zurich",
      delivery: { email: "off", digest_at: null, quiet_hours: null },
    };
    monitor = {
      ...basic,
      configuration,
      configuration_hash: "a".repeat(64),
      runtime: {
        version: 2,
        run_id: reference,
        health: "ready",
        email_consent: false,
        muted: false,
      },
    };
    sample = {
      series: {
        source_id: "synthetic",
        method_version: "synthetic-v1",
        station_id: "PBS",
        allergen: "birch",
        period: "observation_hourly",
        unit: "number/m3",
        forecast: null,
      },
      value: "20",
      valid_at: time,
      fetched_at: time,
      fresh_until: "2026-09-15T08:00:00Z",
      quality: "usable",
      source_revision: 1,
      artifact_hashes: ["a".repeat(64)],
      policy_version: "synthetic",
    };
    detail = {
      entry: {
        id: item,
        configuration_revision: 1,
        created_at: time,
        current: sample,
        previous: null,
        baseline: null,
        reasons: ["threshold_crossed"],
        review: null,
      },
      newer_available: true,
      current_configuration: false,
    };
  }
  const api =
    domain === "pollen" ? "/api/monitoring-subjects" : `/api/${route}`;
  function response(path) {
    if (path.endsWith("/capabilities"))
      return {
        drafts_available: true,
        start_available: true,
        blocking_reasons: [],
      };
    if (path.endsWith("/stations"))
      return {
        stations: [
          {
            id: monitor.configuration.station_id,
            name: "Basel station",
            area: "Basel",
            waterbody: "Rhein",
          },
        ],
        health: "ready",
      };
    if (path.endsWith("/catalog") || path.endsWith("/corridors"))
      return page(labels);
    if (path.endsWith("/email")) return email;
    if (path.endsWith("/mutes")) return { muted_hazards: [], hazards: [] };
    if (path.endsWith(`/${item}`)) return detail;
    if (path.endsWith("/state"))
      return {
        ...monitor,
        start_available: true,
        blocking_reasons: [],
        coverage: [],
        current: [],
      };
    if (path.endsWith("/history") || path.endsWith("/revisions"))
      return page([{ revision: 1, configuration: monitor.configuration }]);
    if (path.endsWith("/measurements")) return page([sample]);
    if (
      path.endsWith("/changes") ||
      path.endsWith("/events") ||
      path.endsWith("/activity")
    )
      return page();
    if (path.endsWith(`/${id}`)) return monitor;
    if (path === api || path.endsWith("/monitors")) return page([monitor]);
    return page();
  }
  return {
    monitor,
    detail: { id: item },
    route,
    query,
    sequence: ["warnings", "commute", "traffic"].includes(domain)
      ? 1
      : undefined,
    api,
    response,
  };
}
