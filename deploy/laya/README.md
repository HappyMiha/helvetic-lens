# Optional local decision service

This separate CPU service serves the upstream Apache-2.0 Laya System One API.
It does not replace the native generative model or its manager. Model weights are
not in Git. The Dockerfile pins Laya 0.3.20 source to
`4066d5d5fbf08b66c6757ddeedbd797bd7655bc0` and the multilingual checkpoint to
`e4e9ddf21a7b1903b7acffd8814ad4307bf63a67`. Preserve the upstream licenses in the
image and [model repository](https://huggingface.co/convaiinnovations/laya-multilingual).
Transitive Python wheels/base image resolve at build time; record the built image
digest with release evidence. Do not claim fully reproducible transitive resolution.

Bootstrap the normal native deployment networks first. Generate a random service
token in protected operator storage (not this directory), mode 0600, readable only
by container UID 10001. Set `LAYA_SECRET_FILE` to its absolute path and run
`docker compose -f deploy/laya/compose.yaml up --build -d` from the core checkout.
The initial download needs outbound access to public Hugging Face model assets.
The service has two CPU cores, 4 GB memory, a read-only root, a bounded temporary
filesystem, no Linux capabilities and loopback-only port 18761. It is also reachable
from the native API over its existing private `model-control` Docker network.

Configure the protected native production environment:

- `LAYA_BASE_URL=http://helvetic-lens-laya:8000/v1/systemone`
- `LAYA_API_KEY`: the same private service token
- `SEARCH1API_API_KEY`: web-index account key
- `TYPESAFE_API_KEY`: optional funded hosted Jev account key
- `DECISION_SEARCH_DAILY_LIMIT=25`: aggregate daily search reservation budget
- `JEV_INPUT_USD_PER_MILLION=0.042`, `JEV_OUTPUT_USD_PER_MILLION=0`: operator
  estimate basis, recheck provider pricing before changing it

Apply these through the normal native release; never edit serving source files.
The health endpoint proves service health, not relevance accuracy. Validate a
non-confidential query through the typed adapter after activation. Inference and
search failures are explicit; Auto falls back to Laya, while Jev-only does not.
Provider credits are a separate requirement. No automatic purchase or top-up is
configured by this service. Stop/recreate only this compose project for its own
maintenance; do not restart unrelated model services or retired Monitoring stacks.
