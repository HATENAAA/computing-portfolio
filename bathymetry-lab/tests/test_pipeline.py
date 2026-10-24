import unittest,tempfile,csv
from pathlib import Path
import numpy as np
from pipeline import train,load_samples
class PipelineTests(unittest.TestCase):
    def test_groups_do_not_overlap_and_scaler_fits_train_only(self):
        x=np.arange(160,dtype=float).reshape(40,4)/200;y=x[:,0]*10;groups=np.repeat(['a','b','c','d'],10)
        models,r=train(x,y,groups)
        self.assertFalse(set(r['train_groups']) & set(r['test_groups']))
        for model in models.values():np.testing.assert_allclose(model[0].data_max_,x[r['train_rows']].max(axis=0))
        self.assertLess(r['metrics']['linear']['rmse_m'],1e-8)
    def test_reproducible_split(self):
        x=np.arange(160,dtype=float).reshape(40,4)/200;y=x[:,0]*10;g=np.repeat(['a','b','c','d'],10)
        self.assertEqual(train(x,y,g)[1]['test_rows'],train(x,y,g)[1]['test_rows'])
    def test_temporal_mismatch_and_unit_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.csv'
            def write(image_date='2018-11-16',depth=2):
                with p.open('w',newline='') as f:
                    w=csv.writer(f);w.writerow(['B2','B3','B4','B8','depth_m','group_id','photon_date','image_date'])
                    for i in range(12):w.writerow([1000,2000,3000,4000,depth,str(i//3),'2018-11-16',image_date])
            write('2018-10-17')
            with self.assertRaisesRegex(ValueError,'Temporal mismatch'):load_samples(p,'dn')
            write();x,_,_=load_samples(p,'dn');self.assertAlmostEqual(x[0,0],.1)
            with self.assertRaises(ValueError):load_samples(p,'reflectance')
            write(depth=-3)
            with self.assertRaises(ValueError):load_samples(p,'dn')
if __name__=='__main__':unittest.main()
