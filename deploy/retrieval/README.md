# Pinned local saved-evidence retrieval

This optional CPU service extends the shared search/decision layer; existing
hosted Jev and local Laya keep their own routing and availability. It adds no
external provider, vector database or private search endpoint on the public web.

Build with `docker compose -f deploy/retrieval/compose.yaml build`. Use the same
protected `LAYA_SECRET_FILE` already mounted by the Laya service, then run this
compose project's `up -d --no-build`. Only this separate service is affected.
Configure `EVIDENCE_EMBEDDING_URL=http://helvetic-lens-retrieval:8000/v1/embeddings`
through the protected native production environment and normal native release.
Do not put keys in Git or URLs. Without this optional service, Words and direct
Laya comparison stay available. No hosted fallback receives private text.

The image pins E5-small revision614241f622f53c4eeff9890bdc4f31cfecc418b3 and
PyTorch2.14.0 / Transformers5.17.0 / FastAPI0.141.1 / Uvicorn0.54.0 /
safetensors0.8.0. Transitive wheels and the base image still resolve at build
time; record the final image digest. Model/config/tokenizer files and original
model card are downloaded at build time. Runtime loading is offline, safetensors
only, with no remote code. See THIRD_PARTY_NOTICES.md for attribution.

Runtime:2 CPUs,3GiB, one active inference,16 strings of at most4,000 characters,
512 tokens/model input,384 normalized floats,300kB body and no access logs.
There is no server text/vector cache. The root is read-only, capabilities are
removed, temporary storage is bounded and only the existing private model-control
network is joined. No host port is published; every model
request requires the protected bearer token. Health exposes model identity only.
Cancellation retains the CPU slot until its computation ends. Busy requests
fail explicitly rather than building an unbounded queue.

Native PostgreSQL stores discardable source-contained binary vectors, exact
model/input hashes and truncation metadata. It stores no search question, copied
source body or relevance judgment in that cache. Current dossier/source/page
permissions are reapplied before cache selection, counts and ranking. The original
sources and claims remain authoritative and are never overwritten by preparation.

The native app prepares16 records per short authorized request. A stopped or
lost connection can resume; the client drives further checkpoints only while
its exact session/dossier/query attempt is current. No background query or new
scheduler exists. First preparation may take minutes; later queries reuse inputs.
The20,000-record bound fails visibly instead of silently truncating older records.

Run isolated service contracts with the image and mounted `test_server.py` in
`/opt/retrieval`; they use a controlled encoder and no credentials/model calls.
Native adapter and dossier tests run under the standard API test environment.
The NoMIRACL evaluation script and receipts are linked from
`docs/PRODUCT_CORPUS_SEARCH.md`; no production private data is an evaluation input.
