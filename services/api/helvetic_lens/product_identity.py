"""Public product names with stable, access-scoped historical storage keys."""

LEGAL_PREFIX = "/api/products/legal"
LEGACY_PREFIX = "/api/products/loyer"


def public_product_slug(product):
    if product in {"loyer", "legal"}:
        return "legal"
    if product == "pharma":
        return "pharma"
    raise ValueError("Unknown product")


class ProductAliasMiddleware:
    """Resolve the public legal name before the existing authorization stack.

    Every route, body, cookie, CSRF check and organization/dossier grant continues
    through the same pipeline. This avoids copying or rewriting private records,
    historical publication snapshots, idempotency keys or invitation tokens.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] == "http" and (path == LEGAL_PREFIX or path.startswith(LEGAL_PREFIX + "/")):
            scope = dict(scope)
            scope["path"] = LEGACY_PREFIX + path[len(LEGAL_PREFIX):]
            raw = scope.get("raw_path")
            if raw is not None and (raw == LEGAL_PREFIX.encode() or raw.startswith((LEGAL_PREFIX + "/").encode())):
                scope["raw_path"] = LEGACY_PREFIX.encode() + raw[len(LEGAL_PREFIX):]
            else:
                scope.pop("raw_path", None)
        await self.app(scope, receive, send)
