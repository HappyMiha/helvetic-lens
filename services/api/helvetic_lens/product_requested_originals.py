"""Current requested-original execution, separate from fallible identity and truth."""
from copy import deepcopy

from .product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from .product_investigations import rows
from .product_operations import fingerprint

MATCH_CONTRACT = "requested-original-match/v1"
REASONS = {
    "matched_read": "A currently matched original has complete reading and analysis receipts; this does not verify its interpretation.",
    "not_identified": "The requested original has not been identified in current completed acquisition work.",
    "acquisition_unavailable": "An admitted read of the requested public URL was unavailable; no absence of source content is inferred.",
    "reading_incomplete": "The identified original does not yet have a current complete reading receipt.",
    "analysis_incomplete": "The identified original was read, but its complete current analysis has not been established.",
}
ORDER = {"reading_incomplete": 0, "analysis_incomplete": 1, "matched_read": 2}


def valid_match(value, source, requirement, question):
    """Validate the quoted identity binding, not the model's identity judgment."""
    from .product_document_analysis import source_views
    from .product_source_requirements import TARGET_MATCH_CONTRACT, match_contract
    from .research_reference_metadata import citation_use

    if not isinstance(value, dict) or not isinstance(value.get("identity"), dict):
        return False
    identity = value["identity"]
    quote, locator = identity.get("quote"), identity.get("locator")
    contract = match_contract(requirement, question)
    if (value.get("contract") != contract or value.get("question_fingerprint") != fingerprint(question)
            or contract == TARGET_MATCH_CONTRACT and value.get("origin") != requirement["origin"]
            or value.get("requirement_id") != requirement["id"]
            or value.get("requested_source") != requirement["requested_source"]
            or identity.get("source_id") != source.id or not source.sha256
            or identity.get("sha256") != source.sha256 or not source.url
            or not isinstance(quote, str) or not quote.strip() or not isinstance(locator, str)
            or not any(p.get("passage") == locator and quote in p.get("text", "")
                for p in source.snapshot.get("excerpts", []))):
        return False
    return citation_use(source_views([source])[source.id], locator, quote) != "reference_metadata"


def _sources(session, run):
    """Use the ordinary public-source fence, including exact recall lineage."""
    from .product_source_reviews import current_reviews
    from .research_knowledge import eligible_sources, origin_pin

    blocked = {url for url, review in current_reviews(session, run.dossier_id).items()
        if review.data_json["decision"] == "exclude"}
    current = {source.id: source for source in rows(session, InvestigationSource, run)
        if (source.investigation_id, source.organization_id, source.dossier_id)
            == (run.id, run.organization_id, run.dossier_id)
        and source.kind == "public_source" and source.snapshot.get("allow_discovery", True)
        and not ({source.url, source.snapshot.get("requested_url"), *source.snapshot.get("redirect_chain", [])} & blocked)}
    copies = [source for source in current.values() if "retained_origin" in source.snapshot]
    allowed = {source.id: source for source in session.scalars(eligible_sources(run))} if copies else {}
    origins = {}
    for source in copies:
        pin = source.snapshot["retained_origin"]
        identifier = pin.get("source_id") if isinstance(pin, dict) else None
        origin = allowed.get(identifier) if isinstance(identifier, str) else None
        if (origin is None or pin != origin_pin(origin) or source.url != origin.url or source.sha256 != origin.sha256
                or source.snapshot.get("excerpts") != origin.snapshot.get("excerpts")):
            current.pop(source.id)
        else:
            origins[source.id] = origin
    return current, origins, allowed, blocked


def _matches(source, origin, requirement, question):
    values = source.snapshot.get("requested_source_matches", [])
    if not isinstance(values, list):
        return False
    for value in values:
        if valid_match(value, source, requirement, question):
            return True
        # Recall keeps immutable old IDs. Only an exact revocable copy may use
        # its original note; neither matching text nor a shared SHA is lineage.
        original_values = origin.snapshot.get("requested_source_matches", []) if origin else []
        if (origin is not None and isinstance(original_values, list) and value in original_values
                and valid_match(value, origin, requirement, question)):
            return True
    return False


def _document_status(session, run, branch, key, doc, available):
    from .product_document_analysis import current_document_reading, duplicate_analysis

    ids = doc.get("source_ids")
    if (not isinstance(ids, list) or not ids or len(set(i for i in ids if isinstance(i, str))) != len(ids)
            or any(identifier not in available or available[identifier].sha256 != doc.get("sha256")
                for identifier in ids)):
        return None
    if any("duplicate_of" in available[identifier].snapshot for identifier in ids):
        proof = duplicate_analysis(session, run, doc)
        return "matched_read" if proof and all(identifier in available for identifier in proof["source_ids"]) else None
    if not doc.get("read_complete") or doc.get("next_cursor") or doc.get("error") or doc.get("warnings"):
        return "reading_incomplete"
    if current_document_reading(session, run, branch, key, doc, available):
        return "matched_read"
    return "analysis_incomplete"


