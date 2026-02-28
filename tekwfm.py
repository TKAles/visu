"""
Tektronix WFM file reader.

Reads voltage-vs-time records (including FastFrame) from little-endian
version 3 WFM files.

Reference: Tektronix part # 077-0220-10
"Performance Oscilloscope Reference Waveform File Format"
https://www.tek.com/oscilloscope/dpo7000-digital-phosphor-oscilloscope-manual-4

License: https://www.tek.com/sample-license
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import numpy as np


# ---------------------------------------------------------------------------
# Header field byte offsets within the 838-byte header block
# ---------------------------------------------------------------------------
_OFF_BYTE_ORDER     =   0   # uint16  – 0x0f0f = little-endian
_OFF_VERSION        =   2   # 8s      – b':WFM#003'
_OFF_BPS            =  15   # int8    – bytes per sample
_OFF_CURVE_OFFSET   =  16   # int32   – file offset to curve block
_OFF_NUM_FRAMES_M1  =  72   # uint32  – (number of FastFrames) - 1
_OFF_FASTFRAME      =  78   # uint32  – 1 = FastFrame enabled
_OFF_IMP_DIM_COUNT  = 114   # uint32
_OFF_EXP_DIM_COUNT  = 118   # uint32
_OFF_RECORD_TYPE    = 122   # uint32  – must be 2 (WFMDATA_VECTOR)
_OFF_SUMMARY_FRAME  = 154   # int16
_OFF_VSCALE         = 168   # float64 – volts per count
_OFF_VOFFSET        = 176   # float64 – volts offset
_OFF_CODE           = 240   # int32   – sample data type code
_OFF_EXP_DIM_1_TYPE = 244   # uint32  – must be 0 (EXPLICIT_SAMPLE)
_OFF_TSCALE         = 488   # float64 – seconds per sample
_OFF_TSTART         = 496   # float64 – trigger time offset (s)
_OFF_TIME_BASE_1    = 768   # uint32  – must be 0 (BASE_TIME)
_OFF_TFRAC          = 788   # float64 – trigger fraction (frame 0)
_OFF_TDATEFRAC      = 796   # float64 – date fraction    (frame 0)
_OFF_TDATE          = 804   # uint32  – date stamp       (frame 0)
_OFF_DPRE           = 822   # uint32  – pre-trigger bytes
_OFF_DPOST          = 826   # uint32  – post-trigger bytes (exclusive end)
_OFF_ALLBYTES       = 830   # uint32  – total bytes in curve record

_HEADER_SIZE = 838

# FastFrame timing table: one record per frame after the first.
_FASTFRAME_DTYPE = np.dtype([
    ('wusp',      'i4'),
    ('tfrac',     'f8'),
    ('tdatefrac', 'f8'),
    ('tdate',     'i4'),
])

# (code, bps) → numpy dtype name
_SAMPLE_DTYPES: dict[tuple[int, int], str] = {
    (7, 1): 'int8',
    (0, 2): 'int16',
    (4, 4): 'float32',
}

_REQUIRED_BYTE_ORDER = 0x0F0F
_REQUIRED_VERSION    = b':WFM#003'


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class WfmReadError(Exception):
    """Raised when a WFM file cannot be parsed."""


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class WaveformHeader:
    """
    Decoded metadata from a WFM file header.

    Most fields are raw values from the spec.  Fields marked *derived* are
    computed from the raw values for convenience.
    """
    byte_order:      int
    version:         bytes
    bps:             int
    curve_offset:    int
    num_frames:      int
    fastframe:       bool
    imp_dim_count:   int
    exp_dim_count:   int
    record_type:     int
    code:            int
    exp_dim_1_type:  int
    sample_dtype:    str        # e.g. 'int16', 'float32'
    vscale:          float
    voffset:         float
    tscale:          float
    tstart:          float
    summary_frame:   int
    time_base_1:     int
    tfrac:           float      # trigger fraction, frame 0
    tdatefrac:       float      # date fraction,    frame 0
    tdate:           int        # date stamp,       frame 0
    dpre:            int
    dpost:           int
    allbytes:        int
    # derived
    available_values: int       # total samples per frame (including buffers)
    pre_values:       int       # leading buffer samples
    post_values:      int       # trailing buffer samples
    n_samples:        int       # usable samples per frame


@dataclass(slots=True, frozen=True)
class Waveform:
    """
    All data returned from a single WFM file.

    Attributes
    ----------
    volts : ndarray, shape (n_samples, n_frames), float64
        Scaled voltage data.
    tstart : float
        Time of first sample relative to trigger (seconds).
    tscale : float
        Sample interval (seconds per sample).
    tfrac : ndarray, shape (n_frames,), float64
        Sub-sample trigger fraction for each frame.
    tdatefrac : ndarray, shape (n_frames,), float64
        Fractional seconds of the trigger date/time for each frame.
    tdate : ndarray, shape (n_frames,), int32
        Integer date stamp for each frame.
    header : WaveformHeader
        Full decoded header metadata.
    """
    volts:      np.ndarray
    tstart:     float
    tscale:     float
    tfrac:      np.ndarray
    tdatefrac:  np.ndarray
    tdate:      np.ndarray
    header:     WaveformHeader


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _u(fmt: str, data: bytes, offset: int):
    """Unpack a single value from *data* at *offset* using *fmt*."""
    return struct.unpack_from(fmt, data, offset)[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def decode_header(header_bytes: bytes) -> WaveformHeader:
    """
    Parse the 838-byte WFM header block.

    Parameters
    ----------
    header_bytes : bytes
        Exactly 838 bytes read from the start of a WFM file.

    Returns
    -------
    WaveformHeader

    Raises
    ------
    WfmReadError
        If the header is the wrong size, the file format is unsupported,
        or required invariants are violated.
    """
    if len(header_bytes) != _HEADER_SIZE:
        raise WfmReadError(
            f'Header must be {_HEADER_SIZE} bytes; got {len(header_bytes)}'
        )

    byte_order      = _u('H',  header_bytes, _OFF_BYTE_ORDER)
    version         = _u('8s', header_bytes, _OFF_VERSION)
    bps             = _u('b',  header_bytes, _OFF_BPS)
    curve_offset    = _u('i',  header_bytes, _OFF_CURVE_OFFSET)
    num_frames      = _u('I',  header_bytes, _OFF_NUM_FRAMES_M1) + 1
    fastframe       = bool(_u('I', header_bytes, _OFF_FASTFRAME))
    imp_dim_count   = _u('I',  header_bytes, _OFF_IMP_DIM_COUNT)
    exp_dim_count   = _u('I',  header_bytes, _OFF_EXP_DIM_COUNT)
    record_type     = _u('I',  header_bytes, _OFF_RECORD_TYPE)
    code            = _u('i',  header_bytes, _OFF_CODE)
    exp_dim_1_type  = _u('I',  header_bytes, _OFF_EXP_DIM_1_TYPE)
    vscale          = _u('d',  header_bytes, _OFF_VSCALE)
    voffset         = _u('d',  header_bytes, _OFF_VOFFSET)
    tscale          = _u('d',  header_bytes, _OFF_TSCALE)
    tstart          = _u('d',  header_bytes, _OFF_TSTART)
    summary_frame   = _u('h',  header_bytes, _OFF_SUMMARY_FRAME)
    time_base_1     = _u('I',  header_bytes, _OFF_TIME_BASE_1)
    tfrac           = _u('d',  header_bytes, _OFF_TFRAC)
    tdatefrac       = _u('d',  header_bytes, _OFF_TDATEFRAC)
    tdate           = _u('I',  header_bytes, _OFF_TDATE)
    dpre            = _u('I',  header_bytes, _OFF_DPRE)
    dpost           = _u('I',  header_bytes, _OFF_DPOST)
    allbytes        = _u('I',  header_bytes, _OFF_ALLBYTES)

    # Format validation
    if byte_order != _REQUIRED_BYTE_ORDER:
        raise WfmReadError(
            f'Only little-endian (0x{_REQUIRED_BYTE_ORDER:04X}) is supported; '
            f'got 0x{byte_order:04X}'
        )
    if version != _REQUIRED_VERSION:
        raise WfmReadError(
            f'Only WFM version 3 ({_REQUIRED_VERSION!r}) is supported; got {version!r}'
        )
    if imp_dim_count != 1:
        raise WfmReadError(f'Expected imp_dim_count=1; got {imp_dim_count}')
    if exp_dim_count != 1:
        raise WfmReadError(f'Expected exp_dim_count=1; got {exp_dim_count}')
    if record_type != 2:
        raise WfmReadError(
            f'Expected record_type=2 (WFMDATA_VECTOR); got {record_type}'
        )
    if exp_dim_1_type != 0:
        raise WfmReadError(
            f'Expected exp_dim_1_type=0 (EXPLICIT_SAMPLE); got {exp_dim_1_type}'
        )
    if time_base_1 != 0:
        raise WfmReadError(f'Expected time_base_1=0 (BASE_TIME); got {time_base_1}')

    sample_dtype = _SAMPLE_DTYPES.get((code, bps))
    if sample_dtype is None:
        raise WfmReadError(
            f'Unknown sample format: code={code}, bps={bps}. '
            f'Supported (code, bps) combinations: {list(_SAMPLE_DTYPES)}'
        )

    available_values = allbytes // bps
    pre_values       = dpre // bps
    post_values      = (allbytes - dpost) // bps
    n_samples        = available_values - pre_values - post_values

    return WaveformHeader(
        byte_order=byte_order,
        version=version,
        bps=bps,
        curve_offset=curve_offset,
        num_frames=num_frames,
        fastframe=fastframe,
        imp_dim_count=imp_dim_count,
        exp_dim_count=exp_dim_count,
        record_type=record_type,
        code=code,
        exp_dim_1_type=exp_dim_1_type,
        sample_dtype=sample_dtype,
        vscale=vscale,
        voffset=voffset,
        tscale=tscale,
        tstart=tstart,
        summary_frame=summary_frame,
        time_base_1=time_base_1,
        tfrac=tfrac,
        tdatefrac=tdatefrac,
        tdate=tdate,
        dpre=dpre,
        dpost=dpost,
        allbytes=allbytes,
        available_values=available_values,
        pre_values=pre_values,
        post_values=post_values,
        n_samples=n_samples,
    )


def read_wfm(path: Union[str, Path]) -> Waveform:
    """
    Read a Tektronix WFM file and return fully scaled waveform data.

    Multiprocessing-safe: the file is opened and fully read within a single
    ``with`` block.  The memory-mapped curve data is copied into an ordinary
    ``ndarray`` before the file is closed, so the returned ``Waveform`` is
    entirely picklable and can be sent across process boundaries without any
    open file handles.

    Parameters
    ----------
    path : str or Path
        Path to the ``.wfm`` file.

    Returns
    -------
    Waveform
        Scaled voltage array plus per-frame timing metadata.

    Raises
    ------
    WfmReadError
        If the file format is unsupported or the header is malformed.
    FileNotFoundError
        If *path* does not exist.
    """
    path = Path(path)

    with path.open('rb') as f:
        hdr = decode_header(f.read(_HEADER_SIZE))

        # --- Per-frame trigger timing arrays ---
        tfrac     = np.empty(hdr.num_frames, dtype=np.float64)
        tdatefrac = np.empty(hdr.num_frames, dtype=np.float64)
        tdate     = np.empty(hdr.num_frames, dtype=np.int32)

        tfrac[0]     = hdr.tfrac
        tdatefrac[0] = hdr.tdatefrac
        tdate[0]     = hdr.tdate

        if hdr.fastframe and hdr.num_frames > 1:
            ff = np.fromfile(f, dtype=_FASTFRAME_DTYPE, count=hdr.num_frames - 1)
            tfrac[1:]     = ff['tfrac']
            tdatefrac[1:] = ff['tdatefrac']
            tdate[1:]     = ff['tdate']

        # --- Curve block ---
        # np.memmap gives zero-copy access to the raw samples.  We immediately
        # slice off the pre/post buffer regions and copy into a plain ndarray
        # so the file handle can be released and the data can cross process
        # boundaries via pickle.
        raw = np.memmap(
            f,
            dtype=hdr.sample_dtype,
            mode='r',
            offset=hdr.curve_offset,
            shape=(hdr.available_values, hdr.num_frames),
            order='F',                          # frames are stored column-major
        )
        clipped = np.array(
            raw[hdr.pre_values : hdr.available_values - hdr.post_values, :],
            dtype=np.float64,
            copy=True,                          # detach from the mmap
        )
        # raw is released here; file closes at end of `with` block

    # Scale to volts — pure arithmetic, no I/O
    volts = clipped * hdr.vscale + hdr.voffset

    return Waveform(
        volts=volts,
        tstart=hdr.tstart,
        tscale=hdr.tscale,
        tfrac=tfrac,
        tdatefrac=tdatefrac,
        tdate=tdate,
        header=hdr,
    )


def read_wfm_dc_mean(path: Union[str, Path]) -> np.ndarray:
    """
    Return the mean voltage per FastFrame without allocating a full float64 waveform.

    Three optimisations over the mmap approach:

    1. **Single read syscall** — ``f.read()`` avoids mmap page-fault overhead,
       which dominates for the small DC files typical in this pipeline.
    2. **Zero-copy reshape** — the curve block is stored F-order (frame 0 samples
       contiguous, then frame 1, …).  Reinterpreting the raw bytes as
       ``(n_frames, available_values)`` C-order is a free reshape; no copy is made.
    3. **Integer accumulation** — for int8/int16 files a 64-bit integer ``sum``
       followed by a single float64 divide is faster than float64 element-wise
       accumulation inside ``mean()``.

    Peak memory: ``(n_samples × n_frames × bps) + (n_frames × 8 bytes)`` —
    a 4× reduction versus the full :func:`read_wfm` path for int16 files.

    Parameters
    ----------
    path : str or Path
        Path to the ``.wfm`` file.

    Returns
    -------
    ndarray, shape (n_frames,), float64
        Mean voltage per frame.
    """
    path = Path(path)
    with path.open('rb') as f:
        hdr = decode_header(f.read(_HEADER_SIZE))
        f.seek(hdr.curve_offset)
        raw_bytes = f.read(hdr.available_values * hdr.num_frames * hdr.bps)

    # Curve data is stored F-order: frame 0's samples first, then frame 1's, …
    # Reinterpreting as (n_frames, available_values) C-order is a zero-copy view
    # of the same bytes; each row is one frame's contiguous samples.
    raw = np.frombuffer(raw_bytes, dtype=hdr.sample_dtype).reshape(
        (hdr.num_frames, hdr.available_values)
    )
    clipped = raw[:, hdr.pre_values : hdr.available_values - hdr.post_values]

    if hdr.sample_dtype == 'float32':
        # float32 → float64 accumulation via mean() is already optimal
        mean_counts = clipped.mean(axis=1)
    else:
        # Integer types: accumulate in int64 (avoids per-element float64 casts),
        # then convert to float64 with a single multiply.
        mean_counts = clipped.sum(axis=1, dtype=np.int64) * (1.0 / hdr.n_samples)

    return mean_counts * hdr.vscale + hdr.voffset


def read_wfm_batch(
    paths: list[Union[str, Path]],
    *,
    workers: int | None = None,
    executor=None,
) -> list[Waveform]:
    """
    Read multiple WFM files in parallel using a process pool.

    Parameters
    ----------
    paths : list of str or Path
        WFM files to read.
    workers : int, optional
        Number of worker processes.  Defaults to ``os.cpu_count()``.
        Ignored when *executor* is supplied.
    executor : concurrent.futures.Executor, optional
        An already-running executor to reuse.  When provided, no new pool is
        created, eliminating per-batch spawn overhead.

    Returns
    -------
    list of Waveform
        Results in the same order as *paths*.
    """
    from concurrent.futures import ProcessPoolExecutor
    if executor is not None:
        return list(executor.map(read_wfm, paths))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(read_wfm, paths))
