# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**visu3** is a Python desktop GUI application for scientific data visualization of Tektronix oscilloscope scan data. It reads raw WFM files, computes FFT and DC maps, and renders them as 2D imshow plots in a tabbed Qt window.

## Tech Stack

- **Python 3.14+** with **PySide6** (Qt6) for the GUI
- **uv** as the package manager (not pip/poetry)
- **NumPy / SciPy / PyFFTW** for numerical processing; optional **CuPy** for GPU FFT
- **Matplotlib** embedded via `FigureCanvasQTAgg` (`matplotlib.use('QtAgg')`)
- UI layout loaded at runtime from `main.ui` via `QUiLoader` (not compiled with `pyside6-uic`)

## Commands

```bash
# Run the application
uv run python main.py

# Add a dependency
uv add <package>

# Sync dependencies from pyproject.toml
uv sync
```

No test runner, linter, or build system is configured yet.

## Architecture

### Module overview

- **`tekwfm.py`** — Low-level Tektronix WFM v3 file parser. Exposes `read_wfm(path) → Waveform` (full float64 array), `read_wfm_dc_mean(path) → ndarray` (mean per frame, memory-efficient), and `read_wfm_batch(paths)` (parallel). The `Waveform` dataclass holds `volts: ndarray(n_samples, n_frames)` plus timing metadata.

- **`loader.py`** — Data collation and processing pipeline. Key functions:
  - `scan_directory(path) → CollatedDataset` — finds all `TYPE-SCANNUMBER-ROWNUMBER.WFM` files and groups them by scan/row.
  - `process_dataset(collated) → ProcessedDataset` — runs FFT and DC extraction in parallel via `ProcessPoolExecutor`, returns 3D arrays `(n_scans, n_rows, n_frames)`.
  - `save_dataset / load_dataset` — persists to `processed/dataset.json` + `.npy` files.

- **`main.py`** — Qt application. `MainWindow` is a plain controller class (not a `QWidget` subclass) that holds a reference to the UI widget loaded from `main.ui`. Visualization uses `FigureCanvasQTAgg` tabs in `tabWidget`. Heavy processing runs on `_ProcessingWorker(QThread)`.

### Data structures

```
WFM files on disk (TYPE-SCAN-ROW.WFM)
    → scan_directory()  →  CollatedDataset (RawScan list, file paths only)
    → process_dataset() →  ProcessedDataset
                              .fft_map  (n_scans, n_rows, n_frames)  # peak RF power V²
                              .dc_map   (n_scans, n_rows, n_frames)  # mean DC voltage V
                              .dcb_map  (same | None)                # dual-channel only
```

### WFM file naming convention

`TYPE-SCANNUMBER-ROWNUMBER.WFM` where TYPE is `RF`, `DC`, `DCA`, or `DCB`. DC mode is determined automatically: `DCA+DCB` → `dual`, otherwise single-channel. Each WFM file is one scan row; each FastFrame within it is one pixel (column).

### FFT details

FFT size targets 1 MHz/bin, snapped to FFTW-optimal lengths via `scipy.fft.next_fast_len`. Typical values: 6250 (6.25 GS/s) or 25000 (25 GS/s). FFTW wisdom is cached at `~/.cache/visu3/fftw_wisdom.pkl` and loaded on import of `loader`. CuPy GPU backend is used automatically when CUDA is available.

### Processed dataset format

Saved to `<source_dir>/processed/`:
- `dataset.json` — metadata including version, shape, tscale, fft_params, file references
- `fft_map.npy`, `dc_map.npy`, `dcb_map.npy` (dual only)

Scan metadata (friendly name, material, physical axis parameters) is stored in `scan.json` alongside the raw WFM files and edited via `MetadataDialog`.
