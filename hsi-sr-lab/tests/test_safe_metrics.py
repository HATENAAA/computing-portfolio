import unittest
import numpy as np
from safe_metrics import assess
class MetricsTests(unittest.TestCase):
    def test_identical_nonconstant(self):
        x=np.random.default_rng(4).random((8,9,4));r,_=assess(x,x)
        self.assertEqual(r['RMSE'],0);self.assertTrue(r['psnr_has_infinite_band'])
        self.assertAlmostEqual(r['MSSIM'],1);self.assertLess(r['SAM_deg'],1e-5)
        self.assertAlmostEqual(r['CrossCorrelation'],1);self.assertEqual(r['ERGAS'],0)
    def test_zero_spectra_are_explicitly_undefined(self):
        r,a=assess(np.zeros((8,8,3)),np.zeros((8,8,3)))
        self.assertIsNone(r['SAM_deg']);self.assertIsNone(r['ERGAS']);self.assertIsNone(r['CrossCorrelation'])
        self.assertEqual(r['sam_valid_pixels'],0);self.assertTrue(np.isnan(a).all())
    def test_known_orthogonal_angle(self):
        x=np.zeros((3,3,2));y=x.copy();x[:,:,0]=1;y[:,:,1]=1
        r,_=assess(x,y);self.assertAlmostEqual(r['SAM_deg'],90)
    def test_shape_and_nan_rejected(self):
        with self.assertRaises(ValueError):assess(np.ones((3,3,2)),np.ones((3,3,3)))
        x=np.ones((3,3,2));x[0,0,0]=np.nan
        with self.assertRaises(ValueError):assess(x,x)
    def test_small_spatial_extent_and_known_rmse(self):
        r,_=assess(np.ones((2,2,3)),np.ones((2,2,3))*.5)
        self.assertEqual(r['RMSE'],.5);self.assertIsNone(r['MSSIM'])
        self.assertAlmostEqual(r['MPSNR'],10*np.log10(4))
if __name__=='__main__':unittest.main()
