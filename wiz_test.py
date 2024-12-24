import sys
import os
import json
import asyncio
import subprocess
import random
import tempfile
import shutil
import tempfile
import pyi_splash


from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QListWidget, QPushButton,
    QInputDialog, QLabel, QColorDialog, QVBoxLayout, QWidget,
    QComboBox, QGroupBox, QCheckBox, QTabWidget, QLineEdit, QGraphicsDropShadowEffect, QGraphicsBlurEffect, QSlider, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from pywizlight import wizlight, discovery, PilotBuilder
from qasync import QEventLoop, asyncSlot
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QColor, QIcon
from pattern_editor import PatternEditor



# Define the supported bulb effects with scene IDs and names
SCENES = {
    1: "Ocean",
    2: "Romance",
    3: "Sunset",
    4: "Party",
    5: "Fireplace",
    6: "Cozy",
    7: "Forest",
    8: "Pastel colors",
    9: "Wake-up",
    10: "Bedtime",
    11: "Warm white",
    12: "Daylight",
    13: "Cool white",
    14: "Night light",
    15: "Focus",
    16: "Relax",
    17: "True colors",
    18: "TV time",
    19: "Plant growth",
    20: "Spring",
    21: "Summer",
    22: "Fall",
    23: "Deep dive",
    24: "Jungle",
    25: "Mojito",
    26: "Club",
    27: "Christmas",
    28: "Halloween",
    29: "Candlelight",
    30: "Golden white",
    31: "Pulse",
    32: "Steampunk",
    33: "Diwali",
    34: "White",
    35: "Alarm",
    1000: "Rhythm",
}

# Map scene names to their IDs for quick access
SCENE_NAME_TO_ID = {
    "Ocean": 1,
    "Romance": 2,
    "Sunset": 3,
    "Party": 4,
    "Fireplace": 5,
    "Cozy": 6,
    "Forest": 7,
    "Pastel colors": 8,
    "Wake-up": 9,
    "Bedtime": 10,
    "Warm white": 11,
    "Daylight": 12,
    "Cool white": 13,
    "Night light": 14,
    "Focus": 15,
    "Relax": 16,
    "True colors": 17,
    "TV time": 18,
    "Plant growth": 19,
    "Spring": 20,
    "Summer": 21,
    "Fall": 22,
    "Deep dive": 23,
    "Jungle": 24,
    "Mojito": 25,
    "Club": 26,
    "Christmas": 27,
    "Halloween": 28,
    "Candlelight": 29,
    "Golden white": 30,
    "Pulse": 31,
    "Steampunk": 32,
    "Diwali": 33,
    "White": 34,
    "Alarm": 35,
    "Rhythm": 1000,
}


def load_icon():
    """
    Load the program's icon dynamically, considering both development and packaged environments.
    """
    if getattr(sys, '_MEIPASS', False):  # If running as a packaged app
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")

    icon_path = os.path.join(base_path, 'icon', 'main3.ico')
    print(f"Trying to load icon from: {icon_path}")  # Debug statement

    return QIcon(icon_path)


# Define the path to the theme effects settings file dynamically
if getattr(sys, 'frozen', False):  # If running as a packaged app
    base_path = sys._MEIPASS  # Path to extracted resources in packaged mode
else:
    base_path = os.path.abspath(".")  # For development or when not packaged

THEME_EFFECTS_PATH = os.path.join(base_path, "themes", "theme_effects.json")

print(THEME_EFFECTS_PATH)  # For debugging purposes to verify the path





def load_stylesheet(app, theme_name="dark"):
    """
    Load a stylesheet based on the theme name from the 'themes' folder.
    """
    if getattr(sys, '_MEIPASS', False):  # If running as a packaged app
        base_path = os.path.join(sys._MEIPASS, 'themes')
    else:
        base_path = os.path.join(os.path.abspath("."), 'themes')

    theme_path = os.path.join(base_path, f"{theme_name}.qss")
    print(f"Trying to load stylesheet from: {theme_path}")  # Debug statement

    try:
        with open(theme_path, "r") as f:
            stylesheet = f.read()
            app.setStyleSheet(stylesheet)
    except FileNotFoundError:
        print(f"Stylesheet not found: {theme_path}")

