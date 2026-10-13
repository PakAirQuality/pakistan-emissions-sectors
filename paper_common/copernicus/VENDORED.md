# Vendored: the Copernicus Publications LaTeX package

This directory is a verbatim copy of the publisher's LaTeX macro package, kept in the
tree so that the ESSD manuscript (`paper_national/paper_national.tex`) compiles the same
way on every machine and in CI. **It is the publisher's work, not this project's**, and
the CC-BY-4.0 grant in `LICENSE-data` does not cover it; each file carries its own
copyright and licence header (the class and the `pdfscreen` styles are under the LaTeX
Project Public License, the `.bst` is Patrick W. Daly's LPPL-licensed style).

| Field | Value |
|---|---|
| Source | https://publications.copernicus.org/Copernicus_LaTeX_Package.zip |
| Package version | 7.15 (25 August 2026); `copernicus.cls` 10.1.34, `copernicus.bst` 1.6 |
| Zip SHA-256 | `f31563e860a42c6bb980de4f29c670881eccca42b31f084fc11b7f0070040767` |
| Vendored on | 2026-08-29 |

Files (unchanged from the archive, except that `template.tex` is renamed
`template_reference.txt` so that no build loop treats it as a manuscript):

- `copernicus.cls`, `copernicus.cfg`, `copernicus.bst`
- `pdfscreen.sty`, `pdfscreencop.sty`
- `README_copernicus_package_7_15.txt`
- `template_reference.txt` (the publisher's `template.tex`, kept for reference only)

How the build finds them: the Makefile's `paper-national` target exports
`TEXINPUTS=../paper_common/copernicus//:` and `BSTINPUTS=../paper_common/copernicus//:`
for `latexmk`; CI's tectonic step copies the class files beside the master before
compiling and removes them afterwards, because tectonic does not read `TEXINPUTS`.

To update: download the archive again, record the new zip digest and date here, and
replace the files wholesale; never patch them in place.
