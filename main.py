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

import os
import shutil
import winreg
import subprocess
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import QApplication, QMessageBox
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QIcon

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def prompt_install():
    if not getattr(sys, 'frozen', False):
        return # Only run if compiled as EXE
        
    exe_path = sys.executable
    appdata = os.getenv('APPDATA')
    install_dir = os.path.join(appdata, 'liquidisland')
    target_exe = os.path.join(install_dir, 'LiquidIsland.exe')
    
    if os.path.normcase(exe_path) != os.path.normcase(target_exe):
        reply = QMessageBox.question(None, 'Install LiquidIsland', 
                                     'Do you want to install LiquidIsland to your PC?\n\nIf you select Yes, it will be added to your startup applications automatically. If you select No, the application will exit.',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if not os.path.exists(install_dir):
                    os.makedirs(install_dir)
                    
                import psutil
                current_pid = os.getpid()
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['name'] and proc.info['name'].lower() in ['liquidisland.exe', 'liquidisland']:
                            if proc.info['pid'] != current_pid:
                                proc.kill()
                    except Exception:
                        pass
                
                shutil.copy2(exe_path, target_exe)
                
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "liquidisland", 0, winreg.REG_SZ, f'"{target_exe}"')
                winreg.CloseKey(key)

                # Register in Windows Settings > Apps > Installed apps
                uninstall_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\LiquidIsland"
                un_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_path)
                winreg.SetValueEx(un_key, "DisplayName", 0, winreg.REG_SZ, "LiquidIsland")
                winreg.SetValueEx(un_key, "DisplayIcon", 0, winreg.REG_SZ, target_exe)
                winreg.SetValueEx(un_key, "DisplayVersion", 0, winreg.REG_SZ, "1.0.0")
                winreg.SetValueEx(un_key, "Publisher", 0, winreg.REG_SZ, "LiquidIsland")
                file_size_kb = int(os.path.getsize(target_exe) / 1024)
                winreg.SetValueEx(un_key, "EstimatedSize", 0, winreg.REG_DWORD, file_size_kb)
                cmd_uninstall = f'cmd.exe /c "taskkill /F /IM LiquidIsland.exe & timeout /t 1 & rmdir /S /Q \"{install_dir}\" & reg delete HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v liquidisland /f & reg delete HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LiquidIsland /f"'
                winreg.SetValueEx(un_key, "UninstallString", 0, winreg.REG_SZ, cmd_uninstall)
                winreg.CloseKey(un_key)
                
                QMessageBox.information(None, "Success", "Installed successfully! LiquidIsland will now run.")
                subprocess.Popen([target_exe])
                sys.exit(0)
            except Exception as e:
                QMessageBox.critical(None, "Error", f"Failed to install: {e}")
                sys.exit(1)
        else:
            # User refused install
            sys.exit(0)

def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(get_resource_path('icon.ico')))
    prompt_install()
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
    island.show()
    island.raise_()
    island.activateWindow()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