def load_theme_effects(theme_name):
    """
    Load theme effects from the JSON settings based on the theme name.
    """
    if getattr(sys, '_MEIPASS', False):  # If running as a packaged app
        base_path = os.path.join(sys._MEIPASS, 'themes')
    else:
        base_path = os.path.join(os.path.abspath("."), 'themes')

    effects_path = os.path.join(base_path, 'theme_effects.json')
    print(f"Trying to load theme effects from: {effects_path}")  # Debug statement

    try:
        with open(effects_path, "r") as f:
            effects = json.load(f)
            return effects.get(theme_name, {})
    except FileNotFoundError:
        print("Theme effects file not found.")
        return {}
    except json.JSONDecodeError:
        print("Error parsing theme effects file.")
        return {}




class LightApp(QMainWindow):
    light_state_updated = pyqtSignal(str, str)
    current_pattern_task = None
    pattern_timer = None  # Timer for pattern running

    def change_theme(self, theme_name):
        """
        Change the application theme by loading the appropriate .qss file from the themes folder.
        """
        theme_path = os.path.join("themes", f"{theme_name}.qss")
        load_stylesheet(QApplication.instance(), theme_path)  # Load and apply the theme

    def __init__(self):
        super().__init__()
        self.current_speed = 0  # Set initial value for speed
        self.current_dimming = 100  # Set initial value for dimming
        self.apply_theme_effects()  # Apply initial theme effects
        self.lights = []
        self.scenes_tab = QWidget(self)  # Create the QWidget for scenes_tab
        self.setCentralWidget(self.scenes_tab)  # Optionally, set this as the central widget if necessary
        self.discovered_lights = []  # This will store the discovered lights
        self.light_names = {}  # For renaming lights
        self.lightCheckBoxes = {}  # For light checkboxes in UI
        # Call the method to initialize the scenes tab UI elements
        self.init_scenes_tab()
        self.presets = []
        self.groupBox = QGroupBox("Group Name", self)
        self.groupBoxLayout = QVBoxLayout(self.groupBox)
        self.groupBox.setLayout(self.groupBoxLayout)
        self.applyPresetButton = QPushButton('Apply Preset to Group', self.groupBox)
        self.groupBoxLayout.addWidget(self.applyPresetButton)
        self.light_names = {}
        self.patterns = []
        self.current_pattern_task = None  # Track the running task for presets
        self.initUI()
        self.light_state_updated.connect(self.on_light_state_updated)
        QTimer.singleShot(1000, self.refreshLights)
        # Connect signal for updating light state
        self.light_state_updated.connect(self.on_light_state_updated)
        self.patternListWidget.itemSelectionChanged.connect(self.display_selected_pattern_description)

        # Start discovery on initialization
        QTimer.singleShot(1000, self.refreshLights)

    def initUI(self):
        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle('WiZ Light Control')
        self.setWindowIcon(load_icon())  # Load the icon dynamically
        self.statusLabel = QLabel("Welcome to WiZ Light Control v 0.03", self)

        # Create the main layout and tab widget
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        # Device List Tab
        self.deviceListTab = QWidget()
        self.tabs.addTab(self.deviceListTab, "Device List")
        self.deviceListLayout = QVBoxLayout(self.deviceListTab)
        self.deviceListLayout.addWidget(self.statusLabel)

        self.listWidget = QListWidget(self)
        self.deviceListLayout.addWidget(self.listWidget)

        self.refreshButton = QPushButton('Refresh', self)
        self.refreshButton.clicked.connect(self.refreshLights)
        self.deviceListLayout.addWidget(self.refreshButton)

        self.renameButton = QPushButton('Rename Light', self)
        self.renameButton.clicked.connect(self.renameLight)
        self.deviceListLayout.addWidget(self.renameButton)

        # Light Controls Tab
        self.lightControlsTab = QWidget()
        self.tabs.addTab(self.lightControlsTab, "Light Controls")
        self.lightControlsLayout = QVBoxLayout(self.lightControlsTab)

        # Group Management
        self.groupBox = QGroupBox("Select Lights for Group Action", self.lightControlsTab)
        self.lightControlsLayout.addWidget(self.groupBox)
        self.groupBoxLayout = QVBoxLayout()

        self.lightCheckBoxes = {}
        self.groupBox.setLayout(self.groupBoxLayout)
        # Scrollable area for checkboxes
        self.ipListContainer = QScrollArea(self.lightControlsTab)
        self.ipListContainer.setWidgetResizable(True)  # Allow scrolling as more items are added
        self.lightControlsLayout.addWidget(self.ipListContainer)
        
        self.applyGroupColorButton = QPushButton('Apply Color to Group', self.groupBox)
        self.applyGroupColorButton.clicked.connect(self.applyToGroup)
        self.groupBoxLayout.addWidget(self.applyGroupColorButton)

        # Brightness Label
        self.brightnessLabel = QLabel("Brightness: 255", self)
        self.brightnessSlider = QSlider(Qt.Horizontal, self)
        self.brightnessSlider.setMaximum(255)
        self.brightnessSlider.setValue(255)
        self.brightnessSlider.valueChanged.connect(self.updateBrightness)
        self.lightControlsLayout.addWidget(self.brightnessLabel)
        self.lightControlsLayout.addWidget(self.brightnessSlider)


        self.groupBox.hide()  # Hide group box initially

        # Create scenes tab
        self.scenes_tab = QWidget()
        self.init_scenes_tab()
        self.tabs.addTab(self.scenes_tab, "Scenes")

        # Patterns Tab
        self.patternsTab = QWidget()
        self.tabs.addTab(self.patternsTab, "Patterns")
        self.patternsLayout = QVBoxLayout(self.patternsTab)
        # Add a QLabel to show the pattern description
        self.patternDescriptionLabel = QLabel("Select a pattern to see its description here.")
        self.patternsLayout.addWidget(self.patternDescriptionLabel)

        self.patternListWidget = QListWidget(self)
        self.patternsLayout.addWidget(self.patternListWidget)

        self.loadPatternsButton = QPushButton('Load Patterns', self)
        self.loadPatternsButton.clicked.connect(self.loadPatterns)
        self.patternsLayout.addWidget(self.loadPatternsButton)

        # Revised runPattern Button Connection
        self.runPatternButton = QPushButton('Run Selected Pattern', self)
        self.runPatternButton.clicked.connect(self.onRunPatternButtonClicked)  # Change this line
        self.patternsLayout.addWidget(self.runPatternButton)

        self.stopPatternButton = QPushButton('Stop Pattern', self)
        self.stopPatternButton.clicked.connect(self.stopPattern)
        self.patternsLayout.addWidget(self.stopPatternButton)

                # Add button to open Pattern Editor
        self.openPatternEditorButton = QPushButton("Open Pattern Editor", self)
        self.openPatternEditorButton.clicked.connect(self.onOpenPatternEditorButtonClicked)
        self.patternsLayout.addWidget(self.openPatternEditorButton)
    





        # Visualizer tab
        self.visualizer_tab = QWidget()
        self.setup_visualizer_tab()
        self.tabs.addTab(self.visualizer_tab, "Visualizer")

        # Create settings tab
        self.settings_tab = QWidget()
        self.init_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")





