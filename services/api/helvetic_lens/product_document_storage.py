"""Retain one anonymous original for local, integrity-checked continuation."""
import hashlib
import os


def retain(folder, prefix, body, metadata):
    digest = hashlib.sha256(body).hexdigest()
    key = f"research-{prefix}-{digest}.original"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / key
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Retained original integrity mismatch") from None
    else:
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(body)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    return {**metadata, "artifact_key": key, "sha256": digest}


async def read(service, work):
    from .product_contributions import read_file

    original = work["retained_document"]
    result = await read_file(service.environment_settings.storage_path / "artifacts",
        {**original, "cursor": work["document_cursor"]})
    return {**result, "url": original["url"], "fetched_at": original["fetched_at"],
        "links": original.get("links", []), "_retained_document": original,
        "requested_url": original.get("requested_url"), "redirect_chain": original.get("redirect_chain", [])}
