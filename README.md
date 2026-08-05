# LiquidIsland for Windows

A pure, standalone LiquidIsland UI for Windows desktop. This tool sits at the top of your screen as an unobtrusive pill, showing a minimal indicator by default. When media is playing (e.g. Spotify, Chrome, Edge), it polls the Windows Media Transport Controls and allows you to expand the island into a fully-functional Mini Player!

## Features
- **Always on Top, Transparent Pill**: Renders natively on your desktop with a sleek liquid glass effect.
- **Drag & Drop Repositioning**: Simply click and drag the island while closed to place it anywhere on your screen.
- **Adjustable Scroll Sensitivity**: Right-click the island to access a precise slider to adjust scroll speed; your preference is automatically saved.
- **Extensible Modules**: Includes rich modules for Media, Time, Wi-Fi, Bluetooth, Battery, Camera, and System Controls (Volume/Brightness).
- **Media Polling**: Automatically grabs track, artist, album art, and live progress for whatever is playing on Windows.
- **Playback Controls**: Play, Pause, Next, Prev, and seek through tracks using the UI.
- **Smart Focus**: Click on the album art to immediately focus the app playing the media.
- **Adaptive Accent Colors**: Smoothly adopts your Windows accent color.

## Installation
1. Install Python 3.10+
2. Install requirements:
   ```cmd
   pip install -r requirements.txt
   ```
3. Run the application:
   ```cmd
   python main.py
   ```
