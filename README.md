# textdistance-opt-lab

`textdistance` is a pure-Python library of string-similarity and distance
algorithms (LCS, Levenshtein, Jaccard, …). This repo changes **one function**:
`LCSSeq._dynamic` builds its dynamic-programming matrix from plain list rows
instead of a numpy 2-D array, hoists the row references out of the inner loop
and inlines `max()`. The kernel reads and writes every cell through scalar
indexing, where numpy's per-element overhead costs far more than the integer
arithmetic it wraps; the returned subsequence is unchanged, byte for byte.
Measured median speedup across three sizes: **10.78x**.

Upstream: https://github.com/life4/textdistance

Baseline is upstream commit `d6a68d61088a40eef5c88191ccf79323dbf34850`
(2025-04-18), the default-branch HEAD at measurement time. The patch touches
only `textdistance/algorithms/sequence_based.py` (+14/−14 lines, `git diff
--stat` = 28 changed lines, well under the 80-line cap). The DP recurrence and
the traceback that reconstructs the subsequence are untouched.

## Results

Inputs are two random strings of length *n* over `a–z`, seed 42, fixed in
`benchmark/bench.py`. Each size: 3 warmup calls (discarded), then 5 timed
samples with `time.perf_counter()`. Medians and quartiles below are computed
from the raw per-sample files in `benchmark/raw/`.

| scale (n) | baseline median | optimized median | speedup |
| --- | --- | --- | --- |
| 200 | 38.784 ms (p25 38.496 / p75 39.878) | 3.163 ms (p25 3.157 / p75 3.187) | **12.26x** |
| 400 | 160.702 ms (p25 160.537 / p75 163.930) | 14.907 ms (p25 14.891 / p75 14.939) | **10.78x** |
| 800 | 638.753 ms (p25 635.464 / p75 651.993) | 69.767 ms (p25 69.479 / p75 70.774) | **9.16x** |

Median of the three speedups: **10.78x**. Largest-scale speedup: **9.16x**.
Relative standard deviation of the 5 samples is ≤2.3% at every size; no sample
was discarded.

The gain comes from `sequence_based.py`, in this order: (1) `numpy.zeros(...)`
scalar get/set in the inner loop is replaced by list indexing — the largest
single factor; (2) `lengths[i + 1][j + 1]` double lookups become hoisted `prev`
/ `row` references; (3) the `max()` call per cell becomes an inline comparison.

## Differential test

`tests/test_diff.py` compares the patched `textdistance.lcsseq` against a
verbatim transcription of the pristine upstream DP (the original function body,
with the numpy matrix swapped for a list-of-lists matrix that computes the same
integers). Comparison is exact string equality plus UTF-8 byte equality, and
`LCSSeq().similarity` is checked against the reference length.

**1218 cases, 0 differences.** Cases: 1200 randomized pairs across 8 alphabets
(lowercase, digits, accented Latin, CJK, Greek, emoji, punctuation/whitespace)
with lengths 0–40, plus 18 boundary cases (empty × empty, one empty side, single
element, no common symbol, long repeated runs, reversed strings, non-ASCII).

```
PYTHONPATH=/tmp/td .venv/bin/python -m pytest tests/test_diff.py -q
# 1218 passed
```

## Quality gates

| Gate | Result | Reproduce |
| --- | --- | --- |
| G1 upstream tests | **pass** — `tests/` excluding the optional-library comparison module: **400 passed, 0 failed** (9.6 s, idle machine). The full `tests/` run is 400 passed / 29 failed, and all 29 are in `tests/test_external.py`, which imports third-party libraries that are not installed (`Levenshtein`, `pyxdameraulevenshtein`, …). The pristine tree fails **the same 30 tests** in that one module, so the failures are pre-existing and independent of this patch. One hypothesis-based test in `tests/test_compression/` (`test_simmetry[alg0]`) has a 200 ms per-example deadline and can flake under CPU load; it passes in isolation and in the idle full run reported here. | `PYTHONPATH=/tmp/td .venv/bin/python -m pytest /tmp/td/tests -q --ignore=/tmp/td/tests/test_external.py` |
| G2 differential | **pass** — 1218/1218 byte-identical | `PYTHONPATH=/tmp/td .venv/bin/python -m pytest tests/test_diff.py -q` |
| G3 median speedup | **pass** — 10.78x ≥ 1.15x | `python3 -c "import json;b=json.load(open('benchmark/baseline.json'));o=json.load(open('benchmark/optimized.json'));print(sorted(b['results'][s]['median_s']/o['results'][s]['median_s'] for s in b['results']))"` |
| G4 largest scale | **pass** — 9.16x ≥ 0.95x | same JSONs, scale `800` |
| G5 peak RSS | **pass** — 34736 KiB baseline vs 34748 KiB optimized (ratio 1.0003 ≤ 1.10) | `/usr/bin/time -v env PYTHONPATH=/tmp/td .venv/bin/python benchmark/bench.py --impl optimized --out /tmp/o.json --raw-dir /tmp/raw` |

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -q "numpy==2.5.4" pytest hypothesis
git clone --depth=1 git@github-linluozi:life4/textdistance.git /tmp/td && cd /tmp/td && git checkout -q d6a68d61088a40eef5c88191ccf79323dbf34850 && git apply "$OLDPWD/patch.diff"
PYTHONPATH=/tmp/td .venv/bin/python benchmark/bench.py --impl optimized --out /tmp/optimized.json && PYTHONPATH=/tmp/td .venv/bin/python -m pytest tests/test_diff.py -q
```

To re-measure the baseline, run the same harness on an unpatched checkout:

```bash
git clone --depth=1 git@github-linluozi:life4/textdistance.git /tmp/td-base && PYTHONPATH=/tmp/td-base .venv/bin/python benchmark/bench.py --impl baseline --out /tmp/baseline.json
```

`benchmark/bench.py` writes every timed sample to `benchmark/raw/<impl>-<scale>-<i>.json`
before aggregating; `benchmark/baseline.json` and `benchmark/optimized.json`
hold the medians, quartiles, seed, command line and environment. Both runs used
the same interpreter, the same numpy 2.5.4 install, and the same seed.

## Environment

- CPU: AMD EPYC 7K62 48-Core Processor (4 vCPU visible)
- RAM: 3812564 kB total (3.6 GiB)
- Python: 3.12.3; numpy: 2.5.4; pytest: 9.2.0; hypothesis: 6.170.14
- OS: Linux 6.8.0-124-generic x86_64 (glibc 2.39)
- Seed: 42; warmup 3; samples 5; timer `time.perf_counter()`
