"""
Results table widget for StarVisibility GUI.

Displays SelectedTarget objects in a sortable, filterable QTableView
backed by a custom QAbstractTableModel.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Slot,
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.models.domain import SelectedTarget

# Subset of export columns shown in the GUI table (full set goes to CSV)
_DISPLAY_COLUMNS = [
    ("Night",      "observing_night"),
    ("Slot Start",  "slot_start_local"),
    ("Slot End",    "slot_end_local"),
    ("Sector",     "sector"),
    ("Type",       "target_type"),
    ("Bin",        "mag_bin_label"),
    ("Star Name",  "star_name"),
    ("Vmag",       "vmag"),
    ("Alt Min",    "alt_min_deg"),
    ("Alt Mean",   "alt_mean_deg"),
    ("Az Mean",    "az_mean_deg"),
    ("Full Slot",  "visible_full_slot"),
    ("Repeated",   "repeated_from_previous_slot"),
    ("Hotspot Δ°", "hotspot_distance_deg"),
    ("Score",      "ranking_score"),
    ("Notes",      "notes"),
]

_HEADERS = [h for h, _ in _DISPLAY_COLUMNS]
_KEYS = [k for _, k in _DISPLAY_COLUMNS]
_MAG_COL_IDX = 7   # index of the magnitude column in _DISPLAY_COLUMNS / _HEADERS


class TargetTableModel(QAbstractTableModel):
    """Qt model backed by a list of SelectedTarget export dicts.

    Call :meth:`set_band` to switch the magnitude column header and values
    to the currently selected photometric band.
    """

    def __init__(self, targets: Optional[List[SelectedTarget]] = None) -> None:
        super().__init__()
        self._rows: List[dict] = []
        # Instance-level copies so we can mutate the mag column without
        # touching the module-level constants.
        self._headers: List[str] = list(_HEADERS)
        self._keys: List[str] = list(_KEYS)
        if targets:
            self.set_targets(targets)

    def set_band(self, band: str) -> None:
        """Switch the magnitude column to *band* (e.g. 'J' for Jmag).

        Updates both the column header and the key used to look up the value
        in the per-target export dict, then notifies the view.
        """
        mag_header = f"{band}mag"
        mag_key = f"{band.lower()}mag"
        self._headers[_MAG_COL_IDX] = mag_header
        self._keys[_MAG_COL_IDX] = mag_key
        self.headerDataChanged.emit(
            Qt.Horizontal, _MAG_COL_IDX, _MAG_COL_IDX
        )
        # Refresh all data cells so the magnitude column re-reads the new key
        if self._rows:
            self.dataChanged.emit(
                self.index(0, _MAG_COL_IDX),
                self.index(len(self._rows) - 1, _MAG_COL_IDX),
            )

    def set_targets(self, targets: List[SelectedTarget]) -> None:
        self.beginResetModel()
        self._rows = [t.to_export_dict() for t in targets]
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = self._keys[index.column()]
        value = row.get(key, "")

        if role == Qt.DisplayRole:
            return str(value)

        if role == Qt.ForegroundRole:
            # Colour "NO" in full-slot column red
            if key == "visible_full_slot" and value == "NO":
                return QColor("#FF6B6B")
            if key == "repeated_from_previous_slot" and value == "YES":
                return QColor("#FFD700")
            return None

        if role == Qt.TextAlignmentRole:
            if key in {"vmag", "alt_min_deg", "alt_mean_deg", "az_mean_deg",
                       "hotspot_distance_deg", "ranking_score"}:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        if orientation == Qt.Horizontal and role == Qt.FontRole:
            f = QFont()
            f.setBold(True)
            return f
        return None


class ResultsTable(QWidget):
    """
    Widget that wraps a sortable, filterable table of planning results.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = TargetTableModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # search all columns
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText(
            "Type to filter by any column …"
        )
        self._filter_edit.textChanged.connect(self._proxy.setFilterFixedString)
        filter_row.addWidget(self._filter_edit, 3)

        filter_row.addWidget(QLabel("Column:"))
        self._col_combo = QComboBox()
        self._col_combo.addItem("All columns", -1)
        for h in _HEADERS:
            self._col_combo.addItem(h)
        self._col_combo.currentIndexChanged.connect(self._on_column_filter_changed)
        filter_row.addWidget(self._col_combo, 1)

        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(60)
        btn_clear.clicked.connect(self._filter_edit.clear)
        filter_row.addWidget(btn_clear)

        layout.addLayout(filter_row)

        # Table view
        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QTableView.SelectRows)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.verticalHeader().setVisible(False)
        self._view.setStyleSheet(
            "QTableView { gridline-color: #3A3A3A; font-size: 11px; }"
            "QHeaderView::section { background-color: #2D5A8E; color: #FFFFFF;"
            "  padding: 4px; font-weight: bold; }"
            "QTableView::item:selected { background-color: #3A6EA5; }"
        )
        layout.addWidget(self._view)

        # Summary label
        self._summary_label = QLabel("No results loaded.")
        layout.addWidget(self._summary_label)

    @Slot(int)
    def _on_column_filter_changed(self, idx: int) -> None:
        col = self._col_combo.itemData(idx)
        self._proxy.setFilterKeyColumn(col if col is not None else -1)

    def load_targets(self, targets: List[SelectedTarget], band: str = "V") -> None:
        """Populate the table with a new list of targets.

        *band* controls which magnitude column is shown (e.g. 'J' for Jmag).
        """
        self._model.set_band(band)
        self._model.set_targets(targets)
        self._view.resizeColumnsToContents()
        n = len(targets)
        self._summary_label.setText(
            f"{n} target{'s' if n != 1 else ''} selected."
        )

    def clear(self) -> None:
        self._model.set_targets([])
        self._summary_label.setText("No results loaded.")
