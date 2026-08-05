import asyncio
import threading
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QLinearGradient, QBrush
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QRect, QRectF, Qt
from core.module import BaseModule

class WifiModule(BaseModule):
    def __init__(self, island):
        super().__init__(island)
        self.is_cycleable = True
        self.ssid = "Not Connected"
        self.connected = False
        self.is_on = True
        self.last_toggle_time = 0
        self._running = False
        self.glow_intensity = 0.5
        self.glow_progress = 1.0
        self.last_time = 0
        
    @property
    def priority(self) -> int:
        return 1

    def is_active(self) -> bool:
        return True

    def get_idle_size(self):
        return (160, 48)

    def get_expanded_size(self):
        return (440, 180)

    def get_accent_color(self) -> QColor:
        return QColor(0, 120, 215) if self.is_on else QColor(100, 100, 100)

    def on_start(self):
        self._running = True
        self.poll_thread = threading.Thread(target=self.start_poller, daemon=True)
        self.poll_thread.start()

    def on_stop(self):
        self._running = False

    def on_tick(self, anim_step):
        import time
        now = time.time()
        if getattr(self, 'last_time', 0) == 0:
            self.last_time = now
            return
        dt = now - self.last_time
        self.last_time = now
        
        if not hasattr(self, 'glow_progress'):
            self.glow_progress = 1.0 if self.is_on else 0.0

        target_progress = 1.0 if self.is_on else 0.0
        speed = 1.0 / 0.25 # 250ms transition
        
        if self.glow_progress < target_progress:
            self.glow_progress = min(1.0, self.glow_progress + dt * speed)
        elif self.glow_progress > target_progress:
            self.glow_progress = max(0.0, self.glow_progress - dt * speed)
            
        # OutCubic easing: 1 - (1-t)^3
        t = self.glow_progress
        ease_t = 1.0 - pow(1.0 - t, 3)
        
        self.glow_intensity = ease_t * 0.5

    def start_poller(self):
        asyncio.run(self.poll_wifi())
        
    async def poll_wifi(self):
        try:
            import ctypes
            try:
                ctypes.windll.combase.RoInitialize(1)
            except Exception:
                pass
            # pyrefly: ignore [missing-import]
            from winsdk.windows.networking.connectivity import NetworkInformation
            # pyrefly: ignore [missing-import]
            from winsdk.windows.devices.radios import Radio, RadioKind, RadioState
        except ImportError:
            return
            
        import time
        while self._running:
            try:
                radios = await Radio.get_radios_async()
                wifi_radio = next((r for r in radios if r.kind == RadioKind.WI_FI), None)
                if wifi_radio:
                    real_on = (wifi_radio.state == RadioState.ON)
                    if time.time() - getattr(self, 'last_toggle_time', 0) > 2.0:
                        self.is_on = real_on
                        
                profile = NetworkInformation.get_internet_connection_profile()
                if profile and profile.is_wlan_connection_profile:
                    self.ssid = profile.profile_name
                    self.connected = True
                else:
                    self.ssid = "Not Connected"
                    self.connected = False
            except Exception:
                pass
            await asyncio.sleep(2)
            
    def on_mouse_press(self, x, y, state):
        if state == "mini_player":
            button_rect = QRect((440 - 80) // 2, 30, 80, 80)
            if button_rect.contains(int(x), int(y)):
                import time
                self.is_on = not self.is_on
                self.last_toggle_time = time.time()
                threading.Thread(target=self.toggle_wifi_sync, daemon=True).start()
        
    def toggle_wifi_sync(self):
        asyncio.run(self.toggle_wifi_async())
        
    async def toggle_wifi_async(self):
        try:
            import ctypes
            try:
                ctypes.windll.combase.RoInitialize(1)
            except Exception:
                pass
            # pyrefly: ignore [missing-import]
            from winsdk.windows.devices.radios import Radio, RadioKind, RadioState
            radios = await Radio.get_radios_async()
            for r in radios:
                if r.kind == RadioKind.WI_FI:
                    state = RadioState.OFF if r.state == RadioState.ON else RadioState.ON
                    await r.set_state_async(state)
        except Exception:
            pass

    def draw_thick_wifi(self, painter: QPainter, center_x: float, center_y: float, size: float, glow_intensity: float):
        pw = size * 0.12
        start_angle = 45 * 16
        span_angle = 90 * 16
        dot_cy = center_y + size * 0.3
        
        r1 = size * 1.2
        r2 = size * 0.8
        r3 = size * 0.4
        dot_r = size * 0.18

        top_y = dot_cy - r1/2
        bottom_y = dot_cy + dot_r/2

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Semi-transparent glass base
        painter.setPen(QPen(QColor(255, 255, 255, 110), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for r in [r1, r2, r3]:
            painter.drawArc(QRectF(center_x - r/2, dot_cy - r/2, r, r), start_angle, span_angle)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 110))
        painter.drawEllipse(QRectF(center_x - dot_r/2, dot_cy - dot_r/2, dot_r, dot_r))

        # Soft inner shadow (simulated with a slight dark offset)
        painter.setPen(QPen(QColor(0, 0, 0, 30), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(0, 1)
        for r in [r1, r2, r3]:
            painter.drawArc(QRectF(center_x - r/2, dot_cy - r/2, r, r), start_angle, span_angle)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 30))
        painter.drawEllipse(QRectF(center_x - dot_r/2, dot_cy - dot_r/2, dot_r, dot_r))
        painter.translate(0, -1)

        # 2. INTERNAL GLOW (Additive warm white light)
        if glow_intensity > 0.001:
            ratio = glow_intensity / 0.5
            glow_alpha = int(115 * ratio) # 45% opacity max
            
            painter.save()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            
            # Warm white #FAFAFA
            painter.setPen(QPen(QColor(250, 250, 250, glow_alpha), pw * 0.75, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for r in [r1, r2, r3]:
                painter.drawArc(QRectF(center_x - r/2, dot_cy - r/2, r, r), start_angle, span_angle)
                
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(250, 250, 250, glow_alpha))
            w_dot = dot_r * 0.75
            painter.drawEllipse(QRectF(center_x - w_dot/2, dot_cy - w_dot/2, w_dot, w_dot))
            
            painter.restore()

        # 3. Reflections (Very subtle white highlight gradient)
        refl_grad = QLinearGradient(center_x, top_y, center_x, bottom_y)
        refl_grad.setColorAt(0, QColor(255, 255, 255, 120))
        refl_grad.setColorAt(1, QColor(255, 255, 255, 0))
        
        painter.setPen(QPen(QBrush(refl_grad), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for r in [r1, r2, r3]:
            painter.drawArc(QRectF(center_x - r/2, dot_cy - r/2, r, r), start_angle, span_angle)
            
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(refl_grad))
        painter.drawEllipse(QRectF(center_x - dot_r/2, dot_cy - dot_r/2, dot_r, dot_r))

        # 4. Thin edge highlight
        # Drawn 1px offset up to catch the top edge
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(0, -1)
        for r in [r1, r2, r3]:
            painter.drawArc(QRectF(center_x - r/2, dot_cy - r/2, r, r), start_angle, span_angle)
        painter.translate(0, 1)

    def paint_idle(self, painter: QPainter, rect: QRect, anim_step: int):
        self.draw_thick_wifi(painter, rect.width() / 2, rect.height() / 2, 26, self.glow_intensity)

    def paint_expanded(self, painter: QPainter, rect: QRect, anim_step: int):
        # Draw custom thick icon in the center
        self.draw_thick_wifi(painter, rect.width() / 2, 70, 70, self.glow_intensity)
        
        # Draw connected text below the button
        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        status = self.ssid if self.connected and self.is_on else ("Not Connected" if self.is_on else "Off")
        text_rect = QRect(20, 125, rect.width() - 40, 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, status)
