"""Usage: python evaluate_cubes.py pairs.csv --data-range 1 --scale 4 --out runs/check01"""
import argparse,csv,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from safe_metrics import assess

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('--data-range',type=float,required=True);p.add_argument('--scale',type=float,required=True);p.add_argument('--out',type=Path,default=Path('runs/latest'));a=p.parse_args()
    with a.manifest.open(encoding='utf-8-sig') as source:
        records=list(csv.DictReader(source))
    if not records:raise ValueError('Empty manifest')
    a.out.mkdir(parents=True,exist_ok=True);results=[]
    for i,row in enumerate(records):
        paths=[a.manifest.parent/row[k] for k in ('truth','prediction')]
        x,y=[np.load(path,allow_pickle=False) for path in paths]
        metrics,angles=assess(x,y,a.data_range,a.scale)
        heat=np.nan_to_num(angles,nan=0.0)/180.0
        rgb=np.stack([heat*255,np.zeros_like(heat), (1-heat)*255],axis=2).astype('uint8')
        rgb[~np.isfinite(angles)]=[100,100,100]
        Image.fromarray(rgb).save(a.out/f'{i:03d}_sam.png')
        np.save(a.out/f'{i:03d}_sam_deg.npy',angles)
        results.append(dict(truth=row['truth'],prediction=row['prediction'],truth_sha256=hashlib.sha256(paths[0].read_bytes()).hexdigest(),
                            prediction_sha256=hashlib.sha256(paths[1].read_bytes()).hexdigest(),metrics=metrics))
    (a.out/'report.json').write_text(json.dumps(dict(data_range=a.data_range,scale=a.scale,layout='HWC',samples=results),indent=2,allow_nan=False))
    print(a.out/'report.json')
if __name__=='__main__':main()
