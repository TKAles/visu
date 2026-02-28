"""
Data loading, collation, and processing for visu3.

File naming convention
----------------------
    TYPE-SCANNUMBER-ROWNUMBER.WFM
        TYPE        : RF | DC | DCA | DCB
        SCANNUMBER  : zero-padded integer, e.g. 001
        ROWNUMBER   : zero-padded integer, e.g. 001

Scan structure
--------------
A *scan* is all rows that share the same SCANNUMBER.
A complete dataset contains RF + either DC (single) or DCA+DCB (dual-channel).
Visualisation only requires one DC channel; DCA is preferred when both are present.

Pixel mapping
-------------
  Each WFM file = one row in the 2D map.
  Each FastFrame within a WFM file = one pixel (column) in that row.
  Output map shape: (n_scans, n_rows, n_frames).

FFT details
-----------
  The FFT size is chosen so that each bin spans exactly 1 MHz, snapped to the
  nearest FFTW-optimal length (products of small primes).
  Each pixel stores the peak single-sided power (V²) found across the RF
  spectrum, excluding the DC bin.  The frequency axis can be reconstructed
  as np.fft.rfftfreq(n_fft, d=tscale).
"""

from __future__ import annotations

import json
import os
import pickle
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

import numpy as np
import pyfftw
import pyfftw.interfaces.numpy_fft as _pfft
from scipy.fft import next_fast_len

from concurrent.futures import ProcessPoolExecutor

from tekwfm import Waveform, read_wfm, read_wfm_batch, read_wfm_dc_mean

# ---------------------------------------------------------------------------
# FFT backend configuration
# ---------------------------------------------------------------------------

_N_THREADS: int = os.cpu_count() or 1
_FREQ_RESOLUTION_HZ: float = 1e6        # target bin width: 1 MHz

# pyfftw: measure-quality plans, shared across calls via interface cache
pyfftw.config.NUM_THREADS       = _N_THREADS
pyfftw.config.PLANNER_EFFORT    = 'FFTW_MEASURE'
pyfftw.interfaces.cache.enable()
pyfftw.interfaces.cache.set_keepalive_time(60.0)

# Persist FFTW wisdom so planning cost is paid only on the first run
_WISDOM_PATH = Path.home() / '.cache' / 'visu3' / 'fftw_wisdom.pkl'


def _load_fftw_wisdom() -> None:
    if _WISDOM_PATH.exists():
        try:
            pyfftw.import_wisdom(pickle.loads(_WISDOM_PATH.read_bytes()))
        except Exception:
            pass  # corrupt file — FFTW will re-plan silently


def _save_fftw_wisdom() -> None:
    try:
        _WISDOM_PATH.parent.mkdir(parents=True, exist_ok=True)
        _WISDOM_PATH.write_bytes(pickle.dumps(pyfftw.export_wisdom()))
    except OSError:
        pass


_load_fftw_wisdom()

# Optional GPU backend (CuPy / CUDA).  Falls back to pyfftw when unavailable.
try:
    import cupy as _cp
    _cp.cuda.runtime.getDeviceCount()  # raises if no CUDA driver
    _GPU_AVAILABLE = True
except Exception:
    _cp = None                          # type: ignore[assignment]
    _GPU_AVAILABLE = False

_FFT_BACKEND: str = 'cupy' if _GPU_AVAILABLE else 'pyfftw'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATASET_VERSION   = 1
DATASET_FILENAME  = 'dataset.json'

# TYPE-SCANNUMBER-ROWNUMBER.WFM  (case-insensitive)
_FILE_RE = re.compile(r'^(RF|DCA|DCB|DC)-(\d+)-(\d+)\.wfm$', re.IGNORECASE)

DCMode = Literal['DC', 'DCA', 'DCB', 'dual']

# ---------------------------------------------------------------------------
# Raw collation structures
# ---------------------------------------------------------------------------


