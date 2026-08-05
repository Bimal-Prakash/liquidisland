import threading
import asyncio
import queue
import time
from ctypes import cast, POINTER
# pyrefly: ignore [missing-import]
import comtypes
# pyrefly: ignore [missing-import]
from comtypes import CLSCTX_ALL
# pyrefly: ignore [missing-import]
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
# pyrefly: ignore [missing-import]
import screen_brightness_control as sbc

# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath, QLinearGradient, QRadialGradient
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QRect, QRectF, Qt, QPoint, QPointF
from core.module import BaseModule
import math

class ControlModule(BaseModule):
    """
    Control Center module for LiquidIsland.
    Provides draggable sliders for system Volume and screen Brightness.
    """
    def __init__(self, island):
        super().__init__(island)
        self.is_cycleable = True
        self.volume_level = 0.5
        self.brightness_level = 0.5

        self.dragging_vol = False
        self.dragging_bright = False

        # Cooldown: don't read hardware for 1s after a set command
        self._vol_set_time = 0.0
        self._bright_set_time = 0.0
        self._COOLDOWN = 1.0  # seconds

        # Liquid capsule layout (island expanded = 440×180)
        self.vol_rect = QRectF(35, 30, 370, 44)
        self.bright_rect = QRectF(35, 100, 370, 44)

        self._running = False

        # Queue for volume set commands -> processed on the COM thread
        self._vol_queue = queue.Queue()
        # Queue for brightness set commands -> processed on a brightness thread
        self._bright_queue = queue.Queue()

    @property
    def priority(self) -> int:
        return 2

    def is_active(self) -> bool:
        return True

    def get_idle_size(self):
        return (140, 48)

    def get_expanded_size(self):
        return (440, 180)

    def get_accent_color(self) -> QColor:
        return QColor(255, 255, 255)

    def on_start(self):
        self._running = True
        # Single persistent COM thread for all audio operations
        self._com_thread = threading.Thread(target=self._com_worker, daemon=True)
        self._com_thread.start()
        # Separate thread for brightness (sbc is slow, no COM needed)
        self._bright_thread = threading.Thread(target=self._brightness_worker, daemon=True)
        self._bright_thread.start()

    def on_stop(self):
        self._running = False

    # ── COM Worker (Volume) ──────────────────────────────────────────
    def _com_worker(self):
        """Single long-lived thread that owns all COM objects."""
        comtypes.CoInitialize()
        try:
            # Cache the volume interface once
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol_ctrl = cast(interface, POINTER(IAudioEndpointVolume))

            while self._running:
                # Read current volume level
                try:
                    if not self.dragging_vol and (time.time() - self._vol_set_time) > self._COOLDOWN:
                        self.volume_level = vol_ctrl.GetMasterVolumeLevelScalar()
                except Exception:
                    pass

                # Drain any pending set-volume commands (use latest only)
                target = None
                while not self._vol_queue.empty():
                    try:
                        target = self._vol_queue.get_nowait()
                    except queue.Empty:
                        break

                if target is not None:
                    try:
                        vol_ctrl.SetMasterVolumeLevelScalar(target, None)
                    except Exception:
                        pass

                if hasattr(self.island, 'update'):
                    self.island.update()

                # Sleep briefly — fast enough for drag responsiveness
                time.sleep(0.05)

        except Exception:
            pass
        # COM objects are released here while COM is still initialized
        # then we uninitialize
        comtypes.CoUninitialize()

    # ── Brightness Worker ────────────────────────────────────────────
    def _brightness_worker(self):
        """Dedicated thread for brightness reads/writes (no COM needed)."""
        while self._running:
            # Read current brightness
            try:
                if not self.dragging_bright and (time.time() - self._bright_set_time) > self._COOLDOWN:
                    brights = sbc.get_brightness()
                    if brights and len(brights) > 0:
                        self.brightness_level = brights[0] / 100.0
            except Exception:
                pass

            # Drain any pending set-brightness commands (use latest only)
            target = None
            while not self._bright_queue.empty():
                try:
                    target = self._bright_queue.get_nowait()
                except queue.Empty:
                    break

            if target is not None:
                try:
                    sbc.set_brightness(int(target * 100), display=0)
                except Exception:
                    pass

            time.sleep(0.1)

    # ── Public API ───────────────────────────────────────────────────
    def set_system_volume(self, level: float):
        self._vol_set_time = time.time()
        self._vol_queue.put(level)

    def set_system_brightness(self, level: float):
        self._bright_set_time = time.time()
        self._bright_queue.put(level)

    def on_mouse_press(self, x, y, state):
        if state == "mini_player":
            if self.vol_rect.contains(x, y):
                self.dragging_vol = True
                self.update_level_from_mouse(x, True)
            elif self.bright_rect.contains(x, y):
                self.dragging_bright = True
                self.update_level_from_mouse(x, False)

    def on_mouse_move(self, x, y, state):
        if state == "mini_player":
            if self.dragging_vol:
                self.update_level_from_mouse(x, True)
            elif self.dragging_bright:
                self.update_level_from_mouse(x, False)

    def on_mouse_release(self, x, y, state):
        if self.dragging_vol:
            self.dragging_vol = False
        if self.dragging_bright:
            self.dragging_bright = False

    def update_level_from_mouse(self, x: float, is_vol: bool):
        rect = self.vol_rect if is_vol else self.bright_rect
        clamped_x = max(rect.left(), min(x, rect.right()))
        percentage = (clamped_x - rect.left()) / rect.width()

        if is_vol:
            self.volume_level = percentage
            self.set_system_volume(percentage)
        else:
            self.brightness_level = percentage
            self.set_system_brightness(percentage)

        if hasattr(self.island, 'reset_inactivity_timer'):
            self.island.reset_inactivity_timer()

        if hasattr(self.island, 'update'):
            self.island.update()

    # ── Rendering ────────────────────────────────────────────────────
    def paint_idle(self, painter: QPainter, rect: QRect, anim_step: int):
        cx = rect.width() / 2
        cy = rect.height() / 2
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pw, ph = 30, 5
        inset = 1.0
        inner_h = ph - inset * 2
        rad_o = ph / 2
        rad_i = inner_h / 2

        for i, level in enumerate([self.volume_level, self.brightness_level]):
            ty = cy + (i * 11) - 5
            # Housing (dark glass)
            painter.setPen(QPen(QColor(255, 255, 255, 30), 0.5))
            painter.setBrush(QColor(40, 40, 45, 180))
            painter.drawRoundedRect(QRectF(cx - pw/2, ty, pw, ph), rad_o, rad_o)
            # Liquid (slightly lighter dark glass with glow)
            lw = max(inner_h, (pw - inset * 2) * level)
            painter.setPen(QPen(QColor(255, 255, 255, 70), 0.5))
            painter.setBrush(QColor(80, 85, 95, 200))
            painter.drawRoundedRect(QRectF(cx - pw/2 + inset, ty + inset, lw, inner_h), rad_i, rad_i)

    def paint_expanded(self, painter: QPainter, rect: QRect, anim_step: int):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_liquid_glass(painter, self.vol_rect, self.volume_level, True)
        self._draw_liquid_glass(painter, self.bright_rect, self.brightness_level, False)

    def _draw_liquid_glass(self, painter: QPainter, r: QRectF, level: float, is_vol: bool):
        rad = r.height() / 2
        inset = 3.0  # Inner capsule margin from outer edges

        # ════════════════════════════════════════════════════════════
        #  LAYER 1 — OUTER HOUSING
        # ════════════════════════════════════════════════════════════

        # Dark, smooth background
        bg_grad = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        bg_grad.setColorAt(0.0, QColor(45, 45, 50, 180))
        bg_grad.setColorAt(1.0, QColor(25, 25, 30, 180))
        painter.setBrush(QBrush(bg_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(r, rad, rad)

        # Outer border
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1.0))
        painter.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad)

        # ════════════════════════════════════════════════════════════
        #  LAYER 2 — INNER LIQUID CAPSULE
        # ════════════════════════════════════════════════════════════

        inset = 1.5
        inner_h = r.height() - inset * 2
        inner_rad = inner_h / 2
        inner_max_w = r.width() - inset * 2

        if level > 0.005:
            inner_w = max(inner_h, inner_max_w * level)
            ir = QRectF(r.left() + inset, r.top() + inset, inner_w, inner_h)

            # Fill body - dark but slightly lighter than background
            fill_grad = QLinearGradient(ir.left(), ir.top(), ir.left(), ir.bottom())
            fill_grad.setColorAt(0.0, QColor(80, 85, 95, 140))
            fill_grad.setColorAt(1.0, QColor(50, 55, 60, 140))
            painter.setBrush(QBrush(fill_grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(ir, inner_rad, inner_rad)

            # Inner border
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 80), 1.0))
            painter.drawRoundedRect(ir.adjusted(0.5, 0.5, -0.5, -0.5), inner_rad, inner_rad)

            # ════════════════════════════════════════════════════════════
            #  THE GLOW — Soft fluid highlight at the right edge
            # ════════════════════════════════════════════════════════════
            painter.save()
            
            # Clip to inner capsule so glow doesn't spill out
            clip_path = QPainterPath()
            clip_path.addRoundedRect(ir, inner_rad, inner_rad)
            painter.setClipPath(clip_path)

            # Radial glow
            glow_radius = ir.height() * 1.5
            glow_center = QPointF(ir.right() - glow_radius * 0.4, ir.center().y())
            glow_grad = QRadialGradient(glow_center, glow_radius)
            glow_grad.setColorAt(0.0, QColor(220, 235, 255, 220)) # Bright icy center
            glow_grad.setColorAt(0.5, QColor(180, 210, 255, 80))
            glow_grad.setColorAt(1.0, QColor(100, 150, 255, 0))
            
            painter.setBrush(QBrush(glow_grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(ir)

            # Crisp bright line right on the edge of the glow
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(220, 235, 255, 200), 2.0))
            painter.drawRoundedRect(ir.adjusted(1, 1, -1, -1), inner_rad, inner_rad)
            
            painter.restore()

        # ════════════════════════════════════════════════════════════
        #  TOP GLOSS — Unifies the glass
        # ════════════════════════════════════════════════════════════
        painter.save()
        gloss_path = QPainterPath()
        gloss_path.addRoundedRect(r, rad, rad)
        painter.setClipPath(gloss_path)
        
        gloss_h = r.height() * 0.4
        gloss_rect = QRectF(r.left(), r.top(), r.width(), gloss_h)
        gloss_grad = QLinearGradient(r.left(), r.top(), r.left(), r.top() + gloss_h)
        gloss_grad.setColorAt(0.0, QColor(255, 255, 255, 40))
        gloss_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(gloss_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(gloss_rect)
        painter.restore()

        # ════════════════════════════════════════════════════════════
        #  ICON + PERCENTAGE — quiet, never competing
        # ════════════════════════════════════════════════════════════
        icon_s = 14
        lx = r.left() + inset + 12
        iy = r.center().y() - icon_s / 2
        tc = QColor(255, 255, 255, 255) # Pure white to match reference

        painter.setPen(QPen(tc, 1.5, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        if is_vol:
            sp = QPainterPath()
            sp.moveTo(lx + 1, iy + 3.5)
            sp.lineTo(lx + 3.5, iy + 3.5)
            sp.lineTo(lx + 7, iy + 0.5)
            sp.lineTo(lx + 7, iy + 11.5)
            sp.lineTo(lx + 3.5, iy + 8.5)
            sp.lineTo(lx + 1, iy + 8.5)
            sp.closeSubpath()
            painter.setBrush(tc)
            painter.drawPath(sp)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if level > 0.05:
                painter.drawArc(QRectF(lx + 6.5, iy + 3, 4.5, 6), -50 * 16, 100 * 16)
        else:
            scx = lx + icon_s / 2
            scy = r.center().y()
            sr = 2.5
            painter.setBrush(tc)
            painter.drawEllipse(QRectF(scx - sr, scy - sr, sr * 2, sr * 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(8):
                a = i * 45 * (math.pi / 180)
                painter.drawLine(
                    QPoint(int(scx + math.cos(a) * (sr + 1.5)),
                           int(scy + math.sin(a) * (sr + 1.5))),
                    QPoint(int(scx + math.cos(a) * (sr + 3.5)),
                           int(scy + math.sin(a) * (sr + 3.5)))
                )

        pct = int(level * 100)
        f = QFont("Segoe UI", 9)
        f.setWeight(QFont.Weight.Normal)
        painter.setFont(f)
        painter.setPen(tc)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(QRectF(lx + icon_s + 3, r.top(), 28, r.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         str(pct))
