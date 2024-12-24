# WiZ Light Control Program

Welcome to the **WiZ Light Control Program**! This program is a comprehensive tool for managing, customizing, and visualizing your WiZ smart lights. It features advanced controls for lighting scenes, patterns, and visualizations, as well as a pattern editor and previewer for creating custom lighting effects.

---

## Features

### 1. **Device Management**
- **Discover Lights:** Automatically discovers all WiZ lights on the network.
- **Rename Lights:** Rename your lights for easier identification.
- **View and Manage Light States:** Displays the current state, color, and mode of each light.
- **Group Actions:** Apply colors or settings to groups of lights.

### 2. **Light Controls**
- **Brightness Slider:** Adjust the brightness of selected lights in real-time.
- **Color Picker:** Set custom RGB colors for individual or grouped lights.
- **Scenes:** Apply preset lighting effects such as "Ocean," "Party," or "Christmas."
  - Adjust speed and dimming levels for scene effects.

### 3. **Patterns**
- **Run Patterns:** Select and run preloaded patterns to create dynamic lighting effects.
- **Stop Patterns:** Stop any running pattern immediately.
- **Load Patterns:** Load new pattern files into the program.
- **Pattern Editor:** Open the built-in editor to create or modify lighting patterns.

### 4. **Pattern Editor**
- **Create New Patterns:** Start from scratch with a new pattern.
- **Edit Patterns:** Modify existing patterns with a visual editor.
- **Step Management:**
  - Add, edit, duplicate, or remove steps.
  - Reorder steps with drag-and-drop functionality.
  - Customize each step with color, brightness, duration, and assigned lights.
- **Save Patterns:** Save your patterns to a file for future use.

### 5. **Pattern Preview**
- **Preview Patterns:** Simulate patterns with visual feedback before applying them to actual lights.
- **Customizable Layout:** Arrange light icons to reflect your real-world setup.
- **Playback Controls:** Play, pause, or restart the pattern preview.

### 6. **Audio Visualizers**
- **Frequency Visualizer:** Sync your lights to the frequency spectrum of the audio.
- **Volume Visualizer:** Create effects based on the audio volume.

### 7. **Settings**
- **Theme Customization:** Choose between dark and light themes, or create your own.
- **Broadcast Address:** Configure the network broadcast address for discovering lights.

---

## Installation
1. Download the installer .exe
2. Follow the on-screen instructions in the install wizard
3. Launch the program

### Prerequisites for Building the program from Source
- **Python 3.8+**
- Required libraries:
  - PyQt5
  - pywizlight
  - qasync
  - asyncio
  - json

### Steps to build from Source
1. Clone this repository:
   ```bash
   git clone https://github.com/WiZ-Light-Control/wiz-light-control
   ```
2. Navigate to the project directory:
   ```bash
   cd wiz-light-control
   ```
3. Install the required libraries:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the program:
   ```bash
   python wiz_test.py
   ```

---

## Usage

### Main Application
1. Launch `wiz_test.py` to start the main program.
2. Use the tabs to navigate between **Device List**, **Light Controls**, **Scenes**, **Patterns**, **Visualizer**, and **Settings**.
3. Discover your WiZ lights and begin customizing!

### Pattern Editor
1. Open the **Pattern Editor** from the "Patterns" tab.
2. Create a new pattern or load an existing one.
3. Use the editor to define steps, assign lights, and configure effects.
4. Save your pattern and use it in the main program. Save the pattern within the "patterns" directory in the main program's folder.

### Pattern Preview
1. Preview patterns directly from the **Pattern Editor** or the **Patterns** tab.
2. Arrange light icons to match your setup.
3. Play and pause the preview to test your effects.

### Note:

Currently the Audio visualizers do not work correctly when opened from the main program's GUI. If you wish to use the visualizers please use the .exe's located in the installed folder. The Visualizer's names are config_gui.exe for the Frequency visualizer and volume_config_gui.exe for the Volume visualier. You can also download and install the visualizers as standalone programs from my Github.

### Audio Visualizers
1. Access the visualizers from the "Visualizer" tab.
2. Open the **Frequency** or **Volume** visualizer configuration tools.
3. Sync your lights to audio inputs in real-time.

---

## Notes
- The program is designed to work with WiZ smart lights and may not support other brands.
- Ensure all lights are connected to the same network as the program.
- Save your settings and patterns to avoid losing progress.

---

## Contributing
Contributions are welcome! Please fork the repository, create a feature branch, and submit a pull request.


---

## Acknowledgments
Special thanks to the creators of the PyQt5 and pywizlight libraries for enabling this project.


