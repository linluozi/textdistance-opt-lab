#!/usr/bin/env python3
"""Benchmark harness for textdistance LCSSeq (dynamic-programming kernel).

Measures ``textdistance.lcsseq(a, b)`` on three fixed random-string sizes.
Warmup runs are discarded; every timed sample is written verbatim to
``benchmark/raw/<impl>-<scale>-<i>.json`` so the aggregate can be re-derived.

Usage:
    python benchmark/bench.py --impl baseline  --out benchmark/baseline.json
    python benchmark/bench.py --impl optimized --out benchmark/optimized.json
"""
from __future__ import annotations

import argparse
import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path

SCALES = (200, 400, 800)
SEED = 42
WARMUP = 3
SAMPLES = 5
ALPHABET = 'abcdefghijklmnopqrstuvwxyz'


def make_inputs() -> dict[int, tuple[str, str]]:
    rng = random.Random(SEED)
    out = {}
    for n in SCALES:
        a = ''.join(rng.choice(ALPHABET) for _ in range(n))
        b = ''.join(rng.choice(ALPHABET) for _ in range(n))
        out[n] = (a, b)
    return out


def pct(values: list[float], q: float) -> float:
    """Linear-interpolated percentile (same convention as numpy default)."""
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def env_info() -> dict:
    cpu = ''
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                cpu = line.split(':', 1)[1].strip()
                break
    except OSError:
        pass
    mem_kb = 0
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal'):
                mem_kb = int(line.split()[1])
                break
    except OSError:
        pass
    try:
        import numpy
        np_ver = numpy.__version__
    except Exception:  # pragma: no cover - optional dependency
        np_ver = None
    return {
        'cpu': cpu,
        'mem_total_kb': mem_kb,
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'numpy': np_ver,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--impl', required=True, choices=('baseline', 'optimized'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--raw-dir', default='benchmark/raw')
    args = ap.parse_args()

    import textdistance

    inputs = make_inputs()
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for n in SCALES:
        a, b = inputs[n]
        for _ in range(WARMUP):
            textdistance.lcsseq(a, b)
        samples = []
        for i in range(SAMPLES):
            t0 = time.perf_counter()
            value = textdistance.lcsseq(a, b)
            dt = time.perf_counter() - t0
            samples.append(dt)
            record = {
                'impl': args.impl,
                'scale': n,
                'sample': i,
                'seconds': dt,
                'result_len': len(value),
                'seed': SEED,
            }
            (raw_dir / f'{args.impl}-{n}-{i}.json').write_text(
                json.dumps(record, sort_keys=True) + '\n'
            )
        results[str(n)] = {
            'scale': n,
            'input_bytes': len(a) + len(b),
            'samples_s': samples,
            'median_s': statistics.median(samples),
            'p25_s': pct(samples, 0.25),
            'p75_s': pct(samples, 0.75),
            'min_s': min(samples),
            'max_s': max(samples),
            'stdev_s': statistics.stdev(samples) if len(samples) > 1 else 0.0,
            'result_len': len(textdistance.lcsseq(a, b)),
        }

    doc = {
        'impl': args.impl,
        'command': ' '.join([sys.executable, *sys.argv]),
        'seed': SEED,
        'warmup': WARMUP,
        'samples': SAMPLES,
        'scales': list(SCALES),
        'env': env_info(),
        'results': results,
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
    for n in SCALES:
        r = results[str(n)]
        print(f'{n:5d}  median={r["median_s"] * 1000:9.3f} ms  '
              f'p25={r["p25_s"] * 1000:9.3f}  p75={r["p75_s"] * 1000:9.3f}  '
              f'len={r["result_len"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
