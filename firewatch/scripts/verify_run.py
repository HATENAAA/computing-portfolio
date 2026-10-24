"""Verify a saved run's output bytes and reproducibility fingerprint without loading images."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(folder):
    folder = Path(folder)
    report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    provenance = report['provenance']
    signature = {key: provenance[key] for key in
                 ('source_sha256', 'detector_sha256', 'algorithm', 'config', 'opencv', 'numpy')}
    expected = hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    errors = []
    if report['config'] != provenance['config'] or report['algorithm'] != provenance['algorithm']:
        errors.append('report parameters or algorithm differ from provenance')
    if expected != provenance['fingerprint']:
        errors.append('analysis fingerprint mismatch')
    for name, expected_hash in provenance['output_sha256'].items():
        # Never follow paths supplied in a report outside this run folder.
        if name not in ('original.png', 'mask.png', 'overlay.png', 'sobel.png',
                        'canny.png', 'laplacian.png', 'scharr.png'):
            errors.append('invalid output name: ' + name)
            continue
        path = folder / name
        if path.resolve().parent != folder.resolve():
            errors.append('output resolves outside run folder: ' + name)
            continue
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            errors.append('output missing or changed: ' + name)
    if set(provenance['output_sha256']) != {'original.png', 'mask.png', 'overlay.png',
            'sobel.png', 'canny.png', 'laplacian.png', 'scharr.png'}:
        errors.append('output manifest incomplete')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_folder')
    args = parser.parse_args()
    try:
        errors = verify(args.run_folder)
    except (KeyError, ValueError, OSError, TypeError) as exc:
        parser.exit(1, f'Invalid run: {exc}\n')
    print(json.dumps({'verified': not errors, 'errors': errors}, ensure_ascii=False))
    raise SystemExit(1 if errors else 0)
