from typing import Tuple
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QRect
import ctypes

class BaseModule:
    """
    Base class for all LiquidIsland modules/features.
    """
    
    def __init__(self, island):
        """
        :param island: Reference to the main LiquidIsland widget, to allow modules to trigger updates.
        """
        self.island = island

    @property
    def priority(self) -> int:
        """
        Priority of the module. Higher priority modules take over the island if active.
        """
        return 0

    def is_active(self) -> bool:
        """
        Check if the module should be currently displayed.
        """
        return False

    def get_idle_size(self) -> Tuple[int, int]:
        """
        Returns (width, height) for the idle state.
        """
        return (200, 48)

    def get_expanded_size(self) -> Tuple[int, int]:
        """
        Returns (width, height) for the expanded (mini_player) state.
        """
        return (440, 180)

    def get_accent_color(self) -> QColor:
        """
        Returns the accent color for the module. Return None to use the system default.
        """
        return None

    def on_start(self):
        """
        Called when the module is registered. Start polling/threads here.
        """
        pass

    def on_stop(self):
        """
        Called when the module is unregistered or app closes.
        """
        pass

    # --- Painting ---

    def paint_idle(self, painter: QPainter, rect: QRect, anim_step: int):
        """
        Draw the idle content (e.g. pill).
        """
        pass

    def paint_expanded(self, painter: QPainter, rect: QRect, anim_step: int):
        """
        Draw the expanded content.
        """
        pass

    # --- Interaction ---

    def on_mouse_press(self, x: int, y: int, state: str):
        """
        Handle mouse click inside the module.
        """
        pass

    def on_mouse_move(self, x: int, y: int, state: str):
        """
        Handle mouse drag inside the module.
        """
        pass

    def on_mouse_release(self, x: int, y: int, state: str):
        """
        Handle mouse release inside the module.
        """
        pass

    def on_double_click(self, x: int, y: int, state: str):
        """
        Handle mouse double click inside the module.
        """
        pass
