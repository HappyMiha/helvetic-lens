"""Execution isolation; permissions and durable admission remain native."""

CONTROL = "monitoring_control"
SOURCES = "monitoring_sources"
BULK = "monitoring_bulk"
PROJECTION = "monitoring_projection"
DELIVERY = "monitoring_delivery"
QUEUES = frozenset({CONTROL, SOURCES, BULK, PROJECTION, DELIVERY})

# These existing refresh jobs include source I/O and deterministic evaluation.
# Keep their native atomic boundaries, while isolating the whole job from legal
# ingestion and the private projection/reminder worker.
SOURCE_JOBS = frozenset({"pollen_refresh", "river_refresh", "air_refresh"})
BULK_JOBS = frozenset({"tender_refresh"})
PROJECTION_JOBS = frozenset({"commute_refresh", "road_refresh", "hazard_refresh"})
DELIVERY_JOBS = frozenset(f"{domain}_email" for domain in (
    "pollen", "river", "air", "hazard", "commute", "road", "tender", "trademark", "auction"))


def durable_queue(job_type, fallback):
    if job_type in SOURCE_JOBS:
        return SOURCES
    if job_type in BULK_JOBS:
        return BULK
    if job_type in PROJECTION_JOBS:
        return PROJECTION
    if job_type in DELIVERY_JOBS:
        return DELIVERY
    return fallback


PERIODIC_QUEUES = {
    **{f"helvetic_lens.{name}": CONTROL for name in (
        "dispatch_outbox", "recover_jobs", "schedule_connectors", "schedule_digests",
        "schedule_pollen_monitoring", "schedule_river_monitoring", "schedule_air_monitoring",
        "schedule_tender_monitoring", "schedule_commute_monitoring", "schedule_road_monitoring",
        "schedule_hazard_monitoring", "schedule_river_email",
        "schedule_air_email", "schedule_commute_email",
        "schedule_road_email", "schedule_hazard_email", "schedule_trademark_email", "schedule_auction_email")},
    **{f"helvetic_lens.{name}": SOURCES for name in (
        "collect_commute_sources", "collect_road_source", "collect_hazard_source")},
    **{f"helvetic_lens.{name}": BULK for name in (
        "collect_commute_static", "collect_ipi_source", "collect_aste_source")},
    **{f"helvetic_lens.{name}": PROJECTION for name in (
        "schedule_auction_monitoring", "schedule_trademark_monitoring", "schedule_auction_reminders")},
}

# Independent consumers share the existing worker-cpu CONTAINER lifecycle, so a
# pinned older release controller still quiesces every writer during rollback.
CPU_WORKERS = (
    ("cpu", "interactive,ingest,parse_diff,maintenance", 2),
    ("control", CONTROL, 1),
    ("sources", SOURCES, 2),
    ("bulk", BULK, 1),
    ("projection", PROJECTION, 1),
    ("delivery", DELIVERY, 1),
)
