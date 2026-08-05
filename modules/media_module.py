import time
import math
import threading
import asyncio
import ctypes
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QFont, QBrush, QTransform, QImage, QPixmap, QPolygon, QPen
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QRect, Qt, QPoint
from core.module import BaseModule

try:
    # pyrefly: ignore [missing-import]
    from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
    WINSDK_AVAILABLE = True
except ImportError:
    WINSDK_AVAILABLE = False

class MediaModule(BaseModule):
    """
    Handles media polling, playback controls, and visualizing track info.
    """
    
    def __init__(self, island):
        super().__init__(island)
        self.media_app_name = ""
        self.media_title = ""
        self.media_artist = ""
        self.media_pos = 0.0
        self.media_end = 0.0
        self.is_playing = False
        self.media_thumb_bytes = b""
        self.media_thumb_pixmap = None
        
        self.accent_color = None
        self.dragging_progress = False
        self.drag_pct = 0.0
        
        self.poll_thread = None
        self._running = False
        
    @property
    def priority(self) -> int:
        return 10

    def is_active(self) -> bool:
        return (self.media_end > 0 or self.media_app_name != "")

    def get_idle_size(self):
        return (160, 48)

    def get_expanded_size(self):
        return (440, 180)

    def get_accent_color(self) -> QColor:
        return self.accent_color

    def on_start(self):
        if WINSDK_AVAILABLE:
            self._running = True
            self.poll_thread = threading.Thread(target=self.start_media_poller, daemon=True)
            self.poll_thread.start()

    def on_stop(self):
        self._running = False

    def on_tick(self, anim_step):
        now = time.time()
        if not self.dragging_progress and self.media_end > 0:
            if hasattr(self, 'last_anim_time'):
                dt = now - self.last_anim_time
                if self.is_playing:
                    self.media_pos = min(self.media_end, self.media_pos + dt)
        self.last_anim_time = now

    def start_media_poller(self):
        asyncio.run(self.poll_media())
        
    async def poll_media(self):
        current_title_for_thumb = ""
        current_thumbnail_bytes = b""
        try:
            try:
                ctypes.windll.combase.RoInitialize(1)
            except Exception:
                try:
                    ctypes.windll.ole32.CoInitialize(None)
                except Exception:
                    pass
                    
            manager = await MediaManager.request_async()
            while self._running:
                try:
                    session = manager.get_current_session()
                    if not session:
                        sessions = manager.get_sessions()
                        if sessions and len(sessions) > 0:
                            session = sessions[0]
                            
                    if session:
                        info = await session.try_get_media_properties_async()
                        app_id = session.source_app_user_model_id
                        app_name = app_id.split("!")[-1].split(".exe")[0].capitalize()
                        
                        playback_info = session.get_playback_info()
                        playing = (playback_info.playback_status == 4) if playback_info else False
                        
                        timeline = session.get_timeline_properties()
                        pos = timeline.position.total_seconds() if timeline else -1.0
                        end = timeline.end_time.total_seconds() if timeline else -1.0
                        
                        try:
                            if info.title != current_title_for_thumb:
                                current_title_for_thumb = info.title
                                if info.thumbnail:
                                    # pyrefly: ignore [missing-import]
                                    from winsdk.windows.storage.streams import DataReader, Buffer
                                    stream = await info.thumbnail.open_read_async()
                                    buffer = Buffer(stream.size)
                                    await stream.read_async(buffer, stream.size, 0)
                                    reader = DataReader.from_buffer(buffer)
                                    current_thumbnail_bytes = bytes(reader.read_buffer(buffer.length))
                                else:
                                    current_thumbnail_bytes = b""
                        except Exception:
                            current_thumbnail_bytes = b""
                            
                        # Update data in thread-safe way by relying on Qt event loop or just direct assignment
                        # In PyQt, modifying primitive attributes from threads is usually safe.
                        # Wait, we need to handle debounce and extraction like main.py
                        self.update_media(app_name, info.title, info.artist, playing, pos, end, current_thumbnail_bytes)
                    else:
                        self.update_media("", "", "", False, 0.0, 0.0, b"")
                        
                except Exception:
                    pass
                await asyncio.sleep(0.5)
        except Exception:
            pass

    def update_media(self, app, title, artist, playing, pos, end, thumb_bytes):
        self.media_app_name = app
        self.media_title = title
        self.media_artist = artist
        
        if hasattr(self, 'last_toggle_time') and time.time() - self.last_toggle_time < 1.5:
            playing = self.is_playing
            
        if pos == -1.0 or end == -1.0:
            return
            
        is_new_track = (not hasattr(self, '_last_title') or self._last_title != title)
        self._last_title = title
        
        if not hasattr(self, 'last_raw_pos'):
            self.last_raw_pos = -1.0
        is_fresh_update = (pos != self.last_raw_pos) or is_new_track
        self.last_raw_pos = pos
        
        if is_new_track and hasattr(self, 'last_seek_time'):
            self.last_seek_time = 0
            
        if hasattr(self, 'last_seek_time') and time.time() - self.last_seek_time < 1.5:
            pos = getattr(self, 'seek_target_pos', self.media_pos)
        else:
            if not hasattr(self, 'media_pos') or is_new_track:
                self.media_pos = pos
            elif is_fresh_update:
                if abs(self.media_pos - pos) > 0.5:
                    self.media_pos = pos
                    
        self.is_playing = playing
        self.media_end = end
        
        if thumb_bytes and thumb_bytes != self.media_thumb_bytes:
            self.media_thumb_bytes = thumb_bytes
            img = QImage.fromData(thumb_bytes)
            self.media_thumb_pixmap = QPixmap.fromImage(img)
            self.accent_color = self.extract_album_accent_color(img)
        elif not thumb_bytes and self.media_thumb_bytes:
            self.media_thumb_bytes = b""
            self.media_thumb_pixmap = None
            self.accent_color = QColor(255, 255, 255)

    def extract_album_accent_color(self, img: QImage) -> QColor:
        if img.isNull():
            return QColor(255, 255, 255)

        scaled = img.scaled(16, 16, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        best_color = None
        max_score = -1.0
        
        total_r, total_g, total_b = 0, 0, 0
        pixel_count = 16 * 16

        for x in range(16):
            for y in range(16):
                c = scaled.pixelColor(x, y)
                r, g, b = c.red(), c.green(), c.blue()
                total_r += r
                total_g += g
                total_b += b

                sat = c.hsvSaturationF()
                val = c.valueF()

                # Score vibrant colors that aren't pitch black or stark white
                if 0.15 <= val <= 0.95 and sat >= 0.10:
                    score = sat * 2.5 + val
                    if score > max_score:
                        max_score = score
                        best_color = c

        if not best_color:
            avg_r = total_r // pixel_count
            avg_g = total_g // pixel_count
            avg_b = total_b // pixel_count
            best_color = QColor(avg_r, avg_g, avg_b)

        h, s, v, a = best_color.getHsv()
        if v < 150:
            best_color.setHsv(h, max(s, 140), 180, a)

        return best_color

    def paint_idle(self, painter: QPainter, rect: QRect, anim_step: int):
        art_size = 32
        art_x, art_y = 10, (48 - art_size) // 2
        if self.media_thumb_pixmap:
            scaled_pix = self.media_thumb_pixmap.scaled(art_size, art_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            crop_rect = QRect((scaled_pix.width() - art_size) // 2, (scaled_pix.height() - art_size) // 2, art_size, art_size)
            brush = QBrush(scaled_pix.copy(crop_rect))
            brush.setTransform(QTransform().translate(art_x, art_y))
            painter.setBrush(brush)
        else:
            painter.setBrush(QColor(200, 200, 200, 200))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(art_x, art_y, art_size, art_size, int(art_size/2), int(art_size/2))
        
        if self.is_playing and not (hasattr(self.island, 'is_camera_active') and self.island.is_camera_active()):
            painter.setBrush(self.accent_color if self.accent_color else QColor(255, 255, 255))
            vis_x = rect.width() - 36
            for i in range(4):
                h = 4 + 6 * abs(math.cos((anim_step * 0.15) + (i * 0.8)))
                y = (rect.height() - h) / 2
                painter.drawRoundedRect(int(vis_x + (i*5)), int(y), 2, int(h), 1, 1)

    def paint_expanded(self, painter: QPainter, rect: QRect, anim_step: int):
        painter.setPen(QColor(255, 255, 255))
        
        art_x, art_y, art_size = 45, 20, 64
        if self.media_thumb_pixmap:
            scaled_pix = self.media_thumb_pixmap.scaled(art_size, art_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            crop_rect = QRect((scaled_pix.width() - art_size) // 2, (scaled_pix.height() - art_size) // 2, art_size, art_size)
            brush = QBrush(scaled_pix.copy(crop_rect))
            brush.setTransform(QTransform().translate(art_x, art_y))
            painter.setBrush(brush)
        else:
            painter.setBrush(QColor(200, 200, 200, 200))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(art_x, art_y, art_size, art_size, 12, 12)
        
        text_x = art_x + art_size + 15
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        
        raw_title = self.media_title.strip() if self.media_title else ""
        title = raw_title if raw_title and raw_title != "Live Activity" else self.media_app_name
        if not title:
            title = "Media Player"
            
        raw_artist = self.media_artist.strip() if self.media_artist else ""
        if not raw_artist or raw_artist.lower() == "unknown artist":
            painter.drawText(QRect(text_x, 30, 200, 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        else:
            painter.drawText(QRect(text_x, 22, 200, 25), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
            painter.setPen(QColor(180, 180, 180))
            painter.setFont(QFont('Segoe UI', 11))
            painter.drawText(QRect(text_x, 47, 200, 25), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, raw_artist)
        
        if self.is_playing and not (hasattr(self.island, 'is_camera_active') and self.island.is_camera_active()):
            painter.setBrush(self.accent_color if self.accent_color else QColor(255, 255, 255))
            vis_x = rect.width() - 80
            for i in range(4):
                h = 4 + 8 * abs(math.cos((anim_step * 0.15) + (i * 0.8)))
                y = 40 - (h / 2)
                painter.drawRoundedRect(int(vis_x + (i*6)), int(y), 3, int(h), 1, 1)

        bar_y = 100
        line_w = rect.width() - 160
        
        def fmt(s): return f"{int(s//60)}:{int(s%60):02d}"
        t_curr = fmt(self.media_pos)
        rem = max(0, self.media_end - self.media_pos)
        t_rem = f"-{fmt(rem)}" if rem > 0 else "0:00"
        
        painter.setFont(QFont('Segoe UI', 8))
        painter.setPen(QColor(150, 150, 150))
        painter.drawText(QRect(35, bar_y - 8, 40, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t_curr)
        painter.drawText(QRect(rect.width() - 75, bar_y - 8, 40, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, t_rem)
        
        line_x = 80
        painter.setBrush(QColor(80, 80, 80))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(line_x, bar_y - 4, line_w, 12, 6, 6)
        
        if self.media_end > 0:
            if self.dragging_progress:
                pct = self.drag_pct
            else:
                pct = min(1.0, max(0.0, self.media_pos / self.media_end))
            fill_w = int(line_w * pct)
            painter.setBrush(QColor(255, 255, 255))
            painter.drawRoundedRect(line_x, bar_y - 4, fill_w, 12, 6, 6)

        button_y = 145
        center_x = rect.width() // 2
        pen = QPen(QColor(255, 255, 255))
        pen.setWidth(3)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255))
        
        px = center_x - 95
        py = button_y - 15
        painter.drawPolygon(QPolygon([QPoint(px - 16, py + 15), QPoint(px, py), QPoint(px, py + 30)]))
        painter.drawPolygon(QPolygon([QPoint(px + 2, py + 15), QPoint(px + 18, py), QPoint(px + 18, py + 30)]))
        
        px = center_x
        py = button_y - 15
        if self.is_playing:
            painter.drawRoundedRect(px - 14, py, 10, 30, 2, 2)
            painter.drawRoundedRect(px + 4, py, 10, 30, 2, 2)
        else:
            painter.drawPolygon(QPolygon([QPoint(px - 12, py), QPoint(px + 18, py + 15), QPoint(px - 12, py + 30)]))
            
        px = center_x + 100
        py = button_y - 15
        painter.drawPolygon(QPolygon([QPoint(px - 18, py), QPoint(px - 2, py + 15), QPoint(px - 18, py + 30)]))
        painter.drawPolygon(QPolygon([QPoint(px, py), QPoint(px + 16, py + 15), QPoint(px, py + 30)]))

    def on_mouse_press(self, x: int, y: int, state: str):
        if state == "mini_player":
            center_x = self.get_expanded_size()[0] // 2
            
            PROG_Y_MIN, PROG_Y_MAX = 85, 115
            BTN_Y_MIN, BTN_Y_MAX = 125, 175
            PREV_X_MIN, PREV_X_MAX = center_x - 120, center_x - 70
            PLAY_X_MIN, PLAY_X_MAX = center_x - 20, center_x + 25
            NEXT_X_MIN, NEXT_X_MAX = center_x + 75, center_x + 125
            FOCUS_Y_MIN, FOCUS_Y_MAX = 20, 80
            FOCUS_X_MIN, FOCUS_X_MAX = 20, 300
            
            if PROG_Y_MIN <= y <= PROG_Y_MAX and 80 <= x <= (self.get_expanded_size()[0] - 80) and self.media_end > 0:
                bar_w = self.get_expanded_size()[0] - 160
                click_x = x - 80
                self.drag_pct = max(0.0, min(1.0, click_x / bar_w))
                self.dragging_progress = True
                return
                
            if BTN_Y_MIN <= y <= BTN_Y_MAX:
                if PREV_X_MIN <= x <= PREV_X_MAX:
                    if self.media_pos > 3.0:
                        self.last_seek_time = time.time()
                        self.seek_target_pos = 0.0
                        self.media_pos = 0.0
                        self.seek_media(0.0)
                    else:
                        self.last_seek_time = 0
                        self.media_pos = 0.0
                        ctypes.windll.user32.keybd_event(0xB1, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(0xB1, 0, 2, 0)
                    return
                elif PLAY_X_MIN <= x <= PLAY_X_MAX:
                    self.last_toggle_time = time.time()
                    ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
                    self.is_playing = not self.is_playing
                    self.island.update()
                    return
                elif NEXT_X_MIN <= x <= NEXT_X_MAX:
                    self.last_seek_time = 0
                    self.media_pos = 0.0
                    ctypes.windll.user32.keybd_event(0xB0, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xB0, 0, 2, 0)
                    return
                    
            if FOCUS_Y_MIN <= y <= FOCUS_Y_MAX and FOCUS_X_MIN <= x <= FOCUS_X_MAX and self.media_app_name:
                def focus_app():
                    try:
                        import re
                        # pyrefly: ignore [missing-import]
                        import pygetwindow as gw
                        app_name = self.media_app_name.lower()
                        track_title = self.media_title.lower().strip() if self.media_title else ""
                        clean_words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', track_title).split() if len(w) > 2]
                        
                        target_win = None
                        
                        # 1. Try finding a window whose title matches the specific track/media title
                        if clean_words:
                            for win in gw.getAllWindows():
                                if win.title and win.title != "Program Manager":
                                    w_title = win.title.lower()
                                    if any(word in w_title for word in clean_words):
                                        target_win = win
                                        break
                                        
                        # 2. Fallback: find window matching app_name (e.g. "chrome", "spotify", "vlc")
                        if not target_win:
                            for win in gw.getAllWindows():
                                if win.title and win.title != "Program Manager":
                                    w_title = win.title.lower()
                                    if app_name and app_name in w_title:
                                        target_win = win
                                        break
                                    if "chrome" in app_name and "chrome" in w_title:
                                        target_win = win
                                        break
                                    if ("edge" in app_name or "msedge" in app_name) and "edge" in w_title:
                                        target_win = win
                                        break
                                    if "firefox" in app_name and "firefox" in w_title:
                                        target_win = win
                                        break

                        if target_win:
                            try:
                                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                                ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
                                if target_win.isMinimized:
                                    target_win.restore()
                                ctypes.windll.user32.ShowWindow(target_win._hWnd, 9)
                                ctypes.windll.user32.SetForegroundWindow(target_win._hWnd)
                                
                                # If it's a web browser and the currently active tab title is not the media tab, use Tab Search (Ctrl+Shift+A)
                                is_browser = any(b in app_name or b in target_win.title.lower() for b in ['chrome', 'edge', 'firefox', 'brave', 'opera'])
                                if is_browser and clean_words and not any(w in target_win.title.lower() for w in clean_words):
                                    time.sleep(0.15)
                                    # Send Ctrl+Shift+A (Chrome/Edge Tab Search)
                                    ctypes.windll.user32.keybd_event(0x11, 0, 0, 0) # Ctrl
                                    ctypes.windll.user32.keybd_event(0x10, 0, 0, 0) # Shift
                                    ctypes.windll.user32.keybd_event(0x41, 0, 0, 0) # A
                                    time.sleep(0.05)
                                    ctypes.windll.user32.keybd_event(0x41, 0, 2, 0)
                                    ctypes.windll.user32.keybd_event(0x10, 0, 2, 0)
                                    ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
                                    time.sleep(0.15)
                                    
                                    # Type the track keyword into tab search
                                    search_query = clean_words[0]
                                    for char in search_query:
                                        vk = ctypes.windll.user32.VkKeyScanW(ord(char)) & 0xFF
                                        if vk > 0:
                                            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                                            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
                                    time.sleep(0.1)
                                    # Press Enter to select the matching tab!
                                    ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0) # Enter
                                    ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
                            except Exception:
                                pass
                    except Exception:
                        pass
                threading.Thread(target=focus_app, daemon=True).start()
                return

    def on_mouse_move(self, x: int, y: int, state: str):
        if self.dragging_progress and state == "mini_player" and self.media_end > 0:
            bar_w = self.get_expanded_size()[0] - 160
            click_x = x - 80
            self.drag_pct = max(0.0, min(1.0, click_x / bar_w))
            self.island.update()

    def on_mouse_release(self, x: int, y: int, state: str):
        if self.dragging_progress:
            self.last_seek_time = time.time()
            self.seek_target_pos = self.drag_pct * self.media_end
            self.media_pos = self.seek_target_pos
            self.seek_media(self.drag_pct)
            self.dragging_progress = False

    def seek_media(self, pct):
        def _seek():
            try:
                async def _do_seek():
                    manager = await MediaManager.request_async()
                    session = manager.get_current_session()
                    if session:
                        target = int(pct * self.media_end * 10_000_000)
                        await session.try_change_playback_position_async(target)
                asyncio.run(_do_seek())
            except Exception:
                pass
        threading.Thread(target=_seek, daemon=True).start()