def _reading_statuses(session, run, branches, current, origins, allowed, retained_branches):
    statuses = {}

    def remember(identifier, status):
        if status and ORDER[status] > ORDER.get(statuses.get(identifier), -1):
            statuses[identifier] = status

    for branch in branches:
        for key, doc in branch.checkpoint.get("document_reads", {}).items():
            status = _document_status(session, run, branch, key, doc, current)
            if status:
                for identifier in doc["source_ids"]:
                    remember(identifier, status)

    # A recalled portion alone is not a complete original. All original
    # portions must have exact authorized current copies, and the old analysis
    # must still prove this complete question against its current dependencies.
    copied = {}
    for identifier, origin in origins.items():
        copied.setdefault(origin.id, []).append(identifier)
    for previous, previous_branches in retained_branches:
        original_sources = {identifier: source for identifier, source in allowed.items()
            if source.investigation_id == previous.id}
        for branch in previous_branches:
            for key, doc in branch.checkpoint.get("document_reads", {}).items():
                ids = doc.get("source_ids")
                if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in copied for i in ids):
                    continue
                if any("duplicate_of" in original_sources[i].snapshot for i in ids):
                    from .product_document_analysis import duplicate_analysis
                    proof = duplicate_analysis(session, previous, doc)
                    if not proof or not set(proof["source_ids"]) <= copied.keys():
                        continue
                status = _document_status(session, previous, branch, key, doc, original_sources)
                if status:
                    for identifier in ids:
                        for copy_id in copied[identifier]:
                            remember(copy_id, status)
    return statuses


def _submitted(run, branch, url):
    """A literal URL must have been admitted through the submitted-source path."""
    from .product_source_recovery import public_state

    return public_state(branch.checkpoint) and any(
        question.get("id") == branch.checkpoint["question_id"] and question.get("branch_id") == branch.id
        for question in run.research_state.get("questions", [])) and any(
        item.get("url") == url and (item.get("submitted_public_source") is True
            or item.get("provider") == "Submitted public source")
        for item in branch.checkpoint.get("items", []))


def _direct_sources(run, branches, url, current):
    ids = set()
    failed = False
    for branch in branches:
        if not _submitted(run, branch, url):
            continue
        for step in branch.checkpoint.get("steps", []):
            if step.get("phase") != "read" or step.get("source_url") != url or step.get("skipped"):
                continue
            identifier = step.get("source_id")
            source = current.get(identifier) if isinstance(identifier, str) else None
            if step.get("status") == "completed" and source and url in {
                    source.url, source.snapshot.get("requested_url"), *source.snapshot.get("redirect_chain", [])}:
                ids.add(source.id)
            if step.get("status") == "unavailable" and not step.get("recovered_by"):
                failed = True
    return ids, failed


def outcomes(session, run, question_id=None):
    """Safe current execution summaries; no private identity quotes or receipts."""
    from .product_source_requirements import requirements

    required = requirements(run, question_id)
    if not required:
        return []
    current, origins, allowed, blocked = _sources(session, run)
    branches = [branch for branch in rows(session, InvestigationBranch, run)
        if (branch.investigation_id, branch.organization_id, branch.dossier_id)
            == (run.id, run.organization_id, run.dossier_id)]
    retained_branches = []
    for run_id in dict.fromkeys(origin.investigation_id for origin in origins.values()):
        previous = session.get(Investigation, run_id)
        if previous is not None and previous.question == run.question:
            retained_branches.append((previous, rows(session, InvestigationBranch, previous)))
    statuses = _reading_statuses(session, run, branches, current, origins, allowed, retained_branches)
    results = []
    for requirement in required:
        ids, unavailable, basis = set(), False, None
        if requirement.get("direct_url"):
            if requirement["direct_url"] not in blocked:
                ids, unavailable = _direct_sources(run, branches, requirement["direct_url"], current)
                for previous, previous_branches in retained_branches:
                    original_ids, _ = _direct_sources(previous, previous_branches, requirement["direct_url"], allowed)
                    ids.update(identifier for identifier, origin in origins.items() if origin.id in original_ids)
            if ids or unavailable:
                basis = "submitted_url"
        else:
            ids = {identifier for identifier, source in current.items()
                if ("duplicate_of" not in source.snapshot or statuses.get(identifier) == "matched_read")
                and _matches(source, origins.get(identifier), requirement, run.question)}
            if ids:
                basis = "quoted_match"
        status = (max((statuses.get(identifier, "reading_incomplete") for identifier in ids), key=ORDER.get)
            if ids else "acquisition_unavailable" if unavailable else "not_identified")
        result = {key: deepcopy(requirement[key]) for key in ("id", "requested_source", "question_id", "origin")}
        result.update(status=status, reason=REASONS[status])
        if requirement['origin'] == 'planner_interpretation' and status == 'not_identified':
            result['reason'] = 'The planned source target has not been identified in current completed acquisition work.'
        if basis:
            result.update(identity_basis=basis, read_complete=status in {"matched_read", "analysis_incomplete"},
                analysis_complete=status == "matched_read")
        results.append(result)
    return results
