# Environment variables the code reads

Names only. No value in this package is a secret, and no secret is needed to validate or
reproduce the canonical outputs: the one phase that needs a credential (FIRMS fire
detections) is skipped by `run_all.py --quick`, and its cached product ships in
`data/gis/manual/` with its hash in `data/SOURCE_MANIFEST.csv`.

| variable | read by | purpose | needed for validate.sh / reproduce.sh |
|---|---|---|---|
| `PKINV_ROOT` | `src/pkinv/paths.py` | the tree to treat as the repository root; every data, output and document path derives from it | **set by both scripts** to the package root (reproduce.sh points it at the temporary copy) |
| `PYTHONPATH` | the interpreter | `src/`, `tests/`, `tests/paper_numbers/` so the package needs no `pip install -e .` | set by both scripts |
| `PYTHON` | both scripts | interpreter to use (default `python3`) | optional |
| `FIRMS_MAP_KEY` | `src/pkinv/sectors/agriculture/gis/fetch_firms.py` | NASA FIRMS API key for the one network phase | **not needed**; unset by both scripts |
| `OPENSKY_TRINO_HOST`, `OPENSKY_TRINO_PORT`, `OPENSKY_TRINO_CATALOG`, `OPENSKY_TRINO_SCHEMA` (+ credentials) | `src/pkinv/sectors/aviation/opensky.py` | hand-run OpenSky acquisition, not a build phase | not needed |
| `GDAL_DISABLE_READDIR_ON_OPEN`, `CPL_VSIL_CURL_ALLOWED_EXTENSIONS` | `src/pkinv/core/gis/proxies.py` (`setdefault`) | GDAL behaviour when a raster is opened over HTTP; the proxies ship as national `.npy` caches so this path is not exercised | not needed |
| `PKINV_SLOW` | `tests/test_data_rederivation.py` | opt-in to the 317 MB OSM shapefile re-derivation test | optional (`PKINV_SLOW=1` if the OSM extract is present) |
| `http_proxy`, `https_proxy` (+ upper-case) | the interpreter's `urllib` | **exported to an unroutable address by both scripts** so any network attempt fails loudly | set by both scripts |
| `TMPDIR` | `reproduce.sh` | where the temporary copy is built (several GB) | optional |
