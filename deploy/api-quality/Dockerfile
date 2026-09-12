# Test-only tools. Never added to the production API image.
FROM ghcr.io/astral-sh/uv@sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36
# Keep package extraction/building bounded on hosts shared with running services.
# The gate's bind-mounted cache and ephemeral environment use different filesystems.
ENV UV_CONCURRENT_INSTALLS=1 \
    UV_CONCURRENT_BUILDS=1 \
    UV_CONCURRENT_DOWNLOADS=2 \
    UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends git && apt-get clean
RUN git --version && uv --version
