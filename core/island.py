import os
import sys
import winreg
import ctypes
from typing import List, Optional
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import QApplication, QWidget
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QRect, QRectF, QPoint, QEasingCurve
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QCursor

class LiquidIsland(QWidget):
    state_changed_signal = pyqtSignal(str)
    popup_requested_signal = pyqtSignal(object, int)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("LiquidIsland")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.current_state = "idle"
        self.height_ = 48
        
        self.modules = []
        self.cycle_list = [None]
        self.current_slot = 0
        self.active_module = None
        
        # pyrefly: ignore [missing-import]
        from PyQt6.QtCore import QSettings
        self.scroll_sensitivity = int(QSettings("LiquidIsland", "Settings").value("scroll_sensitivity", 37))
        
        # Initial geometry
        screen = QApplication.primaryScreen().geometry()
        self.center_x = screen.width() // 2
        self.y_pos = 10
        self.setGeometry(self.center_x - 60, self.y_pos, 120, self.height_)

        # Animation state
        self.anim_step = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)
        
        self.state_changed_signal.connect(self.animate_state_change)
        self.popup_requested_signal.connect(self.show_module_popup)
        
        self.accent_color = QColor(0, 255, 204)
        self.update_system_accent_color()

    def show_module_popup(self, module, duration_ms: int = 3000):
        if hasattr(self, 'cycle_list') and module in self.cycle_list:
            self.current_slot = self.cycle_list.index(module)
        self.active_module = module
        self.state_changed_signal.emit("mini_player")
        
        if not hasattr(self, 'popup_timer'):
            self.popup_timer = QTimer(self)
            self.popup_timer.setSingleShot(True)
            self.popup_timer.timeout.connect(self._on_popup_timeout)
        else:
            self.popup_timer.stop()
            
        self.popup_timer.start(duration_ms)

    def _on_popup_timeout(self):
        if self.current_state == "mini_player":
            self.state_changed_signal.emit("idle")


    def register_module(self, module_class):
        mod = module_class(self)
        self.modules.append(mod)
        self.modules.sort(key=lambda m: m.priority, reverse=True)
        self.rebuild_cycle_list()
        mod.on_start()

    def rebuild_cycle_list(self):
        self.cycle_list = [None]
        for m in self.modules:
            if getattr(m, 'is_cycleable', False):
                self.cycle_list.append(m)

    def get_active_module(self):
        if getattr(self, 'current_slot', 0) > 0 and self.current_slot < len(self.cycle_list):
            return self.cycle_list[self.current_slot]
            
        for mod in self.modules:
            if not getattr(mod, 'is_cycleable', False) and mod.is_active():
                return mod
                
        return self.modules[-1] if self.modules else None

    def enable_windows_acrylic(self):
        try:
            from ctypes import c_int, Structure, POINTER, pointer
            class ACCENTPOLICY(Structure):
                _fields_ = [("AccentState", c_int), ("AccentFlags", c_int), ("GradientColor", c_int), ("AnimationId", c_int)]
            class WINDOWCOMPOSITIONATTRIBDATA(Structure):
                _fields_ = [("Attribute", c_int), ("Data", POINTER(ACCENTPOLICY)), ("SizeOfData", c_int)]
            
            hwnd = int(self.winId())
            accent = ACCENTPOLICY()
            accent.AccentState = 3 # ACCENT_ENABLE_BLURBEHIND
            accent.GradientColor = 0x01000000
            
            data = WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = 19
            data.Data = pointer(accent)
            data.SizeOfData = ctypes.sizeof(accent)
            
            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, pointer(data))
        except Exception:
            pass

    def update_system_accent_color(self):
        try:
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\DWM")
            value, _ = winreg.QueryValueEx(key, "ColorizationColor")
            r = (value >> 16) & 0xFF
            g = (value >> 8) & 0xFF
            b = value & 0xFF
            self.accent_color = QColor(r, g, b)
        except Exception:
            pass

    def update_animation(self):
        import time
        self.anim_step += 1
        
        if self.anim_step % 50 == 0:
            self.update_system_accent_color()
            
        new_active = self.get_active_module()
        if new_active != self.active_module:
            self.active_module = new_active
            self.animate_state_change(self.current_state)
            
        if self.active_module and hasattr(self.active_module, 'on_tick'):
            self.active_module.on_tick(self.anim_step)
            
        # Global click detection for dismissal
        if self.current_state == "mini_player":
            state = ctypes.windll.user32.GetAsyncKeyState(0x01)
            if state & 0x8000:
                cursor_pos = QCursor.pos()
                if not self.geometry().contains(cursor_pos):
                    self.state_changed_signal.emit("idle")
                    
        self.update()

    def animate_state_change(self, new_state):
        if new_state == "ready":
            QTimer.singleShot(300, self.show)
            new_state = "idle"
            
        if new_state == "idle":
            self.current_slot = 0
            if hasattr(self, 'cycle_list'):
                self.active_module = self.get_active_module()
            
        self.current_state = new_state
        
        if not self.active_module:
            return

        if new_state == "idle":
            target_width, target_height = self.active_module.get_idle_size()
        else: # mini_player
            target_width, target_height = self.active_module.get_expanded_size()
            
        screen_geo = self.screen().availableGeometry()
        target_x = max(screen_geo.left(), min(self.center_x - (target_width // 2), screen_geo.right() - target_width + 1))
        target_y = max(screen_geo.top(), min(self.y_pos, screen_geo.bottom() - target_height + 1))
        
        self.geom_anim = QPropertyAnimation(self, b"geometry")
        self.geom_anim.setDuration(250)
        self.geom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.geom_anim.setStartValue(self.geometry())
        self.geom_anim.setEndValue(QRect(target_x, target_y, target_width, target_height))
        self.geom_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        radius = min(rect.width(), rect.height()) // 2
        
        # Liquid Background
        bg_gradient = QLinearGradient(0, 0, 0, rect.height())
        bg_gradient.setColorAt(0.0, QColor(20, 20, 25, 80))
        bg_gradient.setColorAt(1.0, QColor(0, 0, 5, 140))
        painter.setBrush(QBrush(bg_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, radius, radius)
        
        gloss_gradient = QLinearGradient(0, 0, 0, rect.height())
        gloss_gradient.setColorAt(0.0, QColor(255, 255, 255, 90))
        gloss_gradient.setColorAt(0.3, QColor(255, 255, 255, 15))
        gloss_gradient.setColorAt(0.4, QColor(255, 255, 255, 0))
        gloss_gradient.setColorAt(0.8, QColor(255, 255, 255, 0))
        gloss_gradient.setColorAt(1.0, QColor(255, 255, 255, 50))
        painter.setBrush(QBrush(gloss_gradient))
        painter.drawRoundedRect(rect, radius, radius)
        
        pen_gradient = QLinearGradient(0, 0, 0, rect.height())
        pen_gradient.setColorAt(0.0, QColor(255, 255, 255, 180))
        pen_gradient.setColorAt(0.5, QColor(255, 255, 255, 40))
        pen_gradient.setColorAt(1.0, QColor(255, 255, 255, 100))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QBrush(pen_gradient), 1.5))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
        
        if self.active_module:
            if self.current_state == "idle":
                self.active_module.paint_idle(painter, rect, self.anim_step)
            else:
                self.active_module.paint_expanded(painter, rect, self.anim_step)

        # Draw iOS Green Camera Privacy Dot Indicator if camera is active
        if self.is_camera_active():
            dot_r = 4.0
            if self.current_state == "idle":
                # Occupies the exact slot of the idle equalizer
                dot_cx = rect.width() - 28
                dot_cy = rect.height() / 2
            else:
                # Occupies the exact slot of the expanded equalizer
                dot_cx = rect.width() - 70
                dot_cy = 40
            
            # Outer glow
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(52, 199, 89, 90))
            painter.drawEllipse(QRectF(dot_cx - dot_r*1.6, dot_cy - dot_r*1.6, dot_r*3.2, dot_r*3.2))
            
            # Inner solid dot
            painter.setBrush(QColor(52, 199, 89, 255))
            painter.drawEllipse(QRectF(dot_cx - dot_r, dot_cy - dot_r, dot_r*2, dot_r*2))

    def is_camera_active(self) -> bool:
        for mod in self.modules:
            if getattr(mod, 'is_camera_in_use', False):
                return True
        return False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())
            return
            
        self.oldPos = event.globalPosition().toPoint()
        self._pressed_pos = event.position().toPoint()
        self.is_dragging = False
        
        if self.current_state == "mini_player":
            if self.active_module:
                self.active_module.on_mouse_press(event.position().x(), event.position().y(), self.current_state)

    def mouseMoveEvent(self, event):
        if hasattr(self, 'geom_anim') and self.geom_anim.state() == QPropertyAnimation.State.Running:
            return
            
        if self.current_state == "idle":
            if hasattr(self, '_pressed_pos'):
                dist = (event.position().toPoint() - self._pressed_pos).manhattanLength()
                if dist > 3:
                    self.is_dragging = True
                    
            if getattr(self, 'is_dragging', False) and hasattr(self, 'oldPos'):
                delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
                new_x = self.x() + delta.x()
                new_y = self.y() + delta.y()
                screen_geo = self.screen().availableGeometry()
                new_x = max(screen_geo.left(), min(new_x, screen_geo.right() - self.width() + 1))
                new_y = max(screen_geo.top(), min(new_y, screen_geo.bottom() - self.height() + 1))
                self.move(new_x, new_y)
                self.oldPos = event.globalPosition().toPoint()
                return
                
        if self.active_module:
            self.active_module.on_mouse_move(event.position().x(), event.position().y(), self.current_state)

    def mouseReleaseEvent(self, event):
        was_dragging = getattr(self, 'is_dragging', False)
        self.is_dragging = False
        
        if self.current_state == "idle" and not was_dragging:
            self.state_changed_signal.emit("mini_player")
            
        if self.active_module:
            self.active_module.on_mouse_release(event.position().x(), event.position().y(), self.current_state)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            
            if self.active_module and hasattr(self.active_module, 'on_double_click'):
                self.active_module.on_double_click(event.position().x(), event.position().y(), self.current_state)
            else:
                for mod in self.modules:
                    if mod.__class__.__name__ == 'BatteryModule':
                        mod.on_double_click(event.position().x(), event.position().y(), self.current_state)
                        break

    def wheelEvent(self, event):
        if self.current_state != "mini_player":
            return
            
        if not hasattr(self, 'cycle_list') or len(self.cycle_list) <= 1:
            return
            
        import time
        now = time.time()
        sens = getattr(self, 'scroll_sensitivity', 37)
        delay_threshold = 0.02 + (100 - sens) * 0.0036
        if hasattr(self, 'last_scroll_time') and now - self.last_scroll_time < delay_threshold:
            return
        self.last_scroll_time = now
            
        delta = event.angleDelta().y()
        if delta > 0:
            self.current_slot = (getattr(self, 'current_slot', 0) - 1) % len(self.cycle_list)
        elif delta < 0:
            self.current_slot = (getattr(self, 'current_slot', 0) + 1) % len(self.cycle_list)
            
        self.reset_inactivity_timer()
        self.active_module = self.get_active_module()
        self.animate_state_change(self.current_state)

    def reset_inactivity_timer(self):
        if not hasattr(self, 'inactivity_timer'):
            self.inactivity_timer = QTimer(self)
            self.inactivity_timer.timeout.connect(self.on_inactivity_timeout)
        self.inactivity_timer.start(10000)
        
    def on_inactivity_timeout(self):
        if getattr(self, 'current_slot', 0) != 0:
            self.current_slot = 0
            if self.current_state == "mini_player":
                self.state_changed_signal.emit("idle")
            else:
                self.active_module = self.get_active_module()
                self.animate_state_change("idle")

    def show_context_menu(self, pos):
        # pyrefly: ignore [missing-import]
        from PyQt6.QtWidgets import QMenu, QWidgetAction, QSlider, QWidget, QHBoxLayout
        # pyrefly: ignore [missing-import]
        from PyQt6.QtGui import QAction
        # pyrefly: ignore [missing-import]
        from PyQt6.QtCore import Qt

        menu = QMenu(self)
        menu.setStyleSheet('''
            QMenu { background-color: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 5px; }
            QMenu::item { color: white; padding: 8px 25px; font-size: 13px; }
            QMenu::item:selected { background-color: #333; border-radius: 4px; }
        ''')

        sens_menu = QMenu("Sensitivity", self)
        sens_menu.setStyleSheet(menu.styleSheet())
        
        sens_action = QWidgetAction(self)
        sens_widget = QWidget()
        sens_layout = QHBoxLayout(sens_widget)
        sens_layout.setContentsMargins(10, 5, 10, 5)
        
        sens_slider = QSlider(Qt.Orientation.Horizontal)
        sens_slider.setRange(25, 50)
        sens_slider.setMinimumWidth(100)
        sens_slider.setValue(getattr(self, 'scroll_sensitivity', 37))
        sens_slider.setStyleSheet('''
            QSlider::groove:horizontal { border-radius: 2px; height: 4px; background: #555; }
            QSlider::handle:horizontal { background: white; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        ''')
        
        def on_sens_changed(val):
            self.scroll_sensitivity = val
            # pyrefly: ignore [missing-import]
            from PyQt6.QtCore import QSettings
            QSettings("LiquidIsland", "Settings").setValue("scroll_sensitivity", val)
            
        sens_slider.valueChanged.connect(on_sens_changed)
        
        sens_layout.addWidget(sens_slider)
        sens_action.setDefaultWidget(sens_widget)
        sens_menu.addAction(sens_action)
        
        menu.addMenu(sens_menu)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        
        uninstall_action = QAction("Uninstall", self)
        uninstall_action.triggered.connect(self.uninstall_app)
        
        menu.addAction(quit_action)
        menu.addSeparator()
        menu.addAction(uninstall_action)
        menu.exec(pos)

    def uninstall_app(self):
        import subprocess
        # pyrefly: ignore [missing-import]
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Uninstall liquidisland", "Are you sure you want to uninstall?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, "liquidisland")
                winreg.CloseKey(key)
            except Exception: pass
            
            install_dir = os.path.join(os.getenv('APPDATA'), 'liquidisland')
            if os.path.exists(install_dir):
                subprocess.Popen(f'ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{install_dir}"', shell=True)
                
            QMessageBox.information(self, "Uninstalled", "liquidisland has been uninstalled successfully.")
            QApplication.quit()

    def closeEvent(self, event):
        for mod in self.modules:
            mod.on_stop()
        super().closeEvent(event)
