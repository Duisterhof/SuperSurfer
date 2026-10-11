# Third-party components

The GPL grant covers SuperSurfer's original code, not third-party works under
separate terms. Keep the following notices with source and binary distributions.
This inventory describes the current bundled components; dependency changes need
a license review too.

| Component | License | Notices shipped with the app |
| --- | --- | --- |
| Electron and Chromium | MIT and component-specific licenses | Electron package `LICENSE` and `LICENSES.chromium.html` |
| Monaco editor | MIT; third-party notices | `ui/vendor/monaco/LICENSE`, `ThirdPartyNotices.txt`, generated `.LEGAL.txt` files |
| PDF.js | Apache-2.0; font/codec/color-profile component notices | `ui/vendor/pdfjs/LICENSE` and notices in `cmaps`, `standard_fonts`, `wasm`, `iccs` |
| KaTeX | MIT and font licenses | `ui/vendor/katex/LICENSE` and bundled font notices |
| Plotly basic | MIT | `ui/vendor/plotly-basic.min.js.LICENSE.txt` |
| nspell | MIT | Generated spelling worker/extension `.LEGAL.txt` notices |
| English Hunspell dictionary / SCOWL | MIT and BSD notices | `ui/vendor/spelling/license`, `editor_extension/DICTIONARY-LICENSE` |

Build scripts retain the editor, PDF and dictionary notices. Electron packaging
includes its upstream license files. The optional Code OSS/code-server runtime
is downloaded separately; its licenses stay in that runtime. User-installed
extensions, AI provider CLIs and user projects have their own terms and are not
relicensed by SuperSurfer.

PDF.js's Apache-2.0 terms are incompatible with GPLv2-only, but compatible with
GPLv3. SuperSurfer's **GPLv2-or-later** grant allows distribution of the combined
app under GPLv3. A copy is in `GPL-3.0.txt`. Retain the Apache notices too.

For binary distribution, provide the exact corresponding source (including any
changes), build scripts and the applicable dependency source, as required by the
chosen GPL version. A link to a moving `main` branch alone is not an exact source
release. Tag source releases and retain the lockfile. See `CONTRIBUTING.md` for
build instructions.
