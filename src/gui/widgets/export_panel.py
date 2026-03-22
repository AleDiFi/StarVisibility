"""
Export panel widget for StarVisibility GUI.

Provides buttons to:
  - Export targets CSV
  - Export summary CSV
  - Export Excel workbook (if openpyxl available)
  - Open the output folder in Finder/Explorer
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config.settings import OUTPUT_DIR
from src.models.domain import PlanningResult
from src.utils.logging_utils import get_logger

log = get_logger("export_panel")


class ExportPanel(QWidget):
    """Export panel with CSV and optional Excel buttons."""

    export_done = Signal(str)   # emits the path of the exported file

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._result: Optional[PlanningResult] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        group = QGroupBox("Export Results")
        g_layout = QVBoxLayout(group)

        self._status_label = QLabel("No results to export.")
        self._status_label.setStyleSheet("color: #AAAAAA;")
        g_layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()

        self._btn_csv_targets = QPushButton("Export Targets CSV")
        self._btn_csv_targets.setEnabled(False)
        self._btn_csv_targets.setToolTip(
            "Save all selected targets to a UTF-8 CSV file (Excel-ready)."
        )
        self._btn_csv_targets.clicked.connect(self._export_targets_csv)
        btn_row.addWidget(self._btn_csv_targets)

        self._btn_csv_summary = QPushButton("Export Summary CSV")
        self._btn_csv_summary.setEnabled(False)
        self._btn_csv_summary.setToolTip(
            "Save slot/sector coverage summary to CSV."
        )
        self._btn_csv_summary.clicked.connect(self._export_summary_csv)
        btn_row.addWidget(self._btn_csv_summary)

        self._btn_xlsx = QPushButton("Export Excel (.xlsx)")
        self._btn_xlsx.setEnabled(False)
        self._btn_xlsx.setToolTip(
            "Save both sheets to a formatted Excel workbook.\n"
            "Requires openpyxl (pip install openpyxl)."
        )
        self._btn_xlsx.clicked.connect(self._export_excel)
        btn_row.addWidget(self._btn_xlsx)

        self._btn_open_dir = QPushButton("Open Output Folder")
        self._btn_open_dir.clicked.connect(self._open_output_dir)
        btn_row.addWidget(self._btn_open_dir)

        g_layout.addLayout(btn_row)
        layout.addWidget(group)
        layout.addStretch()

    def set_result(self, result: Optional[PlanningResult]) -> None:
        """Enable/disable export buttons based on whether results exist."""
        self._result = result
        has_results = result is not None and len(result.selected_targets) > 0
        self._btn_csv_targets.setEnabled(has_results)
        self._btn_csv_summary.setEnabled(has_results)
        self._btn_xlsx.setEnabled(has_results)
        if has_results:
            n = len(result.selected_targets)
            ns = sum(1 for c in result.coverage if not c.fully_covered)
            self._status_label.setText(
                f"{n} targets ready for export. "
                f"{ns} slot-sector(s) have incomplete coverage."
            )
            self._status_label.setStyleSheet(
                "color: #FF6B6B;" if ns else "color: #90EE90;"
            )

    @Slot()
    def _export_targets_csv(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Targets CSV", str(OUTPUT_DIR / "targets.csv"),
            "CSV files (*.csv);;All files (*.*)"
        )
        if not path:
            return
        try:
            from src.io.csv_exporter import export_targets_csv
            out = export_targets_csv(self._result.selected_targets, Path(path))
            self.export_done.emit(str(out))
            QMessageBox.information(self, "Export", f"Targets saved to:\n{out}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    @Slot()
    def _export_summary_csv(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Summary CSV", str(OUTPUT_DIR / "summary.csv"),
            "CSV files (*.csv);;All files (*.*)"
        )
        if not path:
            return
        try:
            from src.io.csv_exporter import export_summary_csv
            out = export_summary_csv(self._result.coverage, Path(path))
            self.export_done.emit(str(out))
            QMessageBox.information(self, "Export", f"Summary saved to:\n{out}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    @Slot()
    def _export_excel(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel Workbook", str(OUTPUT_DIR / "starvisibility.xlsx"),
            "Excel files (*.xlsx);;All files (*.*)"
        )
        if not path:
            return
        try:
            from src.io.excel_formatter import export_to_excel
            out = export_to_excel(self._result, Path(path))
            self.export_done.emit(str(out))
            QMessageBox.information(self, "Export", f"Workbook saved to:\n{out}")
        except ImportError as exc:
            QMessageBox.warning(self, "Missing Dependency", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    @Slot()
    def _open_output_dir(self) -> None:
        path = str(OUTPUT_DIR)
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
