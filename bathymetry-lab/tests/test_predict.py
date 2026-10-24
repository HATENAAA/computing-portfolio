import csv
import tempfile
import unittest
from pathlib import Path
import joblib
import numpy as np
from pipeline import train, BANDS
from predict import predict_samples


class PredictionTests(unittest.TestCase):
    def test_export_reload_preserves_features_and_reports_extrapolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            x = np.arange(160, dtype=float).reshape(40, 4) / 400 + .1
            models, _ = train(x, x[:, 0] * 10, np.repeat(['a', 'b', 'c', 'd'], 10))
            joblib.dump(dict(model=models['linear'], bands=BANDS, input_units='reflectance'), root/'linear.joblib')
            (root/'input.csv').write_text('sample_id,B2,B3,B4,B8\nknown,2000,2025,2050,2075\noutside,9000,9025,9050,9075\n')
            report = predict_samples(root/'linear.joblib', root/'input.csv', 'dn', root/'output.csv')
            with (root/'output.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]['sample_id'], 'known')
            self.assertAlmostEqual(float(rows[0]['predicted_depth_m']), 2)
            self.assertEqual(rows[1]['outside_training_range'], 'True')
            self.assertEqual(report['count'], 2)
            self.assertTrue((root/'output.metadata.json').is_file())

    def test_invalid_bands_and_nonfinite_inputs_fail_before_loading_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for content in ['B2,B3\n1,2\n', 'B2,B3,B4,B8\nnan,.2,.3,.4\n', 'B2,B3,B4,B8\n']:
                (root/'bad.csv').write_text(content)
                with self.assertRaises(ValueError):
                    predict_samples(root/'missing.joblib', root/'bad.csv', 'reflectance', root/'out.csv')
