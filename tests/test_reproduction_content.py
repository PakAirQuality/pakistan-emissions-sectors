"""A NetCDF rebuild must reproduce values, masks, labels and scientific metadata."""
import os
import tempfile
import unittest

import netCDF4
import numpy as np
from validation.compare_outputs import cube_diff, numeric_csv_diff


class ReproductionContent(unittest.TestCase):
    def test_missing_rows_and_nonfinite_replacements_fail_csv_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [os.path.join(folder, name + ".csv") for name in ("a", "b")]
            with open(paths[0], "w") as handle:
                handle.write("key,mass\na,1\nb,2\n")
            for text in ("key,mass\na,1\n", "key,mass\na,nan\nb,2\n",
                         "key,mass\na,inf\nb,2\n", "key,mass\na,1\nb,3\n"):
                with open(paths[1], "w") as handle:
                    handle.write(text)
                self.assertGreater(numeric_csv_diff(*paths)[1], 1e-9)

    def test_changed_mask_units_or_values_cannot_pass_as_container_churn(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [os.path.join(folder, name + ".nc") for name in ("a", "b")]
            def write(path, units="Gg", values=(1., 2., -9999.)):
                with netCDF4.Dataset(path, "w") as ds:
                    ds.createDimension("cell", 3)
                    var = ds.createVariable("mass", "f4", ("cell",), fill_value=-9999.)
                    var.units = units
                    var[:] = values
            for path in paths:
                write(path)
            self.assertEqual(0., cube_diff(*paths)[1])
            for kwargs in ({"units": "kg"}, {"values": (1., 2., 0.)},
                           {"values": (1., 3., -9999.)}, {"values": (np.nan, 2., -9999.)}):
                write(paths[1], **kwargs)
                self.assertGreater(cube_diff(*paths)[1], 1e-9, kwargs)


if __name__ == "__main__":
    unittest.main()
