import ctypes
import time
from typing import Tuple
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QRect, Qt, QRectF
from core.module import BaseModule

VK_CAPITAL = 0x14
VK_NUMLOCK = 0x90

class LockStatusModule(BaseModule):
    def __init__(self, island):
        super().__init__(island)
        self.is_cycleable = False
        self._last_caps = self._get_caps_state()
        self._last_num = self._get_num_state()
        self.active_alert = None
        self.alert_time = 0.0

    @property
    def priority(self) -> int:
        return 5

    def _get_caps_state(self) -> bool:
        try:
            return bool(ctypes.windll.user32.GetKeyState(VK_CAPITAL) & 1)
        except Exception:
            return False

    def _get_num_state(self) -> bool:
        try:
            return bool(ctypes.windll.user32.GetKeyState(VK_NUMLOCK) & 1)
        except Exception:
            return False

    def is_active(self) -> bool:
        return (time.time() - self.alert_time) < 1.8

    def get_idle_size(self) -> Tuple[int, int]:
        return (160, 48)

    def get_expanded_size(self) -> Tuple[int, int]:
        return (160, 48)

    def on_tick(self, step: int):
        curr_caps = self._get_caps_state()
        curr_num = self._get_num_state()

        if curr_caps != self._last_caps:
            self._last_caps = curr_caps
            self.active_alert = ("Caps Lock", curr_caps)
            self.alert_time = time.time()
            self.island.show_module_popup(self, duration_ms=1800)

        elif curr_num != self._last_num:
            self._last_num = curr_num
            self.active_alert = ("Num Lock", curr_num)
            self.alert_time = time.time()
            self.island.show_module_popup(self, duration_ms=1800)

    def _draw_hud(self, painter: QPainter, rect: QRect):
        if not self.active_alert:
            return

        name, is_on = self.active_alert

        # Accent Glow Color
        # ponytail: amber for ON, gray for OFF – green is reserved for camera privacy dot
        dot_color = QColor(255, 179, 0) if is_on else QColor(142, 142, 147)
        text_str = f"{name.upper()} {'ON' if is_on else 'OFF'}"

        painter.save()
        
        # Draw status indicator dot / icon
        cx = rect.left() + 24
        cy = rect.center().y()
        r = 5.0

        if is_on:
            # Outer glow ring
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 179, 0, 70))
            painter.drawEllipse(QRectF(cx - r*1.6, cy - r*1.6, r*3.2, r*3.2))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        painter.drawEllipse(QRectF(cx - r, cy - r, r*2, r*2))

        # Text label
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 240 if is_on else 170))

        text_rect = QRect(rect.left() + 40, rect.top(), rect.width() - 50, rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text_str)
        
        painter.restore()

    def paint_idle(self, painter: QPainter, rect: QRect, anim_step: int):
        self._draw_hud(painter, rect)

    def paint_expanded(self, painter: QPainter, rect: QRect, anim_step: int):
        self._draw_hud(painter, rect)
