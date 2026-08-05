import asyncio
import threading
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QLinearGradient, QBrush
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QRect, QRectF, Qt
from core.module import BaseModule

class BluetoothModule(BaseModule):
    def __init__(self, island):
        super().__init__(island)
        self.is_cycleable = True
        self.device_name = "Not Connected"
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
        asyncio.run(self.poll_bluetooth())
        
    async def poll_bluetooth(self):
        try:
            import ctypes
            try:
                ctypes.windll.combase.RoInitialize(1)
            except Exception:
                pass
            # pyrefly: ignore [missing-import]
            from winsdk.windows.devices.radios import Radio, RadioKind, RadioState
        except ImportError:
            return
            
        import time
        while self._running:
            try:
                radios = await Radio.get_radios_async()
                bt_radio = next((r for r in radios if r.kind == RadioKind.BLUETOOTH), None)
                if bt_radio:
                    real_on = (bt_radio.state == RadioState.ON)
                    if time.time() - getattr(self, 'last_toggle_time', 0) > 2.0:
                        self.is_on = real_on
                        
                # Actually getting connected BT devices is complex in pure python without extra libs.
                # For now we'll just show On/Off.
                self.connected = self.is_on
                self.device_name = "Bluetooth"
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
                threading.Thread(target=self.toggle_bluetooth_sync, daemon=True).start()
        
    def toggle_bluetooth_sync(self):
        asyncio.run(self.toggle_bluetooth_async())
        
    async def toggle_bluetooth_async(self):
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
                if r.kind == RadioKind.BLUETOOTH:
                    state = RadioState.OFF if r.state == RadioState.ON else RadioState.ON
                    await r.set_state_async(state)
        except Exception:
            pass

    def draw_thick_bluetooth(self, painter: QPainter, center_x: float, center_y: float, size: float, glow_intensity: float):
        # pyrefly: ignore [missing-import]
        from PyQt6.QtGui import QPainterPath
        pw = size * 0.10
        
        # Windows 11 Bluetooth rune geometry
        # The glyph is: UL → LR → B → T → UR → LL (continuous stroke)
        #
        #        T (stem top)
        #       /|
        #      / |   ← upper arrow (UR tip)
        #  UL/  |
        #     \ |
        #      \|   ← lower arrow (LR tip)
        #       \
        #        B (stem bottom)
        #
        half_h  = size * 0.44   # Half stem height (~8% shorter)
        notch_y = half_h * 0.52 # Arrow tips closer to center (~10% shorter triangles)
        tip_x   = notch_y * 1.12 # Slightly wider than tall (steeper, more compact angles)
        cross_x = tip_x         # Left cross lines mirror the right tips
        cy = center_y + size * 0.01  # Nudge visual center down slightly
        
        # 6 key points of the Bluetooth rune
        ul = (center_x - cross_x, cy - notch_y)  # Upper-left cross end
        lr = (center_x + tip_x,   cy + notch_y)  # Lower-right arrow tip
        b  = (center_x,           cy + half_h)    # Stem bottom
        t  = (center_x,           cy - half_h)    # Stem top
        ur = (center_x + tip_x,   cy - notch_y)  # Upper-right arrow tip
        ll = (center_x - cross_x, cy + notch_y)  # Lower-left cross end
        
        path = QPainterPath()
        path.moveTo(*ul)
        path.lineTo(*lr)
        path.lineTo(*b)
        path.lineTo(*t)
        path.lineTo(*ur)
        path.lineTo(*ll)

        top_y = t[1]
        bottom_y = b[1]

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Semi-transparent glass base
        painter.setPen(QPen(QColor(255, 255, 255, 110), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        # Soft inner shadow (simulated with a slight dark offset)
        painter.setPen(QPen(QColor(0, 0, 0, 30), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.translate(0, 1)
        painter.drawPath(path)
        painter.translate(0, -1)

        # 2. INTERNAL GLOW (Additive warm white light)
        if glow_intensity > 0.001:
            ratio = glow_intensity / 0.5
            glow_alpha = int(115 * ratio) # 45% opacity max
            
            painter.save()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            
            # Warm white #FAFAFA
            painter.setPen(QPen(QColor(250, 250, 250, glow_alpha), pw * 0.75, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(path)
            
            painter.restore()

        # 3. Reflections (Very subtle white highlight gradient)
        refl_grad = QLinearGradient(center_x, top_y, center_x, bottom_y)
        refl_grad.setColorAt(0, QColor(255, 255, 255, 120))
        refl_grad.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(refl_grad), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)

        # 4. Thin edge highlight
        # Drawn 1px offset up to catch the top edge
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.translate(0, -1)
        painter.drawPath(path)
        painter.translate(0, 1)

    def paint_idle(self, painter: QPainter, rect: QRect, anim_step: int):
        self.draw_thick_bluetooth(painter, rect.width() / 2, rect.height() / 2, 26, self.glow_intensity)

    def paint_expanded(self, painter: QPainter, rect: QRect, anim_step: int):
        # Draw custom thick icon in the center
        self.draw_thick_bluetooth(painter, rect.width() / 2, 70, 70, self.glow_intensity)
        
        # Draw connected text below the button
        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        status = self.device_name if self.connected and self.is_on else ("Not Connected" if self.is_on else "Off")
        text_rect = QRect(20, 125, rect.width() - 40, 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, status)
