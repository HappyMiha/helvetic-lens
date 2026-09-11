FROM python:3.11-slim@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff AS definitions
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git init /tmp/cosmo && cd /tmp/cosmo \
    && git remote add origin https://github.com/COSMO-ORG/eccodes-cosmo-resources.git \
    && git fetch --depth 1 origin 019e3357ebbfcc1924b237565514978b451c9b51 \
    && git -c core.autocrlf=false -c core.eol=lf archive --format=tar --prefix=cosmo/ FETCH_HEAD > /tmp/cosmo.tar \
    && echo '40269dfa8c5315e47c31d47ca9e4b3b2042b4ea6ec4010d1ecc837da61a0d8c5  /tmp/cosmo.tar' | sha256sum -c - \
    && tar -xf /tmp/cosmo.tar -C /opt

FROM mambaorg/micromamba:2.3.2@sha256:ce2026639d612fbe837a35ca9d513292a8d776a24a5e6c82cccf9dddf45ad3d2
COPY scripts/pollen-decoder/linux-64.lock /tmp/decoder.lock
RUN micromamba install -y -n base -f /tmp/decoder.lock && micromamba clean --all --yes
COPY --from=definitions /opt/cosmo/definitions /opt/cosmo/definitions
COPY --from=definitions /opt/cosmo/RELEASE /opt/cosmo/RELEASE
COPY scripts/pollen_decode_proof.py services/pollen-decoder/server.py /app/
ENV ECCODES_DEFINITION_PATH=/opt/cosmo/definitions:/opt/conda/share/eccodes/definitions
ENV ECCODES_DIR=/opt/conda
WORKDIR /app
EXPOSE 8093
CMD ["python", "/app/server.py"]
