"""
Main window for StarVisibility.

Architecture: lightweight MVVM.
  - GUI widgets own no scientific logic.
  - The PlannerWorker QThread wraps the Planner core and emits signals.
  - MainWindow mediates between widgets and the worker.

Layout:
  ┌──────────────────────────────────────────────────────────┐
  │ Toolbar: [Run] [Stop] [Save Config] [Load Config]        │
  ├─────────────────────┬────────────────────────────────────┤
  │ Left: Tab Setup     │ Right: Tab Results / Log           │
  │  ├─ Constraints     │  ├─ Results Table                  │
  │  └─ Sectors         │  └─ Log Panel                      │
  ├─────────────────────┴────────────────────────────────────┤
  │ Status bar: [progress bar] [status text]  [Export btns]  │
  └──────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal, Slot, Qt
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.config.defaults import DEFAULT_APP_CONFIG
from src.config.settings import (
    APP_TITLE,
    APP_VERSION,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_READY,
    STATUS_RUNNING,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from src.core.planner import Planner
from src.gui.widgets.constraints_panel import ConstraintsPanel
from src.gui.widgets.export_panel import ExportPanel
from src.gui.widgets.log_panel import LogPanel
from src.gui.widgets.results_table import ResultsTable
from src.gui.widgets.sector_editor import SectorEditor
from src.io.persistence import load_config, save_config
from src.models.domain import AppConfig, PlanningResult
from src.utils.logging_utils import APP_LOGGER, add_callback_handler, get_logger, remove_handler

log = get_logger("main_window")


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------


class PlannerWorker(QThread):
    """
    Runs the Planner in a background thread to keep the GUI responsive.
    """

    progress = Signal(int, int, str)    # current, total, message
    finished = Signal(object)           # PlanningResult or None on error
    error = Signal(str)                 # error message

    def __init__(self, config: AppConfig, force_refresh: bool = False) -> None:
        super().__init__()
        self._config = config
        self._force_refresh = force_refresh
        self._planner = Planner(config)
        self._aborted = False

    def abort(self) -> None:
        self._aborted = True

    def run(self) -> None:
        try:
            def progress_cb(current: int, total: int, msg: str) -> None:
                if self._aborted:
                    raise InterruptedError("Planning aborted by user.")
                self.progress.emit(current, total, msg)

            result = self._planner.run(
                progress_callback=progress_cb,
                force_catalog_refresh=self._force_refresh,
            )
            self.finished.emit(result)
        except InterruptedError:
            self.error.emit("Planning cancelled.")
        except Exception as exc:
            log.exception("Planning failed")
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """Application main window."""

    def __init__(self) -> None:
        super().__init__()
        self._config: AppConfig = copy.deepcopy(DEFAULT_APP_CONFIG)
        self._result: Optional[PlanningResult] = None
        self._worker: Optional[PlannerWorker] = None
        self._log_handler = None

        self._build_ui()
        self._connect_log_handler()
        self._load_default_config()

        self.setWindowTitle(f"{APP_TITLE}  v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._set_status(STATUS_READY)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # --- Toolbar ---
        self._build_toolbar()

        # --- Main splitter (left config panel | right results/log) ---
        splitter = QSplitter(Qt.Horizontal)

        # Left: setup tabs
        left_tabs = QTabWidget()
        left_tabs.setMinimumWidth(380)
        left_tabs.setMaximumWidth(520)

        self._constraints_panel = ConstraintsPanel()
        left_tabs.addTab(
            _scrollable(self._constraints_panel),
            "⚙  Observation Setup"
        )

        self._sector_editor = SectorEditor()
        left_tabs.addTab(self._sector_editor, "🌍  Sectors")

        splitter.addWidget(left_tabs)

        # Right: results + log
        right_tabs = QTabWidget()

        self._results_table = ResultsTable()
        right_tabs.addTab(self._results_table, "📋  Results")

        self._log_panel = LogPanel()
        right_tabs.addTab(self._log_panel, "📝  Log")

        self._export_panel = ExportPanel()
        right_tabs.addTab(self._export_panel, "💾  Export")

        splitter.addWidget(right_tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)

        # --- Status bar ---
        self._build_status_bar(main_layout)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._btn_run = QPushButton("▶  Run Planning")
        self._btn_run.setStyleSheet(
            "QPushButton { background: #2D7D2D; color: white; font-weight: bold;"
            " padding: 6px 14px; border-radius: 4px; }"
            "QPushButton:hover { background: #3A9C3A; }"
            "QPushButton:disabled { background: #555; color: #888; }"
        )
        self._btn_run.clicked.connect(self._on_run)
        tb.addWidget(self._btn_run)

        tb.addSeparator()

        self._btn_stop = QPushButton("⏹  Stop")
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet(
            "QPushButton { background: #7D2D2D; color: white; padding: 6px 14px;"
            " border-radius: 4px; }"
            "QPushButton:hover { background: #9C3A3A; }"
            "QPushButton:disabled { background: #555; color: #888; }"
        )
        self._btn_stop.clicked.connect(self._on_stop)
        tb.addWidget(self._btn_stop)

        tb.addSeparator()

        btn_save = QPushButton("💾  Save Config")
        btn_save.clicked.connect(self._on_save_config)
        tb.addWidget(btn_save)

        btn_load = QPushButton("📂  Load Config")
        btn_load.clicked.connect(self._on_load_config)
        tb.addWidget(btn_load)

        btn_reset = QPushButton("↺  Reset Defaults")
        btn_reset.clicked.connect(self._on_reset_defaults)
        tb.addWidget(btn_reset)

        tb.addSeparator()
        lbl = QLabel(f" {APP_TITLE}  v{APP_VERSION} ")
        lbl.setStyleSheet("color: #888; font-size: 11px;")
        tb.addWidget(lbl)

    def _build_status_bar(self, parent_layout: QVBoxLayout) -> None:
        status_bar = QWidget()
        status_bar.setFixedHeight(28)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(4, 2, 4, 2)
        status_layout.setSpacing(8)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setTextVisible(True)
        status_layout.addWidget(self._progress_bar, 3)

        self._status_label = QLabel(STATUS_READY)
        self._status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self._status_label, 1)

        parent_layout.addWidget(status_bar)

    # ------------------------------------------------------------------
    # Logging integration
    # ------------------------------------------------------------------

    def _connect_log_handler(self) -> None:
        """Route application log messages to the GUI log panel."""
        self._log_handler = add_callback_handler(
            callback=self._log_panel.append_log_line,
            level=logging.INFO,
        )

    def closeEvent(self, event) -> None:
        if self._log_handler:
            remove_handler(self._log_handler)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Config management
    # ------------------------------------------------------------------

    def _load_default_config(self) -> None:
        """Populate GUI panels with the default (CaNaPy) configuration."""
        self._apply_config(self._config)

    def _apply_config(self, config: AppConfig) -> None:
        self._config = config
        self._constraints_panel.load_config(config)
        self._sector_editor.load_sectors(config.sectors)

    def _collect_config_from_gui(self) -> tuple[AppConfig, list]:
        """
        Read GUI fields into a fresh AppConfig copy.
        Returns (config, error_list).
        """
        config = copy.deepcopy(self._config)
        errors = self._constraints_panel.read_config(config)
        config.sectors = self._sector_editor.read_sectors()
        return config, errors

    # ------------------------------------------------------------------
    # Toolbar actions
    # ------------------------------------------------------------------

    @Slot()
    def _on_run(self) -> None:
        config, errors = self._collect_config_from_gui()
        if errors:
            QMessageBox.warning(
                self, "Validation Errors",
                "Please fix the following errors before running:\n\n"
                + "\n".join(f"• {e}" for e in errors),
            )
            return

        self._config = config
        force_refresh = self._constraints_panel.force_catalog_refresh

        log.info("Starting planning run …")
        log.info("Campaign: %s → %s  |  %d nights",
                 config.session.start_night, config.session.end_night,
                 len([1 for _ in range(10)]))
        log.info("Catalog: %s | Vmag ≤ %.1f",
                 config.catalog_source, config.catalog_vmag_limit)
        log.info("Sectors: %s",
                 ", ".join(s.name for s in config.sectors if s.enabled))

        self._worker = PlannerWorker(config, force_refresh=force_refresh)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_planning_finished)
        self._worker.error.connect(self._on_planning_error)

        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._results_table.clear()
        self._export_panel.set_result(None)
        self._set_status(STATUS_RUNNING)
        self._progress_bar.setValue(0)

        self._worker.start()

    @Slot()
    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            log.info("Aborting planning …")
            self._worker.abort()
            self._worker.wait(3000)
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._set_status(STATUS_READY)

    @Slot()
    def _on_save_config(self) -> None:
        config, errors = self._collect_config_from_gui()
        if errors:
            QMessageBox.warning(self, "Config Errors",
                                "Fix errors before saving:\n" + "\n".join(errors))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", "", "JSON files (*.json);;All files (*.*)"
        )
        if not path:
            return
        try:
            save_config(config, path)
            log.info("Configuration saved to %s", path)
            QMessageBox.information(self, "Saved", f"Configuration saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    @Slot()
    def _on_load_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "", "JSON files (*.json);;All files (*.*)"
        )
        if not path:
            return
        try:
            config = load_config(path)
            self._apply_config(config)
            log.info("Configuration loaded from %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    @Slot()
    def _on_reset_defaults(self) -> None:
        reply = QMessageBox.question(
            self, "Reset Defaults",
            "Reset all settings to the CaNaPy April 2026 defaults?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._apply_config(copy.deepcopy(DEFAULT_APP_CONFIG))
            log.info("Configuration reset to defaults.")

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    @Slot(int, int, str)
    def _on_progress(self, current: int, total: int, message: str) -> None:
        pct = int(current * 100 / total) if total else 0
        self._progress_bar.setValue(pct)
        self._progress_bar.setFormat(f"{pct}%  —  {message}")

    @Slot(object)
    def _on_planning_finished(self, result: PlanningResult) -> None:
        self._result = result
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._progress_bar.setValue(100)

        n_targets = result.total_targets
        n_incomplete = result.unsatisfied_slot_sectors
        n_total = len(result.coverage)

        msg = (
            f"✓ Done — {n_targets} target(s) selected. "
            f"{n_total - n_incomplete}/{n_total} slot-sectors fully covered."
        )
        if n_incomplete:
            msg += f"  ⚠ {n_incomplete} incomplete."
        self._set_status(STATUS_DONE, msg)
        log.info(msg)

        if result.warnings:
            for w in result.warnings:
                log.warning(w)

        self._results_table.load_targets(
            result.selected_targets,
            band=self._config.catalog_band,
        )
        self._export_panel.set_result(result)

    @Slot(str)
    def _on_planning_error(self, error_msg: str) -> None:
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._set_status(STATUS_FAILED, f"Error: {error_msg}")
        log.error("Planning failed: %s", error_msg)
        QMessageBox.critical(self, "Planning Failed", error_msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, status: str, detail: str = "") -> None:
        colours = {
            STATUS_READY:   "#CCCCCC",
            STATUS_RUNNING: "#FFD700",
            STATUS_DONE:    "#90EE90",
            STATUS_FAILED:  "#FF6B6B",
        }
        colour = colours.get(status, "#CCCCCC")
        text = f"<span style='color:{colour}'><b>{status}</b></span>"
        if detail:
            text += f"  {detail}"
        self._status_label.setText(text)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scrollable(widget: QWidget) -> QScrollArea:
    """Wrap *widget* in a QScrollArea."""
    scroll = QScrollArea()
    scroll.setWidget(widget)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    return scroll
