"""visu3 — main entry point."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

import numpy as np

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtCore import QFile, Qt, QThread, Signal
from PySide6.QtGui import QActionGroup, QDoubleValidator, QFont
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import loader
from loader import (
    CollatedDataset,
    ProcessedDataset,
    DATASET_FILENAME,
    DATASET_VERSION,
    is_oldworld_directory,
    read_metadata,
)

_UI_FILE = Path(__file__).with_name('main.ui')
_APP_NAME = 'VISU3'
_PREFS_PATH  = Path.home() / '.config' / 'visu3' / 'preferences.json'
_CLIM_STEPS  = 1000


# ---------------------------------------------------------------------------
# Preference helpers
# ---------------------------------------------------------------------------


def _load_prefs() -> dict:
    defaults = {'generation_wavelength_um': 12.5}
    if not _PREFS_PATH.exists():
        return defaults
    try:
        data = json.loads(_PREFS_PATH.read_text(encoding='utf-8'))
        return {**defaults, **data} if isinstance(data, dict) else defaults
    except (json.JSONDecodeError, OSError):
        return defaults


def _save_prefs(prefs: dict) -> None:
    try:
        _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding='utf-8')
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Background processing workers
# ---------------------------------------------------------------------------


class _DCWorker(QThread):
    """Runs loader.process_dc_maps on a background thread."""

    progress = Signal(int, int, int, int, int)   # (scan_idx, scan_done, scan_total, overall_done, overall_total)
    finished = Signal(object)     # ProcessedDataset — dc_map populated, fft_map=None
    error    = Signal(str)

    def __init__(self, collated: CollatedDataset, parent=None) -> None:
        super().__init__(parent)
        self._collated = collated

    def run(self) -> None:
        try:
            result = loader.process_dc_maps(
                self._collated,
                progress_callback=lambda si, sd, st, od, ot: self.progress.emit(si, sd, st, od, ot),
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class _FFTWorker(QThread):
    """Runs loader.process_fft_maps on a background thread."""

    progress = Signal(int, int, int, int, int)   # (scan_idx, scan_done, scan_total, overall_done, overall_total)
    finished = Signal(object)     # ProcessedDataset — fft_map populated
    error    = Signal(str)

    def __init__(
        self,
        collated: CollatedDataset,
        dc_result: ProcessedDataset,
        dc_threshold: float | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._collated      = collated
        self._dc_result     = dc_result
        self._dc_threshold  = dc_threshold

    def run(self) -> None:
        try:
            result = loader.process_fft_maps(
                self._collated,
                self._dc_result,
                dc_threshold=self._dc_threshold,
                progress_callback=lambda si, sd, st, od, ot: self.progress.emit(si, sd, st, od, ot),
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Metadata dialog
# ---------------------------------------------------------------------------


class MetadataDialog(QDialog):
    """Dialog for viewing and editing scan.json metadata."""

    _SCAN_JSON = 'scan.json'

    def __init__(self, source_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self._scan_json = source_dir / self._SCAN_JSON
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        self.setWindowTitle('Edit Metadata')
        self.setMinimumWidth(360)

        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self._friendly_name = QLineEdit()
        self._material = QLineEdit()
        self._start_x = QLineEdit()
        self._start_y = QLineEdit()
        self._delta_x = QLineEdit()
        self._delta_y = QLineEdit()

        dbl = QDoubleValidator()
        for w in (self._start_x, self._start_y, self._delta_x, self._delta_y):
            w.setValidator(dbl)

        layout.addRow('Friendly Name', self._friendly_name)
        layout.addRow('Material', self._material)
        layout.addRow('Start X', self._start_x)
        layout.addRow('Start Y', self._start_y)
        layout.addRow('Delta X', self._delta_x)
        layout.addRow('Delta Y', self._delta_y)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load(self) -> None:
        if not self._scan_json.exists():
            return
        try:
            data = json.loads(self._scan_json.read_text())
        except (json.JSONDecodeError, OSError):
            return

        self._friendly_name.setText(str(data.get('friendly_name', '')))
        self._material.setText(str(data.get('material', '')))
        for widget, key in [
            (self._start_x, 'start_x'),
            (self._start_y, 'start_y'),
            (self._delta_x, 'delta_x'),
            (self._delta_y, 'delta_y'),
        ]:
            val = data.get(key)
            if val is not None:
                widget.setText(str(val))

    def _save_and_accept(self) -> None:
        numeric_fields = [
            (self._start_x, 'Start X'),
            (self._start_y, 'Start Y'),
            (self._delta_x, 'Delta X'),
            (self._delta_y, 'Delta Y'),
        ]
        for widget, label in numeric_fields:
            text = widget.text().strip()
            if text:
                try:
                    float(text)
                except ValueError:
                    QMessageBox.warning(self, 'Invalid value', f'{label} must be a number.')
                    widget.setFocus()
                    return

        def _to_float(text: str) -> float | None:
            text = text.strip()
            return float(text) if text else None

        data = {
            'friendly_name': self._friendly_name.text().strip(),
            'material': self._material.text().strip(),
            'start_x': _to_float(self._start_x.text()),
            'start_y': _to_float(self._start_y.text()),
            'delta_x': _to_float(self._delta_x.text()),
            'delta_y': _to_float(self._delta_y.text()),
        }

        try:
            self._scan_json.write_text(json.dumps(data, indent=2))
        except OSError as exc:
            QMessageBox.critical(self, 'Save failed', f'Could not write scan.json:\n{exc}')
            return

        self.accept()


# ---------------------------------------------------------------------------
# Preferences dialog
# ---------------------------------------------------------------------------


class PreferencesDialog(QDialog):
    """Dialog for editing application-level preferences."""

    def __init__(self, prefs: dict, parent=None) -> None:
        super().__init__(parent)
        self._prefs = dict(prefs)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle('Preferences')
        self.setMinimumWidth(320)

        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self._wavelength_spin = QDoubleSpinBox()
        self._wavelength_spin.setSuffix(' µm')
        self._wavelength_spin.setRange(0.001, 100000.0)
        self._wavelength_spin.setDecimals(3)
        self._wavelength_spin.setValue(self._prefs.get('generation_wavelength_um', 12.5))
        layout.addRow('Generation Wavelength', self._wavelength_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accepted)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_accepted(self) -> None:
        self._prefs['generation_wavelength_um'] = self._wavelength_spin.value()
        self.accept()

    def get_prefs(self) -> dict:
        return dict(self._prefs)


# ---------------------------------------------------------------------------
# Export dialog
# ---------------------------------------------------------------------------


class _ExportDialog(QDialog):
    """Dialog for choosing an output directory and file prefix before export."""

    def __init__(self, suggested_dir: Path, suggested_prefix: str, parent=None) -> None:
        super().__init__(parent)
        self._result_dir: Path | None = None
        self._result_prefix: str = ''
        self._setup_ui(suggested_dir, suggested_prefix)

    def _setup_ui(self, suggested_dir: Path, suggested_prefix: str) -> None:
        self.setWindowTitle('Export')
        self.setMinimumWidth(460)

        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        dir_widget = QWidget()
        dir_hbox = QHBoxLayout(dir_widget)
        dir_hbox.setContentsMargins(0, 0, 0, 0)
        self._dir_edit = QLineEdit(str(suggested_dir))
        browse_btn = QPushButton('Browse…')
        browse_btn.clicked.connect(self._browse)
        dir_hbox.addWidget(self._dir_edit, stretch=1)
        dir_hbox.addWidget(browse_btn)
        layout.addRow('Output Directory', dir_widget)

        self._prefix_edit = QLineEdit(suggested_prefix)
        layout.addRow('File Prefix', self._prefix_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accepted)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _browse(self) -> None:
        start = self._dir_edit.text().strip() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self, 'Choose Output Directory', start,
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self._dir_edit.setText(directory)

    def _on_accepted(self) -> None:
        dir_text = self._dir_edit.text().strip()
        prefix = self._prefix_edit.text().strip()
        if not dir_text:
            QMessageBox.warning(self, 'Missing directory', 'Please choose an output directory.')
            return
        if not prefix:
            QMessageBox.warning(self, 'Missing prefix', 'Please enter a file prefix.')
            return
        self._result_dir = Path(dir_text)
        self._result_prefix = prefix
        self.accept()

    def get_result(self) -> tuple[Path, str] | None:
        if self._result_dir is None:
            return None
        return self._result_dir, self._result_prefix


# ---------------------------------------------------------------------------
# Dual progress dialog
# ---------------------------------------------------------------------------


class _DualProgressDialog(QDialog):
    """Progress dialog with per-scan and overall progress bars."""

    def __init__(self, title: str, description: str, n_scans: int, total_rows: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(description))

        self._n_scans = n_scans
        self._scan_label = QLabel(f'Scan 1 of {n_scans}')
        self._scan_bar = QProgressBar()
        layout.addWidget(self._scan_label)
        layout.addWidget(self._scan_bar)

        self._overall_label = QLabel(f'Overall: 0 of {total_rows} rows')
        self._overall_bar = QProgressBar()
        self._overall_bar.setRange(0, total_rows)
        layout.addWidget(self._overall_label)
        layout.addWidget(self._overall_bar)

    def update_progress(self, scan_idx: int, scan_done: int, scan_total: int, overall_done: int, overall_total: int) -> None:
        self._scan_label.setText(f'Scan {scan_idx + 1} of {self._n_scans}: {scan_done} / {scan_total} rows')
        self._scan_bar.setMaximum(scan_total)
        self._scan_bar.setValue(scan_done)
        self._overall_label.setText(f'Overall: {overall_done} / {overall_total} rows')
        self._overall_bar.setMaximum(overall_total)
        self._overall_bar.setValue(overall_done)


# ---------------------------------------------------------------------------
# Display tab factory
# ---------------------------------------------------------------------------


def _make_display_tab(im, canvas, vmin: float, vmax: float, fmt: str) -> QWidget:
    """Return a QWidget containing *canvas* plus min/max colormap sliders."""
    # Guard against NaN / equal limits so sliders are always responsive.
    data_min = vmin if np.isfinite(vmin) else 0.0
    data_max = vmax if np.isfinite(vmax) else 1.0
    if data_min == data_max:
        data_max = data_min + 1.0

    def _tick_to_float(tick: int) -> float:
        return data_min + (data_max - data_min) * tick / _CLIM_STEPS

    # Labels
    min_label = QLabel(fmt % _tick_to_float(0))
    min_label.setMinimumWidth(72)
    max_label = QLabel(fmt % _tick_to_float(_CLIM_STEPS))
    max_label.setMinimumWidth(72)

    # Sliders
    min_slider = QSlider(Qt.Orientation.Horizontal)
    min_slider.setRange(0, _CLIM_STEPS)
    min_slider.setValue(0)

    max_slider = QSlider(Qt.Orientation.Horizontal)
    max_slider.setRange(0, _CLIM_STEPS)
    max_slider.setValue(_CLIM_STEPS)

    def _on_min_changed(tick: int) -> None:
        if tick > max_slider.value():
            max_slider.blockSignals(True)
            max_slider.setValue(tick)
            max_slider.blockSignals(False)
            max_label.setText(fmt % _tick_to_float(tick))
        min_label.setText(fmt % _tick_to_float(tick))
        im.set_clim(vmin=_tick_to_float(min_slider.value()),
                    vmax=_tick_to_float(max_slider.value()))
        canvas.draw_idle()

    def _on_max_changed(tick: int) -> None:
        if tick < min_slider.value():
            min_slider.blockSignals(True)
            min_slider.setValue(tick)
            min_slider.blockSignals(False)
            min_label.setText(fmt % _tick_to_float(tick))
        max_label.setText(fmt % _tick_to_float(tick))
        im.set_clim(vmin=_tick_to_float(min_slider.value()),
                    vmax=_tick_to_float(max_slider.value()))
        canvas.draw_idle()

    min_slider.valueChanged.connect(_on_min_changed)
    max_slider.valueChanged.connect(_on_max_changed)

    # Controls row
    controls = QWidget()
    hbox = QHBoxLayout(controls)
    hbox.setContentsMargins(4, 2, 4, 2)
    hbox.addWidget(QLabel('Min:'))
    hbox.addWidget(min_slider, stretch=1)
    hbox.addWidget(min_label)
    hbox.addSpacing(16)
    hbox.addWidget(QLabel('Max:'))
    hbox.addWidget(max_slider, stretch=1)
    hbox.addWidget(max_label)

    # Container
    container = QWidget()
    vbox = QVBoxLayout(container)
    vbox.setContentsMargins(0, 0, 0, 0)
    vbox.addWidget(canvas, stretch=1)
    vbox.addWidget(controls, stretch=0)

    return container


def _make_dc_display_tab(
    im,
    canvas,
    dc_image: np.ndarray,
    vmin: float,
    vmax: float,
    fmt: str,
    on_threshold_changed=None,
) -> QWidget:
    """
    Return a QWidget with min/max colormap sliders and a DC threshold slider.

    The threshold slider zeroes out pixels in the DC display whose values fall
    below the chosen threshold.  ``on_threshold_changed(value)`` is called
    whenever the threshold changes so the main window can track it for FFT
    processing.
    """
    # Guard against NaN / equal limits.
    data_min = vmin if np.isfinite(vmin) else 0.0
    data_max = vmax if np.isfinite(vmax) else 1.0
    if data_min == data_max:
        data_max = data_min + 1.0

    dc_orig = dc_image.copy()  # keep original for threshold masking

    def _tick_to_float(tick: int) -> float:
        return data_min + (data_max - data_min) * tick / _CLIM_STEPS

    # Labels
    min_label   = QLabel(fmt % data_min);  min_label.setMinimumWidth(72)
    max_label   = QLabel(fmt % data_max);  max_label.setMinimumWidth(72)
    thresh_label = QLabel(fmt % data_min); thresh_label.setMinimumWidth(72)

    # Colour-range sliders
    min_slider = QSlider(Qt.Orientation.Horizontal)
    min_slider.setRange(0, _CLIM_STEPS)
    min_slider.setValue(0)

    max_slider = QSlider(Qt.Orientation.Horizontal)
    max_slider.setRange(0, _CLIM_STEPS)
    max_slider.setValue(_CLIM_STEPS)

    # Threshold slider
    thresh_slider = QSlider(Qt.Orientation.Horizontal)
    thresh_slider.setRange(0, _CLIM_STEPS)
    thresh_slider.setValue(0)

    def _update_display() -> None:
        thresh_val = _tick_to_float(thresh_slider.value())
        masked = dc_orig.copy()
        masked[dc_orig < thresh_val] = 0.0
        im.set_data(masked)
        im.set_clim(
            vmin=_tick_to_float(min_slider.value()),
            vmax=_tick_to_float(max_slider.value()),
        )
        canvas.draw_idle()

    def _on_min_changed(tick: int) -> None:
        if tick > max_slider.value():
            max_slider.blockSignals(True)
            max_slider.setValue(tick)
            max_slider.blockSignals(False)
            max_label.setText(fmt % _tick_to_float(tick))
        min_label.setText(fmt % _tick_to_float(tick))
        _update_display()

    def _on_max_changed(tick: int) -> None:
        if tick < min_slider.value():
            min_slider.blockSignals(True)
            min_slider.setValue(tick)
            min_slider.blockSignals(False)
            min_label.setText(fmt % _tick_to_float(tick))
        max_label.setText(fmt % _tick_to_float(tick))
        _update_display()

    def _on_thresh_changed(tick: int) -> None:
        thresh_val = _tick_to_float(tick)
        thresh_label.setText(fmt % thresh_val)
        _update_display()
        if on_threshold_changed:
            on_threshold_changed(thresh_val)

    min_slider.valueChanged.connect(_on_min_changed)
    max_slider.valueChanged.connect(_on_max_changed)
    thresh_slider.valueChanged.connect(_on_thresh_changed)

    # Row 1: colour range
    controls1 = QWidget()
    hbox1 = QHBoxLayout(controls1)
    hbox1.setContentsMargins(4, 2, 4, 2)
    hbox1.addWidget(QLabel('Min:'))
    hbox1.addWidget(min_slider, stretch=1)
    hbox1.addWidget(min_label)
    hbox1.addSpacing(16)
    hbox1.addWidget(QLabel('Max:'))
    hbox1.addWidget(max_slider, stretch=1)
    hbox1.addWidget(max_label)

    # Row 2: DC threshold
    controls2 = QWidget()
    hbox2 = QHBoxLayout(controls2)
    hbox2.setContentsMargins(4, 2, 4, 2)
    hbox2.addWidget(QLabel('DC Threshold:'))
    hbox2.addWidget(thresh_slider, stretch=1)
    hbox2.addWidget(thresh_label)

    container = QWidget()
    vbox = QVBoxLayout(container)
    vbox.setContentsMargins(0, 0, 0, 0)
    vbox.addWidget(canvas, stretch=1)
    vbox.addWidget(controls1, stretch=0)
    vbox.addWidget(controls2, stretch=0)

    return container


# ---------------------------------------------------------------------------
# Main window controller
# ---------------------------------------------------------------------------


class MainWindow:
    """Controller for the main application window."""

    def __init__(self) -> None:
        self._collated:      CollatedDataset | None  = None
        self._processed:     ProcessedDataset | None = None
        self._dataset_path:  Path | None             = None
        self._worker:        QThread | None          = None
        self._metadata:      dict                    = {}
        self._view_mode:     Literal['dc', 'fft']   = 'dc'
        self._prefs:         dict                   = _load_prefs()
        self._dc_threshold:  float | None           = None
        self._tab_canvases:  list[tuple[str, FigureCanvasQTAgg]] = []

        self._win = _load_ui(_UI_FILE)
        self._win.setWindowTitle(_APP_NAME)
        self._build_central_widget()
        self._connect_actions()
        self._update_workflow_state()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show(self) -> None:
        self._win.show()

    # ------------------------------------------------------------------
    # File menu handlers
    # ------------------------------------------------------------------

    def _open_unprocessed_dir(self) -> None:
        start = str(
            self._collated.source_dir if self._collated else Path.home()
        )
        directory = QFileDialog.getExistingDirectory(
            self._win,
            'Open Unprocessed Directory',
            start,
            QFileDialog.Option.ShowDirsOnly,
        )
        if not directory:
            return

        path = Path(directory)

        oldworld = is_oldworld_directory(path)
        if oldworld:
            reply = QMessageBox.question(
                self._win,
                'oldWorld Scan Detected',
                'This directory contains RF/DC .wfm files consistent with an '
                'oldWorld scan format.\n\nIs this an oldWorld scan?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            collated = loader.scan_directory(path)
        except ValueError as exc:
            QMessageBox.warning(self._win, 'Cannot open directory', str(exc))
            return

        self._collated = collated
        self._processed = None
        self._dataset_path = None
        self._metadata = read_metadata(path)

        self._tab_widget.clear()
        self._win.setWindowTitle(f'{_APP_NAME} — {path.name}')
        self._win.statusBar().showMessage(
            f'Opened: {path}  |  {collated.summary()}'
        )

        self._update_workflow_state()

        if oldworld:
            dialog = MetadataDialog(path, self._win)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._metadata = read_metadata(path)
                self._win.statusBar().showMessage(
                    f'Opened: {path}  |  {collated.summary()}  |  Metadata saved'
                )

    def _open_processed_dataset(self) -> None:
        if self._dataset_path:
            start = str(self._dataset_path.parent)
        elif self._collated:
            start = str(self._collated.source_dir)
        else:
            start = str(Path.home())

        file_path, _ = QFileDialog.getOpenFileName(
            self._win,
            'Open Processed Dataset',
            start,
            f'Dataset files ({DATASET_FILENAME});;JSON files (*.json)',
        )
        if not file_path:
            return

        path = Path(file_path)
        try:
            processed = loader.load_dataset(path)
        except ValueError as exc:
            QMessageBox.critical(
                self._win, 'Failed to open dataset', str(exc)
            )
            return

        self._processed = processed
        self._dataset_path = path
        self._collated = None
        self._metadata = read_metadata(processed.source_dir)

        self._view_mode = 'dc'
        self._win.setWindowTitle(f'{_APP_NAME} — {path.parent.name} (processed)')
        self._win.statusBar().showMessage(f'Loaded dataset: {path}')
        self._display_maps()
        self._update_workflow_state()

    def _quit(self) -> None:
        QApplication.instance().quit()

    def _open_preferences(self) -> None:
        dialog = PreferencesDialog(self._prefs, self._win)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._prefs = dialog.get_prefs()
            _save_prefs(self._prefs)

    # ------------------------------------------------------------------
    # Processing menu handlers
    # ------------------------------------------------------------------

    def _edit_metadata(self) -> None:
        if self._collated is None:
            QMessageBox.warning(
                self._win,
                'No directory loaded',
                'Open an unprocessed directory first (File → Open Unprocessed Directory).',
            )
            return

        dialog = MetadataDialog(self._collated.source_dir, self._win)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._metadata = read_metadata(self._collated.source_dir)
            self._win.statusBar().showMessage(
                f'Metadata saved to {self._collated.source_dir / MetadataDialog._SCAN_JSON}'
            )

    def _process_dc(self) -> None:
        if self._collated is None:
            QMessageBox.warning(
                self._win,
                'No data loaded',
                'Open an unprocessed directory first (File → Open Unprocessed Directory).',
            )
            return

        total_rows = sum(scan.n_rows for scan in self._collated.scans)
        n_scans    = self._collated.n_scans
        progress = _DualProgressDialog(
            'Processing DC',
            f'Processing DC maps — {self._collated.summary()} …',
            n_scans, total_rows, self._win,
        )
        progress.show()

        self._worker = _DCWorker(self._collated, self._win)
        self._worker.progress.connect(progress.update_progress)
        self._worker.finished.connect(
            lambda result: self._on_dc_done(result, progress)
        )
        self._worker.error.connect(
            lambda msg: self._on_dc_error(msg, progress)
        )
        self._worker.start()

    def _process_fft(self) -> None:
        if self._collated is None:
            QMessageBox.warning(
                self._win,
                'No data loaded',
                'Open an unprocessed directory first (File → Open Unprocessed Directory).',
            )
            return

        if self._processed is None:
            QMessageBox.warning(
                self._win,
                'DC maps required',
                'Run "Process DC Bias Maps" first.\n\n'
                'Examining the DC scan first lets you decide whether the RF '
                'data is worth the longer FFT processing time.',
            )
            return

        total_rows = sum(scan.n_rows for scan in self._collated.scans)
        n_scans    = self._collated.n_scans
        progress = _DualProgressDialog(
            'Processing FFT',
            f'Processing FFT maps — {self._collated.summary()} …',
            n_scans, total_rows, self._win,
        )
        progress.show()

        self._worker = _FFTWorker(self._collated, self._processed, self._dc_threshold, self._win)
        self._worker.progress.connect(progress.update_progress)
        self._worker.finished.connect(
            lambda result: self._on_fft_done(result, progress)
        )
        self._worker.error.connect(
            lambda msg: self._on_fft_error(msg, progress)
        )
        self._worker.start()

    # ------------------------------------------------------------------
    # View toggle
    # ------------------------------------------------------------------

    def _on_view_changed(self, action) -> None:
        self._view_mode = 'fft' if action == self._win.actionViewFFT else 'dc'
        self._display_maps()
        self._update_workflow_state()

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def _display_maps(self) -> None:
        """Redraw the tab widget for the current view mode and dataset."""
        if self._processed is None:
            return
        if self._view_mode == 'fft' and self._processed.fft_map is not None:
            self._display_fft_maps(self._processed, self._metadata)
        else:
            self._display_dc_maps(self._processed, self._metadata)

    def _display_dc_maps(
        self, processed: ProcessedDataset, metadata: dict | None = None
    ) -> None:
        """Populate the tab widget with one DC imshow per scan."""
        tab_widget = self._tab_widget
        tab_widget.clear()
        self._tab_canvases = []

        meta = metadata or {}
        friendly = meta.get('friendly_name', '') or ''
        material = meta.get('material', '') or ''

        _phys_keys = ('start_x', 'delta_x', 'start_y', 'delta_y')
        has_phys = all(meta.get(k) is not None for k in _phys_keys)

        n_scans = processed.dc_map.shape[0]
        channels: list[tuple[str, np.ndarray]] = [('DC', processed.dc_map)]
        if processed.dcb_map is not None:
            channels.append(('DC-B', processed.dcb_map))

        for label, data in channels:
            for scan_idx in range(n_scans):
                dc_image = data[scan_idx]          # (n_rows, n_frames)
                n_rows, n_frames = dc_image.shape

                fig = Figure(tight_layout=True)
                ax = fig.add_subplot(111)

                if has_phys:
                    sx = float(meta['start_x'])
                    dx = float(meta['delta_x'])
                    sy = float(meta['start_y'])
                    dy = float(meta['delta_y'])
                    extent = [sx, sx + n_frames * dx, sy + n_rows * dy, sy]
                    ax.set_xlabel('X position')
                    ax.set_ylabel('Y position')
                else:
                    extent = None
                    ax.set_xlabel('Pixel (frame index)')
                    ax.set_ylabel('Row index')

                # Use actual data range; guard against all-NaN images.
                dc_min = float(np.nanmin(dc_image))
                dc_max = float(np.nanmax(dc_image))
                if not np.isfinite(dc_min) or not np.isfinite(dc_max):
                    dc_min, dc_max = 0.0, 1.0
                elif dc_min == dc_max:
                    dc_min -= 0.5
                    dc_max += 0.5

                im = ax.imshow(
                    dc_image,
                    aspect='auto',
                    origin='upper',
                    interpolation='nearest',
                    cmap='viridis',
                    vmin=dc_min,
                    vmax=dc_max,
                    extent=extent,
                )
                fig.colorbar(im, ax=ax, label='DC Voltage (V)')

                if friendly and material:
                    ax.set_title(f'{friendly}\n{material}', fontsize=10)
                elif friendly:
                    ax.set_title(friendly, fontsize=10)
                elif material:
                    ax.set_title(material, fontsize=10)

                canvas = FigureCanvasQTAgg(fig)
                tab_name = (
                    f'Scan {scan_idx + 1}'
                    if len(channels) == 1
                    else f'{label} — Scan {scan_idx + 1}'
                )
                self._tab_canvases.append((tab_name, canvas))
                tab_widget.addTab(
                    _make_dc_display_tab(
                        im, canvas, dc_image,
                        vmin=dc_min, vmax=dc_max, fmt='%.3f V',
                        on_threshold_changed=lambda v: setattr(self, '_dc_threshold', v),
                    ),
                    tab_name,
                )

    def _display_fft_maps(
        self, processed: ProcessedDataset, metadata: dict | None = None
    ) -> None:
        """Populate the tab widget with one peak-frequency imshow per scan."""
        tab_widget = self._tab_widget
        tab_widget.clear()
        self._tab_canvases = []

        meta = metadata or {}
        friendly = meta.get('friendly_name', '') or ''
        material = meta.get('material', '') or ''

        _phys_keys = ('start_x', 'delta_x', 'start_y', 'delta_y')
        has_phys = all(meta.get(k) is not None for k in _phys_keys)

        fft_map = processed.fft_map   # (n_scans, n_rows, n_frames), MHz
        n_scans = fft_map.shape[0]

        for scan_idx in range(n_scans):
            freq_image = fft_map[scan_idx]         # (n_rows, n_frames), MHz
            n_rows, n_frames = freq_image.shape

            fig = Figure(tight_layout=True)
            ax = fig.add_subplot(111)

            if has_phys:
                sx = float(meta['start_x'])
                dx = float(meta['delta_x'])
                sy = float(meta['start_y'])
                dy = float(meta['delta_y'])
                extent = [sx, sx + n_frames * dx, sy + n_rows * dy, sy]
                ax.set_xlabel('X position')
                ax.set_ylabel('Y position')
            else:
                extent = None
                ax.set_xlabel('Pixel (frame index)')
                ax.set_ylabel('Row index')

            im = ax.imshow(
                freq_image,
                aspect='auto',
                origin='upper',
                interpolation='nearest',
                cmap='plasma',
                extent=extent,
            )
            fig.colorbar(im, ax=ax, label='Peak Frequency (MHz)')

            if friendly and material:
                ax.set_title(f'{friendly}\n{material}', fontsize=10)
            elif friendly:
                ax.set_title(friendly, fontsize=10)
            elif material:
                ax.set_title(material, fontsize=10)

            fft_min = float(np.nanmin(freq_image))
            fft_max = float(np.nanmax(freq_image))

            canvas = FigureCanvasQTAgg(fig)
            tab_name = f'Scan {scan_idx + 1}'
            self._tab_canvases.append((tab_name, canvas))
            tab_widget.addTab(
                _make_display_tab(im, canvas, vmin=fft_min, vmax=fft_max, fmt='%.1f MHz'),
                tab_name,
            )

    # ------------------------------------------------------------------
    # Processing callbacks
    # ------------------------------------------------------------------

    def _on_dc_done(
        self, result: ProcessedDataset, progress: _DualProgressDialog
    ) -> None:
        progress.close()

        output_dir = result.source_dir / 'processed'
        try:
            dataset_path = loader.save_dataset(result, output_dir)
        except OSError as exc:
            QMessageBox.critical(
                self._win, 'Save failed', f'Could not write dataset:\n{exc}'
            )
            return

        self._processed = result
        self._dataset_path = dataset_path
        self._metadata = read_metadata(result.source_dir)

        # Stay in DC view; FFT is not yet available
        self._view_mode = 'dc'

        self._win.statusBar().showMessage(
            f'DC processing complete — dataset saved to {dataset_path}'
        )
        self._display_maps()
        self._update_workflow_state()

    def _on_dc_error(
        self, message: str, progress: _DualProgressDialog
    ) -> None:
        progress.close()
        QMessageBox.critical(self._win, 'DC processing failed', message)
        self._win.statusBar().showMessage('DC processing failed.')
        self._update_workflow_state()

    def _on_fft_done(
        self, result: ProcessedDataset, progress: _DualProgressDialog
    ) -> None:
        progress.close()

        output_dir = result.source_dir / 'processed'
        try:
            dataset_path = loader.save_dataset(result, output_dir)
        except OSError as exc:
            QMessageBox.critical(
                self._win, 'Save failed', f'Could not write dataset:\n{exc}'
            )
            return

        self._processed = result
        self._dataset_path = dataset_path

        # Switch to FFT view now that data is available
        self._view_mode = 'fft'

        self._win.statusBar().showMessage(
            f'FFT processing complete — dataset saved to {dataset_path}'
        )
        self._display_maps()
        self._update_workflow_state()

    def _on_fft_error(
        self, message: str, progress: _DualProgressDialog
    ) -> None:
        progress.close()
        QMessageBox.critical(self._win, 'FFT processing failed', message)
        self._win.statusBar().showMessage('FFT processing failed.')
        self._update_workflow_state()

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def _export_suggested(self) -> tuple[Path, str]:
        if self._dataset_path:
            out_dir = self._dataset_path.parent
        elif self._collated:
            out_dir = self._collated.source_dir
        else:
            out_dir = Path.home()
        prefix = (
            self._metadata.get('friendly_name')
            or (self._dataset_path.parent.name if self._dataset_path else
                self._collated.source_dir.name if self._collated else 'export')
        )
        return out_dir, str(prefix)

    def _export_images(self) -> None:
        if self._processed is None:
            QMessageBox.warning(self._win, 'No data', 'Load and process data first.')
            return
        if not self._tab_canvases:
            QMessageBox.warning(self._win, 'Nothing to export', 'No maps are currently displayed.')
            return

        suggested_dir, suggested_prefix = self._export_suggested()
        dialog = _ExportDialog(suggested_dir, suggested_prefix, self._win)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        out_dir, prefix = dialog.get_result()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self._win, 'Export failed', f'Cannot create directory:\n{exc}')
            return

        errors: list[str] = []
        saved = 0
        for tab_name, canvas in self._tab_canvases:
            safe = tab_name.replace(' ', '_').replace('—', '-').replace('/', '-')
            out_path = out_dir / f'{prefix}_{safe}.png'
            try:
                canvas.figure.savefig(str(out_path), dpi=150, bbox_inches='tight')
                saved += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f'{out_path.name}: {exc}')

        if errors:
            QMessageBox.warning(
                self._win, 'Export partially failed',
                f'Saved {saved} image(s).\nErrors:\n' + '\n'.join(errors),
            )
        else:
            self._win.statusBar().showMessage(f'Exported {saved} image(s) to {out_dir}')

    def _export_csv(self) -> None:
        if self._processed is None:
            QMessageBox.warning(self._win, 'No data', 'Load and process data first.')
            return

        suggested_dir, suggested_prefix = self._export_suggested()
        dialog = _ExportDialog(suggested_dir, suggested_prefix, self._win)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        out_dir, prefix = dialog.get_result()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self._win, 'Export failed', f'Cannot create directory:\n{exc}')
            return

        to_export: list[tuple[str, np.ndarray]] = []
        if self._view_mode == 'fft' and self._processed.fft_map is not None:
            for i in range(self._processed.fft_map.shape[0]):
                to_export.append((f'FFT_scan{i + 1}', self._processed.fft_map[i]))
        else:
            for i in range(self._processed.dc_map.shape[0]):
                to_export.append((f'DC_scan{i + 1}', self._processed.dc_map[i]))
            if self._processed.dcb_map is not None:
                for i in range(self._processed.dcb_map.shape[0]):
                    to_export.append((f'DC-B_scan{i + 1}', self._processed.dcb_map[i]))

        errors: list[str] = []
        saved = 0
        for name, data in to_export:
            out_path = out_dir / f'{prefix}_{name}.csv'
            try:
                np.savetxt(str(out_path), data, delimiter=',')
                saved += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f'{out_path.name}: {exc}')

        if errors:
            QMessageBox.warning(
                self._win, 'Export partially failed',
                f'Saved {saved} CSV(s).\nErrors:\n' + '\n'.join(errors),
            )
        else:
            self._win.statusBar().showMessage(f'Exported {saved} CSV(s) to {out_dir}')

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addStretch()

        card = QWidget()
        card.setMaximumWidth(480)
        card_vbox = QVBoxLayout(card)
        card_vbox.setSpacing(12)

        title = QLabel('VISU3')
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_vbox.addWidget(title)

        subtitle = QLabel('Tektronix WFM Scan Visualizer')
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_vbox.addWidget(subtitle)

        card_vbox.addSpacing(16)

        open_btn = QPushButton('Open Scan Folder')
        open_btn.setMinimumHeight(40)
        open_btn.clicked.connect(self._open_unprocessed_dir)
        card_vbox.addWidget(open_btn)

        card_vbox.addSpacing(12)

        instructions = QLabel(
            '1. Open a scan folder containing .WFM files\n'
            '2. Edit scan metadata (optional)\n'
            '3. Process DC Bias Maps\n'
            '4. Process FFT Maps'
        )
        card_vbox.addWidget(instructions)

        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch()

        return page

    def _build_toolbar_row(self) -> QWidget:
        toolbar = QWidget()
        hbox = QHBoxLayout(toolbar)
        hbox.setContentsMargins(6, 4, 6, 4)
        hbox.setSpacing(4)

        self._btn_open = QPushButton('1  Open Folder')
        self._btn_metadata = QPushButton('2  Edit Metadata')
        self._btn_process_dc = QPushButton('3  Process DC')
        self._btn_process_fft = QPushButton('4  Process FFT')

        for btn in (self._btn_open, self._btn_metadata, self._btn_process_dc, self._btn_process_fft):
            btn.setFlat(True)

        hbox.addWidget(self._btn_open)
        hbox.addWidget(QLabel('→'))
        hbox.addWidget(self._btn_metadata)
        hbox.addWidget(QLabel('→'))
        hbox.addWidget(self._btn_process_dc)
        hbox.addWidget(QLabel('→'))
        hbox.addWidget(self._btn_process_fft)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        hbox.addWidget(sep1)

        self._btn_export_images = QPushButton('Export Images')
        self._btn_export_csv = QPushButton('Export CSV')
        hbox.addWidget(self._btn_export_images)
        hbox.addWidget(self._btn_export_csv)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        hbox.addWidget(sep2)

        self._btn_view_dc = QPushButton('DC')
        self._btn_view_dc.setCheckable(True)
        self._btn_view_fft = QPushButton('FFT')
        self._btn_view_fft.setCheckable(True)
        hbox.addWidget(self._btn_view_dc)
        hbox.addWidget(self._btn_view_fft)

        hbox.addStretch()

        return toolbar

    def _build_central_widget(self) -> None:
        self._tab_widget = QTabWidget()

        welcome = self._build_welcome_page()

        self._stack = QStackedWidget()
        self._stack.addWidget(welcome)       # page 0 — welcome
        self._stack.addWidget(self._tab_widget)  # page 1 — maps

        toolbar_row = self._build_toolbar_row()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)

        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(toolbar_row)
        vbox.addWidget(sep)
        vbox.addWidget(self._stack, stretch=1)

        self._win.setCentralWidget(container)

    def _update_workflow_state(self) -> None:
        folder_open = self._collated is not None
        dc_done = self._processed is not None
        fft_done = dc_done and self._processed.fft_map is not None

        # Reset view mode if FFT data is no longer available
        if not fft_done and self._view_mode == 'fft':
            self._view_mode = 'dc'

        # Stack: show welcome until DC data is available
        self._stack.setCurrentIndex(1 if dc_done else 0)

        # Determine suggested next step (0-indexed)
        if not folder_open and not dc_done:
            suggested = 0
        elif folder_open and not dc_done:
            suggested = 2
        elif folder_open and dc_done and not fft_done:
            suggested = 3
        else:
            suggested = -1

        _SUGGESTED = 'font-weight: bold; border: 1px solid palette(highlight);'
        _DONE = 'color: gray;'

        steps = [
            (self._btn_open,        '1  Open Folder',   True,                    folder_open),
            (self._btn_metadata,    '2  Edit Metadata',  folder_open,             False),
            (self._btn_process_dc,  '3  Process DC',    folder_open,             dc_done),
            (self._btn_process_fft, '4  Process FFT',   folder_open and dc_done, fft_done),
        ]

        for i, (btn, label, enabled, done) in enumerate(steps):
            btn.setEnabled(enabled)
            if done:
                btn.setText(f'✓ {label}')
                btn.setStyleSheet(_DONE)
            else:
                btn.setText(label)
                btn.setStyleSheet(_SUGGESTED if i == suggested else '')

        self._btn_export_images.setEnabled(dc_done)
        self._btn_export_csv.setEnabled(dc_done)

        self._btn_view_fft.setEnabled(fft_done)
        self._win.actionViewFFT.setEnabled(fft_done)
        self._btn_view_dc.setChecked(self._view_mode == 'dc')
        self._btn_view_fft.setChecked(self._view_mode == 'fft')
        self._win.actionViewDC.setChecked(self._view_mode == 'dc')
        self._win.actionViewFFT.setChecked(self._view_mode == 'fft')

    def _on_view_dc_btn_clicked(self) -> None:
        self._view_mode = 'dc'
        self._display_maps()
        self._update_workflow_state()

    def _on_view_fft_btn_clicked(self) -> None:
        self._view_mode = 'fft'
        self._display_maps()
        self._update_workflow_state()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _connect_actions(self) -> None:
        w = self._win
        # File menu
        w.actionOpen_Directory_2.triggered.connect(self._open_unprocessed_dir)
        w.actionOpen_Processed_Directory.triggered.connect(self._open_processed_dataset)
        w.actionQuit_VISU.triggered.connect(self._quit)
        # Processing menu
        w.actionEdit_Metadata.triggered.connect(self._edit_metadata)
        w.actionProcess_DC_Bias_Maps.triggered.connect(self._process_dc)
        w.actionProcess_FFT_Maps.triggered.connect(self._process_fft)
        # System Options
        w.actionSystem_Options.triggered.connect(self._open_preferences)
        # Export menu
        w.actionExport_Images.triggered.connect(self._export_images)
        w.actionExport_CSV_Files.triggered.connect(self._export_csv)
        # View menu — exclusive checkable toggle (DC ↔ FFT)
        view_group = QActionGroup(w)
        view_group.addAction(w.actionViewDC)
        view_group.addAction(w.actionViewFFT)
        view_group.setExclusive(True)
        view_group.triggered.connect(self._on_view_changed)
        # Toolbar buttons
        self._btn_open.clicked.connect(self._open_unprocessed_dir)
        self._btn_metadata.clicked.connect(self._edit_metadata)
        self._btn_process_dc.clicked.connect(self._process_dc)
        self._btn_process_fft.clicked.connect(self._process_fft)
        self._btn_export_images.clicked.connect(self._export_images)
        self._btn_export_csv.clicked.connect(self._export_csv)
        self._btn_view_dc.clicked.connect(self._on_view_dc_btn_clicked)
        self._btn_view_fft.clicked.connect(self._on_view_fft_btn_clicked)


# ---------------------------------------------------------------------------
# UI loader
# ---------------------------------------------------------------------------


def _load_ui(ui_path: Path):
    """Load a Qt Designer .ui file and return the top-level widget."""
    loader_obj = QUiLoader()
    qfile = QFile(str(ui_path))
    if not qfile.open(QFile.OpenModeFlag.ReadOnly):
        raise RuntimeError(f'Cannot open UI file: {ui_path}')
    widget = loader_obj.load(qfile)
    qfile.close()
    if widget is None:
        raise RuntimeError(f'Failed to load UI: {loader_obj.errorString()}')
    return widget


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(_APP_NAME)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
