"""
Constraints panel widget for StarVisibility GUI.

Groups:
  - Observation Setup (dates, timezone, sunset/sunrise, slot duration)
  - Catalog Source (VizieR vs local file)
  - Magnitude Bins (dynamic add/remove)
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.models.domain import AppConfig, MagnitudeBin, ObservingSession
from src.utils.validation import (
    validate_date_range,
    validate_hhmm,
    validate_magnitude_bins,
    collect_errors,
)


class ConstraintsPanel(QWidget):
    """
    Panel for editing observation setup and magnitude constraints.
    Emits config_changed signal when the user modifies any field.
    """

    config_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._config: Optional[AppConfig] = None
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(10)

        # --- Observation Setup group ---
        obs_group = QGroupBox("Observation Setup")
        obs_layout = QFormLayout(obs_group)
        obs_layout.setSpacing(6)

        self._start_night = QLineEdit()
        self._start_night.setPlaceholderText("YYYY-MM-DD")
        self._start_night.setToolTip("First observing night (date of sunset).")
        obs_layout.addRow("Start Night:", self._start_night)

        self._end_night = QLineEdit()
        self._end_night.setPlaceholderText("YYYY-MM-DD")
        self._end_night.setToolTip("Last observing night (date of sunset).")
        obs_layout.addRow("End Night:", self._end_night)

        self._timezone = QLineEdit()
        self._timezone.setPlaceholderText("Europe/Madrid")
        self._timezone.setToolTip("IANA timezone string (e.g. Europe/Madrid).")
        obs_layout.addRow("Timezone:", self._timezone)

        self._sunset_local = QLineEdit()
        self._sunset_local.setPlaceholderText("HH:MM")
        self._sunset_local.setToolTip("Observing start time in local time (e.g. 20:00).")
        obs_layout.addRow("Sunset (local):", self._sunset_local)

        self._sunrise_local = QLineEdit()
        self._sunrise_local.setPlaceholderText("HH:MM")
        self._sunrise_local.setToolTip("Observing end time in local time (e.g. 08:00).")
        obs_layout.addRow("Sunrise (local):", self._sunrise_local)

        self._slot_duration = QDoubleSpinBox()
        self._slot_duration.setRange(0.5, 12.0)
        self._slot_duration.setSingleStep(0.5)
        self._slot_duration.setSuffix(" h")
        self._slot_duration.setToolTip("Duration of each observing slot (default: 2 h).")
        obs_layout.addRow("Slot Duration:", self._slot_duration)

        self._slot_step = QDoubleSpinBox()
        self._slot_step.setRange(0.25, 12.0)
        self._slot_step.setSingleStep(0.25)
        self._slot_step.setSuffix(" h")
        self._slot_step.setToolTip(
            "Sliding-window step between slot starts.\n"
            "Set equal to Slot Duration for non-overlapping blocks (default: 1 h)."
        )
        obs_layout.addRow("Slot Step:", self._slot_step)

        self._sample_minutes = QSpinBox()
        self._sample_minutes.setRange(1, 60)
        self._sample_minutes.setSuffix(" min")
        self._sample_minutes.setToolTip(
            "Interval between AltAz samples within a slot.\n"
            "Smaller = more accurate but slower."
        )
        obs_layout.addRow("Sample Interval:", self._sample_minutes)

        main_layout.addWidget(obs_group)

        # --- Catalog Source group ---
        cat_group = QGroupBox("Catalog Source")
        cat_layout = QVBoxLayout(cat_group)

        self._cat_combo = QComboBox()
        self._cat_combo.addItem("VizieR (Hipparcos, online)", "vizier")
        self._cat_combo.addItem("SIMBAD (all bands, online)", "simbad")
        self._cat_combo.addItem("Local file (CSV / FITS)", "local")
        self._cat_combo.currentIndexChanged.connect(self._on_catalog_source_changed)
        cat_layout.addWidget(self._cat_combo)

        # Photometric band selector
        band_row = QHBoxLayout()
        band_row.addWidget(QLabel("Photometric Band:"))
        self._band_combo = QComboBox()
        for b in ("U", "B", "V", "R", "I", "J", "H", "K"):
            self._band_combo.addItem(b, b)
        self._band_combo.setCurrentText("V")
        self._band_combo.setToolTip(
            "Photometric band used for magnitude filtering and display.\n"
            "Stars without data in the selected band are excluded."
        )
        band_row.addWidget(self._band_combo)
        band_row.addStretch()
        cat_layout.addLayout(band_row)

        self._vmag_limit = QDoubleSpinBox()
        self._vmag_limit.setRange(2.0, 12.0)
        self._vmag_limit.setSingleStep(0.5)
        self._vmag_limit.setValue(7.5)
        self._vmag_limit.setToolTip("Maximum Vmag to fetch from VizieR.")

        vmag_row = QHBoxLayout()
        vmag_row.addWidget(QLabel("Vmag limit:"))
        vmag_row.addWidget(self._vmag_limit)
        vmag_row.addStretch()
        cat_layout.addLayout(vmag_row)

        local_row = QHBoxLayout()
        self._local_path = QLineEdit()
        self._local_path.setPlaceholderText("Path to local catalog file …")
        self._local_path.setEnabled(False)
        local_row.addWidget(self._local_path, 3)
        self._browse_btn = QPushButton("Browse …")
        self._browse_btn.setFixedWidth(80)
        self._browse_btn.setEnabled(False)
        self._browse_btn.clicked.connect(self._browse_catalog)
        local_row.addWidget(self._browse_btn)
        cat_layout.addLayout(local_row)

        self._force_refresh_cb = QCheckBox("Force catalog refresh (VizieR)")
        self._force_refresh_cb.setToolTip(
            "Re-download from VizieR even if a cache already exists."
        )
        cat_layout.addWidget(self._force_refresh_cb)

        main_layout.addWidget(cat_group)

        # --- Magnitude Bins group ---
        bins_group = QGroupBox("Magnitude Bins")
        bins_layout = QVBoxLayout(bins_group)

        bins_note = QLabel(
            "Bounds are exclusive: vmag_min < V < vmag_max.\n"
            "Use -99 as vmag_min to mean 'no lower limit'.\n"
            "Bins with overlapping ranges share stars (see reuse option below)."
        )
        bins_note.setWordWrap(True)
        bins_note.setStyleSheet("color: #AAAAAA; font-size: 10px;")
        bins_layout.addWidget(bins_note)

        self._bins_table = QTableWidget(0, 6)
        self._bins_table.setHorizontalHeaderLabels(
            ["Label", "Type", "Vmag Min", "Vmag Max", "Required", "Allow Reuse"]
        )
        self._bins_table.horizontalHeader().setStretchLastSection(True)
        self._bins_table.setAlternatingRowColors(True)
        self._bins_table.setMinimumHeight(150)
        bins_layout.addWidget(self._bins_table)

        bins_btn_row = QHBoxLayout()
        btn_add_bin = QPushButton("+ Add Bin")
        btn_add_bin.clicked.connect(self._add_bin_row)
        btn_remove_bin = QPushButton("− Remove Selected")
        btn_remove_bin.clicked.connect(self._remove_bin_row)
        bins_btn_row.addWidget(btn_add_bin)
        bins_btn_row.addWidget(btn_remove_bin)
        bins_btn_row.addStretch()
        bins_layout.addLayout(bins_btn_row)

        self._allow_global_reuse = QCheckBox(
            "Allow global star reuse across bins (same slot+sector)"
        )
        self._allow_global_reuse.setToolTip(
            "If checked, a star with vmag in the overlap region may satisfy "
            "multiple bins in the same slot+sector simultaneously."
        )
        bins_layout.addWidget(self._allow_global_reuse)

        main_layout.addWidget(bins_group)
        main_layout.addStretch()

    # ------------------------------------------------------------------
    def load_config(self, config: AppConfig) -> None:
        """Populate all fields from config."""
        self._config = config
        s = config.session

        self._start_night.setText(s.start_night)
        self._end_night.setText(s.end_night)
        self._timezone.setText(config.observatory.timezone)
        self._sunset_local.setText(s.sunset_local)
        self._sunrise_local.setText(s.sunrise_local)
        self._slot_duration.setValue(s.slot_duration_hours)
        self._slot_step.setValue(s.slot_step_hours)
        self._sample_minutes.setValue(config.visibility_sample_minutes)

        # Catalog
        source_map = {"vizier": 0, "simbad": 1, "local": 2}
        self._cat_combo.setCurrentIndex(source_map.get(config.catalog_source, 0))
        self._vmag_limit.setValue(config.catalog_vmag_limit)
        self._band_combo.setCurrentText(config.catalog_band)
        self._local_path.setText(config.local_catalog_path)

        # Mag bins
        self._bins_table.setRowCount(0)
        for b in config.magnitude_bins:
            self._append_bin_to_table(b)

        self._allow_global_reuse.setChecked(config.allow_global_reuse)

    # ------------------------------------------------------------------
    def read_config(self, config: AppConfig) -> List[str]:
        """
        Read GUI fields back into *config* (in-place mutation).
        Returns a list of validation error strings (empty = OK).
        """
        errors: List[str] = []

        start = self._start_night.text().strip()
        end = self._end_night.text().strip()
        err = validate_date_range(start, end)
        if err:
            errors.append(err)
        else:
            config.session.start_night = start
            config.session.end_night = end

        err_ss = validate_hhmm(self._sunset_local.text(), "Sunset (local)")
        err_sr = validate_hhmm(self._sunrise_local.text(), "Sunrise (local)")
        errors += [e for e in [err_ss, err_sr] if e]
        if not err_ss:
            config.session.sunset_local = self._sunset_local.text().strip()
        if not err_sr:
            config.session.sunrise_local = self._sunrise_local.text().strip()

        config.session.slot_duration_hours = self._slot_duration.value()
        config.session.slot_step_hours = self._slot_step.value()
        config.visibility_sample_minutes = self._sample_minutes.value()
        config.observatory.timezone = self._timezone.text().strip()

        config.catalog_source = self._cat_combo.currentData()
        config.catalog_vmag_limit = self._vmag_limit.value()
        config.catalog_band = self._band_combo.currentData()
        config.local_catalog_path = self._local_path.text().strip()

        # Magnitude bins
        bins, bin_errors = self._read_bins_table()
        errors += bin_errors
        if not bin_errors:
            config.magnitude_bins = bins

        config.allow_global_reuse = self._allow_global_reuse.isChecked()
        return errors

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_catalog_source_changed(self, idx: int) -> None:
        is_local = self._cat_combo.currentData() == "local"
        self._local_path.setEnabled(is_local)
        self._browse_btn.setEnabled(is_local)

    @Slot()
    def _browse_catalog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Local Catalog",
            str(Path.home()),
            "Catalog files (*.csv *.fits *.fit *.fz);;All files (*.*)"
        )
        if path:
            self._local_path.setText(path)

    def _append_bin_to_table(self, b: MagnitudeBin) -> None:
        row = self._bins_table.rowCount()
        self._bins_table.insertRow(row)
        self._bins_table.setItem(row, 0, QTableWidgetItem(b.label))
        self._bins_table.setItem(row, 1, QTableWidgetItem(b.target_type))
        self._bins_table.setItem(row, 2, QTableWidgetItem(str(b.vmag_min)))
        self._bins_table.setItem(row, 3, QTableWidgetItem(str(b.vmag_max)))
        self._bins_table.setItem(row, 4, QTableWidgetItem(str(b.required_count)))
        cb = QCheckBox()
        cb.setChecked(b.allow_reuse)
        cb.setStyleSheet("margin-left: 20px;")
        self._bins_table.setCellWidget(row, 5, cb)

    @Slot()
    def _add_bin_row(self) -> None:
        row = self._bins_table.rowCount()
        self._bins_table.insertRow(row)
        self._bins_table.setItem(row, 0, QTableWidgetItem("NEW_BIN"))
        self._bins_table.setItem(row, 1, QTableWidgetItem("NGS"))
        self._bins_table.setItem(row, 2, QTableWidgetItem("4.0"))
        self._bins_table.setItem(row, 3, QTableWidgetItem("6.0"))
        self._bins_table.setItem(row, 4, QTableWidgetItem("1"))
        cb = QCheckBox()
        cb.setStyleSheet("margin-left: 20px;")
        self._bins_table.setCellWidget(row, 5, cb)

    @Slot()
    def _remove_bin_row(self) -> None:
        rows = {idx.row() for idx in self._bins_table.selectedIndexes()}
        for row in sorted(rows, reverse=True):
            self._bins_table.removeRow(row)

    def _read_bins_table(self):
        bins: List[MagnitudeBin] = []
        errors: List[str] = []
        for row in range(self._bins_table.rowCount()):
            def cell(c):
                item = self._bins_table.item(row, c)
                return item.text().strip() if item else ""

            label = cell(0)
            target_type = cell(1)
            try:
                vmag_min = float(cell(2))
                vmag_max = float(cell(3))
                req = int(cell(4))
                cb = self._bins_table.cellWidget(row, 5)
                allow = cb.isChecked() if cb else False
            except ValueError:
                errors.append(f"Bin row {row+1}: invalid numeric value.")
                continue

            if vmag_min >= vmag_max:
                errors.append(
                    f"Bin '{label}': vmag_min ({vmag_min}) must be < vmag_max ({vmag_max})."
                )
            if req < 1:
                errors.append(f"Bin '{label}': required_count must be ≥ 1.")

            bins.append(MagnitudeBin(
                label=label,
                target_type=target_type,
                vmag_min=vmag_min,
                vmag_max=vmag_max,
                required_count=req,
                allow_reuse=allow,
            ))
        return bins, errors

    @property
    def force_catalog_refresh(self) -> bool:
        return self._force_refresh_cb.isChecked()