# DEVICES AND DISCOVERY

    @asyncSlot()
    async def onRunPatternButtonClicked(self):
        await self.runSelectedPattern()

    @asyncSlot()
    async def refreshLights(self):
        self.statusLabel.setText("Searching for connected devices...")
        await self.discover_lights()

    async def discover_lights(self):
        self.statusLabel.setText("Discovering lights...")
        self.lights = []  # Clear previously discovered lights before starting a new search
        
        # Retrieve the broadcast address from the configuration (you can change this as needed)
        broadcast_address = self.get_broadcast_address()  # This method can return a default or user-configured value

        retry_attempts = 3  # Set retry attempts to 3
        attempt = 0

        while attempt < retry_attempts:
            try:
                lights = await discovery.discover_lights(broadcast_space=broadcast_address)
                if not lights:
                    raise Exception("No lights found.")
                print(f"Discovered lights: {lights}")
                self.on_discovery_completed(lights)
                return  # Exit if discovery is successful
            except Exception as e:
                print(f"Error during discovery: {e}")
                self.statusLabel.setText(f"Error discovering lights. Retrying... ({attempt + 1}/{retry_attempts})")
                await asyncio.sleep(1)  # Optional: Add a short delay before retrying
                attempt += 1

        # If we reach this point, the discovery failed after 3 attempts
        self.statusLabel.setText("Failed to discover lights after 3 attempts. Please check your network.")

    def get_broadcast_address(self):
        # This is where you retrieve or set the broadcast address, 
        # you can change this to a user-configured value or a default.
        return "255.255.255.255"  # Default broadcast address, change as needed.

    def on_discovery_completed(self, lights):
        # Update self.lights with the newly discovered lights
        self.lights = lights

        # Clear the listWidget to avoid duplicate entries
        self.listWidget.clear()
        self.statusLabel.setText(f"Discovery completed. {len(lights)} light(s) found.")

        if not self.lights:
            self.statusLabel.setText("No lights found. Please check your network and try again.")
        else:
            for light in self.lights:
                # Set or update the light's name if not already named
                if light.ip not in self.light_names or not self.light_names[light.ip]:
                    self.light_names[light.ip] = light.ip  # Use IP as fallback if no name

                # Ensure each light has a checkbox, or create one if it doesn’t
                light_name = self.light_names[light.ip]
                if light.ip not in self.lightCheckBoxes:
                    checkbox = QCheckBox(light_name, self.groupBox)
                    self.lightCheckBoxes[light.ip] = checkbox
                    self.groupBoxLayout.addWidget(checkbox)
                else:
                    # Update checkbox text if the name has changed
                    self.lightCheckBoxes[light.ip].setText(light_name)

                # Asynchronously update the light's state in the list widget
                asyncio.create_task(self.update_light_state(light))

            self.groupBox.show()

    def on_light_state_updated(self, ip, light_info):
        """Update the main device list with the new light state."""
        for index in range(self.listWidget.count()):
            if self.listWidget.item(index).text().startswith(ip):
                self.listWidget.item(index).setText(light_info)
                return
        self.listWidget.addItem(light_info)

    async def update_light_state(self, light):
        try:
            # Retrieve the light's current state
            state = await light.updateState()
            light_name = self.light_names.get(light.ip, light.ip)

            # Format light info with state details
            light_info = f"{light_name} - {'ON' if state.get_state() else 'OFF'}, " \
                        f"Color: {state.get_rgb()}, Mode: {state.get_scene()}"

            # Update or add the light's information in the main device list
            for index in range(self.listWidget.count()):
                if self.listWidget.item(index).text().startswith(light.ip):
                    self.listWidget.item(index).setText(light_info)
                    return

            # Add the light info if not already present in the list
            self.listWidget.addItem(light_info)

        except Exception as e:
            print(f"Error updating light {light.ip}: {e}")

    @asyncSlot()
    async def renameLight(self):
        current_item = self.listWidget.currentItem()
        if current_item:
            current_name = current_item.text().split(' - ')[0]
            new_name, ok = QInputDialog.getText(self, 'Rename Light', 'Enter new name:', text=current_name)
            if ok and new_name:
                for light in self.lights:
                    if self.light_names.get(light.ip, light.ip) == current_name:
                        self.light_names[light.ip] = new_name
                        break
                self.listWidget.clear()
                for light in self.lights:
                    state = await light.updateState()
                    light_name = self.light_names.get(light.ip, light.ip)
                    is_on = state.get_state()
                    self.listWidget.addItem(f"{light_name} - {'ON' if is_on else 'OFF'}")
                for light in self.lights:
                    if light.ip in self.lightCheckBoxes:
                        self.lightCheckBoxes[light.ip].setText(self.light_names.get(light.ip, light.ip))

    def openColorPicker(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.setLightColor(color)

    def setLightColor(self, color):
        rgb = (color.red(), color.green(), color.blue())
        current_item = self.listWidget.currentItem()
        if current_item:
            selected_ip = current_item.text().split(' - ')[0]
            for light in self.lights:
                if light.ip == selected_ip:
                    asyncio.create_task(light.turn_on(PilotBuilder(rgb=rgb)))
                    break
        else:
            self.statusLabel.setText("Please select a light to change its color.")

    def get_broadcast_address(self):
        # You can replace this with the logic to get the current broadcast address
        return "255.255.255.255"  # Default address

    def save_broadcast_address(self):
        # Get the text from the broadcast input field
        broadcast_address = self.broadcast_input.text()

        # Validate the broadcast address (simple example, you can improve this)
        if self.is_valid_broadcast_address(broadcast_address):
            # Save the broadcast address to a config or internal variable
            self.broadcast_address = broadcast_address
            print(f"Broadcast address saved: {broadcast_address}")
            self.statusLabel.setText("Broadcast address saved successfully.")
        else:
            self.statusLabel.setText("Invalid broadcast address. Please try again.")

    def is_valid_broadcast_address(self, address):
        # Simple check to ensure the address looks like a valid broadcast address
        # This can be improved to be more robust if needed
        parts = address.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit() or not 0 <= int(part) <= 255:
                return False
        return True




# PRESETS



    @asyncSlot()
    async def updateBrightness(self):
        """
        Update the brightness of the selected lights in the group in real-time and update the label.
        """
        brightness = self.brightnessSlider.value()  # Get the brightness value from the slider
        self.brightnessLabel.setText(f"Brightness: {brightness}")  # Update the brightness label

        selected_lights = [ip for ip, checkbox in self.lightCheckBoxes.items() if checkbox.isChecked()]

        for light in self.lights:
            if light.ip in selected_lights:
                try:
                    # Use PilotBuilder to create a new state with the desired brightness
                    pilot = PilotBuilder(brightness=brightness)
                    await light.turn_on(pilot)  # Turn on the light with the updated brightness
                except Exception as e:
                    print(f"Error updating brightness for light {light.ip}: {e}")



    @asyncSlot()
    async def applyToGroup(self):
        selected_lights = [ip for ip, checkbox in self.lightCheckBoxes.items() if checkbox.isChecked()]
        color = QColorDialog.getColor()
        if color.isValid():
            rgb = (color.red(), color.green(), color.blue())
            for light in self.lights:
                if light.ip in selected_lights:
                    await light.turn_on(PilotBuilder(rgb=rgb))







# VISUALIZER


    def setup_visualizer_tab(self):
        layout = QVBoxLayout()

        # Button to open config_gui.py
        open_config_button = QPushButton("Open Frequency Visualizer")
        open_config_button.clicked.connect(self.open_config_gui)
        layout.addWidget(open_config_button)

        # Button to open config_gui.py
        open_config_button = QPushButton("Open Volume Visualizer")
        open_config_button.clicked.connect(self.open_volume_config_gui)
        layout.addWidget(open_config_button)

        self.visualizer_tab.setLayout(layout)






    def open_config_gui(self):
        current_theme = self.theme_combo.currentText()

        try:
            # Determine the executable path based on the environment
            if getattr(sys, '_MEIPASS', False):  # Packaged environment
                # _MEIPASS already points to the root extraction directory
                script_path = os.path.join(sys._MEIPASS, 'config_gui.exe')
            else:  # Development environment
                base_path = os.path.abspath(".")
                script_path = os.path.join(base_path, 'config_gui.exe')

            print(f"Trying to open config_gui.exe from: {script_path}")  # Debug statement

            subprocess.Popen([script_path, current_theme])  # Pass the theme as an argument
        except FileNotFoundError:
            print(f"config_gui.exe not found at: {script_path}")


    def open_volume_config_gui(self):
        current_theme = self.theme_combo.currentText()

        try:
            # Determine the executable path based on the environment
            if getattr(sys, '_MEIPASS', False):  # Packaged environment
                # _MEIPASS already points to the root extraction directory
                script_path = os.path.join(sys._MEIPASS, 'volume_config_gui.exe')
            else:  # Development environment
                base_path = os.path.abspath(".")
                script_path = os.path.join(base_path, 'volume_config_gui.exe')

            print(f"Trying to open volume_config_gui.exe from: {script_path}")  # Debugging

            subprocess.Popen([script_path, current_theme])  # Pass theme
        except FileNotFoundError:
            print(f"volume_config_gui.exe not found at: {script_path}")














# PATTERNS

# Run patterns
    def onOpenPatternEditorButtonClicked(self):
        self.open_pattern_editor()

    def open_pattern_editor(self):
        # Check if pattern editor is already open
        if hasattr(self, 'pattern_editor') and self.pattern_editor.isVisible():
            self.pattern_editor.raise_()
            self.pattern_editor.activateWindow()
        else:
            # Create and show the pattern editor, passing the discovered lights
            lights_list = [{"ip": light.ip, "name": self.light_names.get(light.ip, light.ip)} for light in self.lights]
            self.pattern_editor = PatternEditor(discovered_lights=lights_list)
            self.pattern_editor.show()


    async def runSelectedPattern(self):
        """Retrieve and run the selected pattern."""
        current_item = self.patternListWidget.currentItem()
        if current_item:
            pattern_name = current_item.text()
            print(f"Attempting to run pattern: {pattern_name}")
            for pattern in self.patterns:
                if pattern.get("name") == pattern_name:
                    await self.startPattern(pattern)
                    break
        else:
            print("No pattern selected.")

    async def runPattern(self, pattern):
        """Updates lights according to the specified pattern."""
        steps = pattern.get("steps", [])
        try:
            while True:  # Infinite loop
                for step in steps:
                    duration = step.get("duration", 0) / 1000  # Convert milliseconds to seconds
                    tasks = []

                    if step.get("light_ip") == "all":
                        # Apply to all lights if "all" is specified as the light_ip
                        action = step.get("action")
                        for light in self.lights:
                            tasks.append(self.performAction(light, action, step))
                    else:
                        # Apply to specific lights
                        light_ips = step.get("light_ip")
                        if isinstance(light_ips, str):
                            light_ips = [light_ips]  # Ensure light_ips is a list
                        for light_ip in light_ips:
                            light = next((l for l in self.lights if l.ip == light_ip), None)
                            if light:
                                action = step.get("action")
                                tasks.append(self.performAction(light, action, step))
                            else:
                                print(f"Light with IP {light_ip} not found.")

                    if tasks:
                        await asyncio.gather(*tasks)
                    else:
                        print(f"No tasks to execute for step: {step}")
                    
                    await asyncio.sleep(duration)  # Delay based on duration
        except asyncio.CancelledError:
            print("Pattern task was canceled.")


    async def performAction(self, light, action, light_info):
        """Perform light action with a timeout to avoid freezing."""
        try:
            if action == "set_color":
                color = light_info.get("color", [255, 255, 255])
                brightness = light_info.get("brightness", 255)

                # Ensure color components are integers
                color = {k: int(v) for k, v in color.items()}

                # Debugging output to check types
                print(f"Color: {color}, Type: {type(color)}")
                print(f"Brightness: {brightness}, Type: {type(brightness)}")

                await light.turn_on(PilotBuilder(rgb=(color['r'], color['g'], color['b']), brightness=brightness))
            elif action == "turn_off":
                await light.turn_off()
        except asyncio.TimeoutError:
            print(f"Timeout while performing action '{action}' for light {light.ip}")
        except Exception as e:
            print(f"Error while performing action '{action}' for light {light.ip}: {e}")


    async def startPattern(self, pattern):
        """Starts a new pattern, stopping any existing one first."""
        if self.current_pattern_task:
            self.current_pattern_task.cancel()
            try:
                await self.current_pattern_task  # Wait for the task to be canceled
            except asyncio.CancelledError:
                pass
            print("Stopped previous pattern task.")
        self.current_pattern_task = asyncio.create_task(self.runPattern(pattern))
        print(f"Started new pattern task for {pattern.get('name')}")

    def stopPattern(self):
        """Stops the currently running pattern."""
        if self.current_pattern_task:
            self.current_pattern_task.cancel()
            self.current_pattern_task = None
            print("Pattern stopped.")  # Debugging line

    def loadPatterns(self):
        self.patternListWidget.clear()
        self.patterns = []  # Reset patterns list

        if getattr(sys, '_MEIPASS', False):  # If running as a packaged app
            pattern_dir = os.path.join(sys._MEIPASS, 'patterns')
        else:
            pattern_dir = os.path.join(os.path.abspath("."), 'patterns')

        print(f"Pattern directory path: {pattern_dir}")  # Debug statement

        try:
            pattern_files = [f for f in os.listdir(pattern_dir) if f.endswith(".json")]

            # Sort the pattern filenames alphabetically
            pattern_files.sort()

            for filename in pattern_files:
                try:
                    with open(os.path.join(pattern_dir, filename)) as f:
                        pattern = json.load(f)
                        self.patterns.append(pattern)
                        self.patternListWidget.addItem(pattern.get("name", "Unnamed Pattern"))
                except json.JSONDecodeError as e:
                    print(f"Error loading {filename}: {e}")
                except Exception as e:
                    print(f"Unexpected error with {filename}: {e}")

            if not self.patternListWidget.count():
                self.patternListWidget.addItem("No patterns found.")
        except FileNotFoundError:
            print(f"Pattern directory not found: {pattern_dir}")
            self.patternListWidget.addItem("No patterns found.")


    def display_selected_pattern_description(self):
        current_item = self.patternListWidget.currentItem()
        if current_item:
            pattern_name = current_item.text()
            for pattern in self.patterns:
                if pattern.get("name") == pattern_name:
                    description = pattern.get("description", "No description available.")
                    self.patternDescriptionLabel.setText(description)
                    return
        self.patternDescriptionLabel.setText("Select a pattern to see its description here.")


# SETTINGS



    def init_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)
        
        # Label and input for broadcast address
        self.broadcast_label = QLabel("Set Broadcast Address:", self)
        self.broadcast_input = QLineEdit(self)
        self.broadcast_input.setText(self.get_broadcast_address())  # Pre-fill with current address if available
        self.broadcast_input.setPlaceholderText("Enter Broadcast Address (e.g., 192.168.1.255)")

        # Add the label and input to the layout
        layout.addWidget(self.broadcast_label)
        layout.addWidget(self.broadcast_input)

        # Button to save the broadcast address
        self.save_broadcast_button = QPushButton("Save Broadcast Address", self)
        self.save_broadcast_button.clicked.connect(self.save_broadcast_address)

        # Add the button to the layout
        layout.addWidget(self.save_broadcast_button)

        # Set the layout for the settings tab
        self.settings_tab.setLayout(layout)

        # Theme selection dropdown
        theme_label = QLabel("Select Theme:")
        self.theme_combo = QComboBox()
        
        # Load available theme files in themes directory
        if getattr(sys, '_MEIPASS', False):  # If running as a packaged app
            base_path = os.path.join(sys._MEIPASS, 'themes')
        else:
            base_path = os.path.join(os.path.abspath("."), 'themes')

        print(f"Theme directory path: {base_path}")  # Debug statement

        try:
            theme_files = [f.replace('.qss', '') for f in os.listdir(base_path) if f.endswith('.qss')]
        except FileNotFoundError:
            theme_files = []  # No themes available

        # Check for dark and light themes, and place them first and second in the list
        if 'dark' in theme_files:
            theme_files.remove('dark')
            theme_files.insert(0, 'dark')
        
        if 'light' in theme_files:
            theme_files.remove('light')
            theme_files.insert(1, 'light')
        
        # Add theme files to the combobox
        self.theme_combo.addItems(theme_files)
        
        # Set default theme to 'dark' if available, else 'light' if available, else first theme in list
        if theme_files:
            self.theme_combo.setCurrentText('dark' if 'dark' in theme_files else 'light' if 'light' in theme_files else theme_files[0])
        else:
            self.theme_combo.setCurrentText('')  # No themes available
        
        # Connect the theme change to update immediately
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)



    @pyqtSlot(str)
    def change_theme(self, theme_name):
        """
        Change the application theme by loading the appropriate .qss file from the themes folder.
        """
        load_stylesheet(QApplication.instance(), theme_name)
        self.apply_theme_effects(theme_name)


    def apply_drop_shadow(self, widget):
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(10)
        shadow_effect.setColor(QColor(50, 50, 50, 120))
        shadow_effect.setOffset(5, 5)
        widget.setGraphicsEffect(shadow_effect)

    def apply_blur_effect(self, widget):
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(0)
        widget.setGraphicsEffect(blur_effect)

    def apply_theme_effects(self, theme_name="dark"):
        theme_effects = load_theme_effects(theme_name)
        
        # Apply shadow effect if enabled in the theme
        if theme_effects.get("shadow", False):
            self.apply_drop_shadow(self)
        
        # Apply blur effect if enabled
        if theme_effects.get("blur", False):
            self.apply_blur_effect(self)

    def closeEvent(self, event):
        self.stopPattern()  # Stop any running patterns
        event.accept()  # Accept the event to close the application