@dataclass
class RawScan:
    """WFM file paths for a single scan number, ordered by row."""

    scan_number: int
    rf:  list[Path] = field(default_factory=list)  # one file per row
    dc:  list[Path] = field(default_factory=list)  # DC or DCA rows
    dcb: list[Path] = field(default_factory=list)  # DCB rows (dual only)

    @property
    def n_rows(self) -> int:
        return len(self.rf)


@dataclass
class CollatedDataset:
    """Result of scanning an unprocessed directory."""

    source_dir: Path
    dc_mode: DCMode           # 'DC', 'DCA', 'DCB', or 'dual'
    scans: list[RawScan]      # sorted ascending by scan_number

    @property
    def n_scans(self) -> int:
        return len(self.scans)

    @property
    def n_rows(self) -> int:
        return self.scans[0].n_rows if self.scans else 0

    def summary(self) -> str:
        return (
            f'{self.n_scans} scan(s) × {self.n_rows} row(s), '
            f'DC mode: {self.dc_mode}'
        )


# ---------------------------------------------------------------------------
# Processed data structure
# ---------------------------------------------------------------------------


@dataclass
class ProcessedDataset:
    """
    Processed 2D pixel maps ready for visualisation.

    Pixel layout
    ------------
    Axis 0 — scan index  (SCANNUMBER, e.g. a DC bias step)
    Axis 1 — row index   (ROWNUMBER, y-position on sample)
    Axis 2 — frame index (FastFrame index, x-position on sample)

    Attributes
    ----------
    source_dir : Path
    dc_mode    : DCMode
    fft_map    : ndarray, shape (n_scans, n_rows, n_frames), float64
        Peak single-sided RF power (V²) per pixel.
        Frequency axis: np.fft.rfftfreq(n_fft, d=tscale)[1:]
    dc_map     : ndarray, shape (n_scans, n_rows, n_frames), float64
        Mean DC voltage (V) per pixel (primary channel).
    dcb_map    : ndarray or None, same shape
        Mean DC voltage of the secondary channel (dual mode only).
    n_fft      : int
        FFT length used; bin width = 1 / (n_fft * tscale) Hz ≈ 1 MHz.
    tscale     : float
        RF sample interval (s).
    """

    source_dir: Path
    dc_mode:    DCMode
    fft_map:    np.ndarray
    dc_map:     np.ndarray
    dcb_map:    np.ndarray | None
    n_fft:      int
    tscale:     float

    @property
    def freq_axis(self) -> np.ndarray:
        """Frequency axis in Hz, shape (n_fft // 2,) — DC bin excluded."""
        return np.fft.rfftfreq(self.n_fft, d=self.tscale)[1:]


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------


def is_oldworld_directory(path: Path) -> bool:
    """Return True if *path* contains any files matching the oldWorld TYPE-SCAN-ROW.wfm convention."""
    for p in path.rglob('*'):
        if p.suffix.lower() == '.wfm' and _FILE_RE.match(p.name):
            return True
    return False


