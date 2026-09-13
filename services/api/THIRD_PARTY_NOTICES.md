# Third-party notices

The Apache License 2.0 in this repository covers original Helvetic Lens code
and documentation, not third-party software or content. Retain the licenses and
copyright notices shipped with each dependency when distributing it.

## Transport protobuf runtime

- **gtfs-realtime-bindings 2.2.0**: Apache-2.0, MobilityData and contributors.
  https://github.com/MobilityData/gtfs-realtime-bindings
  The generated classes are distributed as a dependency, not copied into this
  repository. Preserve the package license and the repository Apache-2.0 license.
- **protobuf 7.36.1**: BSD-3-Clause, Copyright 2008 Google Inc.
  https://github.com/protocolbuffers/protobuf
  Preserve the distribution's `protobuf-7.36.1.dist-info/LICENSE`, including its
  redistribution conditions, disclaimer and generated-code ownership notice.

## PDF processing

- **pdfminer.six 20260107** (runtime): MIT, Yusuke Shinyama and contributors.
  https://github.com/pdfminer/pdfminer.six
- **ReportLab 4.5.1** (development/tests only): BSD-3-Clause, ReportLab Inc.
  https://www.reportlab.com/

The following license wording is copied from the locked distributions; trailing whitespace is normalized.

### pdfminer.six license

```
Copyright (c) 2004-2016  Yusuke Shinyama <yusuke at shinyama dot jp>

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

### ReportLab license (development only)

```
#####################################################################################
#
#	Copyright (c) 2000-2024, ReportLab Inc.
#	All rights reserved.
#
#	Redistribution and use in source and binary forms, with or without modification,
#	are permitted provided that the following conditions are met:
#
#		*	Redistributions of source code must retain the above copyright notice,
#			this list of conditions and the following disclaimer.
#		*	Redistributions in binary form must reproduce the above copyright notice,
#			this list of conditions and the following disclaimer in the documentation
#			and/or other materials provided with the distribution.
#		*	Neither the name of the company nor the names of its contributors may be
#			used to endorse or promote products derived from this software without
#			specific prior written permission.
#
#	THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#	ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#	WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
#	IN NO EVENT SHALL THE OFFICERS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
#	INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
#	TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
#	OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
#	IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
#	IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
#	SUCH DAMAGE.
#
#####################################################################################
```

## Other dependencies and content

Hazard Watch administrative geometry uses **pyproj 3.7.2** (MIT, with PROJ's
distributed `LICENSE_proj`) and **Shapely 2.1.2** (BSD 3-Clause). Shapely wheels
include GEOS under LGPL 2.1; retain the installed `LICENSE_GEOS`, the library and
its applicable redistribution/relinking obligations. Windows wheels additionally
carry their Visual C++ runtime notice (`LICENSE_win32`). NumPy's exact distribution
contains BSD-3-Clause, 0BSD, MIT, Zlib and CC0-1.0 components and bundled notices.
Keep each wheel's complete `dist-info/licenses` directory in built distributions;
this summary does not replace those license texts or relicense GEOS.

The native swissBOUNDARIES3D administrative dataset is attributed to **Federal
Office of Topography swisstopo**, under its
[OGD terms](https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices).
The source archive stays outside Git; retained proofs include its version, hash
and attribution. Geographic reuse rights do not grant access to warning feeds.

This is not an exhaustive software bill of materials. Exact JavaScript and Python
versions are recorded in `package-lock.json`, `services/api/uv.lock`, and the model
manager requirements. Their distributed license files remain authoritative; the
project's license does not override them.

- Next.js, React, Tailwind, Radix, icons, fonts, Python libraries, and their
  transitive dependencies retain their own copyrights and licenses.
- PostgreSQL, Redis, Caddy, operating-system/container packages, CUDA, and
  llama.cpp are separately licensed components, not relicensed under the
  repository license. In particular, the Compose Redis 7.4 image has its own
  licensing terms.
- Apertus/GGUF model weights and upstream chat templates retain the terms of
  their exact upstream revision. Model catalogue license/acceptance fields still
  apply; no model weights are licensed by the Helvetic Lens LICENSE file.
- Laws, court decisions, parliamentary material, news, imported documents,
  source-provider content, and user data are not relicensed by this project.
  Observe their source terms and any applicable attribution requirements.
- Third-party character names, trademarks, voices, and other media are not
  granted additional rights by the project license.

Before redistributing a combined build or offering a separately licensed service,
review the actual bundled components and preserve their notices. Licenses for
system packages and optional assets must travel with those components.
