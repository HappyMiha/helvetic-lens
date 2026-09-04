# Third-party notices

The Elastic License 2.0 in this repository covers original Helvetic Lens code
and documentation, not third-party software or content. Retain the licenses and
copyright notices shipped with each dependency when distributing it.

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

This is not an exhaustive software bill of materials. Exact JavaScript and Python
versions are recorded in `package-lock.json`, `services/api/uv.lock`, and the model
manager requirements. Their distributed license files remain authoritative; the
project's license does not override them.

- Next.js, React, Tailwind, Radix, icons, fonts, Python libraries, and their
  transitive dependencies retain their own copyrights and licenses.
- PostgreSQL, Redis, Caddy, operating-system/container packages, CUDA, and
  llama.cpp are separately licensed components, not relicensed as ELv2. In
  particular, the Compose Redis 7.4 image has its own licensing terms.
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
