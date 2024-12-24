import sys
import json
import subprocess
import threading
import asyncio
import ast
import os
import psutil 
import pyaudio
import pyi_splash

from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QComboBox, QGraphicsDropShadowEffect, QGraphicsBlurEffect, QColorDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QCheckBox, QPushButton, QLabel, QGroupBox, QScrollArea, QMessageBox, QListWidget, QSizePolicy
from pywizlight import discovery


def load_icon():
    """
    Load the program's icon dynamically, considering both development and packaged environments.
    """
    if getattr(sys, '_MEIPASS', False):  # If running as a packaged app
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")

    icon_path = os.path.join(base_path, 'icon', 'volume.ico')
    print(f"Trying to load icon from: {icon_path}")  # Debug statement

    return QIcon(icon_path)

def get_default_input_device():
    """
    Get the name and index of the default audio input device (recording device) using PyAudio.
    """
    p = pyaudio.PyAudio()
    try:
        # Get default input device info (recording device)
        default_device_index = p.get_default_input_device_info()["index"]
        default_device_info = p.get_device_info_by_index(default_device_index)
        print("Default input device info:", default_device_info)  # Debug statement
        return default_device_index, default_device_info["name"]
    except Exception as e:
        print(f"Error retrieving default input device: {e}")
        return None, "Unknown"
    finally:
        p.terminate()


def stop_visualizer():
    global visualizer_process
    if visualizer_process:
        visualizer_process.terminate()
        visualizer_process = None
        print("Visualizer stopped.")

class DiscoveryThread(QThread):
    # Signal to emit the discovered lights
    discovered = pyqtSignal(list)

    def __init__(self, discover_lights_async, parent=None):
        super().__init__(parent)
        self.discover_lights_async = discover_lights_async

    def run(self):
        # Run the discovery in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            discovered_lights = loop.run_until_complete(self.discover_lights_async())
            self.discovered.emit(discovered_lights)  # Emit the discovered lights
        finally:
            loop.close()

# Define the path to the theme effects settings file dynamically
if getattr(sys, 'frozen', False):  # If running as a packaged app
    base_path = os.path.dirname(os.path.abspath(sys.executable))  # Path to the executable in packaged mode
else:
    base_path = os.path.abspath(".")  # For development or when not packaged

THEME_EFFECTS_PATH = os.path.join(base_path, "themes", "theme_effects.json")

print(THEME_EFFECTS_PATH)  # For debugging purposes to verify the path

def load_stylesheet(app, theme_name="dark"):
    """
    Load a stylesheet based on the theme name from the 'themes' folder.
    """
    if getattr(sys, 'frozen', False):  # If running as a packaged app
        base_path = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'themes')
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
    if getattr(sys, 'frozen', False):  # If running as a packaged app
        base_path = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'themes')
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


# Global variable to keep track of the process
visualizer_process = None

