# Compile-on-save size-limit diagnosis

Reviewed from the project diagnostic export on October 11, 2026. Only relevant
environment and reproduction details are retained here; activity logs, private
paths, project identifiers and source excerpts remain local.

SuperSurfer 0.1.42 on Linux x86_64/Python 3.10.12 recorded repeated save-triggered
builds that failed during source snapshotting with `LaTeX file exceeds its size
limit`. The original thesis tree contains roughly 242 MB of inputs, above the
100 MiB source cap. Its complete output is above the separate 50 MiB PDF cap.
The configured root `main.tex` was absent, and the page displayed a static PDF.

The application patch increases the bounded compiler allowances to match the
512 MiB viewer/artifact allowance and reports the offending source path when
the aggregate source budget is exceeded. Project repair adds a small root
`main.tex` that imports the original thesis and its local dependencies, then
connects the PDF tile to compiler output. It does not copy or rewrite prose.

Reproduce the large-source and save-triggered behavior without the dissertation:

```sh
python3 -m unittest discover -s tests -p test_latex.py -v
node tests/large-latex.browser.cjs
```

To verify a local large document, set `SUPERSURFER_TEST_LATEX_REPO` to its Git
repository containing `main.tex`. The fixture copies Git-visible inputs to a
temporary project, then compiles, edits and saves only that copy. The local
dissertation fixture produced two successful 226-page builds of about 80 MB.
Neither the document nor private diagnostic logs are included in this PR.
