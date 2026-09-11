# Offline development proof only; no application image or deployment dependency.
FROM mambaorg/micromamba:2.3.2@sha256:ce2026639d612fbe837a35ca9d513292a8d776a24a5e6c82cccf9dddf45ad3d2 AS definitions
USER root
COPY cosmo-24702.tar /tmp/cosmo.tar
RUN echo '40269dfa8c5315e47c31d47ca9e4b3b2042b4ea6ec4010d1ecc837da61a0d8c5  /tmp/cosmo.tar' | sha256sum -c - \
    && tar -xf /tmp/cosmo.tar -C /opt

FROM mambaorg/micromamba:2.3.2@sha256:ce2026639d612fbe837a35ca9d513292a8d776a24a5e6c82cccf9dddf45ad3d2
COPY linux-64.lock /tmp/decoder.lock
RUN micromamba install -y -n base -f /tmp/decoder.lock && micromamba clean --all --yes
COPY --from=definitions /opt/cosmo/definitions /opt/cosmo/definitions
COPY --from=definitions /opt/cosmo/RELEASE /opt/cosmo/RELEASE
ENV ECCODES_DEFINITION_PATH=/opt/cosmo/definitions:/opt/conda/share/eccodes/definitions
ENV ECCODES_DIR=/opt/conda
CMD ["python", "-c", "import eccodes; print(eccodes.codes_get_api_version())"]
