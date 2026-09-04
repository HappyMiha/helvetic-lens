# Licensing Helvetic Lens

The original Helvetic Lens code and documentation are **source-available under
[Elastic License 2.0](../LICENSE)**, SPDX identifier `Elastic-2.0`. This is not an
OSI-approved open-source license. The unmodified license text is authoritative;
this page explains it without adding conditions or exceptions.

## Practical examples

| Use | Under the standard license |
| --- | --- |
| Run the portal for yourself or internally within your company | Allowed, including commercial organizations. |
| Inspect, modify, or share copies of the code | Allowed subject to the license, including preservation of notices and identifying modifications. |
| Charge for consulting or installation on a client's own internal deployment | Not prohibited merely because it is paid; the hosted/managed-service limitation still applies. |
| Operate a hosted or managed Helvetic Lens portal for third parties with access to a substantial set of its features | Requires a separate agreement with the relevant rights holders. This restriction applies whether access is paid or free. |
| Keep your modifications private | ELv2 does not require publishing modified source code. Contributions upstream are welcome, not mandatory. |

ELv2 is **not a blanket ban on earning money**. It specifically limits hosted or
managed access to substantial software functionality, circumvention of license-key
functionality, and removal or obscuring of licensing/copyright/other notices. No
license keys, paywall, telemetry, or registration restrictions are added by this
licensing change.

For a separate hosting/commercial agreement, contact the project maintainer through
the [HappyMiha GitHub profile](https://github.com/HappyMiha), or open a
[licensing inquiry](https://github.com/HappyMiha/helvetic-lens/issues/new) without
posting private business information. An inquiry is not permission to operate a
restricted service. Separate grants depend on the rights held by the relevant
copyright owners; this repository does not grant rights to relicense third-party
code or other contributors' work under unrelated terms.

## Scope and packaging

- Third-party libraries, model weights, runtimes, fonts, voices, and downloaded
  public documents keep their own licenses and usage terms. The project license
  does not transfer ownership of these materials or customer data. See
  [third-party notices](../THIRD_PARTY_NOTICES.md).
- This change does not retroactively relicense previous releases or third-party
  code. PyMuPDF was removed from the current runtime, tests, and dependency lock;
  historical commits and already built images can still contain it under its own
  terms. Rebuild before distributing this release.
- JavaScript and Python package metadata use `Elastic-2.0`. The built API wheel
  and sdist include the license and notices; application Docker images carry them
  as well. Container base images and installed dependencies have separate terms.
- `services/api/LICENSE`, `services/api/NOTICE`, and
  `services/api/THIRD_PARTY_NOTICES.md` mirror the root files because the API has
  its own Docker build context. Keep those copies byte-identical when updating.

## References

- [Official ELv2 text](https://www.elastic.co/licensing/elastic-license)
- [Official examples and FAQ](https://www.elastic.co/licensing/elastic-license/faq)
- [SPDX identifier](https://spdx.org/licenses/Elastic-2.0.html)

Have nonstandard commercial arrangements reviewed by qualified counsel before
signing them. Do not append a noncommercial clause to AGPL or describe ELv2 as
requiring all modifications to become public.
