"""Public query answers must preserve the released period, configuration and species."""
from collections import defaultdict
import unittest
from pkinv.core.io import read_rows
from pkinv.paths import OUTPUTS
from pakemis_query.models import QueryEmissions, QueryAir
from pakemis_query import errors
from semantic._golden import open_engine

class IntegratedReleaseQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=open_engine()
        cls.periods=tuple('FY%d-%02d'%(year,(year+1)%100) for year in range(2015,2025))
        cls.ghg=read_rows(OUTPUTS+'/pakemis_ghg_configuration_atoms.csv')
        cls.air=read_rows(OUTPUTS+'/pakemis_air_annual_fy2015_16_fy2024_25.csv')

    def test_all_ten_years_and_four_configurations_match_native_account_aggregates(self):
        for cfg in ('S_TAN','L_TAN','S_IPCC','L_IPCC'):
            for gwp in ('AR5','AR6'):
                expected=defaultdict(float)
                for row in self.ghg:
                    if row['configuration_id']==cfg:expected[row['period_id']]+=float(row['co2e_Mt_'+gwp])
                answer=self.engine.query_emissions(QueryEmissions(periods=self.periods,configuration_id=cfg,gwp_basis=gwp,group_by=('period_id',)))
                actual={v['group']['period_id']:float(v['exact']) for v in answer['values']}
                self.assertEqual(set(actual),set(self.periods))
                for period in self.periods:self.assertAlmostEqual(actual[period],expected[period],delta=1e-7)

    def test_air_panel_matches_species_native_masses_in_every_configuration(self):
        for cfg in ('S_TAN','L_TAN','S_IPCC','L_IPCC'):
            expected=defaultdict(float)
            for row in self.air:
                if row['configuration_id']==cfg:expected[(row['period_id'],row['pollutant'])]+=float(row['emissions_Gg'])
            answer=self.engine.query_air(QueryAir(periods=self.periods,configuration_id=cfg,group_by=('period_id','pollutant')))
            actual={(v['group']['period_id'],v['group']['pollutant']):float(v['exact']) for v in answer['values']}
            self.assertEqual(set(actual),set(expected))
            for key in expected:self.assertAlmostEqual(actual[key],expected[key],delta=1e-7)

    def test_nested_pollutant_sum_is_refused(self):
        with self.assertRaises(errors.GrainUnavailable):
            self.engine.query_air(QueryAir(pollutants=('PM2.5','BC'),periods=('FY2024-25',)))

    def test_provisional_year_cannot_return_common_scope_national_total(self):
        with self.assertRaises(errors.UnknownDimensionValue):
            self.engine.query_emissions(QueryEmissions(periods=('FY2025-26',)))
        with self.assertRaises(errors.UnknownDimensionValue):
            self.engine.query_air(QueryAir(periods=('FY2025-26',),pollutants=('NOx',)))
