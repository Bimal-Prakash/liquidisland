import asyncio
import threading
import ctypes
from ctypes import wintypes
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QLinearGradient, QBrush, QPainterPath
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QRect, QRectF, Qt
from core.module import BaseModule

class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', wintypes.BYTE),
        ('BatteryFlag', wintypes.BYTE),
        ('BatteryLifePercent', wintypes.BYTE),
        ('SystemStatusFlag', wintypes.BYTE),
        ('BatteryLifeTime', wintypes.DWORD),
        ('BatteryFullLifeTime', wintypes.DWORD),
    ]

class BatteryModule(BaseModule):
    def __init__(self, island):
        super().__init__(island)
        self.is_cycleable = True
        self.percent = 100
        self.is_charging = False
        self._running = False
        
    @property
    def priority(self) -> int:
        return 1

    def is_active(self) -> bool:
        return True

    def get_idle_size(self):
        return (200, 48)

    def get_expanded_size(self):
        return (440, 180)

    def get_accent_color(self) -> QColor:
        if self.is_charging or self.percent > 50:
            return QColor(52, 199, 89)
        elif self.percent >= 20:
            return QColor(255, 204, 0)
        else:
            return QColor(255, 59, 48)

    def on_start(self):
        self._running = True
        self.poll_thread = threading.Thread(target=self.start_poller, daemon=True)
        self.poll_thread.start()

    def on_stop(self):
        self._running = False

    def on_tick(self, anim_step):
        pass

    def start_poller(self):
        asyncio.run(self.poll_battery())
        
    async def poll_battery(self):
        prev_charging = None
        while self._running:
            try:
                status = SYSTEM_POWER_STATUS()
                if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                    p = status.BatteryLifePercent
                    if p != 255:
                        self.percent = max(0, min(100, int(p)))
                    charging = (status.ACLineStatus == 1)
                    if prev_charging is not None and not prev_charging and charging:
                        if hasattr(self.island, 'popup_requested_signal'):
                            self.island.popup_requested_signal.emit(self, 3000)
                    self.is_charging = charging
                    prev_charging = charging

                try:
                    # pyrefly: ignore [missing-import]
                    import winsdk.windows.system.power as winpower
                    if not getattr(self, 'user_override_saver', False):
                        self.energy_saver_on = (int(winpower.PowerManager.energy_saver_status) != 0)
                except Exception:
                    pass
            except Exception:
                pass
            await asyncio.sleep(2)

    def draw_thick_battery(self, painter: QPainter, center_x: float, center_y: float, size: float):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bw = size * 0.75  # Outer battery body width
        bh = size * 0.42  # Outer battery body height
        cw = size * 0.07  # Terminal cap width
        ch = size * 0.20  # Terminal cap height
        r  = size * 0.08  # Corner radius
        pw = size * 0.08  # Glass stroke width

        body_rect = QRectF(center_x - bw/2, center_y - bh/2, bw, bh)
        body_path = QPainterPath()
        body_path.addRoundedRect(body_rect, r, r)

        cap_rect = QRectF(center_x + bw/2 + size*0.02, center_y - ch/2, cw, ch)
        cap_path = QPainterPath()
        cap_path.addRoundedRect(cap_rect, size*0.03, size*0.03)

        top_y = center_y - bh/2
        bottom_y = center_y + bh/2

        # 1. Semi-transparent glass base (White outline + cap)
        painter.setPen(QPen(QColor(255, 255, 255, 110), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(body_path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 110))
        painter.drawPath(cap_path)

        # Soft inner shadow (Simulated with slight dark offset)
        painter.setPen(QPen(QColor(0, 0, 0, 30), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(0, 1)
        painter.drawPath(body_path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 30))
        painter.drawPath(cap_path)
        painter.translate(0, -1)

        # 2. Fill Pill (Color coded based on battery health/charging/energy saver)
        padding = pw * 0.7
        avail_w = bw - (2 * padding)
        fill_w = max(0.0, avail_w * (self.percent / 100.0))
        fill_h = bh - (2 * padding)
        
        if fill_w > 1.0:
            fill_rect = QRectF(center_x - bw/2 + padding, center_y - bh/2 + padding, fill_w, fill_h)
            fill_r = max(2.0, r - padding)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, fill_r, fill_r)

            # Determine color: Healthy (Green), Energy Saver / Moderate (Yellow), Low (Red)
            if self.is_charging or (self.percent > 50 and not getattr(self, 'energy_saver_on', False)):
                fill_color = QColor(52, 199, 89)   # iOS Green #34C759
            elif getattr(self, 'energy_saver_on', False) or self.percent >= 20:
                fill_color = QColor(255, 204, 0)   # iOS Yellow #FFCC00
            else:
                fill_color = QColor(255, 59, 48)    # iOS Red #FF3B30

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill_color)
            painter.drawPath(fill_path)

        # 3. Charging Lightning Bolt Overlay (Centered in the middle of the battery colored space)
        if self.is_charging:
            bs = size * 0.28
            bx, by = center_x, center_y
            bolt = QPainterPath()
            bolt.moveTo(bx + bs*0.05, by - bs*0.5)
            bolt.lineTo(bx - bs*0.25, by + bs*0.05)
            bolt.lineTo(bx - bs*0.02, by + bs*0.05)
            bolt.lineTo(bx - bs*0.08, by + bs*0.5)
            bolt.lineTo(bx + bs*0.25, by - bs*0.05)
            bolt.lineTo(bx + bs*0.02, by - bs*0.05)
            bolt.closeSubpath()

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 240))
            painter.drawPath(bolt)

        # 4. Glass Surface Reflection
        refl_grad = QLinearGradient(center_x, top_y, center_x, bottom_y)
        refl_grad.setColorAt(0, QColor(255, 255, 255, 120))
        refl_grad.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(refl_grad), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(body_path)

        # 5. Thin edge highlight
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(0, -1)
        painter.drawPath(body_path)
        painter.translate(0, 1)

    def paint_idle(self, painter: QPainter, rect: QRect, anim_step: int):
        self.draw_thick_battery(painter, rect.width() / 2, rect.height() / 2, 26)

    def paint_expanded(self, painter: QPainter, rect: QRect, anim_step: int):
        self.draw_thick_battery(painter, rect.width() / 2, 70, 70)
        
        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        
        if self.is_charging:
            status = f"{self.percent}% • Charging"
        elif getattr(self, 'energy_saver_on', False):
            status = f"{self.percent}% • Energy Saver ON"
        elif self.percent < 20:
            status = f"{self.percent}% • Low Power"
        else:
            status = f"{self.percent}%"
            
        text_rect = QRect(20, 125, rect.width() - 40, 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, status)

    def on_mouse_press(self, x: int, y: int, state: str):
        if state == "mini_player":
            threading.Thread(target=self.toggle_energy_saver_sync, daemon=True).start()

    def on_double_click(self, x, y, state):
        threading.Thread(target=self.toggle_energy_saver_sync, daemon=True).start()

    def toggle_energy_saver_sync(self):
        try:
            import subprocess
            import re
            
            NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            saver_overlay = '961cc777-2547-4f9d-8174-7d86181b8a7a'
            off_overlay = '381b4222-f694-41f0-9685-ff5bb260df2e'

            new_state = not getattr(self, 'energy_saver_on', False)
            self.energy_saver_on = new_state
            self.user_override_saver = True

            if new_state:
                # 1. Dim brightness to 30% to conserve display power
                try:
                    # pyrefly: ignore [missing-import]
                    import screen_brightness_control as sbc
                    cb = sbc.get_brightness()
                    if cb:
                        self._prev_brightness = cb[0]
                    sbc.set_brightness(30)
                except Exception:
                    pass

                # 2. Cap CPU Max State to 50% (System Processor Power Management)
                try:
                    subprocess.run(['powercfg', '/setdcvalueindex', 'SCHEME_CURRENT', 'SUB_PROCESSOR', 'PROCTHROTTLEMAX', '50'], capture_output=True, creationflags=NO_WINDOW)
                    subprocess.run(['powercfg', '/setacvalueindex', 'SCHEME_CURRENT', 'SUB_PROCESSOR', 'PROCTHROTTLEMAX', '50'], capture_output=True, creationflags=NO_WINDOW)
                except Exception:
                    pass

                # 3. System Power Scheme Overlay (Better Battery-life)
                try:
                    activescheme = subprocess.check_output(['powercfg', '/getactivescheme'], text=True, errors='ignore', creationflags=NO_WINDOW)
                    match = re.search(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})', activescheme)
                    if match and match.group(1).lower() != saver_overlay:
                        self._prev_power_scheme = match.group(1)
                except Exception:
                    pass

                subprocess.run(['powercfg', '/setactive', saver_overlay], capture_output=True, creationflags=NO_WINDOW)
            else:
                # 1. Restore screen brightness
                try:
                    # pyrefly: ignore [missing-import]
                    import screen_brightness_control as sbc
                    target_b = getattr(self, '_prev_brightness', 80)
                    sbc.set_brightness(target_b)
                except Exception:
                    pass

                # 2. Restore 100% CPU Max State (Full Processor Performance)
                try:
                    subprocess.run(['powercfg', '/setdcvalueindex', 'SCHEME_CURRENT', 'SUB_PROCESSOR', 'PROCTHROTTLEMAX', '100'], capture_output=True, creationflags=NO_WINDOW)
                    subprocess.run(['powercfg', '/setacvalueindex', 'SCHEME_CURRENT', 'SUB_PROCESSOR', 'PROCTHROTTLEMAX', '100'], capture_output=True, creationflags=NO_WINDOW)
                except Exception:
                    pass

                # 3. Restore active power scheme
                target_plan = getattr(self, '_prev_power_scheme', off_overlay)
                subprocess.run(['powercfg', '/setactive', target_plan], capture_output=True, creationflags=NO_WINDOW)

            if hasattr(self.island, 'update'):
                self.island.update()
        except Exception:
            pass
