"""Explainable colour, brightness and edge-based region detector. BGR input."""
from dataclasses import dataclass, asdict
import time
import cv2
import numpy as np

METHODS = ('Sobel', 'Canny', 'Laplacian', 'Scharr')
@dataclass
class Config:
    brightness: int = 150
    edge_ratio: float = 0.6
    min_area_ratio: float = 0.002
    min_component: int = 40
    def __post_init__(self):
        if not 0 <= self.brightness <= 255: raise ValueError('brightness must be 0..255')
        if not 0 <= self.edge_ratio <= 1 or not 0 <= self.min_area_ratio <= 1: raise ValueError('ratios must be 0..1')
        if not 1 <= self.min_component <= 100000: raise ValueError('invalid min_component')

def analyze(img, cfg=None):
    cfg = cfg or Config()
    if img is None or img.dtype != np.uint8 or img.ndim != 3 or img.shape[2] != 3:
        raise ValueError('Expected uint8 BGR image')
    start = time.perf_counter()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    binary = (gray > cfg.brightness).astype('uint8') * 255
    b, g, r = cv2.split(img)
    color = (r > float(r.mean())) & (r > g) & (g < 200) & (b < 100)
    kernel = np.ones((3, 3), np.uint8)
    candidates = (color & (gray > cfg.brightness)).astype('uint8') * 255
    candidates = cv2.morphologyEx(candidates, cv2.MORPH_CLOSE, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(candidates)
    mask = np.zeros(gray.shape, np.uint8)
    boxes = []
    for k in range(1, n):
        x, y, w, h, area = map(int, stats[k])
        if area >= cfg.min_component:
            mask[labels == k] = 255
            boxes.append(dict(x=x, y=y, width=w, height=h, pixels=area))
    area_ratio = float(np.count_nonzero(mask) / mask.size)
    edge_maps = {'Canny': cv2.Canny(binary, 100, 200),
                 'Laplacian': cv2.convertScaleAbs(cv2.Laplacian(binary, cv2.CV_64F, ksize=3))}
    for name, fn in [('Sobel', cv2.Sobel), ('Scharr', cv2.Scharr)]:
        args = {'ksize': 3} if name == 'Sobel' else {}
        gx = fn(binary, cv2.CV_64F, 1, 0, **args)
        gy = fn(binary, cv2.CV_64F, 0, 1, **args)
        edge_maps[name] = cv2.convertScaleAbs(cv2.magnitude(gx, gy))
    # A gradient straddles both sides of a boundary; allow one-pixel color support.
    support = cv2.dilate((color & (gray > cfg.brightness)).astype('uint8'), kernel) > 0
    methods = []
    assets = {'original': img, 'mask': mask}
    overlay = img.copy()
    selected = mask > 0
    overlay[selected] = (img[selected] * 0.45 + np.array([20, 130, 255]) * 0.55).astype('uint8')
    for box in boxes:
        x,y,w,h = (box[k] for k in ('x','y','width','height'))
        cv2.rectangle(overlay, (x,y), (x+w-1,y+h-1), (30,190,255), 2)
    assets['overlay'] = overlay
    for name in METHODS:
        edge = cv2.morphologyEx(edge_maps[name], cv2.MORPH_CLOSE, kernel) > 0
        ratio = float(np.count_nonzero(edge & support) / np.count_nonzero(edge)) if edge.any() else 0.0
        methods.append(dict(method=name, edge_pixels=int(edge.sum()), edge_color_ratio=ratio,
                            detected=bool(edge.any() and ratio >= cfg.edge_ratio and area_ratio >= cfg.min_area_ratio and boxes)))
        assets[name.lower()] = edge.astype('uint8') * 255
    result = dict(algorithm='color-edge-v2', width=img.shape[1], height=img.shape[0], config=asdict(cfg),
                  detected=any(m['detected'] for m in methods), area_ratio=area_ratio, boxes=boxes, methods=methods,
                  elapsed_ms=round((time.perf_counter()-start)*1000, 2),
                  note='颜色规则命中率不是置信度或准确率；橙色物体和夕阳可能误报。')
    return result, assets
