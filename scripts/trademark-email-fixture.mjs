// Synthetic consent/preview responses; delivery is exercised through the real API tests.
export function trademarkEmailFixture() {
  let policy = null;
  return (route, method, body, monitor, state) => {
    if (!monitor || !route.startsWith(`/monitors/${monitor.id}/email`)) return null;
    const result = (value, status = 200) => ({ value, status });
    if (state.emailDenied) return result({ code: "membership_required" }, 403);
    if (method === "PUT") {
      if (body.expected_version !== monitor.version || state.conflict)
        return result({ code: "trademark_version_conflict" }, 409);
      monitor.version++;
      policy = { revision: (policy?.revision || 0) + 1, configuration: body.configuration, consent_active: body.consent };
    }
    if (route.endsWith("/preview")) return result({
      status: state.sourceRevoked ? "unavailable" : "ready", more_available: false, quiet_hours: false,
      items: state.sourceRevoked || !policy?.consent_active ? [] : [{
        detected_at: "2026-09-14T12:00:00+00:00",
        href: `/trademark-watch?monitor=${monitor.id}&candidate=00000000-0000-4000-8000-000000000072&event=00000000-0000-4000-8000-000000000073`
      }]
    });
    return result({
      revision: 0, consent_active: false,
      configuration: { timezone: "Europe/Zurich", delivery: { email: "off", digest_at: null, quiet_hours: null } },
      ...policy, monitor_version: monitor.version, email_verified: true,
      recipient_email: "synthetic@example.invalid", uncertain_deliveries: 0, mail_available: true
    });
  };
}

