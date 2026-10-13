"""Agriculture: IPCC 3.A-3.H, the largest sector of the national inventory.

Two layers live here, and the distinction is worth knowing before reading the files.

THE SECTOR COMPUTATION, which the national rollup consumes through the registry contract:
enteric fermentation, manure management, managed soils, rice, residue burning and liming and
urea, with the emission-factor library and the provincial downscale behind them. The
residential sector's dung-cake closure reads `manure` directly, so this is load-bearing well
outside agriculture.

THE MANUSCRIPT LAYERS, which the sector paper in papers/agriculture/ reports and nothing else
depends on: the nitrogen ledger, the agriculture-scoped Monte Carlo and key-category screen,
the 1990-2024 trend, the air-pollutant trend and uncertainty tables, the manure-management
sensitivity, and the gridded and district surfaces under gis/.

Those layers briefly lived in a separate repository, on the reasoning that they were
"research" rather than inventory. They are back, because the agriculture manuscript is one of
nine sector papers now and a paper whose figures cannot be regenerated from the repository
holding it is not reproducible. What stayed behind is the satellite nowcasting and the machine
learning that feeds it - work that estimates emissions BETWEEN census years, which is a
different question from the one this sector answers.
"""
