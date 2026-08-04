import os
import sys
import shutil
import winreg
import subprocess
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import QApplication, QMessageBox

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def install():
    app = QApplication(sys.argv)
    
    # 1. Target directory
    appdata = os.getenv('APPDATA')
    install_dir = os.path.join(appdata, 'liquidisland')
    if not os.path.exists(install_dir):
        os.makedirs(install_dir)
        
    target_exe = os.path.join(install_dir, 'liquidisland.exe')
    
    # 2. Extract and copy the bundled exe
    source_exe = get_resource_path('liquidisland.exe')
    
    if not os.path.exists(source_exe):
        QMessageBox.critical(None, "Error", "Installation payload not found!")
        return
        
    # Kill any running instance first so we can overwrite the file
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'liquidisland.exe'], 
                       capture_output=True, timeout=5)
        import time
        time.sleep(1)  # Give Windows time to release the file lock
    except Exception:
        pass  # No running instance, that's fine
        
    try:
        shutil.copy2(source_exe, target_exe)
    except Exception as e:
        QMessageBox.critical(None, "Installation Failed", f"Could not copy files: {e}")
        return
        
    # 3. Add to Windows Startup (Registry)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "liquidisland", 0, winreg.REG_SZ, f'"{target_exe}"')
        winreg.CloseKey(key)
    except Exception as e:
        QMessageBox.warning(None, "Startup Error", f"Could not add to startup: {e}")
        
    # 4. Launch the app
    try:
        subprocess.Popen([target_exe])
    except Exception as e:
        QMessageBox.critical(None, "Launch Error", f"Could not start liquidisland: {e}")
        return
    
    QMessageBox.information(None, "Installation Successful", "liquidisland has been successfully installed!\n\nIt will now start automatically whenever you turn on your PC.")

if __name__ == "__main__":
    install()
