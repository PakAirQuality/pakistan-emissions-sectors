"""The field-application dung variant volatilises the nitrogen it adds.

WHY. The variant S_residual_field_application adds the unresolved residual's nitrogen to applied
organic N (FON) and reruns soils. The reference pools carry the organic field releases that
manure.compute derived for the REFERENCE N state, and soils.volatilised_n uses those stored pools
whenever they are present - so until 21 October 2026 the added nitrogen raised direct and leaching
N2O while its volatilisation, and the indirect N2O on it, stayed at the reference value (found by an
external audit). This test fails if that freezing returns: the variant must price more N2O than a
FON bump with the stored pools left untouched would.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.report import dung_variants                              # noqa: E402
from pkinv.sectors.agriculture import manure, soils                 # noqa: E402
from pkinv.sectors.residential import combustion                    # noqa: E402
from pkinv.sectors.residential.data import ResidentialData          # noqa: E402


def _n2o(components):
    return sum(c["emissions_Gg"] for c in components if c["gas"] == "N2O")


class TheAddedNitrogenVolatilises(unittest.TestCase):
    def test_the_variant_prices_the_volatilisation_of_the_added_nitrogen(self):
        priced = dung_variants.price()
        year = priced["year"]
        agri = dung_variants._agriculture(year, ResidentialData().year)
        _comps, npools = manure.compute(agri)
        soils_ref = soils.compute(agri, npools)
        residual = sum(combustion.diverted_n_by_species(agri).values()) * priced["share_unresolved"]

        frozen = dict(npools)                                  # the pre-fix computation
        frozen["FON_N"] = npools["FON_N"] + residual
        frozen_dn2o = _n2o(soils.compute(agri, frozen)) - _n2o(soils_ref)

        variant = priced["variants"]["S_residual_field_application"]["n2o_Gg"]
        self.assertGreater(variant, frozen_dn2o + 1.0,
                           "the field-application variant prices no volatilisation on the added N")

        before = soils.volatilised_n(agri, npools)["organic"]
        rate = before / npools["FON_N"]
        self.assertGreater(rate, 0.0)
        # the added nitrogen volatilises at the reference's own organic field rate
        expected_extra_volatilised = residual * rate
        self.assertGreater(expected_extra_volatilised, 1e8)    # kg N: the residual is ~1 Mt N


if __name__ == "__main__":
    unittest.main()
