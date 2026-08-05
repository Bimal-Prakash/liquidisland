import sys
import logging
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import QApplication
from core.island import LiquidIsland
from modules.time_module import TimeModule
from modules.media_module import MediaModule
from modules.wifi_module import WifiModule
from modules.bluetooth_module import BluetoothModule
from modules.battery_module import BatteryModule
from modules.camera_module import CameraModule
from modules.control_module import ControlModule

logging.basicConfig(level=logging.INFO, format="%(asctime)s [UI Wrapper] %(message)s")
logging.getLogger("screen_brightness_control").setLevel(logging.CRITICAL)

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    island = LiquidIsland()
    
    # Register modules
    island.register_module(TimeModule)
    island.register_module(MediaModule)
    island.register_module(WifiModule)
    island.register_module(BluetoothModule)
    island.register_module(BatteryModule)
    island.register_module(CameraModule)
    island.register_module(ControlModule)
    
    island.state_changed_signal.emit("ready")
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