def read_metadata(source_dir: Path) -> dict:
    """Read scan.json from *source_dir*, returning an empty dict if absent or invalid."""
    scan_json = source_dir / 'scan.json'
    if not scan_json.exists():
        return {}
    try:
        return json.loads(scan_json.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def scan_directory(path: Path) -> CollatedDataset:
    """
    Scan *path* recursively for WFM files and collate by type, scan, and row.

    Raises
    ------
    ValueError
        If no recognisable WFM files are found, RF files are absent, or no DC
        channel files are present.
    """
    # {TYPE_UPPER: {scan_num: {row_num: Path}}}
    found: dict[str, dict[int, dict[int, Path]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    for wfm_path in path.rglob('*'):
        if wfm_path.suffix.lower() != '.wfm':
            continue
        m = _FILE_RE.match(wfm_path.name)
        if not m:
            continue
        file_type = m.group(1).upper()
        scan_num  = int(m.group(2))
        row_num   = int(m.group(3))
        found[file_type][scan_num][row_num] = wfm_path

    if not found:
        raise ValueError(f'No TYPE-SCAN-ROW.wfm files found in {path}')
    if 'RF' not in found:
        raise ValueError(f'No RF files found in {path}')

    # Determine DC mode; DCA+DCB → dual, DCA alone → DCA, etc.
    has_dc  = 'DC'  in found
    has_dca = 'DCA' in found
    has_dcb = 'DCB' in found

    if has_dca and has_dcb:
        dc_mode: DCMode          = 'dual'
        dc_primary: str          = 'DCA'
        dc_secondary: str | None = 'DCB'
    elif has_dca:
        dc_mode, dc_primary, dc_secondary = 'DCA', 'DCA', None
    elif has_dcb:
        dc_mode, dc_primary, dc_secondary = 'DCB', 'DCB', None
    elif has_dc:
        dc_mode, dc_primary, dc_secondary = 'DC', 'DC', None
    else:
        raise ValueError(f'No DC, DCA, or DCB files found in {path}')

    rf_by_scan = found['RF']
    scans: list[RawScan] = []

    for scan_num in sorted(rf_by_scan):
        rf_rows  = rf_by_scan[scan_num]
        dc_rows  = found[dc_primary].get(scan_num, {})
        dcb_rows = found[dc_secondary].get(scan_num, {}) if dc_secondary else {}

        scans.append(RawScan(
            scan_number=scan_num,
            rf =[rf_rows [r] for r in sorted(rf_rows)],
            dc =[dc_rows [r] for r in sorted(dc_rows)],
            dcb=[dcb_rows[r] for r in sorted(dcb_rows)],
        ))

    return CollatedDataset(source_dir=path, dc_mode=dc_mode, scans=scans)


# ---------------------------------------------------------------------------
# FFT helpers
# ---------------------------------------------------------------------------


def _fft_n_for_1mhz_bins(tscale: float) -> int:
    """
    Return the smallest real-FFT-optimal length whose bin width is ≤ 1 MHz.

    Uses ``scipy.fft.next_fast_len(..., real=True)`` to find a length whose
    prime factors are all small (2, 3, 5, 7, 11, 13), which is what FFTW
    requires for efficient real-to-complex transforms.

    Expected values for the two supported oscilloscope rates:

    ==================  ========  ===========  ===========
    Sample rate         tscale    n_fft        f_max
    ==================  ========  ===========  ===========
    6.25 GS/s           160 ps    6 250        3.125 GHz
    25 GS/s (high-res)   40 ps   25 000       12.500 GHz
    ==================  ========  ===========  ===========

    ``round()`` is used instead of ``int()`` to guard against floating-point
    drift in the reciprocal (e.g. 1/40e-12 ≈ 25 000 000 000.000004).
    """
    f_sample = 1.0 / tscale
    n_ideal  = round(f_sample / _FREQ_RESOLUTION_HZ)
    return next_fast_len(n_ideal, real=True)


def _rfft(data: np.ndarray, n_fft: int) -> np.ndarray:
    """
    Compute rfft(data, n=n_fft, axis=0) using the best available backend.

    Parameters
    ----------
    data : ndarray, shape (n_samples, n_frames), float64
        Time-domain voltage, one frame per column.
    n_fft : int
        FFT length (zero-pads or truncates along axis 0).

    Returns
    -------
    ndarray, shape (n_fft // 2 + 1, n_frames), complex128
    """
    if _GPU_AVAILABLE:
        d = _cp.asarray(data)
        out = _cp.fft.rfft(d, n=n_fft, axis=0)
        return _cp.asnumpy(out)
    return _pfft.rfft(data, n=n_fft, axis=0, threads=_N_THREADS)


def _peak_power_per_frame(wfm: Waveform, n_fft: int) -> np.ndarray:
    """
    For each FastFrame, return the peak single-sided power across the RF
    spectrum (DC bin excluded).

    Processing
    ----------
    1. rfft(voltages, n=n_fft) along the sample axis — all frames at once.
    2. One-sided power: P_k = 2|X_k|² / n_fft²  for k ≥ 1.
    3. Peak over frequency bins for each frame → one scalar per frame.

    Parameters
    ----------
    wfm   : Waveform — shape (n_samples, n_frames)
    n_fft : int

    Returns
    -------
    ndarray, shape (n_frames,), float64
        Peak single-sided power (V²) per frame.
    """
    spectra = _rfft(wfm.volts, n_fft)              # (n_fft//2+1, n_frames)

    # One-sided amplitude²/2 normalised to V²; skip bin 0 (DC)
    power   = (2.0 / n_fft ** 2) * np.abs(spectra[1:]) ** 2  # (n_fft//2, n_frames)

    return power.max(axis=0)                        # (n_frames,)


def _mean_dc_per_frame(wfm: Waveform) -> np.ndarray:
    """
    Mean DC voltage (V) within each FastFrame.

    Parameters
    ----------
    wfm : Waveform — shape (n_samples, n_frames)

    Returns
    -------
    ndarray, shape (n_frames,), float64
    """
    return wfm.volts.mean(axis=0)                   # (n_frames,)


# ---------------------------------------------------------------------------
# Main processing pipeline
# ---------------------------------------------------------------------------


def process_dataset(
    collated: CollatedDataset,
    *,
    workers: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ProcessedDataset:
    """
    Load and process all WFM files described by *collated*.

    Each WFM file = one row; each FastFrame = one pixel (column).

    Processing per row
    ------------------
    RF  : rfft → peak single-sided power (V²) per frame  → fft_map pixel
    DC  : mean voltage per frame                          → dc_map pixel
    DCB : mean voltage per frame (dual mode only)         → dcb_map pixel

    Parameters
    ----------
    collated : CollatedDataset
    workers  : int, optional
        Worker processes for parallel WFM I/O. None → os.cpu_count().
    progress_callback : callable(completed_rows, total_rows), optional

    Returns
    -------
    ProcessedDataset
    """
    n_scans = collated.n_scans
    dual    = collated.dc_mode == 'dual'

    # Probe the first RF and DC files for tscale, n_fft, and frame counts.
    # RF and DC files can have different numbers of FastFrames, so probe both
    # and use the minimum so all maps share a single consistent shape.
    rf_probe = read_wfm(collated.scans[0].rf[0])
    dc_probe = read_wfm(collated.scans[0].dc[0])
    tscale   = rf_probe.tscale
    n_fft    = _fft_n_for_1mhz_bins(tscale)
    n_frames = min(rf_probe.volts.shape[1], dc_probe.volts.shape[1])

    # Scans can have different row counts; allocate for the largest scan.
    # NaN-fill so rows that belong to shorter scans are clearly invalid.
    max_rows = max(scan.n_rows for scan in collated.scans)

    # Allocate output maps: (n_scans, max_rows, n_frames)
    fft_map = np.full((n_scans, max_rows, n_frames), np.nan, dtype=np.float64)
    dc_map  = np.full((n_scans, max_rows, n_frames), np.nan, dtype=np.float64)
    dcb_map = np.full((n_scans, max_rows, n_frames), np.nan, dtype=np.float64) if dual else None

    total = sum(scan.n_rows for scan in collated.scans)
    done  = 0

    # Single pool shared across all scans and channels — eliminates per-scan
    # spawn/teardown overhead.  DC files use read_wfm_dc_mean, which computes
    # the per-frame mean in the integer domain and returns only (n_frames,)
    # rather than a full float64 waveform.
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for scan_idx, scan in enumerate(collated.scans):
            rf_futures  = [pool.submit(read_wfm,         p) for p in scan.rf]
            dc_futures  = [pool.submit(read_wfm_dc_mean, p) for p in scan.dc]
            dcb_futures = [pool.submit(read_wfm_dc_mean, p) for p in scan.dcb] if dual else []

            for row_idx, rf_future in enumerate(rf_futures):
                rf_wfm  = rf_future.result()
                dc_vals = dc_futures[row_idx].result()

                rf_vals = _peak_power_per_frame(rf_wfm, n_fft)

                n_rf = min(len(rf_vals), n_frames)
                n_dc = min(len(dc_vals), n_frames)
                fft_map[scan_idx, row_idx, :n_rf] = rf_vals[:n_rf]
                dc_map [scan_idx, row_idx, :n_dc] = dc_vals[:n_dc]

                if dual and dcb_futures:
                    dcb_vals = dcb_futures[row_idx].result()
                    n_dcb = min(len(dcb_vals), n_frames)
                    dcb_map[scan_idx, row_idx, :n_dcb] = dcb_vals[:n_dcb]  # type: ignore[index]

                done += 1
                if progress_callback:
                    progress_callback(done, total)

    # Persist FFTW plans so the next run skips the measurement step
    _save_fftw_wisdom()

    return ProcessedDataset(
        source_dir=collated.source_dir,
        dc_mode=collated.dc_mode,
        fft_map=fft_map,
        dc_map=dc_map,
        dcb_map=dcb_map,
        n_fft=n_fft,
        tscale=tscale,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_dataset(processed: ProcessedDataset, output_dir: Path) -> Path:
    """
    Save a processed dataset to *output_dir*.

    Written files
    -------------
    dataset.json   Metadata and file references.
    fft_map.npy    Peak RF power map,  shape (n_scans, n_rows, n_frames), V².
    dc_map.npy     Primary DC map,     shape (n_scans, n_rows, n_frames), V.
    dcb_map.npy    Secondary DC map    (dual mode only).

    Returns the path to ``dataset.json``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}

    np.save(output_dir / 'fft_map.npy', processed.fft_map); files['fft_map'] = 'fft_map.npy'
    np.save(output_dir / 'dc_map.npy',  processed.dc_map);  files['dc_map']  = 'dc_map.npy'

    if processed.dcb_map is not None:
        np.save(output_dir / 'dcb_map.npy', processed.dcb_map)
        files['dcb_map'] = 'dcb_map.npy'

    meta = {
        'version':    DATASET_VERSION,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_dir': str(processed.source_dir),
        'dc_mode':    processed.dc_mode,
        'tscale':     processed.tscale,
        'shape': {
            'n_scans':  int(processed.fft_map.shape[0]),
            'n_rows':   int(processed.fft_map.shape[1]),
            'n_frames': int(processed.fft_map.shape[2]),
        },
        'fft_params': {
            'n_fft':              processed.n_fft,
            'freq_resolution_hz': _FREQ_RESOLUTION_HZ,
            'backend':            _FFT_BACKEND,
        },
        'files': files,
    }

    dataset_path = output_dir / DATASET_FILENAME
    dataset_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')
    return dataset_path


def load_dataset(dataset_path: Path) -> ProcessedDataset:
    """
    Load a processed dataset from a ``dataset.json`` file.

    Raises
    ------
    ValueError
        If the file is not a valid VISU3 dataset or data files are missing.
    """
    try:
        meta = json.loads(dataset_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'Cannot read dataset file: {exc}') from exc

    if not isinstance(meta, dict) or meta.get('version') != DATASET_VERSION:
        raise ValueError(
            f'Not a valid VISU3 dataset (expected version {DATASET_VERSION})'
        )

    base  = dataset_path.parent
    files = meta['files']

    try:
        fft_map = np.load(base / files['fft_map'])
        dc_map  = np.load(base / files['dc_map'])
        dcb_map = np.load(base / files['dcb_map']) if 'dcb_map' in files else None
    except OSError as exc:
        raise ValueError(f'Missing data file: {exc}') from exc

    return ProcessedDataset(
        source_dir=Path(meta['source_dir']),
        dc_mode=meta['dc_mode'],
        fft_map=fft_map,
        dc_map=dc_map,
        dcb_map=dcb_map,
        n_fft=meta['fft_params']['n_fft'],
        tscale=meta['tscale'],
    )
