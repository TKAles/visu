# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**visu3** is a Python desktop GUI application for scientific data visualization and analysis. It is in early development (UI mockup only — no business logic implemented yet).

## Tech Stack

- **Python 3.14+** with **PySide6** (Qt6) for the GUI
- **uv** as the package manager (not pip/poetry)
- **NumPy / SciPy / PyFFTW** for numerical processing
- **Matplotlib** for plotting
- UI layout defined in `main.ui` (Qt Designer XML)

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

The application is a single-window Qt app. The intended data flow (from the UI menu structure in `main.ui`) is:

```
Open Directory (raw data)
    → Edit Metadata
    → Process: DC Bias Maps / FFT Maps
    → View: DC channels (A, B, A+B) / FFT mode / Velocity mode
    → Export: Images / CSV
```

**UI structure** (`main.ui`): Defines the main window with a central `QGraphicsView` for visualization, a status bar, and a menu bar with File, Processing, View Modes, Export, and About menus.

**`main.py`**: Currently a placeholder `main()` function — the entry point where Qt app initialization should live.

As the project grows, expect to add:
- A module for data loading/parsing
- Processing modules (DC bias, FFT)
- A model/controller layer between data and the Qt views
