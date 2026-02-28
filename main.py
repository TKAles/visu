"""visu3 — main entry point."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtCore import QFile, QThread, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
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


# ---------------------------------------------------------------------------
# Background processing worker
# ---------------------------------------------------------------------------


class _ProcessingWorker(QThread):
    """Runs loader.process_dataset on a background thread."""

    progress = Signal(int, int)   # (completed_rows, total_rows)
    finished = Signal(object)     # ProcessedDataset
    error    = Signal(str)        # error message

    def __init__(self, collated: CollatedDataset, parent=None) -> None:
        super().__init__(parent)
        self._collated = collated

    def run(self) -> None:
        try:
            result = loader.process_dataset(
                self._collated,
                progress_callback=lambda done, total: self.progress.emit(done, total),
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
# Main window controller
# ---------------------------------------------------------------------------


class MainWindow:
    """Controller for the main application window."""

    def __init__(self) -> None:
        self._collated: CollatedDataset | None = None
        self._processed: ProcessedDataset | None = None
        self._dataset_path: Path | None = None
        self._worker: _ProcessingWorker | None = None
        self._metadata: dict = {}

        self._win = _load_ui(_UI_FILE)
        self._win.setWindowTitle(_APP_NAME)
        self._connect_actions()

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

        # Detect scan world before full parsing
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

        self._win.tabWidget.clear()
        self._win.setWindowTitle(f'{_APP_NAME} — {path.name}')
        self._win.statusBar().showMessage(
            f'Opened: {path}  |  {collated.summary()}'
        )

        # Immediately open metadata editor for confirmed oldWorld scans
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

        self._win.setWindowTitle(f'{_APP_NAME} — {path.parent.name} (processed)')
        self._win.statusBar().showMessage(f'Loaded dataset: {path}')
        self._display_dc_maps(processed, self._metadata)

    def _quit(self) -> None:
        QApplication.instance().quit()

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

    def _process_data(self) -> None:
        if self._collated is None:
            QMessageBox.warning(
                self._win,
                'No data loaded',
                'Open an unprocessed directory first (File → Open Unprocessed Directory).',
            )
            return

        total_rows = sum(scan.n_rows for scan in self._collated.scans)
        progress = QProgressDialog(
            f'Processing {self._collated.summary()} …',
            None,                  # no cancel button — pool tear-down is unsafe
            0, total_rows,
            self._win,
        )
        progress.setWindowTitle('Processing')
        progress.setMinimumDuration(0)
        progress.setValue(0)

        self._worker = _ProcessingWorker(self._collated, self._win)
        self._worker.progress.connect(
            lambda done, _total: progress.setValue(done)
        )
        self._worker.finished.connect(
            lambda result: self._on_processing_done(result, progress)
        )
        self._worker.error.connect(
            lambda msg: self._on_processing_error(msg, progress)
        )
        self._worker.start()

    def _display_dc_maps(
        self, processed: ProcessedDataset, metadata: dict | None = None
    ) -> None:
        """Populate the tab widget with one DC imshow per scan."""
        tab_widget = self._win.tabWidget
        tab_widget.clear()

        meta = metadata or {}
        friendly = meta.get('friendly_name', '') or ''
        material = meta.get('material', '') or ''

        # Check if we have enough metadata for physical axes
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

                # Physical extent and axis labels
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

                # Symmetric colormap limits so zero maps to the midpoint
                vmax = np.abs(dc_image).max() or 1.0
                im = ax.imshow(
                    dc_image,
                    aspect='auto',
                    origin='upper',
                    interpolation='nearest',
                    cmap='RdBu_r',
                    vmin=-vmax,
                    vmax=vmax,
                    extent=extent,
                )
                fig.colorbar(im, ax=ax, label='DC Voltage (V)')

                # Title: friendly name as heading, material as subheading
                if friendly and material:
                    ax.set_title(f'{friendly}\n{material}', fontsize=10)
                elif friendly:
                    ax.set_title(friendly, fontsize=10)
                elif material:
                    ax.set_title(material, fontsize=10)

                canvas = FigureCanvasQTAgg(fig)
                tab_name = f'Scan {scan_idx + 1}' if len(channels) == 1 else f'{label} — Scan {scan_idx + 1}'
                tab_widget.addTab(canvas, tab_name)

    def _on_processing_done(
        self, result: ProcessedDataset, progress: QProgressDialog
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

        self._win.statusBar().showMessage(
            f'Processing complete — dataset saved to {dataset_path}'
        )
        self._display_dc_maps(result, self._metadata)

    def _on_processing_error(
        self, message: str, progress: QProgressDialog
    ) -> None:
        progress.close()
        QMessageBox.critical(self._win, 'Processing failed', message)
        self._win.statusBar().showMessage('Processing failed.')

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
        w.actionProcess_DC_Bias_Maps.triggered.connect(self._process_data)
        w.actionProcess_FFT_Maps.triggered.connect(self._process_data)


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
