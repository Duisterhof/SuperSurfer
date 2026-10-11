# Repository PDF HTTP 413 diagnostic excerpt

Reviewed October 11, 2026. The project's diagnostic export was reviewed locally;
this excerpt retains only the relevant environment and verified reproduction.
Private activity, paths, identifiers and source excerpts are omitted.

The reported service is SuperSurfer 0.1.40 on Linux x86_64, Python 3.10.12,
using a Writing workflow. The generated repository PDF is 66,094,149 bytes
and contains 226 pages. The repository path exists and begins with `%PDF-`.
Calling its descriptor-bound PDF reader raises HTTP 413 with
`PDF previews support files up to 32 MiB`, before delivery to PDF.js.
This reproduces independently of PDF rendering or LaTeX compilation.

To reproduce without the original document, the browser regression generates
a valid two-page PDF with a 33 MiB unreferenced stream, saves it in an isolated
fixture repository and opens its authenticated PDF tile:

```sh
node tests/large-pdf.browser.cjs
```

The patched service accepts and renders this fixture. Authenticated download
hashes match the original file; unauthenticated reads still return 401.
Optional `SUPERSURFER_TEST_PDF` selects a local large PDF for verification;
`SUPERSURFER_TEST_SERVICE_ROOT` selects the packaged service directory.
Neither input is committed or published. See VALIDATION.md for build/check
results and the unrelated pre-existing arrangement-test failure.
