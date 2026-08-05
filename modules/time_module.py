import datetime
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QFont
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QRect, Qt
from core.module import BaseModule

class TimeModule(BaseModule):
    """
    Displays the current time in idle state, and date in expanded state.
    """

    @property
    def priority(self) -> int:
        return 0  # Lowest priority, fallback module

    def is_active(self) -> bool:
        return True  # Always fallback to time if nothing else is active

    def get_idle_size(self):
        return (160, 48)

    def get_expanded_size(self):
        return (440, 180)

    def paint_idle(self, painter: QPainter, rect: QRect, anim_step: int):
        time_str = datetime.datetime.now().strftime("%I:%M").lstrip("0")
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont('Segoe UI', 14, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, time_str)

    def paint_expanded(self, painter: QPainter, rect: QRect, anim_step: int):
        time_str = datetime.datetime.now().strftime("%I:%M").lstrip("0")
        date_str = datetime.datetime.now().strftime("%A, %B %d")
        
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont('Segoe UI', 48, QFont.Weight.Bold))
        painter.drawText(QRect(0, 35, rect.width(), 70), Qt.AlignmentFlag.AlignCenter, time_str)
        
        painter.setPen(QColor(180, 180, 180))
        painter.setFont(QFont('Segoe UI', 14))
        painter.drawText(QRect(0, 115, rect.width(), 30), Qt.AlignmentFlag.AlignCenter, date_str)
