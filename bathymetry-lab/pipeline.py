"""Satellite-derived bathymetry regression, with explicit units and grouped evaluation."""
import argparse,csv,hashlib,json
from pathlib import Path
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from datetime import date
import joblib
BANDS=('B2','B3','B4','B8')

def load_samples(path,units,max_days=1):
    if units not in ('reflectance','dn'): raise ValueError('units must be reflectance or dn')
    with Path(path).open(encoding='utf-8-sig') as source:
        records=list(csv.DictReader(source))
    if len(records)<10:raise ValueError('At least 10 labelled samples required')
    for row in records:
        if not row['group_id'].strip(): raise ValueError('group_id must identify a scene, track, or spatial block')
        gap=abs((date.fromisoformat(row['photon_date'])-date.fromisoformat(row['image_date'])).days)
        if gap>max_days:raise ValueError(f'Temporal mismatch: {gap} days exceeds {max_days}')
    x=np.array([[float(r[b]) for b in BANDS] for r in records]);y=np.array([float(r['depth_m']) for r in records])
    if not np.isfinite(x).all() or not np.isfinite(y).all(): raise ValueError('Non-finite values')
    if (y<0).any():raise ValueError('depth_m must be non-negative depth, not uncorrected elevation h')
    if units=='dn':x=x/10000.0
    if (x<0).any() or (x>1).any():raise ValueError('Expected reflectance in [0,1]; verify scale/offset and quality mask')
    return x,y,np.array([r['group_id'] for r in records])

def train(x,y,groups,seed=42):
    if len(set(groups))<3:raise ValueError('At least 3 independent groups required')
    train_idx,test_idx=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=seed).split(x,y,groups))
    if len(test_idx)<2:raise ValueError('Need at least two test samples')
    models={'linear':make_pipeline(MinMaxScaler(),LinearRegression()),
            'svr':make_pipeline(MinMaxScaler(),SVR(C=100,gamma=.1,epsilon=.1))}
    reports={};predictions={}
    for name,model in models.items():
        model.fit(x[train_idx],y[train_idx]);pred=model.predict(x[test_idx]);predictions[name]=pred.tolist()
        reports[name]=dict(rmse_m=float(np.sqrt(mean_squared_error(y[test_idx],pred))),
                           mae_m=float(mean_absolute_error(y[test_idx],pred)),
                           r2=float(r2_score(y[test_idx],pred)) if np.var(y[test_idx])>0 else None)
    report=dict(seed=seed,features=BANDS,split='group_holdout',train_rows=train_idx.tolist(),test_rows=test_idx.tolist(),
                train_groups=sorted(set(groups[train_idx])),test_groups=sorted(set(groups[test_idx])),
                metrics=reports,test_depth_m=y[test_idx].tolist(),predictions=predictions)
    return models,report

def main():
    p=argparse.ArgumentParser();p.add_argument('csv',type=Path);p.add_argument('--units',choices=['reflectance','dn'],required=True)
    p.add_argument('--max-days',type=int,default=1);p.add_argument('--seed',type=int,default=42);p.add_argument('--out',type=Path,default=Path('runs/latest'))
    a=p.parse_args()
    if a.max_days<0:p.error('--max-days must be nonnegative')
    x,y,g=load_samples(a.csv,a.units,a.max_days);models,report=train(x,y,g,a.seed)
    report.update(input_sha256=hashlib.sha256(a.csv.read_bytes()).hexdigest(),units=a.units,max_days=a.max_days,
                  note='Input depths and scene matching must be verified independently. This is a held-out comparison, not new algorithm research.')
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for name,model in models.items():joblib.dump(dict(model=model,input_units='reflectance',bands=BANDS),a.out/f'{name}.joblib')
    with (a.out/'predictions.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['source_row','depth_m','linear_m','svr_m'])
        writer.writerows(zip(report['test_rows'],report['test_depth_m'],report['predictions']['linear'],report['predictions']['svr']))
    print(a.out/'report.json')
if __name__=='__main__':main()
