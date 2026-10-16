"""Source-to-export controls for modelled demographics and missing own-year crop panels."""
from collections import defaultdict
import unittest

from pkinv.assets import asset_path
from pkinv.core.io import read_rows
from pkinv.paths import DATA, OUTPUTS
from pkinv.report import spatial_weights as weights


class SpatialEvidenceSourceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = read_rows(asset_path(OUTPUTS, 'pakemis_spatial_weights_by_year.csv'))
        cls.population = read_rows(asset_path(DATA, 'activity', 'waste', 'population_district.csv'))
        cls.crops = read_rows(asset_path(DATA, 'activity', 'agriculture', 'crop_district_panel.csv'))

    def test_latest_industrial_liquid_source_geography_reaches_final_export(self):
        from pkinv.sectors.industry import province_shape, downscale
        from pkinv.report.grid_cube import period_keys
        period = 'FY2024-25'
        dispatched = downscale.load_shares(period_keys(period))
        for group, profile in province_shape.PROFILE_OF_GROUP.items():
            self.assertEqual(province_shape.months_covered(2025, group), 12)
            self.assertEqual(dispatched[profile], province_shape.shares(group, 2025))
        rows = [row for row in self.registry if row['period_id'] == period
                and row['surface'] == 'builtup+ocac_area_shares']
        self.assertEqual(len(rows), 18)  # six source liquid products, three native gases
        surfaces = {(row['period_id'], row['source_stream_id']): row
                    for row in read_rows(asset_path(OUTPUTS,
                        'pakemis_grid_stream_surfaces_by_year.csv'))}
        for row in rows:
            self.assertEqual(row['module'], 'industry')
            self.assertEqual(row['spatial_time_basis'], 'annual_observed_activity')
            self.assertEqual(row['weight_period'], period)
            self.assertEqual(row['borrowed_from_period'], '')
            self.assertEqual(row['temporal_operator'], 'own_period_pattern')
            self.assertEqual(row['pattern_hash'],
                             surfaces[(period, row['source_stream_id'])]['pattern_hash'])
            self.assertNotEqual(row['pattern_hash'], surfaces[
                ('FY2023-24', row['source_stream_id'])]['pattern_hash'])

    def test_actual_demographic_sources_are_models_not_annual_observations(self):
        for year in ('2024', '2025'):
            rows = [r for r in self.population if r['year'] == year]
            self.assertTrue(rows)
            self.assertTrue(all('PROJECTED' in r['source'] for r in rows))
        rows = [r for r in weights.build() if r['period_id'] == 'FY2024-25'
                and (r['district_panel'].startswith('resi:') or r['district_panel'] == 'waste:population')]
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row['spatial_time_basis'], ('modelled_population_proxy', 'substituted_surface'))
            self.assertEqual(row['activity_evidence_period'], 'mean(CY2024,CY2025)')
            self.assertEqual(row['activity_evidence_status'], 'census_population_projection')
            if row['district_panel'].startswith('resi:'):
                self.assertEqual(row['survey_pattern_period'], 'FY2024-25')
                self.assertEqual(row['survey_pattern_status'], 'own_period_survey_strata')

    def test_reference_households_distinguish_later_survey_from_population_projection(self):
        rows = [r for r in weights.build() if r['period_id'] == 'FY2023-24'
                and r['district_panel'].startswith('resi:')]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row['spatial_time_basis'], 'modelled_population_proxy')
            self.assertEqual(row['activity_evidence_period'], 'mean(CY2023,CY2024)')
            self.assertEqual(row['survey_pattern_period'], 'FY2024-25')
            self.assertEqual(row['survey_pattern_status'], 'fixed_survey_strata_reused')

    def test_absent_crop_source_produces_forward_reference_class(self):
        self.assertFalse([r for r in self.crops if r['period_id'] == 'FY2024-25'])
        rows = [r for r in weights.build() if r['period_id'] == 'FY2024-25'
                and r['district_panel'] in weights.CROP_PANELS]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row['spatial_time_basis'], 'reference_shape_forward')
            self.assertEqual(row['borrowed_from_period'], 'FY2023-24')
            self.assertEqual(row['weight_period'], 'FY2023-24')
            self.assertEqual(row['activity_evidence_status'], 'reference_district_pattern_reused')

    def test_flare_period_is_a_calendar_proxy_not_a_fiscal_observation(self):
        source = read_rows(asset_path(DATA, 'activity', 'fugitives', 'flare_sites_pak.csv'))
        rows = [r for r in weights.build() if r['surface'] == 'flare_points+uniform_fallback'
                and r['spatial_time_basis'] not in ('not_present', 'substituted_surface')]
        self.assertTrue(rows)
        for row in rows:
            year = row['period_id'][2:6]
            self.assertIn(year, source[0])
            self.assertEqual(row['spatial_time_basis'], 'calendar_activity_proxy')
            self.assertEqual(row['weight_period'], 'CY' + year)
            self.assertEqual(row['activity_evidence_period'], 'CY' + year)
            self.assertEqual(row['activity_evidence_status'], 'satellite_calendar_year_flaring_proxy')
            self.assertIn('six months', row['basis'])

    def test_the_final_export_matches_the_source_derived_registry(self):
        keys = lambda r: (r['source_stream_id'], r['period_id'])
        expected = {keys(r): {k: str(v) for k, v in r.items()} for r in weights.build()}
        actual = {keys(r): r for r in self.registry}
        self.assertEqual(actual, expected)

    def test_evidence_repair_does_not_change_the_emitted_weight_patterns(self):
        surface = {(r['source_stream_id'], r['period_id']): r for r in read_rows(
            asset_path(OUTPUTS, 'pakemis_grid_stream_surfaces_by_year.csv'))}
        checked = 0
        for row in weights.build():
            source = surface.get((row['source_stream_id'], row['period_id']))
            if source:
                self.assertEqual(row['pattern_hash'], source['pattern_hash'])
                self.assertEqual(row['surface'], source['surface'])
                self.assertEqual(row['district_panel'], source['district_panel'])
                checked += 1
        self.assertGreater(checked, 100)

    def test_air_exports_keep_the_same_support_and_explicit_model_status(self):
        registry = {(r['source_stream_id'], r['period_id']): r for r in self.registry}
        rows = read_rows(asset_path(OUTPUTS, 'pakemis_air_spatial_support_by_year.csv'))
        checked = 0
        for row in rows:
            reg = registry[(row['source_stream_id'], row['period_id'])]
            if reg['spatial_time_basis'] not in ('modelled_population_proxy', 'reference_shape_forward'):
                continue
            for field in ('spatial_time_basis', 'weight_period', 'pattern_hash',
                          'activity_evidence_status', 'activity_evidence_period',
                          'survey_pattern_period', 'survey_pattern_status'):
                self.assertEqual(row[field], reg[field], (field, row['source_stream_id']))
            checked += 1
        self.assertGreater(checked, 100)

    def test_air_evidence_shares_reconcile_to_process_masses(self):
        support = read_rows(asset_path(OUTPUTS, 'pakemis_air_spatial_support_by_year.csv'))
        masses = defaultdict(lambda: defaultdict(float))
        for row in support:
            cell = masses[(row['period_id'], row['configuration_id'], row['pollutant'])]
            mass = float(row['emissions_Gg'])
            cell[row['spatial_time_basis']] += mass
            cell['total'] += mass
        columns = {'observed_activity_pattern_mass_share': 'annual_observed_activity',
                   'static_pattern_mass_share': 'static_structural',
                   'modelled_population_pattern_mass_share': 'modelled_population_proxy',
                   'calendar_proxy_pattern_mass_share': 'calendar_activity_proxy'}
        for row in read_rows(asset_path(OUTPUTS, 'pakemis_air_uncertainty_split_by_year.csv')):
            cell = masses[(row['period_id'], row['configuration_id'], row['pollutant'])]
            for field, basis in columns.items():
                self.assertAlmostEqual(float(row[field]), cell[basis] / cell['total'], delta=5.1e-7)
            own = sum(cell[b] for b in columns.values()) / cell['total']
            self.assertAlmostEqual(float(row['own_pattern_mass_share']), own, delta=5.1e-7)
            borrowed = (cell['reference_shape_backcast'] + cell['reference_shape_forward']) / cell['total']
            self.assertAlmostEqual(float(row['borrowed_pattern_mass_share']), borrowed, delta=5.1e-7)


if __name__ == '__main__':
    unittest.main()
