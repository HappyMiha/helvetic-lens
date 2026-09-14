// Synthetic browser responses; source permissions and tenant isolation are tested by the real API suite.
import { trademarkExportFixture } from "./trademark-export-fixture.mjs";
import { deadlineFixture } from "./trademark-deadline-fixture.mjs";
export function trademarkReviewFixture() {
  const exportRoute = trademarkExportFixture();
  let candidate = null,
    events = [],
    reviews = [];
  const candidateId = "00000000-0000-4000-8000-000000000072";
  const time = "2026-09-14T12:00:00+00:00";
  const facts = (owner) => ({
    official_id: "SYNTHETIC-IP-1",
    mark: "ALMORA",
    owners: [owner],
    representatives: null,
    classes: [9],
    status: "Registered",
    source_url: "https://example.invalid/register/1",
    origin: "national_ch",
    goods_services: [
      { text: "Computer software", language: "en", class_number: 9 },
    ],
    application_date: "2026-07-01",
    publication_date: "2026-08-12",
    registration_date: "2026-08-09",
    renewal_date: null,
    expiry_date: null,
    cancellation_date: null,
  });
  const assessment = {
    state: "candidate",
    priority: "high",
    unavailable: ["similarity_calibration_unavailable"],
    methods: [
      { kind: "exact", brand_variant: "ALMORA", source_mark: "ALMORA" },
    ],
    goods_services: {
      class_overlap: [9],
      matches: [
        { interest: "Software", phrase: "computer software", language: "en" },
      ],
    },
  };
  const view = (state) =>
    candidate && {
      ...structuredClone(candidate),
      deadline_context: deadlineFixture(state),
      ...(state.sourceRevoked
        ? {
            state: "unavailable",
            facts: null,
            assessment: null,
            can_review: false,
          }
        : {}),
    };
  function project(monitor, state) {
    const owner = state.registerOwner || "Synthetic Owner AG";
    if (!candidate || candidate.facts.owners[0] !== owner) {
      const previous = candidate?.facts || null;
      const sequence = (candidate?.sequence || 0) + 1;
      candidate = {
        id: candidateId,
        monitor_id: monitor.id,
        brand_key: monitor.configuration.brands[0].key,
        version: (candidate?.version || 0) + 1,
        sequence,
        needs_review: true,
        decision: candidate?.decision || null,
        state: "available",
        facts: facts(owner),
        assessment,
        can_review: true,
        evaluation_hash: "a".repeat(64),
        attribution: "Synthetic register fixture",
      };
      const id = `00000000-0000-4000-8000-${String(80 + sequence).padStart(12, "0")}`;
      events.unshift({
        id,
        sequence,
        detected_at: time,
        change_codes: [sequence === 1 ? "new_candidate" : "changed_owners"],
        profile_revision: monitor.revision,
        href: `/trademark-watch?monitor=${monitor.id}&candidate=${candidateId}&event=${id}`,
        snapshot: { facts: structuredClone(candidate.facts) },
        previous: previous ? { facts: structuredClone(previous) } : null,
        assessment,
      });
    }
    monitor.runtime = {
      health: "partial",
      last_check_at: time,
      next_check_at: "2026-09-14T12:01:00+00:00",
      unavailable_count: 0,
    };
  }
  return (route, method, body, monitor, state) => {
    const ok = (value) => ({ value, status: 200 }),
      fail = (code) => ({ value: { code }, status: 409 });
    if (route === "/preview")
      return ok({
        start_available: !!state.sourceReady && !state.sourceRevoked,
        source_attributions: state.sourceReady
          ? ["Synthetic register fixture"]
          : [],
        similarity_unavailable_languages: ["en"],
      });
    if (route === "/today" || route === "/inbox")
      return ok({
        items:
          monitor?.status === "active" &&
          candidate?.needs_review &&
          !state.sourceRevoked
            ? [
                {
                  ...events[0],
                  deadline_context: deadlineFixture(state),
                  name: monitor.configuration.name,
                  mark: candidate.facts.mark,
                  brand: "ALMORA",
                  attribution: candidate.attribution,
                },
              ]
            : [],
        next_cursor: null,
        unavailable_count: state.sourceRevoked ? 1 : 0,
      });
    if (!monitor) return;
    const base = `/monitors/${monitor.id}`;
    if (route === base + "/start" || route === base + "/pause") {
      if (body.expected_version !== monitor.version)
        return fail("trademark_version_conflict");
      if (route.endsWith("/start") && !state.sourceReady)
        return fail("trademark_source_not_configured");
      monitor.status = route.endsWith("/start") ? "active" : "paused";
      monitor.version++;
      return ok(monitor);
    }
    if (route === base + "/refresh") {
      project(monitor, state);
      return ok({ health: monitor.runtime.health });
    }
    if (route === base + "/candidates")
      return ok({ items: candidate ? [view(state)] : [], next_cursor: null });
    if (!candidate) return;
    const exported = exportRoute(route, method, body, {
      monitor,
      candidate,
      events,
      state,
    });
    if (exported) return exported;
    const path = base + "/candidates/" + candidateId;
    if (route === path) return ok(view(state));
    if (route === path + "/review") {
      if (state.sourceRevoked) return fail("trademark_evidence_unavailable");
      if (body.expected_version !== candidate.version || state.conflict)
        return fail("trademark_version_conflict");
      candidate.version++;
      candidate.decision = body.decision;
      candidate.needs_review = false;
      reviews.unshift({
        id: String(candidate.version),
        version: candidate.version,
        sequence: candidate.sequence,
        decision: body.decision,
        created_at: time,
      });
      return ok(view(state));
    }
    if (route === path + "/reviews")
      return ok({ items: reviews, next_cursor: null });
    if (route === path + "/history")
      return ok({
        items: events.map(
          ({ snapshot, previous, assessment, ...rest }) => rest,
        ),
        next_cursor: null,
      });
    const event = events.find((e) => route === path + "/events/" + e.id);
    if (event)
      return ok({
        ...event,
        deadline_context: deadlineFixture(state),
        newer_available: event.sequence < candidate.sequence,
        ...(state.sourceRevoked
          ? {
              snapshot: { facts: null },
              previous: event.previous ? { facts: null } : null,
              assessment: null,
            }
          : {}),
      });
  };
}
