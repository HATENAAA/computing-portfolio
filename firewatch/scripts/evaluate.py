"""Evaluate an independently labelled CSV: path,label (label 0 or 1). No bundled accuracy claims."""
import argparse,csv,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from app.detector import analyze,Config
p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('--output',type=Path,default=Path('evaluation.json'));args=p.parse_args()
rows=[]
with args.manifest.open(encoding='utf-8-sig') as source:
    records=list(csv.DictReader(source))
for row in records:
    path=args.manifest.parent/row['path']
    if row['label'] not in ('0','1'):raise ValueError('label must be 0 or 1')
    img=cv2.imdecode(np.fromfile(path,dtype=np.uint8),1)
    result,_=analyze(img,Config())
    rows.append(dict(path=row['path'],label=int(row['label']),detected=int(result['detected']),elapsed_ms=result['elapsed_ms'],methods=result['methods']))
if not rows:raise ValueError('empty manifest')
def metrics(pred):
    tp=sum(r['label']==1 and y==1 for r,y in zip(rows,pred));fp=sum(r['label']==0 and y==1 for r,y in zip(rows,pred))
    tn=sum(r['label']==0 and y==0 for r,y in zip(rows,pred));fn=sum(r['label']==1 and y==0 for r,y in zip(rows,pred))
    return dict(tp=tp,fp=fp,tn=tn,fn=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
report=dict(config=Config().__dict__,count=len(rows),ensemble=metrics([r['detected'] for r in rows]),
            by_method={name:metrics([int(next(m for m in r['methods'] if m['method']==name)['detected']) for r in rows]) for name in ('Sobel','Canny','Laplacian','Scharr')},
            mean_algorithm_ms=sum(r['elapsed_ms'] for r in rows)/len(rows),rows=rows)
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(args.output)
