# Acquisition requests

Eight requests, drafted to be sent by the maintainer. **None has been sent.**

Each names the exact fields the inventory needs and asks only for permission to publish
normalised monthly weights and aggregated derivatives - never to republish the source
tables, which the deposit does not carry and does not need
(`outputs/pakemis_source_register.csv`).

The ranked reason each matters is `outputs/pakemis_temporal_decomposition.csv`: the
weakly-timed share of the monthly product, by block.

| # | recipient | what it would close |
|---|---|---|
| [01](01_ocac_petroleum.md) | Oil Companies Advisory Council | Monthly petroleum sales by sector, product and province, J |
| [02](02_pbs_energy_mining.md) | Pakistan Bureau of Statistics - Energy and M | Monthly oil, gas, coal production and plant-level electric |
| [03](03_ppis_upstream.md) | Pakistan Petroleum Information Service / Dir | Monthly field-level upstream production, FY2015-16 to FY20 |
| [04](04_sngpl.md) | Sui Northern Gas Pipelines Limited | Monthly gas commodity balance, July 2015 - June 2024 |
| [05](05_ssgc.md) | Sui Southern Gas Company Limited | Monthly gas commodity balance, July 2015 - June 2024 |
| [06](06_nfdc.md) | National Fertilizer Development Centre | Monthly fertiliser offtake, production and stocks, July 20 |
| [07](07_waste_operators.md) | Municipal waste companies | Monthly waste tonnage and wastewater flows, July 2015 - Ju |
| [08](08_pcaa_railways.md) | Pakistan Civil Aviation Authority; and Pakis | Monthly domestic movements and monthly traction fuel, July |

## The three public datasets, attempted and not obtained

The roadmap named PBS QIM, the NFDC monthly fertiliser series and OGRA's monthly LPG
consumption reports as immediately implementable from public sources. All three were
attempted on 19 August 2026 and **all three failed at the discovery stage** — 404, 503, and a
page that serves no document links without client-side rendering. Every attempt is recorded
with its URL and error in `data/acquisition_attempts.csv`.

That is a fact about the attempt, not about the data. Each dataset is documented as existing;
what failed was an unauthenticated guess at its current address, and guessing further is how a
scrape becomes a rabbit hole. The formal requests here are the route that does not depend on
guessing, and a maintainer-side check of the three current publication URLs would likely close
all three without any request at all.
