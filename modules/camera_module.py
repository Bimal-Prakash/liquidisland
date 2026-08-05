import winreg
import asyncio
import threading
import subprocess
import ctypes
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath, QLinearGradient
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QRect, QRectF, Qt
from core.module import BaseModule

class CameraModule(BaseModule):
    """
    Camera module for LiquidIsland.
    Detects active webcam usage on Windows, launches Camera app on click,
    or takes a photo when camera is active.
    """
    def __init__(self, island):
        super().__init__(island)
        self.is_cycleable = True
        self.is_camera_in_use = False
        self._running = False

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
        # Using a highly saturated, neon green for the active indicator
        return QColor(0, 255, 64) if self.is_camera_in_use else QColor(255, 255, 255)

    def on_start(self):
        self._running = True
        self.poll_thread = threading.Thread(target=self.start_poller, daemon=True)
        self.poll_thread.start()

    def on_stop(self):
        self._running = False

    def start_poller(self):
        asyncio.run(self.poll_camera())

    async def poll_camera(self):
        prev_state = False
        while self._running:
            try:
                active = self.check_webcam_active()
                if not prev_state and active:
                    if hasattr(self.island, 'popup_requested_signal'):
                        self.island.popup_requested_signal.emit(self, 3000)
                self.is_camera_in_use = active
                prev_state = active
            except Exception:
                pass
            await asyncio.sleep(1)

    def check_webcam_active(self) -> bool:
        base_path = r'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam'
        try:
            root_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_path)
            subkeys = []
            i = 0
            while True:
                try:
                    subkeys.append(winreg.EnumKey(root_key, i))
                    i += 1
                except OSError:
                    break

            for sk in subkeys:
                target_path = f'{base_path}\\{sk}'
                if sk == 'NonPackaged':
                    try:
                        np_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, target_path)
                        j = 0
                        while True:
                            try:
                                app_name = winreg.EnumKey(np_key, j)
                                app_path = f'{target_path}\\{app_name}'
                                app_k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, app_path)
                                try:
                                    t_start, _ = winreg.QueryValueEx(app_k, 'LastUsedTimeStart')
                                    t_stop, _ = winreg.QueryValueEx(app_k, 'LastUsedTimeStop')
                                    if t_start > 0 and t_stop == 0:
                                        return True
                                except Exception: pass
                                j += 1
                            except OSError:
                                break
                    except Exception: pass
                else:
                    try:
                        app_k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, target_path)
                        try:
                            t_start, _ = winreg.QueryValueEx(app_k, 'LastUsedTimeStart')
                            t_stop, _ = winreg.QueryValueEx(app_k, 'LastUsedTimeStop')
                            if t_start > 0 and t_stop == 0:
                                return True
                        except Exception: pass
                    except Exception: pass
            return False
        except Exception:
            return False

    def on_mouse_press(self, x, y, state):
        if state == "mini_player":
            button_rect = QRect((440 - 80) // 2, 30, 80, 80)
            if button_rect.contains(int(x), int(y)):
                if self.is_camera_in_use:
                    self.take_photo_action()
                else:
                    self.launch_camera_app()
        elif state == "idle":
            if self.is_camera_in_use:
                self.take_photo_action()
            else:
                self.launch_camera_app()

    def launch_camera_app(self):
        try:
            subprocess.Popen("start microsoft.windows.camera:", shell=True)
        except Exception:
            pass

    def take_photo_action(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = None
            
            def enum_windows_callback(h, extra):
                nonlocal hwnd
                if not user32.IsWindowVisible(h):
                    return True
                length = user32.GetWindowTextLengthW(h)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(h, buff, length + 1)
                    title = buff.value
                    title_lower = title.lower()

                    # Ignore code editors, terminals, IDEs, or Python files
                    if any(ignored in title_lower for ignored in ['.py', 'visual studio', 'code', 'antigravity', 'pycharm', 'terminal', 'cmd', 'powershell', 'sublime', 'idea']):
                        return True

                    if title == "Camera" or title == "Windows Camera":
                        hwnd = h
                        return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

            if hwnd:
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)

                # Trigger shutter keypress (VK_SPACE = 0x20)
                user32.keybd_event(0x20, 0, 0, 0)
                user32.keybd_event(0x20, 0, 0x0002, 0)
            else:
                self.launch_camera_app()
        except Exception:
            pass

    def draw_thick_camera(self, painter: QPainter, center_x: float, center_y: float, size: float):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cw = size * 0.75   # Camera body width
        ch = size * 0.50   # Camera body height
        r  = size * 0.12   # Corner radius
        pw = size * 0.08   # Outline stroke width

        # Bump/flash top bump
        bw = size * 0.28
        bh = size * 0.12
        bump_rect = QRectF(center_x - bw/2, center_y - ch/2 - bh + pw*0.5, bw, bh)
        bump_path = QPainterPath()
        bump_path.addRoundedRect(bump_rect, size*0.04, size*0.04)

        # Body rect
        body_rect = QRectF(center_x - cw/2, center_y - ch/2, cw, ch)
        body_path = QPainterPath()
        body_path.addRoundedRect(body_rect, r, r)

        top_y = center_y - ch/2
        bottom_y = center_y + bh/2

        # 1. Semi-transparent glass base
        painter.setPen(QPen(QColor(255, 255, 255, 110), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(body_path)
        painter.setBrush(QColor(255, 255, 255, 110))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(bump_path)

        # Soft inner shadow
        painter.setPen(QPen(QColor(0, 0, 0, 30), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(0, 1)
        painter.drawPath(body_path)
        painter.translate(0, -1)

        # 2. Outer Lens ring
        lens_r = size * 0.22
        painter.setPen(QPen(QColor(255, 255, 255, 180), pw * 0.8, Qt.PenStyle.SolidLine))
        painter.setBrush(QColor(255, 255, 255, 60))
        painter.drawEllipse(QRectF(center_x - lens_r, center_y - lens_r, lens_r*2, lens_r*2))

        # Inner Lens pupil
        pupil_r = size * 0.10
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 240))
        painter.drawEllipse(QRectF(center_x - pupil_r, center_y - pupil_r, pupil_r*2, pupil_r*2))

        # Flash dot (top right)
        flash_r = size * 0.04
        flash_x = center_x + cw/2 - size*0.14
        flash_y = center_y - ch/2 + size*0.12
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.drawEllipse(QRectF(flash_x - flash_r, flash_y - flash_r, flash_r*2, flash_r*2))

        # 3. Reflections
        refl_grad = QLinearGradient(center_x, top_y, center_x, bottom_y)
        refl_grad.setColorAt(0, QColor(255, 255, 255, 120))
        refl_grad.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(refl_grad), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(body_path)

        # 4. Thin edge highlight
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.translate(0, -1)
        painter.drawPath(body_path)
        painter.translate(0, 1)

    def paint_idle(self, painter: QPainter, rect: QRect, anim_step: int):
        self.draw_thick_camera(painter, rect.width() / 2, rect.height() / 2, 26)

    def paint_expanded(self, painter: QPainter, rect: QRect, anim_step: int):
        self.draw_thick_camera(painter, rect.width() / 2, 70, 70)

        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))

        status = "Camera Active" if self.is_camera_in_use else "Camera"
        text_rect = QRect(20, 125, rect.width() - 40, 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, status)