# Load the configuration JSON file
def load_config(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

# Save the configuration to a file
def save_config(file_path, config):
    with open(file_path, 'w') as f:
        json.dump(config, f, indent=4)




class ConfigEditor(QWidget):
    update_status = pyqtSignal(str)

    def __init__(self, config_file, default_file, theme_name='dark'):
        super().__init__()
        self.update_status.connect(self.update_status_label)  # Connect signal to update function

        self.statusLabel = QLabel("WiZ Volume Visualizer Control", self)
        self.config_file = config_file
        self.default_file = default_file

        # Load the current configuration
        try:
            self.config = load_config(self.config_file)
        except FileNotFoundError:
            print(f"Configuration file not found: {self.config_file}")
            QMessageBox.critical(self, "Error", "Configuration file is missing!")
            sys.exit(1)


        self.setWindowTitle("WiZ Visualizer Config Editor")
        self.setGeometry(100, 100, 600, 800)
        self.setWindowIcon(load_icon())  # Load the icon dynamically

        # Main layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.statusLabel)
        # Top buttons layout
        self.top_button_layout = QHBoxLayout()

        # Start button to launch visualizer
        self.start_button = QPushButton("Start Visualizer")
        self.start_button.clicked.connect(self.launch_visualizer_thread)
        self.top_button_layout.addWidget(self.start_button)

        # Stop button to stop visualizer
        self.stop_button = QPushButton("Stop Visualizer")
        self.stop_button.clicked.connect(stop_visualizer)
        self.top_button_layout.addWidget(self.stop_button)

        self.save_button = QPushButton("Save Configuration")
        self.save_button.clicked.connect(self.save_config_to_file)
        self.top_button_layout.addWidget(self.save_button)

        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self.confirm_reset)
        self.top_button_layout.addWidget(self.reset_button)

        self.layout.addLayout(self.top_button_layout)

        # Scroll Area setup for settings
        self.settings_layout = QVBoxLayout()
        self.create_audio_settings()
        self.create_network_settings()
        self.create_visualization_settings()
        self.create_brightness_settings()
        self.create_feature_settings()
        self.create_color_settings()
        self.create_audio_processing_settings()

        scroll_area_widget = QWidget()
        scroll_area_widget.setLayout(self.settings_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_area_widget)

        # Set the scroll area as part of the main layout
        self.layout.addWidget(scroll_area)

        # Bottom buttons layout
        self.bottom_button_layout = QHBoxLayout()
        self.bottom_button_layout.addWidget(self.save_button)
        self.bottom_button_layout.addWidget(self.reset_button)

        self.layout.addLayout(self.bottom_button_layout)
        self.setLayout(self.layout)


    # THEME DEFENITIONS


    def update_status_label(self, message):
        """Update the status label with a new message."""
        self.statusLabel.setText(message)

    def load_stylesheet(app, theme_name="dark"):
        path = os.path.join("themes", f"{theme_name}.qss")
        try:
            with open(path, "r") as f:
                stylesheet = f.read()
                app.setStyleSheet(stylesheet)
        except FileNotFoundError:
            print(f"Stylesheet not found: {path}")


    def apply_theme(self, theme_name):
        """Apply both stylesheet and visual effects for the theme."""
        load_stylesheet(QApplication.instance(), theme_name)
        self.apply_theme_effects(theme_name)

    def apply_theme_effects(self, theme_name):
        """Apply theme-specific visual effects such as shadow and blur."""
        theme_effects = load_theme_effects(theme_name)

        if theme_effects.get("shadow", False):
            self.apply_drop_shadow(self)

        if theme_effects.get("blur", False):
            self.apply_blur_effect(self)

    def apply_drop_shadow(self, widget):
        """Apply drop shadow effect to the widget."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(50, 50, 50, 120))
        shadow.setOffset(5, 5)
        widget.setGraphicsEffect(shadow)

    def apply_blur_effect(self, widget):
        """Apply blur effect to the widget."""
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(10)
        widget.setGraphicsEffect(blur)


#   VISUALIZER


    # Function to launch the C++ visualizer
    def start_visualizer(self):
        global visualizer_process
        # Check if the visualizer process is already running
        if visualizer_process is not None and psutil.pid_exists(visualizer_process.pid):
            self.update_status.emit("Visualizer is already running.")
            return  # Prevent starting another instance

        # Determine the directory where the packaged files are extracted
        if getattr(sys, 'frozen', False):  # Check if we're running in a packaged environment
            # If running as a packaged app (from PyInstaller), use the executable's directory
            base_path = os.path.dirname(os.path.abspath(sys.executable))
        else:
            # Use the current working directory
            base_path = os.getcwd()

        # Path to the wiz_visualizer executable
        visualizer_executable = os.path.join(base_path, "wiz_visualizer.exe")
        # Path to the volume_config.json
        config_file = os.path.join(base_path, "volume_config.json")

        # Print paths for debugging
        print(f"Current working directory: {os.getcwd()}")
        print(f"Base path: {base_path}")
        print(f"Visualizer executable: {visualizer_executable}")
        print(f"Config file: {config_file}")

        # Launch the visualizer process
        try:
            visualizer_process = subprocess.Popen(
                [visualizer_executable, config_file], 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            # Wait for the process to complete and capture the error (if any)
            stdout, stderr = visualizer_process.communicate()

            # If there is an error, display it in the QLabel
            if stderr:
                self.update_status.emit(f"PortAudio error: {stderr.decode()}")
            else:
                self.update_status.emit("WiZ Volume Visualizer Control")
        except Exception as e:
            self.update_status.emit(f"Error starting visualizer: {e}")
            print(f"Error: {e}")






    # Function to stop the C++ visualizer
    def stop_visualizer(self):
        global visualizer_process
        if visualizer_process:
            try:
                # Attempt to terminate the visualizer process gracefully
                visualizer_process.terminate()
                visualizer_process.wait(timeout=5)  # Wait for it to stop
                visualizer_process = None
                self.update_status.emit("Visualizer stopped successfully.")
            except subprocess.TimeoutExpired:
                visualizer_process.kill()  # Force terminate if it doesn't stop in time
                visualizer_process = None
                self.update_status.emit("Visualizer stopped forcefully.")


    def update_status_label(self, message):
        """Update the status label with a new message."""
        self.statusLabel.setText(message)

    def launch_visualizer_thread(self):
        self.update_status.emit("Launching Visualizer...")
        # Save the current config before launching the visualizer
        self.save_config_to_file()
        
        # Start the visualizer in a separate thread (with a callable method)
        thread = threading.Thread(target=self.run_visualizer_in_thread)
        thread.start()

    def stop_visualizer_thread(self):
        """Stop the visualizer in a separate thread."""
        thread = threading.Thread(target=self.run_stop_visualizer_in_thread)
        thread.start()

    def run_visualizer_in_thread(self):
        """This method will run the visualizer in a separate thread."""
        self.start_visualizer()  # Call the method to start visualizer

    def run_stop_visualizer_in_thread(self):
        """This method will stop the visualizer in a separate thread."""
        stop_visualizer()  # Call the method to stop visualizer


    def create_visualization_settings(self):
        visualization_group = QGroupBox("Visualization Settings")
        layout = QFormLayout()

        tooltips = {
            "beat_threshold": "Threshold for beat detection.",
            "color_cycle_duration_ms": "Duration for color cycle in milliseconds.",
            "drum_break_threshold": "Threshold for drum break detection.",
            "drum_break_interval_ms": "Interval for drum break effects in milliseconds.",
            "bpm_interval_ms": "Interval for BPM calculation in milliseconds.",
            "min_bpm": "Minimum BPM for detection.",
            "max_bpm": "Maximum BPM for detection.",
            "min_update_interval_ms": "Minimum interval for updating visual effects in milliseconds.",
            "upper_threshold": "Upper threshold for visual effect intensity.",
            "lower_threshold": "Lower threshold for visual effect intensity.",
            "beat_history_size": "Number of past volume readings used for beat detection smoothing.",
            "drum_break_history_size": "Number of past volume readings used for drum break detection smoothing."
        }

        for key, value in self.config["visualization"].items():
            if isinstance(value, bool):
                widget = QCheckBox()
                widget.setChecked(value)
            else:
                widget = QLineEdit(str(value))

            layout.addRow(key.replace('_', ' ').capitalize(), widget)
            widget.setToolTip(tooltips.get(key, ""))
            setattr(self, key, widget)

        visualization_group.setLayout(layout)
        self.settings_layout.addWidget(visualization_group)

    def create_brightness_settings(self):
        brightness_group = QGroupBox("Brightness Settings")
        layout = QFormLayout()

        tooltips = {
            "user_brightness": "User-defined brightness level.",
            "min_brightness": "Minimum brightness level.",
            "enable_dynamic_brightness": "Enable dynamic brightness adjustment."
        }

        for key, value in self.config["brightness"].items():
            widget = QCheckBox() if isinstance(value, bool) else QLineEdit(str(value))
            if isinstance(value, bool):
                widget.setChecked(value)
            layout.addRow(key.replace('_', ' ').capitalize(), widget)
            widget.setToolTip(tooltips.get(key, ""))
            setattr(self, key, widget)

        brightness_group.setLayout(layout)
        self.settings_layout.addWidget(brightness_group)

    def create_feature_settings(self):
        features_group = QGroupBox("Features")
        layout = QFormLayout()

        tooltips = {
            "enable_smoothing": "Enable smoothing of visual effects.",
            "reverse_colors": "Enable color reversal.",
            "random_reversal_interval": "Enable random reversal intervals.",
            "reversal_interval_min": "Minimum interval for color reversal in milliseconds.",
            "reversal_interval_max": "Maximum interval for color reversal in milliseconds.",
            "enable_drum_break_detection": "Enable detection of drum breaks.",
            "enable_beat_detection": "Enable detection of beats.",
            "enable_tempo_based_intensity": "Enable tempo-based intensity adjustments."
        }

        for key, value in self.config["features"].items():
            widget = QCheckBox() if isinstance(value, bool) else QLineEdit(str(value))
            if isinstance(value, bool):
                widget.setChecked(value)
            layout.addRow(key.replace('_', ' ').capitalize(), widget)
            widget.setToolTip(tooltips.get(key, ""))
            setattr(self, key, widget)

        features_group.setLayout(layout)
        self.settings_layout.addWidget(features_group)

    def create_color_settings(self):
        color_group = QGroupBox("Color Settings")
        layout = QFormLayout()

        for color_type, colors in self.config["color_settings"].items():
            label = QLabel(f"{color_type.replace('_', ' ').capitalize()}:")
            layout.addRow(label)

            for i, color in enumerate(colors):
                color_widget_key = f"{color_type}_{i}"
                color_input = QLineEdit(f"RGB({color[0]}, {color[1]}, {color[2]})")
                layout.addRow(f"Color {i + 1}: {color[0]}, {color[1]}, {color[2]}", color_input)
                color_input.setReadOnly(True)
                color_input.setStyleSheet(f"background-color: rgb({color[0]}, {color[1]}, {color[2]});")
                setattr(self, color_widget_key, color_input)

                color_picker_button = QPushButton("Pick Color")
                color_picker_button.clicked.connect(lambda checked, color_input=color_input: self.open_color_picker(color_input))
                layout.addRow(color_picker_button)

        color_group.setLayout(layout)
        self.settings_layout.addWidget(color_group)

    def open_color_picker(self, color_input):
        color = QColorDialog.getColor()
        if color.isValid():
            color_input.setText(f"RGB({color.red()}, {color.green()}, {color.blue()})")
            color_input.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")

    def create_audio_processing_settings(self):
        audio_processing_group = QGroupBox("Audio Processing Settings")
        layout = QFormLayout()

        tooltips = {
            "max_seen_volume": "Maximum volume seen for normalization.",
            "normalized_volume_factor": "Factor for normalizing volume."
        }

        for key, value in self.config["audio_processing"].items():
            widget = QLineEdit(str(value))
            layout.addRow(key.replace('_', ' ').capitalize(), widget)
            widget.setToolTip(tooltips.get(key, ""))
            setattr(self, key, widget)

        audio_processing_group.setLayout(layout)
        self.settings_layout.addWidget(audio_processing_group)


#   AUDIO DEVICES


    # Display the current default audio device at the top
        self.default_device_label = QLabel("Default Output Device: Fetching...")
        self.layout.addWidget(self.default_device_label)

        # Fetch and set the default device name
        default_device = get_default_input_device()
        self.default_device_label.setText(f"Default Output Device: {default_device}")

    def update_default_device_label(self):
        """
        Update the default device label with the index and name of the default input device
        when the user refreshes the device list.
        """
        default_device_index, default_device_name = get_default_input_device()
        if default_device_index is not None:
            self.default_device_label.setText(f"Default Input Device: {default_device_name} (Index: {default_device_index})")
        else:
            self.default_device_label.setText(f"Default Input Device: Unknown (Index: -1)")

    def create_audio_settings(self):
        """Create the Audio Settings section with dropdown and manual input toggle."""
        audio_group = QGroupBox("Audio Settings")
        layout = QFormLayout()

        # Tooltips for audio settings
        tooltips = {
            "sample_rate": "Sample rate for audio processing.",
            "frames_per_buffer": "Number of frames per buffer.",
            "num_channels": "Number of audio channels.",
            "device_index": "Index of the audio device to use."
        }

        # Dropdown for audio devices
        self.audio_device_dropdown = QComboBox()
        devices = self.list_audio_devices()  # Fetch available devices
        for index, name in devices:
            self.audio_device_dropdown.addItem(f"{index}: {name}", index)

        # Pre-select saved device index
        saved_device_index = self.config['audio'].get('device_index', -1)
        for i in range(self.audio_device_dropdown.count()):
            if self.audio_device_dropdown.itemData(i) == saved_device_index:
                self.audio_device_dropdown.setCurrentIndex(i)
                break

        # Manual input for device index
        self.audio_device_input = QLineEdit(str(saved_device_index))
        self.audio_device_input.setPlaceholderText("Enter device index manually")
        self.audio_device_input.setEnabled(False)  # Initially disable manual input

        # Toggle checkbox for manual input
        self.manual_input_checkbox = QCheckBox("Use Manual Input")
        self.manual_input_checkbox.setChecked(False)
        self.manual_input_checkbox.toggled.connect(self.toggle_manual_input)

        # Connect dropdown and manual input
        self.audio_device_dropdown.currentIndexChanged.connect(self.update_device_input_from_dropdown)
        self.audio_device_input.textChanged.connect(self.update_dropdown_from_device_input)

        # Add widgets to the form layout
        layout.addRow("Select Audio Device", self.audio_device_dropdown)
        layout.addRow(self.manual_input_checkbox)
        layout.addRow("Or Enter Device Index", self.audio_device_input)

        # Add other audio settings from the config
        for key, value in self.config["audio"].items():
            if key != "device_index":  # Exclude device_index as it's handled separately
                widget = QLineEdit(str(value))
                layout.addRow(key.replace('_', ' ').capitalize(), widget)
                widget.setToolTip(tooltips.get(key, ""))
                setattr(self, key, widget)

        # Add layout to the group and settings layout
        audio_group.setLayout(layout)
        self.settings_layout.addWidget(audio_group)
        
    # Toggle manual device selection
    def toggle_manual_input(self, checked):
        """Enable or disable manual input based on the checkbox."""
        self.audio_device_input.setEnabled(checked)
        self.audio_device_dropdown.setEnabled(not checked)

    def list_audio_devices(self):
        import pyaudio
        pa = pyaudio.PyAudio()
        devices = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            devices.append((i, info['name']))
        pa.terminate()
        return devices

    def update_device_input_from_dropdown(self):
        """Update manual input when a device is selected in the dropdown."""
        selected_index = self.audio_device_dropdown.currentData()
        if selected_index is not None:
            self.audio_device_input.setText(str(selected_index))

    def update_dropdown_from_device_input(self):
        self.statusLabel.setText("Searching for connected devices...")
        """Update dropdown selection based on manual input."""
        try:
            manual_index = int(self.audio_device_input.text())
            for i in range(self.audio_device_dropdown.count()):
                if self.audio_device_dropdown.itemData(i) == manual_index:
                    self.audio_device_dropdown.setCurrentIndex(i)
                    return
            self.audio_device_dropdown.setCurrentIndex(-1)  # Deselect if index not found
        except ValueError:
            self.audio_device_dropdown.setCurrentIndex(-1)  # Deselect for invalid input


#   LIGHT NETWORKINGING


    def create_network_settings(self):
        network_group = QGroupBox("Network Settings")
        layout = QFormLayout()

        # UDP Port input
        self.udp_port = QLineEdit(str(self.config['network']['udp_port']))
        layout.addRow("Udp port", self.udp_port)

        # Light IPs label and list
        light_ips_label = QLabel("Light IPs:")
        layout.addRow(light_ips_label)

        self.light_ip_list = QListWidget(self)

        # Set size policy to expand and adjust dynamically
        self.light_ip_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.light_ip_list.setMinimumHeight(100)  # Optional: Set a minimum height

        if isinstance(self.config['network']['light_ips'], list):
            self.light_ip_list.addItems(self.config['network']['light_ips'])

        layout.addRow(self.light_ip_list)


        # Manual IP entry
        self.light_ip_input = QLineEdit(self)
        self.light_ip_input.setPlaceholderText("Enter new light IP")
        layout.addRow(self.light_ip_input)

        # Add Light IP button
        self.add_light_ip_button = QPushButton("Add Light IP")
        self.add_light_ip_button.clicked.connect(self.add_light_ip)
        layout.addRow(self.add_light_ip_button)

        # Remove Light IP button
        self.remove_light_ip_button = QPushButton("Remove Selected Light IP")
        self.remove_light_ip_button.clicked.connect(self.remove_light_ip)
        layout.addRow(self.remove_light_ip_button)

        # Auto Detect button for discovering IPs on-demand
        self.auto_detect_button = QPushButton("Auto Detect Light IPs")
        self.auto_detect_button.clicked.connect(self.add_discovered_lights)
        layout.addRow(self.auto_detect_button)

        network_group.setLayout(layout)
        self.settings_layout.addWidget(network_group)

    # Method to add a new IP from the input field
    def add_light_ip(self):
        new_ip = self.light_ip_input.text()
        if new_ip and new_ip not in self.config['network']['light_ips']:
            self.config['network']['light_ips'].append(new_ip)
            self.light_ip_list.addItem(new_ip)
            self.light_ip_input.clear()
        else:
            QMessageBox.warning(self, "Warning", "IP is already in the list or invalid.")

    # Method to remove the selected IP from the list
    def remove_light_ip(self):
        selected_items = self.light_ip_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            ip = item.text()
            if ip in self.config['network']['light_ips']:
                self.config['network']['light_ips'].remove(ip)
                self.light_ip_list.takeItem(self.light_ip_list.row(item))

    def add_discovered_lights(self):
        # Create and start the discovery thread
        self.discovery_thread = DiscoveryThread(self.discover_lights_async)
        self.discovery_thread.discovered.connect(self.handle_discovered_lights)
        self.discovery_thread.start()

    def handle_discovered_lights(self, discovered_lights):
        # Update the GUI with the discovered lights
        for light in discovered_lights:
            if hasattr(light, 'ip') and light.ip not in self.config['network']['light_ips']:
                self.config['network']['light_ips'].append(light.ip)
                self.light_ip_list.addItem(light.ip)

    async def discover_lights_async(self):
        self.statusLabel.setText("Searching for connected devices...")
        # Discover WiZ lights asynchronously
        discovered_lights = await discovery.discover_lights()
        print(f"Discovered lights: {discovered_lights}")  # Debugging line
        self.statusLabel.setText("WiZ Volume Visualizer Control")
        return discovered_lights
  

#   CONFIGURATION SAVE/LOAD/RESET


    def save_config_to_file(self):
        self.statusLabel.setText("Saving...")
        
        # Update 'network' section
        self.config['network']['udp_port'] = int(self.udp_port.text())  # Save the udp_port from the form
        self.config['network']['light_ips'] = [self.light_ip_list.item(i).text() for i in range(self.light_ip_list.count())]

        # Update the config dictionary with the current widget values
        for section, data in self.config.items():
            for key, value in data.items():
                if hasattr(self, key):
                    widget = getattr(self, key)
                    if isinstance(widget, QCheckBox):  # For boolean values
                        self.config[section][key] = widget.isChecked()
                    elif isinstance(widget, QLineEdit):  # For text inputs
                        text_value = widget.text()
                        if section == 'color_settings':
                            if 'colors' in key or 'color' in key:
                                try:
                                    # Parse and format RGB values
                                    rgb_values = text_value.replace('RGB(', '').replace(')', '').split(',')
                                    self.config[section][key] = [int(val.strip()) for val in rgb_values]
                                except ValueError:
                                    print(f"Error parsing color value: {text_value}")
                                    self.config[section][key] = text_value
                            else:
                                self.config[section][key] = text_value
                        else:
                            try:
                                # Convert to appropriate numerical type
                                if '.' in text_value:
                                    self.config[section][key] = float(text_value)
                                else:
                                    self.config[section][key] = int(text_value)
                            except ValueError:
                                self.config[section][key] = text_value

        # Manually update color settings
        for color_type, colors in self.config['color_settings'].items():
            for i in range(len(colors)):
                color_widget_key = f"{color_type}_{i}"
                if hasattr(self, color_widget_key):
                    widget = getattr(self, color_widget_key)
                    text_value = widget.text().replace('RGB(', '').replace(')', '')
                    rgb_values = [int(val.strip()) for val in text_value.split(',')]
                    self.config['color_settings'][color_type][i] = rgb_values

        # Save Device Info
        if self.manual_input_checkbox.isChecked():
            try:
                manual_index = int(self.audio_device_input.text())
                self.config['audio']['device_index'] = manual_index
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Please enter a valid device index.")
                return
        else:
            selected_index = self.audio_device_dropdown.currentData()
            if selected_index is not None:
                self.config['audio']['device_index'] = selected_index

        # Debug print the final configuration
        print(f"Saving configuration to: {self.config_file}")
        print("Final configuration before saving:", json.dumps(self.config, indent=4))

        # Save the updated configuration to the file
        try:
            save_config(self.config_file, self.config)
            print("Configuration saved successfully!")
            self.statusLabel.setText("Configuration saved.")
        except Exception as e:
            print(f"Error saving configuration: {e}")
            self.statusLabel.setText("Failed to save configuration.")


    def confirm_reset(self):
        reply = QMessageBox.question(self, 'Reset to Default', 
                                    "Are you sure you want to reset the configuration to default?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # Load the default config
            self.config = load_config(self.default_file)
            self.light_ip_list.clear()
            self.add_discovered_lights()

            # Re-populate settings with the default config
            self.populate_settings(self.config)

            print("Configuration reset to default.")

    def populate_settings(self, config):
        # Clear current UI elements first
        for i in reversed(range(self.settings_layout.count())):
            widget = self.settings_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        # Update config reference
        self.config = config

        # Recreate the settings UI with the updated configuration
        self.create_audio_settings()
        self.create_network_settings()
        self.create_visualization_settings()
        self.create_brightness_settings()
        self.create_feature_settings()
        self.create_color_settings()
        self.create_audio_processing_settings()

        # Update the IP list in the UI
        self.light_ip_list.clear()
        if isinstance(self.config['network']['light_ips'], list):
            self.light_ip_list.addItems(self.config['network']['light_ips'])
        else:
            self.config['network']['light_ips'] = [self.config['network']['light_ips']]
            self.light_ip_list.addItems(self.config['network']['light_ips'])

        print("Settings have been updated.")


# Running the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    theme_name = sys.argv[1] if len(sys.argv) > 1 else "dark"
    pyi_splash.close()

    # Determine the base path
    if getattr(sys, 'frozen', False):  # Packaged app
        base_path = os.path.dirname(os.path.abspath(sys.executable))
    else:  # Development mode
        base_path = os.path.abspath(".")

    # Paths for config files
    config_file_path = os.path.join(base_path, 'volume_config.json')
    default_file_path = os.path.join(base_path, 'default_volume_config.json')

    print(f"Config File Path: {config_file_path}")
    print(f"Default File Path: {default_file_path}")

    # Validate default file existence
    if not os.path.exists(default_file_path):
        print("Error: Default configuration file is missing.")
        sys.exit(1)

    # Ensure config file exists by copying from the default
    if not os.path.exists(config_file_path):
        print("Creating configuration file from default...")
        try:
            with open(default_file_path, 'r') as default_file:
                with open(config_file_path, 'w') as config_file:
                    config_file.write(default_file.read())
        except Exception as e:
            print(f"Error creating configuration file: {e}")
            sys.exit(1)

    # Load and run the main window
    load_stylesheet(app, theme_name)
    window = ConfigEditor(config_file_path, default_file_path, theme_name=theme_name)
    window.show()
    sys.exit(app.exec_())


