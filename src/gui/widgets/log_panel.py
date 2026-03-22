"""
Log panel widget for StarVisibility GUI.

Displays log messages from the application logger in a scrollable
text area.  Messages are colour-coded by severity.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogPanel(QWidget):
    """
    A widget that displays log messages with colour-coded severity.

    Call append_message(text, level) to add entries.
    Compatible with the CallbackHandler in utils/logging_utils.py.
    """

    COLOURS = {
        "DEBUG": "#888888",
        "INFO": "#DDDDDD",
        "WARNING": "#FFD700",
        "ERROR": "#FF6B6B",
        "CRITICAL": "#FF0000",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Text area
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Courier New", 9))
        self._text.setStyleSheet(
            "background-color: #1E1E1E; color: #DDDDDD; border: 1px solid #444;"
        )
        layout.addWidget(self._text)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        btn_clear = QPushButton("Clear Log")
        btn_clear.setFixedWidth(90)
        btn_clear.clicked.connect(self._text.clear)
        toolbar.addWidget(btn_clear)
        layout.addLayout(toolbar)

    @Slot(str)
    def append_log_line(self, line: str) -> None:
        """
        Append a formatted log line (as produced by CallbackHandler).
        The level keyword is extracted from the line prefix.
        """
        level = "INFO"
        for lvl in self.COLOURS:
            if lvl in line[:12]:
                level = lvl
                break
        self.append_message(line, level)

    def append_message(self, text: str, level: str = "INFO") -> None:
        """Append *text* to the log area in the colour for *level*."""
        colour = self.COLOURS.get(level.upper(), "#DDDDDD")
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colour))
        cursor.setCharFormat(fmt)
        cursor.insertText(text + "\n")

        # Auto-scroll
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()
