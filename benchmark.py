"""
Benchmark: DC average processing — component-level timings.

Measures three improvements independently so each speedup is clearly visible:

  1. Pool overhead      — N × ProcessPoolExecutor(create+destroy) vs 1 reused pool
  2. DC file read       — read_wfm() + .mean() (full float64) vs read_wfm_dc_mean()
  3. Combined pipeline  — old approach (N pools, full waveform DC)
                          vs new approach (1 pool, int-domain DC mean)

Synthetic WFM v3 files are written to a temp directory; no real data needed.

Usage:
    uv run python benchmark.py
"""

from __future__ import annotations

import struct
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from tekwfm import read_wfm, read_wfm_dc_mean

# ---------------------------------------------------------------------------
# Synthetic WFM file generator
# ---------------------------------------------------------------------------

_HEADER_SIZE    = 838
_FF_RECORD_SIZE = 24   # 4 (wusp) + 8 (tfrac) + 8 (tdatefrac) + 4 (tdate)


def _write_wfm(
    path: Path,
    n_frames: int,
    n_samples: int,
    tscale: float = 160e-12,
) -> None:
    """Write a minimal valid WFM v3 file with random int16 data."""
    bps          = 2        # int16
    code         = 0        # int16 sample code
    allbytes     = n_samples * bps          # per-frame byte count
    curve_offset = _HEADER_SIZE + _FF_RECORD_SIZE * (n_frames - 1)

    hdr = bytearray(_HEADER_SIZE)
    struct.pack_into('<H',  hdr,   0, 0x0F0F)           # byte_order
    struct.pack_into('8s',  hdr,   2, b':WFM#003')      # version
    struct.pack_into('<b',  hdr,  15, bps)              # bytes per sample
    struct.pack_into('<i',  hdr,  16, curve_offset)     # curve block offset
    struct.pack_into('<I',  hdr,  72, n_frames - 1)     # num_frames - 1
    struct.pack_into('<I',  hdr,  78, 1)                # fastframe = True
    struct.pack_into('<I',  hdr, 114, 1)                # imp_dim_count
    struct.pack_into('<I',  hdr, 118, 1)                # exp_dim_count
    struct.pack_into('<I',  hdr, 122, 2)                # record_type = WFMDATA_VECTOR
    struct.pack_into('<h',  hdr, 154, 0)                # summary_frame
    struct.pack_into('<d',  hdr, 168, 1e-3)             # vscale  (1 mV/count)
    struct.pack_into('<d',  hdr, 176, 0.0)              # voffset
    struct.pack_into('<i',  hdr, 240, code)             # sample code
    struct.pack_into('<I',  hdr, 244, 0)                # exp_dim_1_type = EXPLICIT_SAMPLE
    struct.pack_into('<d',  hdr, 488, tscale)           # tscale
    struct.pack_into('<d',  hdr, 496, 0.0)              # tstart
    struct.pack_into('<I',  hdr, 768, 0)                # time_base_1 = BASE_TIME
    struct.pack_into('<d',  hdr, 788, 0.0)              # tfrac  (frame 0)
    struct.pack_into('<d',  hdr, 796, 0.0)              # tdatefrac (frame 0)
    struct.pack_into('<I',  hdr, 804, 0)                # tdate  (frame 0)
    struct.pack_into('<I',  hdr, 822, 0)                # dpre = 0
    struct.pack_into('<I',  hdr, 826, allbytes)         # dpost = allbytes (no post buffer)
    struct.pack_into('<I',  hdr, 830, allbytes)         # allbytes (per frame)

    ff_table = bytes(_FF_RECORD_SIZE * (n_frames - 1))  # all-zero timing records

    # Curve data: shape (n_samples, n_frames), F-order (column-major on disk)
    rng   = np.random.default_rng(42)
    curve = rng.integers(-1000, 1000, size=(n_samples, n_frames), dtype=np.int16)
    curve_bytes = np.asfortranarray(curve).tobytes()    # columns first → F-order

    path.write_bytes(bytes(hdr) + ff_table + curve_bytes)


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

def _timeit(fn, *, repeat: int = 3) -> float:
    """Return best wall-clock time (seconds) over *repeat* calls."""
    best = float('inf')
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def _fmt(seconds: float) -> str:
    if seconds >= 1.0:
        return f'{seconds:.3f} s'
    if seconds >= 1e-3:
        return f'{seconds * 1e3:.1f} ms'
    return f'{seconds * 1e6:.1f} µs'


# ---------------------------------------------------------------------------
# Benchmark 1 — Pool creation overhead
# ---------------------------------------------------------------------------

def _bench_pool_overhead(n_pools: int, n_workers: int = 4) -> tuple[float, float]:
    """
    Compare N × (create pool → small task → destroy) vs 1 pool × N tasks.

    Returns (old_time, new_time) in seconds.
    """
    dummy_paths: list[Path] = []   # pool work is measured by spin cost only

    # Old: create and destroy a pool for each 'batch'
    def old():
        for _ in range(n_pools):
            with ProcessPoolExecutor(max_workers=n_workers) as pool:
                list(pool.map(abs, range(4)))   # tiny task just to force startup

    # New: one pool, same total work
    def new():
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            for _ in range(n_pools):
                list(pool.map(abs, range(4)))

    return _timeit(old), _timeit(new)


# ---------------------------------------------------------------------------
# Benchmark 2 — DC file read: full waveform vs int-domain mean
# ---------------------------------------------------------------------------

def _bench_dc_read(dc_files: list[Path], n_workers: int) -> tuple[float, float]:
    """
    Sequential read of all DC files:
      old — read_wfm + .mean(axis=0)  (full float64 waveform allocated)
      new — read_wfm_dc_mean          (mean computed in int16 domain)
    """
    def old():
        for p in dc_files:
            wfm = read_wfm(p)
            wfm.volts.mean(axis=0)

    def new():
        for p in dc_files:
            read_wfm_dc_mean(p)

    return _timeit(old), _timeit(new)


