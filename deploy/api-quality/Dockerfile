# Test-only tools. Never added to the production API image.
FROM ghcr.io/astral-sh/uv@sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36
RUN apt-get update && apt-get install -y --no-install-recommends git && apt-get clean
RUN git --version && uv --version
