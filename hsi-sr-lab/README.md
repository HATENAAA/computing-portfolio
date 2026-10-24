# Hyperspectral Super Resolution Reproduction and Evaluation

Reproduction materials for the published **MCArb** method, with a standalone CPU evaluation workflow. The method and network are attributed to the original authors; see the unmodified [upstream README and paper citation](UPSTREAM_README.md) and [AGPL licence](LICENSE).

## Added evaluation work

- `safe_metrics.py`: explicit edge-case handling for six reconstruction measures.
- `evaluate_cubes.py`: HWC `.npy` pairs, required data range and scale, per-band errors, spectral-angle maps and input hashes.
- `tests/test_safe_metrics.py`: numerical cases for undefined metrics, exact reconstructions and small spatial dimensions.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-eval.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python evaluate_cubes.py pairs.csv --data-range 1 --scale 4 --out runs/eval-x4
```

The CSV columns are `truth,prediction`; paths are relative to the CSV. Dataset arrays and weights are not bundled. See [evaluation details](UPGRADE.md) for metric definitions and limitations. Original training scripts are retained separately and have not been revalidated with the new metric implementation.
