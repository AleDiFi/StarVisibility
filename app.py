"""
StarVisibility — Astronomical Target Planner
Entry point: python app.py

Usage:
    python app.py               # launch GUI
    python app.py --headless    # run without GUI, use built-in defaults, export CSV
    python app.py --config path/to/config.json  # load config then launch GUI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="StarVisibility — Astronomical Target Planner for OGS/Teide"
    )
    parser.add_argument(
        "--config", metavar="FILE",
        help="Path to a JSON configuration file to load on startup."
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run without GUI: plan with default config and export CSV to ./output/."
    )
    parser.add_argument(
        "--output-dir", metavar="DIR", default="output",
        help="Output directory for headless mode (default: ./output/)."
    )
    return parser.parse_args()


def _run_headless(config_path: str | None, output_dir: str) -> int:
    """Run the planner without a GUI and export results to CSV."""
    import copy
    from src.config.defaults import DEFAULT_APP_CONFIG
    from src.core.planner import Planner
    from src.io.csv_exporter import export_planning_result
    from src.io.persistence import load_config
    from src.utils.logging_utils import setup_logging

    logger = setup_logging()

    if config_path:
        config = load_config(config_path)
        logger.info("Loaded config from %s", config_path)
    else:
        config = copy.deepcopy(DEFAULT_APP_CONFIG)
        logger.info("Using default CaNaPy April 2026 configuration.")

    planner = Planner(config)

    def progress(current, total, msg):
        pct = int(current * 100 / total) if total else 0
        sys.stdout.write(f"\r[{pct:3d}%] {msg[:70]:<70}")
        sys.stdout.flush()

    result = planner.run(progress_callback=progress)
    sys.stdout.write("\n")

    out = Path(output_dir)
    targets_path, summary_path = export_planning_result(result, output_dir=out)

    logger.info("Targets: %s", targets_path)
    logger.info("Summary: %s", summary_path)
    logger.info(
        "Done — %d target(s), %d/%d slot-sectors fully covered.",
        result.total_targets,
        len(result.coverage) - result.unsatisfied_slot_sectors,
        len(result.coverage),
    )

    if result.warnings:
        logger.warning("%d warning(s):", len(result.warnings))
        for w in result.warnings:
            logger.warning("  %s", w)

    return 0


def _run_gui(config_path: str | None) -> int:
    """Launch the PySide6 GUI application."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is not installed.\n"
            "Install it with: pip install PySide6\n"
            "Or run in headless mode: python app.py --headless",
            file=sys.stderr,
        )
        return 1

    from src.utils.logging_utils import setup_logging
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("StarVisibility")
    app.setOrganizationName("INAF CaNaPy")

    # Dark theme stylesheet
    app.setStyleSheet(_DARK_STYLESHEET)

    from src.gui.main_window import MainWindow
    window = MainWindow()

    # Load config if provided on command line
    if config_path:
        try:
            from src.io.persistence import load_config
            config = load_config(config_path)
            window._apply_config(config)
        except Exception as exc:
            print(f"Warning: could not load config {config_path!r}: {exc}", file=sys.stderr)

    window.show()
    return app.exec()


# ---------------------------------------------------------------------------
# Dark theme stylesheet
# ---------------------------------------------------------------------------

_DARK_STYLESHEET = """
QWidget {
    background-color: #2B2B2B;
    color: #EEEEEE;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
}
QMainWindow, QDialog {
    background-color: #2B2B2B;
}
QGroupBox {
    border: 1px solid #555;
    border-radius: 5px;
    margin-top: 10px;
    padding: 8px;
    font-weight: bold;
    color: #AADDFF;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px 0 6px;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {
    background-color: #3C3C3C;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 3px 6px;
    color: #EEEEEE;
    selection-background-color: #3A6EA5;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #6A9FD8;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background-color: #333;
    color: #666;
}
QPushButton {
    background-color: #3C3C3C;
    border: 1px solid #666;
    border-radius: 4px;
    padding: 4px 10px;
    color: #EEEEEE;
}
QPushButton:hover {
    background-color: #4A4A4A;
    border-color: #888;
}
QPushButton:pressed {
    background-color: #2A2A2A;
}
QPushButton:disabled {
    background-color: #333;
    color: #666;
    border-color: #444;
}
QTabWidget::pane {
    border: 1px solid #555;
    border-radius: 3px;
}
QTabBar::tab {
    background: #3C3C3C;
    padding: 6px 14px;
    border: 1px solid #555;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    color: #AAAAAA;
}
QTabBar::tab:selected {
    background: #2D5A8E;
    color: #FFFFFF;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background: #4A4A4A;
}
QScrollBar:vertical {
    background: #333;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #666;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #333;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #666;
    border-radius: 5px;
}
QProgressBar {
    background-color: #3C3C3C;
    border: 1px solid #555;
    border-radius: 4px;
    text-align: center;
    color: #EEEEEE;
}
QProgressBar::chunk {
    background-color: #2D5A8E;
    border-radius: 3px;
}
QTableView, QTableWidget {
    background-color: #2B2B2B;
    alternate-background-color: #333333;
    gridline-color: #444;
    selection-background-color: #2D5A8E;
}
QHeaderView::section {
    background-color: #2D5A8E;
    padding: 4px;
    border: none;
    font-weight: bold;
    color: #FFFFFF;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #666;
    border-radius: 2px;
    background: #3C3C3C;
}
QCheckBox::indicator:checked {
    background: #2D5A8E;
    border-color: #3A6EA5;
}
QSplitter::handle {
    background: #444;
}
QToolBar {
    background: #222;
    border-bottom: 1px solid #444;
    spacing: 4px;
    padding: 3px;
}
QToolBar QLabel {
    color: #888;
}
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = _parse_args()

    if args.headless:
        sys.exit(_run_headless(args.config, args.output_dir))
    else:
        sys.exit(_run_gui(args.config))
