# PakEmis activity data

These 17 CSV tables contain the supplied activity records with readable headers, labels, units and period descriptions.
All 101,808 records and their exact numeric quantities are retained. No new measurements, totals or emissions estimates have been calculated.

## Start here

- Open the relevant `activity_*.csv` file. The first row contains the headers; there are no introductory comment rows.
- Read Value together with Measure, Unit, Period, Evidence and Source series. Filter to one compatible scope before adding records.
- Empty numeric cells mean no value was supplied. They are not zero. Unit magnitudes are unchanged: thousand tonnes stays thousand tonnes.
- CSV has no styling or frozen panes. Files use UTF-8 with a byte-order mark for Excel, commas, standard quoting and CRLF line endings.
- When importing into Excel, set Period and Record ID to Text to prevent automatic date conversion.

## Files

| File | Contents | Records |
| --- | --- | ---: |
| activity_aviation.csv | Aviation traffic | 5,680 |
| activity_crops.csv | Crop area and production | 9,336 |
| activity_fertiliser.csv | Fertiliser offtake | 3,641 |
| activity_fuel_sales_area.csv | Fuel sales by area | 43,770 |
| activity_fuel_sales_national.csv | National fuel sales | 4,071 |
| activity_gas_network.csv | Gas network and infrastructure | 35 |
| activity_gas_supply.csv | Oil production and gas supply | 124 |
| activity_household_fuel.csv | Household fuel use | 570 |
| activity_industry_fuel.csv | Industrial fuel use and supply | 1,529 |
| activity_industry_production.csv | Industrial production and trade | 1,081 |
| activity_livestock.csv | Livestock populations | 1,106 |
| activity_power_monthly.csv | Monthly electricity generation | 15,564 |
| activity_power_plants.csv | Annual power generation and fuel use | 1,618 |
| activity_railways.csv | Railway fuel and traffic | 44 |
| activity_vehicles.csv | Vehicle registrations and activity assumptions | 13,439 |
| activity_waste_flows.csv | Modelled waste flows | 10 |
| activity_waste_services.csv | Waste and sanitation services | 190 |

## Source details

`source_details.csv` preserves all 20 original fields, verbatim, for every record. Join on Record ID to recover the original label, period code, source file, row, column, reference, processing notes and aggregation guidance. The added Original record number counts data rows after the original header.

`column_guide.csv` explains every public column. `file_guide.csv` lists the datasets and measures. `data_notes.csv` groups the limitations shown in the tables.

## Gaps retained from the supplied exports

- Aviation: airport and airline identifiers are missing. Province labels do not uniquely identify the original observation.
- Area fuel sales: monthly and cumulative records overlap, and the additive flag mentioned in the original notes is absent. National fuel sales also contain overlapping totals and source extracts.
- Industrial gas: some monthly plant records contain a month name but no year. It has not been guessed.
- Periods: single fiscal-year codes are expanded only where their source convention is established. Other codes remain explicit. Following-year livestock projections retain their supplied period with a warning about the conflict.
- Mixed source editions and national/provincial/district totals must not be added indiscriminately. Blank source values and conflicting source-unit labels remain visible.

Waste-service province and locality labels were safely separated from their explicit original subcategory; the original generic Pakistan location remains available in source_details.csv. Technical fuel-classification details are separate from the reported monthly generation.

This cleanup improves presentation and exposes source problems. It does not certify the original measurements or resolve missing upstream dimensions.
