"""
Sector editor widget for StarVisibility GUI.

Shows four collapsible GroupBox cards, one per sector (North/South/East/West).
The user can edit azimuth limits, elevation limits, optional hotspot,
and the East rising threshold.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.models.domain import AppConfig, SectorDefinition


class SectorCard(QGroupBox):
    """Editor card for a single sector definition."""

    def __init__(self, sector: SectorDefinition, parent=None) -> None:
        super().__init__(sector.name, parent)
        self.setCheckable(True)
        self.setChecked(sector.enabled)
        self._build_form(sector)

    def _build_form(self, sector: SectorDefinition) -> None:
        form = QFormLayout(self)
        form.setSpacing(6)

        note = QLabel(
            "Azimuth: North=0°, East=90°, South=180°, West=270°\n"
            "North sector wraps through 0° (az_min > az_max is OK)."
        )
        note.setStyleSheet("color: #AAAAAA; font-size: 9px;")
        form.addRow(note)

        def spin(lo, hi, val, tooltip="", decimals=1):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setDecimals(decimals)
            s.setValue(val)
            s.setToolTip(tooltip)
            return s

        self._az_min = spin(0, 360, sector.az_min,
                            "Azimuth lower bound [0, 360).")
        self._az_max = spin(0, 360, sector.az_max,
                            "Azimuth upper bound [0, 360). "
                            "For North sector, az_max < az_min (wraps through 0°).")
        self._el_min = spin(0, 89, sector.el_min,
                            "Minimum elevation required throughout the slot [°].")
        self._el_max = spin(1, 90, sector.el_max,
                            "Maximum elevation (upper limit of sector box) [°].")

        form.addRow("Az Min [°]:", self._az_min)
        form.addRow("Az Max [°]:", self._az_max)
        form.addRow("El Min [°]:", self._el_min)
        form.addRow("El Max [°]:", self._el_max)

        # Hotspot (optional)
        self._has_hotspot = QCheckBox("Enable hotspot")
        self._has_hotspot.setChecked(sector.hotspot_el is not None)
        self._has_hotspot.toggled.connect(self._toggle_hotspot)
        form.addRow(self._has_hotspot)

        hotspot_hl = QHBoxLayout()
        self._hotspot_el = spin(0, 90, sector.hotspot_el or 70.0,
                                "Preferred elevation for ranking bonus [°].")
        self._hotspot_az = spin(0, 360, sector.hotspot_az or 180.0,
                                "Preferred azimuth for ranking bonus [°].")
        hotspot_hl.addWidget(QLabel("El:"))
        hotspot_hl.addWidget(self._hotspot_el)
        hotspot_hl.addWidget(QLabel("Az:"))
        hotspot_hl.addWidget(self._hotspot_az)
        self._hotspot_widget = QWidget()
        self._hotspot_widget.setLayout(hotspot_hl)
        self._hotspot_widget.setEnabled(self._has_hotspot.isChecked())
        form.addRow("Hotspot:", self._hotspot_widget)

        # Rising threshold (optional, East)
        self._has_rising = QCheckBox("Enable rising elevation relaxation")
        self._has_rising.setChecked(sector.rising_el_min is not None)
        self._has_rising.toggled.connect(self._toggle_rising)
        form.addRow(self._has_rising)

        self._rising_el = spin(0, 90, sector.rising_el_min or 55.0,
                               "Accept rising stars above this elevation [°].")
        self._rising_el.setEnabled(self._has_rising.isChecked())
        form.addRow("Rising El Min [°]:", self._rising_el)

    @Slot(bool)
    def _toggle_hotspot(self, checked: bool) -> None:
        self._hotspot_widget.setEnabled(checked)

    @Slot(bool)
    def _toggle_rising(self, checked: bool) -> None:
        self._rising_el.setEnabled(checked)

    def read_sector(self, original: SectorDefinition) -> SectorDefinition:
        """Return an updated SectorDefinition from current field values."""
        return SectorDefinition(
            name=original.name,
            az_min=self._az_min.value(),
            az_max=self._az_max.value(),
            el_min=self._el_min.value(),
            el_max=self._el_max.value(),
            hotspot_el=self._hotspot_el.value() if self._has_hotspot.isChecked() else None,
            hotspot_az=self._hotspot_az.value() if self._has_hotspot.isChecked() else None,
            rising_el_min=self._rising_el.value() if self._has_rising.isChecked() else None,
            enabled=self.isChecked(),
        )


class SectorEditor(QWidget):
    """
    Scrollable container with one SectorCard per sector.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cards: List[SectorCard] = []
        self._sector_originals: List[SectorDefinition] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setSpacing(10)
        self._content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def load_sectors(self, sectors: List[SectorDefinition]) -> None:
        """Populate the panel with sector cards."""
        # Clear existing
        for card in self._cards:
            self._content_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._sector_originals = list(sectors)

        # Remove stretch
        item = self._content_layout.takeAt(self._content_layout.count() - 1)

        for sector in sectors:
            card = SectorCard(sector)
            self._cards.append(card)
            self._content_layout.addWidget(card)

        self._content_layout.addStretch()

    def read_sectors(self) -> List[SectorDefinition]:
        """Return updated SectorDefinition list from current GUI fields."""
        result = []
        for card, original in zip(self._cards, self._sector_originals):
            result.append(card.read_sector(original))
        return result