# SCENES

    def init_scenes_tab(self):
        # Layout for the Scenes tab
        layout = QVBoxLayout(self.scenes_tab)  # Set the layout on scenes_tab directly

        # Scene Selection ComboBox
        self.sceneComboBox = QComboBox(self)
        self.sceneComboBox.addItems(SCENES.values())
        layout.addWidget(self.sceneComboBox)

        # Speed Slider
        self.speedLabel = QLabel("Speed: 100", self)
        layout.addWidget(self.speedLabel)
        self.speedSlider = QSlider(Qt.Horizontal, self)
        self.speedSlider.setRange(10, 200)  # Speed percentage mapped to the acceptable range
        self.speedSlider.setValue(100)  # Default value within range
        self.speedSlider.valueChanged.connect(self.updateSpeed)
        layout.addWidget(self.speedSlider)

        # Dimming Slider
        self.dimmingLabel = QLabel("Brightness: 100%", self)
        layout.addWidget(self.dimmingLabel)
        self.dimmingSlider = QSlider(Qt.Horizontal, self)
        self.dimmingSlider.setRange(0, 100)  # Dimming percentage
        self.dimmingSlider.setValue(100)
        self.dimmingSlider.valueChanged.connect(self.updateDimming)
        layout.addWidget(self.dimmingSlider)

        # Apply Scene Button
        self.applySceneButton = QPushButton("Apply Scene", self)
        self.applySceneButton.clicked.connect(lambda: asyncio.create_task(self.applyScene()))
        layout.addWidget(self.applySceneButton)

    def updateSpeed(self, value):
        # Ensure the value is between 10 and 200
        self.current_speed = max(10, min(value, 200))
        self.speedLabel.setText(f"Speed: {self.current_speed}")


    def updateDimming(self, value):
        self.current_dimming = value
        self.dimmingLabel.setText(f"Dimming: {value}%")

    async def applyScene(self):
        """Apply the selected scene with current speed and dimming values."""
        selected_scene = self.sceneComboBox.currentText()
        scene_id = SCENE_NAME_TO_ID.get(selected_scene)
        selected_lights = [ip for ip, checkbox in self.lightCheckBoxes.items() if checkbox.isChecked()]

        if scene_id is not None:
            # Clamp speed value to be within 10 and 200
            speed = max(10, min(self.current_speed, 200))
            brightness = int((self.current_dimming / 100) * 255)  # Mapping to 0-255 range

            if selected_lights:
                # Apply the scene to each selected light in the Light Controls tab
                tasks = []
                for ip in selected_lights:
                    light = next((l for l in self.lights if l.ip == ip), None)
                    if light:
                        pilot = PilotBuilder(scene=scene_id, speed=speed, brightness=brightness)
                        tasks.append(light.turn_on(pilot))
                await asyncio.gather(*tasks)
            else:
                # Apply the scene to the selected light in the Device List tab
                current_item = self.listWidget.currentItem()
                if current_item:
                    selected_ip = current_item.text().split(' - ')[0]
                    light = next((l for l in self.lights if l.ip == selected_ip), None)
                    if light:
                        pilot = PilotBuilder(scene=scene_id, speed=speed, brightness=brightness)
                        await light.turn_on(pilot)
                else:
                    print("No lights selected for applying the scene.")
        else:
            print("Scene not found or invalid scene selected.")







if __name__ == "__main__":
    app = QApplication(sys.argv)
    load_stylesheet(app, "dark")  # Load the "dark" theme by default
    pyi_splash.close()
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    mainWindow = LightApp()
    mainWindow.show()
    with loop:
        loop.run_forever()
