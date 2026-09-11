# Reproduce the MV2-069 offline decoder

This Linux/amd64 development image is separate from the application and serving
stack. Building downloads public dependencies; decoding uses no network, secrets,
database or production volume. Source collection still requires its own gates.

The native ecCodes and Python bindings are both 2.47.0. The unchanged official
[COSMO release v2.47.0.2](https://github.com/COSMO-ORG/eccodes-cosmo-resources/tree/v2.47.0.2)
requires that native version. The base image is digest-pinned and `linux-64.lock`
records every Conda package URL/build and SHA-256, avoiding a fresh solver result.
This is a reproducible tested dependency set, not a provider endorsement.

In a separate scratch checkout, clone the official resources at tag `v2.47.0.2`,
then verify that HEAD is `019e3357ebbfcc1924b237565514978b451c9b51`:

```sh
git clone --depth 1 --branch v2.47.0.2 https://github.com/COSMO-ORG/eccodes-cosmo-resources.git cosmo-24702
git -C cosmo-24702 rev-parse HEAD
git -C cosmo-24702 -c core.autocrlf=false -c core.eol=lf archive --format=tar --prefix=cosmo/ --output=../cosmo-24702.tar HEAD
```

Copy the resulting archive into this directory (ignored by Git). `git archive`
preserves original blobs and symlinks even on Windows; do not archive the working
directory, normalize line endings or modify upstream definitions. The Dockerfile
rejects an archive whose SHA-256 differs from
`40269dfa8c5315e47c31d47ca9e4b3b2042b4ea6ec4010d1ecc837da61a0d8c5`.
Upstream documentation remains in the source archive.

Complete-feature follow-up, 2026-09-11: Git for Windows had applied CRLF conversion
to 698 text files in the earlier retained archive (SHA-256 `227486af…`). An offline
entry-by-entry comparison found identical names, metadata and all contents after
CRLF-to-LF normalization. The command now explicitly disables conversion. The
canonical Linux archive retains original LF bytes, and its 712-file definition
tree hash is `45a9168efdf755dfe281cb00c0525e7c39d71cbc82513dbd6a819926c8509a1a`.
The earlier proof remains historical evidence of the CRLF runtime; it must not be
described as byte-identical upstream definitions. The canonical runtime was
rechecked offline against the same official capture with matching scientific
results. No source or product gate is granted by that decoding check.

From the repository root:

```sh
docker build --platform linux/amd64 -t helvetic-pollen-decoder:mv2-069-eccodes247 scripts/pollen-decoder
docker run --rm --network none --cpus 1 --memory 1g \
  -v "ABSOLUTE_PROOF_DIRECTORY:/proof:ro" -v "ABSOLUTE_TASK_CHECKOUT:/task:ro" \
  helvetic-pollen-decoder:mv2-069-eccodes247 \
  python /task/scripts/pollen_decode_proof.py --proof /proof --cosmo-root /opt/cosmo --output -
```

Replace both absolute paths with the retained capture and isolated task checkout.
Save stdout as UTF-8 JSON only after checking exit code 0; stderr contains the
summary and any native diagnostics. All input mounts remain read-only. A runtime
version mismatch fails before GRIB reading. The result records the native/Python/
numpy versions, COSMO release and a deterministic definition-tree digest (sorted
relative POSIX filename + NUL + binary SHA-256 of each file, then SHA-256 of the
concatenation). Neither a successful decode nor matching previous numbers closes
category, seasonal coverage, lifecycle, source rights or user acceptance.
