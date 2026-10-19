# The history rewrite of 19 October 2026

On 19 October 2026 this repository's history was rewritten to remove the manuscripts - the
papers, their LaTeX sources, their compiled PDFs, the paper copies in the rc67 baseline and the
tests of their text - from every commit, not only from the current tree (1.0.0rc70 is the first
release without them). Nothing else in any commit changed: each rewritten commit carries the
same files, apart from those paths, with the same messages, authors and dates. The tree of the
commit that began rc70 was byte-identical before and after the rewrite.

Every commit identifier therefore changed. Records written before the rewrite - the release
manifests of rc67-rc69, `CHANGELOG.md`, `docs/reproduction/`, the published deposits and their
`RELEASE_SNAPSHOT.json` - name the OLD identifiers, and are left as written. This table maps
each old identifier to the commit that now carries the same content.

Text mentions of the manuscripts in old commits (comments, prose, manifest rows) were not
edited; only the files were removed. Copies of the old history in clones or forks made before
the rewrite are not affected by it.

| old commit | new commit | date | subject |
|---|---|---|---|
| `383f93918e2b` | `3a93b4976e0b` | 2026-10-13 | PakEmis 1.0.0rc67: public copy |
| `3cef2f397c74` | `3dcbe2ae6c79` | 2026-10-16 | PakEmis 1.0.0rc68: public copy |
| `97e255c5fb87` | `4e478816e568` | 2026-10-16 | Development moves to the public repository; the documents become restricted layers |
| `c2ce7df66af2` | `9e06d6c9d1f6` | 2026-10-16 | A clone without the restricted layers runs its own checks; SPAM rice gets grid caches |
| `9154123e8950` | `8f1da0b84827` | 2026-10-16 | Build phases declare their kind; make dev stops rendering the papers |
| `4bf512b4ac97` | `61d90931128d` | 2026-10-16 | Publish the rc68 reproduction record |
| `f018c834079b` | `645ba6c7f4cb` | 2026-10-16 | Public checks and complete reproduction as two workflows; pin the restricted-skip set |
| `1cd52a416738` | `f1b6866e4a32` | 2026-10-16 | Decompose the year-on-year coal change per species: activity, seam, split and print |
| `9f0497a39ee9` | `90d96e017bd5` | 2026-10-16 | Table 2 separates road transport from off-road machinery; absent-mode seeding is explicit |
| `0aa003ad9ac7` | `3b71a189a622` | 2026-10-16 | Hold the FIRMS VIIRS 2025 Pakistan country file in the raw manifest and the retention ledg |
| `a0272cca654d` | `e78acbd98793` | 2026-10-16 | Measured validation as one compact table (paper Table 4) |
| `aadef1968993` | `e1314cc01bae` | 2026-10-16 | Hold the EMEP/EEA 2023 agriculture chapters (3.B, 3.D) in the raw manifest and retention l |
| `93d99ee6bd01` | `80f4a7e494da` | 2026-10-16 | Nitrogen partition against EMEP/EEA 2023 pathway by pathway; power-stack omission beside t |
| `ab97d5106480` | `aa67ef090f4b` | 2026-10-17 | FY2024-25 burning gets its own fire record; road particulates under Tier 2 technology fact |
| `9b77738b3152` | `732b59c68b2c` | 2026-10-17 | Audit the two conditional-uncertainty phases so they run side by side |
| `fa07d347768a` | `fb3673efd2f7` | 2026-10-17 | Tests: read the longitudinal components once, build the fresh manifest once |
| `ec4442623f03` | `e0df87ff738b` | 2026-10-17 | Public checks: seed the release category without the layers; set the CI environment |
| `a1b9b6875716` | `aa73d4ce5c92` | 2026-10-17 | Grid located share: sum in an order-independent way (PYTHONHASHSEED defect) |
| `c17ce18f673d` | `f7d508a41ad6` | 2026-10-17 | Build performance: October timings for the categorised development group |
| `3666de90d688` | `10e3cc8a555c` | 2026-10-17 | CHANGELOG: the build workflow and the hash-seed sum |
| `67acefbdc136` | `6a6f2c736581` | 2026-10-17 | Public checks: allow a run by hand as well as on push |
| `1e537d346d17` | `8e0e1f73e5a5` | 2026-10-17 | Two tests that depended on the machine, found by the first CI run |
| `a72d3b5e2f3f` | `9f34b0a148b9` | 2026-10-17 | Public checks: compare the Ubuntu rebuild to platform precision, not bytes |
| `4c9c3792762e` | `925ade1f3614` | 2026-10-17 | mint_release: drop three version sites the papers no longer carry; patch the v1 short summ |
| `12769f251996` | `8b78063d2b12` | 2026-10-17 | compare_rebuild: digest columns, decimal-text Parquet, and one-printed-unit slack |
| `dabb2626d8d1` | `6144c1664cf3` | 2026-10-17 | PakEmis 1.0.0rc69: version |
| `140f9abadad3` | `827a398cab80` | 2026-10-17 | Strict build: three forward reads the order check found in the full group |
| `a8efa650304c` | `d9fd1a607395` | 2026-10-17 | PakEmis 1.0.0rc69: the strict build (version stamps and receipts; no number moved) |
| `f3f7faec9d6a` | `ac10d5f729b3` | 2026-10-17 | Receipts converge before the fixpoint (deposit last) |
| `be42daa93c30` | `e4eed1f89d55` | 2026-10-17 | Release manifest, cover, SHA256SUMS and PDFs: regenerate against the clean 1.0.0rc69 tree |
| `a22d5444d9af` | `12f2d9489bc9` | 2026-10-17 | rc69 fixpoint repairs: semantic release on the converged registers, goldens re-frozen |
| `9498083e09f4` | `97e1ceae6438` | 2026-10-17 | Receipts converge before the fixpoint (deposit last) |
| `89dd59627f0e` | `98c4160d225d` | 2026-10-17 | Sync paper figures: skip every generated fragment; declare the coverage table |
| `d8d874622f9a` | `97f38d702bd2` | 2026-10-17 | Receipts converge before the fixpoint (deposit last) |
| `99545cfba7fb` | `65a10df1e084` | 2026-10-17 | Release manifest, cover, SHA256SUMS and PDFs: regenerate against the clean 1.0.0rc69 tree |
| `9e28473da598` | `ce6d839f4c73` | 2026-10-17 | Record the 1.0.0rc69 release run on the fixpoint tree |
| `1ba250711797` | `5be5daffd186` | 2026-10-17 | Validation package: follow an overlay mount of a restricted file |
| `278301af40d7` | `d93fd9077f60` | 2026-10-17 | Revert "Validation package: follow an overlay mount of a restricted file" |
| `ae61ba9ca5d6` | `004cb5cca2f4` | 2026-10-17 | rc69: deposit the reproduction records; a deposit tree is not a public clone |
| `88b97dcaa82e` | `d63e6e73b52a` | 2026-10-17 | release_finish.sh: the rc69 path (own code, campaign hand-off, deposit last) |
| `94aec6bbb484` | `eea579916289` | 2026-10-17 | Receipts converge before the fixpoint (deposit last) |
| `622cd5ca80ed` | `967f3f4e9ef1` | 2026-10-18 | Release manifest, cover, SHA256SUMS and PDFs: regenerate against the clean 1.0.0rc69 tree |
| `d14af798a61e` | `dcb6e134ea3c` | 2026-10-18 | release_finish.sh: repeat the release tail until it stops moving |
| `169811a40abd` | `7abee86119ce` | 2026-10-18 | Receipts converge before the fixpoint (deposit last) |
| `af943613976f` | `7d5602055b13` | 2026-10-18 | Release manifest, cover, SHA256SUMS and PDFs: regenerate against the clean 1.0.0rc69 tree |
| `d93ddc7ff386` | `49351946acba` | 2026-10-19 | Record the 1.0.0rc69 release run on the fixpoint tree |
| `fb4380b159ba` | `9a45c9802cdc` | 2026-10-19 | rc70: the inventory without its manuscripts |
| `985a446fae49` | `b7ba6e44e007` | 2026-10-19 | rc70: documentation and tooling without the manuscripts |
| `758949580b07` | `cf17ee9e940a` | 2026-10-19 | CHANGELOG: the rc70 section, written before the mint |
| `728126d80a4c` | `412dcc689fd8` | 2026-10-19 | rc70: publish the rc69 reproduction record; measured validation reads it |
| `1421e38f807e` | `200d23e70e5b` | 2026-10-16 | docs: searchable title and links to the related PAQI projects |

The full 40-character identifiers are in `docs/history_rewrite_commit_map.txt` (old, new).