def _bench_dc_read_parallel(dc_files: list[Path], n_workers: int) -> tuple[float, float]:
    """Same comparison but using a process pool (closer to real pipeline use)."""
    def old():
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            waveforms = list(pool.map(read_wfm, dc_files))
        for wfm in waveforms:
            wfm.volts.mean(axis=0)

    def new():
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            list(pool.map(read_wfm_dc_mean, dc_files))

    return _timeit(old), _timeit(new)


# ---------------------------------------------------------------------------
# Benchmark 3 — Combined pipeline simulation
# ---------------------------------------------------------------------------

def _old_pipeline(scans: list[list[Path]], n_workers: int) -> None:
    """Simulate old process_dataset DC path: new pool per scan, full waveform."""
    for scan_paths in scans:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            waveforms = list(pool.map(read_wfm, scan_paths))
        for wfm in waveforms:
            wfm.volts.mean(axis=0)


def _new_pipeline(scans: list[list[Path]], n_workers: int) -> None:
    """Simulate new process_dataset DC path: single pool, int-domain mean."""
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        for scan_paths in scans:
            futures = [pool.submit(read_wfm_dc_mean, p) for p in scan_paths]
            for f in futures:
                f.result()


def _bench_pipeline(scans: list[list[Path]], n_workers: int) -> tuple[float, float]:
    old = lambda: _old_pipeline(scans, n_workers)
    new = lambda: _new_pipeline(scans, n_workers)
    return _timeit(old), _timeit(new)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import os
    n_workers = min(os.cpu_count() or 4, 8)

    # Dataset shape
    N_SCANS   = 4
    N_ROWS    = 8
    N_FRAMES  = 200
    N_SAMPLES_DC = 1_000   # DC files are short — just a mean is needed

    print('=' * 62)
    print('  visu3 DC-average benchmark')
    print('=' * 62)
    print(f'  CPU workers : {n_workers}')
    print(f'  Dataset     : {N_SCANS} scans × {N_ROWS} rows')
    print(f'  DC file     : {N_SAMPLES_DC} samples × {N_FRAMES} frames (int16)')
    print()

    with tempfile.TemporaryDirectory(prefix='visu3_bench_') as tmp:
        tmp = Path(tmp)

        # Write synthetic DC WFM files
        all_dc_files: list[Path] = []
        scans: list[list[Path]] = []
        for s in range(N_SCANS):
            scan_files: list[Path] = []
            for r in range(N_ROWS):
                p = tmp / f'DC-{s:03d}-{r:03d}.wfm'
                _write_wfm(p, n_frames=N_FRAMES, n_samples=N_SAMPLES_DC)
                scan_files.append(p)
                all_dc_files.append(p)
            scans.append(scan_files)

        total_files = len(all_dc_files)
        dc_file_kb  = all_dc_files[0].stat().st_size / 1024

        print(f'  Files written : {total_files} × {dc_file_kb:.1f} KB')
        print()

        # ── Benchmark 1: pool overhead ────────────────────────────────────
        n_pools = N_SCANS   # old code creates one pool per scan
        t_old, t_new = _bench_pool_overhead(n_pools, n_workers)
        print(f'[1] Pool creation overhead  ({n_pools} pools × {n_workers} workers)')
        print(f'    Old (N × create/destroy) : {_fmt(t_old)}')
        print(f'    New (1 reused pool)       : {_fmt(t_new)}')
        print(f'    Speedup                   : {t_old / t_new:.1f}×')
        print()

        # ── Benchmark 2a: sequential DC read ─────────────────────────────
        t_old, t_new = _bench_dc_read(all_dc_files, n_workers)
        print(f'[2a] DC read — sequential ({total_files} files)')
        print(f'    Old (read_wfm + .mean)    : {_fmt(t_old)}')
        print(f'    New (read_wfm_dc_mean)    : {_fmt(t_new)}')
        print(f'    Speedup                   : {t_old / t_new:.1f}×')
        print()

        # ── Benchmark 2b: parallel DC read ───────────────────────────────
        t_old, t_new = _bench_dc_read_parallel(all_dc_files, n_workers)
        print(f'[2b] DC read — parallel  ({total_files} files, {n_workers} workers)')
        print(f'    Old (read_wfm + .mean)    : {_fmt(t_old)}')
        print(f'    New (read_wfm_dc_mean)    : {_fmt(t_new)}')
        print(f'    Speedup                   : {t_old / t_new:.1f}×')
        print()

        # ── Benchmark 3: combined pipeline ───────────────────────────────
        t_old, t_new = _bench_pipeline(scans, n_workers)
        print(f'[3] Combined pipeline  ({N_SCANS} scans × {N_ROWS} rows)')
        print(f'    Old (N pools, full waveform DC) : {_fmt(t_old)}')
        print(f'    New (1 pool, int-domain mean)   : {_fmt(t_new)}')
        print(f'    Speedup                          : {t_old / t_new:.1f}×')
        print()

        # ── Memory saved per DC file ──────────────────────────────────────
        bytes_old = N_SAMPLES_DC * N_FRAMES * 8   # float64
        bytes_new = N_SAMPLES_DC * N_FRAMES * 2   # int16 (mmap, never fully copied)
        print(f'[4] Peak DC memory per file')
        print(f'    Old (float64 array) : {bytes_old / 1024:.1f} KB')
        print(f'    New (int16 direct)  : {bytes_new / 1024:.1f} KB  (4× less)')
        print()

    print('Done.')


if __name__ == '__main__':
    main()
