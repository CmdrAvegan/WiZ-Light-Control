import sys
import json
import pyaudio
import os
import time
import asyncio
import pyi_splash
import pyi_splash

from pywizlight import wizlight
from PyQt5.QtCore import QProcess, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from pycaw.utils import AudioUtilities, AudioDeviceState
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFormLayout, QScrollArea, QTabWidget, QTextEdit, QComboBox, QMessageBox, QColorDialog,
)

class LightStateFetcher:
    def __init__(self, ip, update_callback):
        self.light = wizlight(ip)
        self.update_callback = update_callback
        self.running = True

    async def fetch_state(self):
        """Fetch the state of the WiZ light periodically."""
        while self.running:
            if self.update_callback:  # Ensure the callback is defined
                if self.running:  # Check if the visualizer is running
                    try:
                        await self.light.updateState()
                        rgb = self.light.state.get_rgb()
                        if rgb:
                            self.update_callback(rgb)  # Emit signal to update light icon
                    except Exception as e:
                        print(f"Error fetching light state: {e}")
                await asyncio.sleep(0.01)  # Poll every 10ms, adjust as necessary

    def stop(self):
        """Stop the fetch loop."""
        self.running = False



def calibrate_silence_threshold(self):
    self.calibration_process = QProcess(self)
    self.calibration_process.setProgram("wiz_visualizer_freq")
    self.calibration_process.setArguments(["--calibrate", f"--device={self.config.get('audio_device', 'default')}"])
    self.calibration_process.readyReadStandardOutput.connect(self.handle_calibration_output)
    self.calibration_process.finished.connect(self.handle_calibration_finished)
    self.calibration_process.start()

def handle_calibration_output(self):
    output = self.calibration_process.readAllStandardOutput().data().decode()
    print(output)  # Or display in a text widget

def handle_calibration_finished(self):
    QMessageBox.information(self, "Calibration Complete", "Calibration completed successfully.")
    self.config = self.load_config("config.json")
    self.populate_settings(self.config)


class CalibrationThread(QThread):
    # Signal to notify when calibration is done
    calibration_done = pyqtSignal(str)

    def __init__(self, duration, device, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.device = device

    def run(self):
        try:
            import subprocess
            # Run the calibration process in the background
            print(f"Running calibration for {self.duration} seconds with device {self.device}")
            result = subprocess.run(
                ["wiz_visualizer_freq.exe", "--calibrate", f"--duration={self.duration}", f"--device={self.device}"],
                capture_output=True,
                text=True
            )

            # Emit the signal to notify that calibration is done
            if result.returncode == 0:
                self.calibration_done.emit("Calibration completed successfully.")
            else:
                self.calibration_done.emit(f"Calibration failed: {result.stderr}")

        except Exception as e:
            self.calibration_done.emit(f"An error occurred during calibration: {str(e)}")

class LightUpdateThread(QThread):
    update_signal = pyqtSignal(tuple)  # Signal to update the UI

    def __init__(self, ip):
        super().__init__()
        self.ip = ip
        self.fetcher = None

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.fetcher = LightStateFetcher(self.ip, self.emit_update)
        loop.run_until_complete(self.fetcher.fetch_state())

    def emit_update(self, rgb):
        """Emit the updated RGB values as a signal."""
        self.update_signal.emit(rgb)

    def stop(self):
        """Stop the fetcher."""
        if self.fetcher:
            self.fetcher.stop()


def load_icon():
    """
    Load the program's icon dynamically, considering both development and packaged environments.
    """
    if getattr(sys, '_MEIPASS', False):  # If running as a packaged app
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")

    icon_path = os.path.join(base_path, 'icon', 'freq.ico')
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



class ConfigEditor(QMainWindow):
    def __init__(self, theme_name='dark'):
        super().__init__()
        self.setWindowTitle("Frequency Config Editor")
        self.setGeometry(100, 100, 400, 600)
        self.setWindowIcon(load_icon())

        # Define a dictionary to map configuration keys to display names
        self.display_names = {
            'reversal_interval': 'Reverse Interval',
            'sample_rate': 'Sample Rate',
            'frames_per_buffer': 'Frames Per Buffer',
            'num_channels': 'Number of Channels',
            'udp_port': 'UDP Port',
            'min_update_interval_ms': 'Minimum Update Interval (ms)',
            'frequency_sensitivity_threshold': 'Frequency Sensitivity Threshold',
            'dynamic_threshold': 'Dynamic Threshold',
            'target_brightness': 'Target Brightness',
            'current_brightness': 'Current Brightness',
            'is_dimmed': 'Is Dimmed',
            'hysteresis_counter': 'Hysteresis Counter'
            # Add more mappings as needed
        }

        # Load configuration files
        self.default_config = self.load_config('default.json')
        self.config = self.load_config('config.json')  # Load user config here

        self.visualizer_running = False  # Track if the visualizer is running or not

        # Setup UI
        self.init_ui()
        # Load saved config when the program starts
        self.load_config('config.json')
        # QProcess to manage the C++ program
        self.process = QProcess(self)

        # Populate UI with loaded configuration
        self.populate_settings(self.config)


    def calibrate_silence_threshold(self):
        reply = QMessageBox.question(
            self,
            'Calibrate Silence Threshold',
            'Ensure no audio is playing and the environment is silent. Do you want to proceed with calibration?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Get the calibration duration from the input field or default to 5 seconds
            calibration_duration = int(self.calibration_duration_input.text()) if self.calibration_duration_input.text().isdigit() else 5
            audio_device = self.config.get("audio_device", "default")

            # Create the calibration thread
            self.calibration_thread = CalibrationThread(calibration_duration, audio_device)
            
            # Connect the thread's signal to the update method
            self.calibration_thread.calibration_done.connect(self.on_calibration_done)
            
            # Start the calibration thread
            self.calibration_thread.start()

            # Inform the user that the calibration has started
            QMessageBox.information(self, "Calibration", "Calibration has started. Please wait...")

    def on_calibration_done(self, message):
        # Show a message box when calibration is complete or failed
        QMessageBox.information(self, "Calibration Status", message)
        # Optionally, reload the config and update the GUI with the new threshold
        self.config = self.load_config("config.json")
        self.populate_settings(self.config)



    def populate_settings(self, config):
        """
        Populate UI with loaded configuration.
        """
        # Update audio device input
        default_device = config.get('audio_device', '')
        self.audio_device_input.setCurrentText(default_device)

        # Update lights configuration
        for i, light in enumerate(config.get('lights', [])):
            light_ip_input = getattr(self, f'light_{i + 1}_ip', None)
            light_effect_input = getattr(self, f'light_{i + 1}_effect', None)
            light_colors_input = getattr(self, f'light_{i + 1}_colors', None)

            if light_ip_input and light_effect_input and light_colors_input:
                light_ip_input.setText(light['ip'])
                light_effect_input.setCurrentText(light['effect'])
                colors_str = ";".join(",".join(map(str, color)) for color in light['colors'])
                light_colors_input.setText(colors_str)

        # Update general settings
        for key, value in config.get('general_settings', {}).items():
            general_input = getattr(self, f'general_{key}', None)
            if general_input:
                if isinstance(general_input, QComboBox):
                    general_input.setCurrentText(str(value))
                elif isinstance(general_input, QLineEdit):
                    general_input.setText(str(value))

        # Update advanced settings
        for key, value in config.get('advanced_settings', {}).items():
            advanced_input = getattr(self, f'advanced_{key}', None)
            if advanced_input:
                if isinstance(advanced_input, QComboBox):
                    advanced_input.setCurrentText(str(value))
                elif isinstance(advanced_input, QLineEdit):
                    advanced_input.setText(str(value))


    def load_config(self, filename):
        """
        Load a configuration file.
        Prioritizes reading from the executable's directory in packaged mode.
        """
        # Determine the base path for the executable or script
        if getattr(sys, 'frozen', False):  # Running as a packaged executable
            base_path = os.path.dirname(sys.executable)  # Directory of the .exe
        else:  # Running in development mode
            base_path = os.path.dirname(os.path.abspath(__file__))  # Script directory

        # Construct the full path to the configuration file
        config_path = os.path.join(base_path, filename)

        try:
            with open(config_path, 'r') as file:
                return json.load(file)  # Assuming the config files are in JSON format
        except FileNotFoundError:
            print(f"Configuration file '{filename}' not found at {config_path}.")
            return {}  # Return an empty dict or handle as appropriate
        except json.JSONDecodeError:
            print(f"Error decoding JSON from the file '{filename}'.")
            return {}  # Return an empty dict or handle as appropriate


        # Audio Device
        content_layout.addWidget(QLabel("Audio Device:"))
        self.audio_device_input = QComboBox()
        content_layout.addWidget(self.audio_device_input)

        # Initialize device name input field
        self.device_name_input = QLineEdit(self)
        self.device_name_input.setPlaceholderText("Manually enter device name")
        content_layout.addWidget(self.device_name_input)

        # Refresh devices button
        self.refresh_devices_button = QPushButton("Refresh Devices", self)
        self.refresh_devices_button.clicked.connect(self.refresh_audio_devices)
        content_layout.addWidget(self.refresh_devices_button)

                # Color input fields for lights
        for i in range(len(self.config['lights'])):
            light_layout = QVBoxLayout()
            light_ip_label = QLabel(f"Light {i + 1} IP:")
            light_ip_input = QLineEdit(self)
            light_ip_input.setPlaceholderText("Enter light IP")
            light_effect_label = QLabel(f"Light {i + 1} Effect:")
            light_effect_input = QComboBox()
            light_effect_input.addItems(["CHANGE_COLOR", "ANOTHER_EFFECT"])  # Add your actual effects here

            # Adding color input fields
            light_colors_label = QLabel(f"Light {i + 1} Colors (R,G,B):")
            light_colors_input = QLineEdit(self)
            light_colors_input.setPlaceholderText("Enter colors as R,G,B;R,G,B")

            # Add the fields to the layout
            light_layout.addWidget(light_ip_label)
            light_layout.addWidget(light_ip_input)
            light_layout.addWidget(light_effect_label)
            light_layout.addWidget(light_effect_input)
            light_layout.addWidget(light_colors_label)
            light_layout.addWidget(light_colors_input)

            # Store the input fields in attributes for later access
            setattr(self, f'light_{i + 1}_ip', light_ip_input)
            setattr(self, f'light_{i + 1}_effect', light_effect_input)
            setattr(self, f'light_{i + 1}_colors', light_colors_input)

            content_layout.addLayout(light_layout)

        # Finalize layout setup
        central_widget = QWidget(self)
        central_widget.setLayout(content_layout)
        self.setCentralWidget(central_widget)

        # Other initializations...
        self.audio_device_combo = QtWidgets.QComboBox(self)
        p = pyaudio.PyAudio()
        self.audio_device_combo.clear()  # Clear previous entries
        self.audio_device_combo.addItem("Select an audio device")  # Placeholder
        max_width = max([self.audio_device_input.fontMetrics().width(device_info['name']) for device_info in devices])
        self.audio_device_input.setMinimumWidth(max_width + 20)  # Adjust for padding


        self.device_name_input = QtWidgets.QLineEdit(self)
        self.device_name_input.setPlaceholderText("Manually enter device name")

        self.refresh_devices_button = QtWidgets.QPushButton("Refresh Devices", self)
        self.refresh_devices_button.clicked.connect(self.refresh_audio_devices)

        # Layout setup
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.audio_device_combo)
        layout.addWidget(self.device_name_input)
        layout.addWidget(self.refresh_devices_button)

    def refresh_audio_devices(self):
        """
        Refresh the list of audio devices, showing the index and name in the dropdown,
        but saving only the device name in the config.
        """
        self.audio_device_input.clear()  # Clear previous entries
        self.audio_device_input.addItem("Select an audio device")  # Placeholder

        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            # Format as "[index] Device Name" for the dropdown
            self.audio_device_input.addItem(f"[{i}] {device_info['name']}")

        # Update the default device label
        self.update_default_device_label()

        p.terminate()

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


    def populate_audio_devices(self):
        """
        Populate the audio devices dropdown with available devices and select the saved device from config.
        """
        self.audio_device_input.clear()  # Clear previous entries
        self.audio_device_input.addItem("Select an audio device")  # Placeholder

        p = pyaudio.PyAudio()
        saved_device_index = self.config.get('audio', {}).get('device_index', None)  # Load saved device index
        saved_device_name = self.config.get('audio', {}).get('audio_device', '')  # Load saved device name
        selected_device_name = None  # To hold the name of the selected device
        selected_device_index = None  # To hold the selected device index

        # Populate the devices in the dropdown
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            device_name = device_info["name"]
            self.audio_device_input.addItem(f"[{i}] {device_name}")

            # If we find a match with the saved index, select this device
            if saved_device_index == i:
                selected_device_index = i
                selected_device_name = device_name  # Store the matching name
        
        # After populating, we ensure the correct device is selected based on index and name
        if selected_device_index is not None:
            # Set the selected index in the dropdown
            index_to_select = self.audio_device_input.findText(f"[{selected_device_index}] {selected_device_name}")
            if index_to_select >= 0:
                self.audio_device_input.setCurrentIndex(index_to_select)  # Select the device

        p.terminate()






    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create a horizontal layout for the top section (including the label and the light icon)
        top_layout = QHBoxLayout()

        # Add the default device label first
        self.default_device_label = QLabel("Default Output Device: Fetching...")

        # Add some stretch to push the light icon to the right
        top_layout.addWidget(self.default_device_label)

        # Add the stretch to push the light icon to the right side
        top_layout.addStretch()

        # Light icon
        self.light_icon = QLabel(self)
        self.light_icon.setFixedSize(20, 20)  # Set the size of the mini icon
        self.light_icon.setStyleSheet("background-color: rgb(169, 169, 169); "
                                      "border: 1px solid black; "
                                      "border-radius: 10px;")  # Greyed-out icon initially

        # Add the light icon to the layout
        top_layout.addWidget(self.light_icon)

        # Optionally, adjust the spacing between the icon and label
        top_layout.setSpacing(10)  # Adjust the spacing between the light icon and the label

        # Add this layout to the main layout
        main_layout.addLayout(top_layout)



        # Fetch and set the default device name
        default_device = get_default_input_device()
        self.default_device_label.setText(f"Default Output Device: {default_device}")

        # Add Reset Button
        reset_button = QPushButton("Reset to Default")
        reset_button.clicked.connect(self.reset_to_default)
        main_layout.addWidget(reset_button)

        # Create a tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Create the configuration tab
        config_tab = QWidget()
        self.setup_config_tab(config_tab)
        self.tabs.addTab(config_tab, "Configuration")

        # Create the help tab
        help_tab = QWidget()
        self.setup_help_tab(help_tab)
        self.tabs.addTab(help_tab, "Help")

        # Call populate_audio_devices to auto-select saved device
        self.populate_audio_devices()

        # Start and Stop buttons
        self.start_button = QPushButton("Start Program")
        self.start_button.clicked.connect(self.start_program)
        main_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Program")
        self.stop_button.clicked.connect(self.stop_program)
        main_layout.addWidget(self.stop_button)


        # Get the first light's IP from the configuration (default to '192.168.1.73' if no lights are configured)
        self.first_light_ip = self.config.get('lights', [{}])[0].get('ip', '192.168.1.73')

        # Initialize the LightUpdateThread with the first light's IP
        self.light_thread = LightUpdateThread(self.first_light_ip)  # Use the IP of the first light
        self.light_thread.update_signal.connect(self.update_light_icon)
        self.light_thread.start()

    def set_light_icon_active(self):
        """Set the light icon to active (shows current color)"""
        self.light_icon.setStyleSheet("background-color: rgb(0, 255, 0); "
                                      "border: 1px solid black; "
                                      "border-radius: 10px;")  # Active color (green in this case)

    def set_light_icon_grey(self):
        """Set the light icon to grey when the visualizer is not running"""
        self.light_icon.setStyleSheet("background-color: rgb(169, 169, 169); "
                                      "border: 1px solid black; "
                                      "border-radius: 10px;")  # Grey color

    def update_light_icon(self, rgb):
        """Update the light icon with the new RGB values."""
        if self.visualizer_running:
            r, g, b = rgb
            self.light_icon.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); "
                                        "border: 1px solid black; "
                                        "border-radius: 10px;")  # Update color and keep rounded shape
        else:
            self.set_light_icon_grey()  # Ensure the icon is grey if visualizer isn't running

    def update_light_icon_from_state(self):
        """Fetch and update the light icon based on the actual light state."""
        ip = "192.168.1.73"  # Replace with your light's IP
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Create a LightStateFetcher object to fetch the light's state
        light_state_fetcher = LightStateFetcher(ip, self.update_light_icon)
        loop.run_until_complete(light_state_fetcher.fetch_state())

    def update_light_ip(self, new_ip):
        """
        Update the light IP dynamically when the user saves the config.
        Stops the current light update thread and starts a new one with the updated IP.
        """
        # Stop the current thread if it's running
        if self.light_thread is not None:
            self.light_thread.stop()

        # Update the IP in the config and UI (optional)
        self.first_light_ip = new_ip
        self.config['lights'][0]['ip'] = new_ip  # Update the IP of the first light in the config

        # Restart the LightUpdateThread with the new IP
        self.light_thread = LightUpdateThread(self.first_light_ip)
        self.light_thread.update_signal.connect(self.update_light_icon)
        self.light_thread.start()


    def reset_to_default(self):
        reply = QMessageBox.question(
            self, 
            'Reset to Default', 
            'Are you sure you want to reset to default settings?',
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Determine the base path for finding the default.json and saving config.json
                if getattr(sys, 'frozen', False):  # Running as a packaged executable
                    base_path = os.path.dirname(sys.executable)  # Directory of the .exe
                else:  # Running in development mode
                    base_path = os.path.dirname(os.path.abspath(__file__))  # Script directory

                default_path = os.path.join(base_path, 'default.json')
                config_path = os.path.join(base_path, 'config.json')

                # Read default configuration
                with open(default_path, 'r') as default_file:
                    self.config = json.load(default_file)

                # Write default configuration to config.json
                with open(config_path, 'w') as config_file:
                    json.dump(self.config, config_file, indent=4)

                print("Configuration reset to default values.")

                # Refresh the UI to reflect default values
                self.audio_device_input.setCurrentText(self.config.get('audio_device', ''))

                # Define available light effects
                available_effects = ["CHANGE_COLOR", "ADJUST_BRIGHTNESS", "TURN_OFF_ON"]

                for i, light in enumerate(self.config.get('lights', [])):
                    light_ip_input = getattr(self, f'light_{i + 1}_ip', None)
                    light_effect_input = getattr(self, f'light_{i + 1}_effect', None)
                    light_colors_input = getattr(self, f'light_{i + 1}_colors', None)

                    if light_ip_input and light_effect_input and light_colors_input:
                        light_ip_input.setText(light['ip'])
                        effect_input = QComboBox()
                        effect_input.addItems(available_effects)  # Add available effects to ComboBox
                        effect_input.setCurrentText(light['effect'])  # Set the currently saved effect

                        colors_str = ";".join(",".join(map(str, color)) for color in light['colors'])
                        light_colors_input.setText(colors_str)

                        red_color_label = getattr(self, f'light_{i + 1}_red_color_label', None)
                        green_color_label = getattr(self, f'light_{i + 1}_green_color_label', None)
                        blue_color_label = getattr(self, f'light_{i + 1}_blue_color_label', None)

                        if red_color_label and green_color_label and blue_color_label:
                            red_color_label.setStyleSheet(
                                f"background-color: rgb({light['colors'][0][0]},{light['colors'][0][1]},{light['colors'][0][2]});"
                            )
                            green_color_label.setStyleSheet(
                                f"background-color: rgb({light['colors'][1][0]},{light['colors'][1][1]},{light['colors'][1][2]});"
                            )
                            blue_color_label.setStyleSheet(
                                f"background-color: rgb({light['colors'][2][0]},{light['colors'][2][1]},{light['colors'][2][2]});"
                            )

                for key, value in self.config.get('advanced_settings', {}).items():
                    advanced_input = getattr(self, f'advanced_{key}', None)
                    if advanced_input:
                        if isinstance(advanced_input, QComboBox):
                            advanced_input.setCurrentText(str(value))
                        elif isinstance(advanced_input, QLineEdit):
                            advanced_input.setText(str(value))

                for key, value in self.config.get('general_settings', {}).items():
                    general_input = getattr(self, f'general_{key}', None)
                    if general_input:
                        if isinstance(general_input, QComboBox):
                            general_input.setCurrentText(str(value))
                        elif isinstance(general_input, QLineEdit):
                            general_input.setText(str(value))

                # Refresh the lights layout to reflect changes
                self.populate_lights()

            except FileNotFoundError:
                print(f"Default configuration file '{default_path}' not found.")
            except json.JSONDecodeError:
                print(f"Error decoding JSON from '{default_path}'.")






    def setup_config_tab(self, tab):
        layout = QVBoxLayout(tab)

        # Create a scroll area for the configuration settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        # Create a content widget for the scroll area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        self.calibration_duration_input = QLineEdit(self)
        self.calibration_duration_input.setPlaceholderText("Calibration duration (default: 5 seconds)")
        content_layout.addWidget(QLabel("Calibration Duration:"))
        content_layout.addWidget(self.calibration_duration_input)

        # Inside setup_config_tab
        calibrate_button = QPushButton("Calibrate Silence Threshold")
        calibrate_button.clicked.connect(self.calibrate_silence_threshold)
        content_layout.addWidget(calibrate_button)


        # Audio Device
        content_layout.addWidget(QLabel("Audio Device:"))
        self.audio_device_input = QComboBox()
        content_layout.addWidget(self.audio_device_input)
        
        # Initialize device name input field
        self.device_name_input = QLineEdit(self)
        self.device_name_input.setPlaceholderText("Manually enter device name")
        content_layout.addWidget(self.device_name_input)

        # Refresh devices button
        self.refresh_devices_button = QPushButton("Refresh Devices", self)
        self.refresh_devices_button.clicked.connect(self.refresh_audio_devices)
        content_layout.addWidget(self.refresh_devices_button)

        self.populate_audio_devices()  # Call to populate audio devices

        # Lights Configuration
        lights_group = QGroupBox("Lights Configuration")
        self.lights_layout = QFormLayout()
        self.populate_lights()
        lights_group.setLayout(self.lights_layout)
        content_layout.addWidget(lights_group)

        # Buttons to add and remove lights
        add_light_button = QPushButton("Add Light")
        add_light_button.clicked.connect(self.add_light)
        content_layout.addWidget(add_light_button)

        # Add Remove Light button
        remove_light_button = QPushButton("Remove Light")
        remove_light_button.clicked.connect(self.remove_light)
        content_layout.addWidget(remove_light_button)

        # General Settings
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout()

        for key, value in self.config['general_settings'].items():
            # Get the display name from the dictionary, or format it if not found
            label = self.display_names.get(key, key.replace('_', ' ').capitalize())

            if isinstance(value, bool):
                # Create a dropdown for boolean values
                combo = QComboBox()
                combo.addItems(["True", "False"])
                combo.setCurrentText(str(value))  # Set the current value
                general_layout.addRow(f"{label}:", combo)
                setattr(self, f'general_{key}', combo)  # Store for saving later
            else:
                # Handle non-boolean values
                value_input = QLineEdit(str(value))
                general_layout.addRow(f"{label}:", value_input)
                setattr(self, f'general_{key}', value_input)  # Store for saving later

        general_group.setLayout(general_layout)
        content_layout.addWidget(general_group)

        # Advanced Settings
        self.advanced_group = QGroupBox("Advanced Settings")
        self.advanced_layout = QFormLayout()

        for key, value in self.config['advanced_settings'].items():
            label = self.display_names.get(key, key.replace('_', ' ').capitalize())

            if isinstance(value, bool):
                combo = QComboBox()
                combo.addItems(["True", "False"])
                combo.setCurrentText(str(value))
                self.advanced_layout.addRow(f"{label}:", combo)
                setattr(self, f'advanced_{key}', combo)  # Store for saving later
            else:
                value_input = QLineEdit(str(value))
                self.advanced_layout.addRow(f"{label}:", value_input)
                setattr(self, f'advanced_{key}', value_input)  # Store for saving later

        self.advanced_group.setLayout(self.advanced_layout)
        self.advanced_group.setVisible(False)  # Start hidden
        content_layout.addWidget(self.advanced_group)

        # Button to toggle advanced settings visibility
        self.toggle_advanced_button = QPushButton("Show Advanced Settings")
        self.toggle_advanced_button.clicked.connect(self.toggle_advanced_settings)
        content_layout.addWidget(self.toggle_advanced_button)

        # Save Button
        save_button = QPushButton("Save Config")
        save_button.clicked.connect(self.save_config)
        content_layout.addWidget(save_button)

        # Set the layout to the content widget and set it to the scroll area
        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)

        # Add the scroll area to the configuration tab
        layout.addWidget(scroll_area)



    def populate_lights(self):
        # Clear existing rows in the layout to prevent duplicates
        while self.lights_layout.rowCount() > 0:
            self.lights_layout.removeRow(0)

        # Define available light effects
        available_effects = ["CHANGE_COLOR", "ADJUST_BRIGHTNESS", "TURN_OFF_ON"]

        for i, light in enumerate(self.config.get('lights', [])):
            ip_input = QLineEdit(light['ip'])
            # Create a ComboBox for selecting light effect
            effect_input = QComboBox()
            effect_input.addItems(available_effects)  # Add available effects to ComboBox
            effect_input.setCurrentText(light['effect'])  # Set the currently saved effect

            # Initialize color boxes
            red_color_label = QLabel()
            red_color_label.setFixedSize(50, 20)
            red_color_label.setStyleSheet("background-color: rgb({},{},{});".format(*light['colors'][0]))
            red_color_label.mousePressEvent = lambda event, index=i: self.open_color_picker(index, 'red', red_color_label)

            green_color_label = QLabel()
            green_color_label.setFixedSize(50, 20)
            green_color_label.setStyleSheet("background-color: rgb({},{},{});".format(*light['colors'][1]))
            green_color_label.mousePressEvent = lambda event, index=i: self.open_color_picker(index, 'green', green_color_label)

            blue_color_label = QLabel()
            blue_color_label.setFixedSize(50, 20)
            blue_color_label.setStyleSheet("background-color: rgb({},{},{});".format(*light['colors'][2]))
            blue_color_label.mousePressEvent = lambda event, index=i: self.open_color_picker(index, 'blue', blue_color_label)

            red_button = QPushButton("Select Red Color")
            green_button = QPushButton("Select Green Color")
            blue_button = QPushButton("Select Blue Color")

            # Connect buttons to open color picker
            red_button.clicked.connect(lambda checked, index=i: self.open_color_picker(index, 'red', red_color_label))
            green_button.clicked.connect(lambda checked, index=i: self.open_color_picker(index, 'green', green_color_label))
            blue_button.clicked.connect(lambda checked, index=i: self.open_color_picker(index, 'blue', blue_color_label))

            self.lights_layout.addRow(f"Light {i + 1} IP Address:", ip_input)
            self.lights_layout.addRow(f"Light {i + 1} Effect:", effect_input)
            self.lights_layout.addRow("Red Color:", red_color_label)
            self.lights_layout.addRow(red_button)
            self.lights_layout.addRow("Green Color:", green_color_label)
            self.lights_layout.addRow(green_button)
            self.lights_layout.addRow("Blue Color:", blue_color_label)
            self.lights_layout.addRow(blue_button)

            setattr(self, f'light_{i + 1}_ip', ip_input)
            setattr(self, f'light_{i + 1}_effect', effect_input)

    def open_config_editor(self):
        current_theme = self.theme_combo.currentText()

        # Determine if running in packaged mode or development mode
        if getattr(sys, 'frozen', False):
            # If frozen (packaged mode), use sys._MEIPASS for extracting files
            base_path = sys._MEIPASS
        else:
            # If running in development mode, use current directory
            base_path = os.path.dirname(os.path.abspath(__file__))

        # Define the path to the script (config_gui.py)
        script_path = os.path.join(base_path, 'config_gui.py')

        # Call the script with the theme as a command-line argument
        subprocess.Popen([sys.executable, script_path, current_theme])


    def open_color_picker(self, index, color_component, color_label):
        color = QColorDialog.getColor()
        if color.isValid():
            rgb = [color.red(), color.green(), color.blue()]
            if color_component == 'red':
                self.config['lights'][index]['colors'][0] = rgb
                color_label.setStyleSheet(f"background-color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});")
            elif color_component == 'green':
                self.config['lights'][index]['colors'][1] = rgb
                color_label.setStyleSheet(f"background-color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});")
            elif color_component == 'blue':
                self.config['lights'][index]['colors'][2] = rgb
                color_label.setStyleSheet(f"background-color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});")


    def add_light(self):
        light_number = len(self.config['lights']) + 1
        # Set default colors for the new light, change as needed
        default_colors = [[255, 0, 0], [0, 255, 0], [0, 0, 255]]  # Example RGB colors

        new_light = {
            "ip": f"192.168.1.{light_number + 70}",  # Example IP generation
            "effect": "CHANGE_COLOR",
            "colors": default_colors  # Add the colors array
        }
        
        self.config['lights'].append(new_light)
        self.populate_lights()  # Refresh the UI to show the new light

    def remove_light(self, index):
        reply = QMessageBox.question(
            self,
            'Remove Light',
            'Are you sure you want to remove this light?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if 0 <= index < len(self.config['lights']):
                # Remove the light from the configuration
                del self.config['lights'][index]

                # Refresh the lights layout to reflect changes
                self.populate_lights()

            print(f"Light {index + 1} removed.")


    def setup_help_tab(self, tab):
        layout = QVBoxLayout(tab)

        # Add help text
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setPlainText(
    "Configuration Guide\n\n"
    
    "Audio Device\n"
    "audio_device: Sets the input audio device for capturing sound. Default: "
    "\"alsa_output.pci-0000_00_1b.0.analog-stereo.monitor\"\n\n"
    
    "Lights Setup\n"
    "lights: An array defining each light's configuration.\n\n"
    
    "Network and IP Settings\n"
    "ip: The IP address for connecting to your light. Example: \"192.168.1.65\"\n"
    "UDP_PORT: The port used for sending commands to the lights. Default: 38899\n\n"
    
    "Lighting Effects\n"
    "effect: Choose an effect type to control light behavior. Options: \"CHANGE_COLOR\", "
    "\"ADJUST_BRIGHTNESS\", \"TURN_OFF_ON\"\n"
    "colors: Specify RGB color values for lights in a sequence. Example: "
    "[[255, 0, 0], [0, 255, 0], [0, 0, 255]]\n\n"
    
    "Audio Processing Settings\n"
    "SAMPLE_RATE: Sets the audio sample rate in Hz. Default: 48000\n"
    "FRAMES_PER_BUFFER: Number of frames processed per buffer, affecting audio smoothness. Default: 256\n"
    "NUM_CHANNELS: Number of audio channels used. Default: 2\n\n"
    
    "Visualizer Tuning Options\n"
    "MIN_UPDATE_INTERVAL_MS: (Caution: may cause the light to go offline if set too low) Minimum time between updates, in milliseconds. Default: 100\n"
    "FREQUENCY_SENSITIVITY_THRESHOLD: Sensitivity threshold for frequency response. Default: 2.5 (ow = less sensitive to freq, high = more sensitive)\n"
    "dynamic_threshold: Base level for automatic threshold adjustment. Default: 0.0\n\n"
    
    "Brightness and Dimming\n"
    "target_brightness: Desired brightness level for the lights. Default: 255\n"
    "current_brightness: Current set brightness level. Default: 255\n"
    "is_dimmed: Indicates whether lights are in a dimmed state. Default: false\n"
    "dimming_factor: Adjusts the rate of light dimming. Default: 0.001\n"
    "gradual_brightness_recovery: Enable gradual brightness recovery after dimming. Default: true\n"
    "brightness_multiplier: Adjusts brightness based on audio intensity. Default: 2\n\n"
    
    "Color and Pattern Settings\n"
    "reversal_interval: Time interval (ms) for reversing colors. Default: 5000\n"
    "reverse_colors: Enable reversing of the color sequence. Default: false\n"
    "random_reversal_interval: Use random intervals for color reversals. Default: false\n"
    "enable_interpolation: Enable smooth color transitions between changes. Default: true\n\n"
    
    "Beat Detection\n"
    "enable_beat_detection: Enable detection of beats for synchronized lighting. Default: false\n\n"
    
    "Additional Tuning Options\n"
    "off_effect_delay_ms: Delay (ms) for turning lights off and on. Default: 50\n"
    "hysteresis_counter: Initial counter value for visual stabilizing effects. Default: 0\n"
    "hysteresis_limit: Maximum count before adjusting lights based on audio data. Default: 50\n"
    "recent_energies_size: Buffer size for tracking recent audio energies. Default: 50\n"
    "sensitivity_multiplier: Adjusts the overall sensitivity to sound. Default: 1.6\n"
    "enable_smoothing: Smooths audio input for more even lighting. Default: false\n"
    "enable_silence_threshold: Enable or disable processing silent audio. Default: true\n"
    "silence_threshold: Threshold for silence detection, higher values ensure no silence is processed. Default: 0.02\n"
    "apply_smooth_transition: smooth frames by 10% to blend colors when enabled. Default: false"
    "prev_frequency: increase or decrease if the visualizer is not changing colors from previous frequency. Default: 240\n"
    "effects_enabled: enable or disable all effects. Default: false\n\n"

    "This guide provides an overview of each option available to customize your lighting and audio visualizer. "
    "Adjust these settings based on your environment and preferences for the best experience."
        )
        layout.addWidget(help_text)

    def save_config(self):
        selected_device = self.audio_device_input.currentText()
        device_index = self.audio_device_input.currentIndex() - 1  # Adjust index to match PyAudio's 0-based index

        # Strip the index from the device name (e.g., "[1] Device Name" -> "Device Name")
        if selected_device.startswith("[") and "]" in selected_device:
            stripped_device_name = selected_device.split("]", 1)[1].strip()  # Cleaned name without index
        else:
            stripped_device_name = selected_device  # If no index is present, keep the original name


        # Save audio device and device index configuration
        self.config['audio'] = {
            'device_index': device_index,
            "audio_device": stripped_device_name
        }

        self.config["audio_device"] = stripped_device_name

        # Save lights configuration
        for i in range(len(self.config['lights'])):
            light_ip_input = getattr(self, f'light_{i + 1}_ip')
            light_effect_input = getattr(self, f'light_{i + 1}_effect')
            self.config['lights'][i]['ip'] = light_ip_input.text()
            self.config['lights'][i]['effect'] = light_effect_input.currentText()  # Save the selected effect

        # Save general settings
        for key in self.config['general_settings'].keys():
            value_input = getattr(self, f'general_{key}')
            if isinstance(self.config['general_settings'][key], bool):
                self.config['general_settings'][key] = value_input.currentText() == 'True'
            elif isinstance(self.config['general_settings'][key], int):
                self.config['general_settings'][key] = int(value_input.text())
            elif isinstance(self.config['general_settings'][key], float):
                self.config['general_settings'][key] = float(value_input.text())
            else:
                self.config['general_settings'][key] = value_input.text()

        # Save advanced settings
        for key in self.config['advanced_settings'].keys():
            value_input = getattr(self, f'advanced_{key}')
            if isinstance(self.config['advanced_settings'][key], bool):
                self.config['advanced_settings'][key] = value_input.currentText() == 'True'
            elif isinstance(self.config['advanced_settings'][key], int):
                self.config['advanced_settings'][key] = int(value_input.text())
            elif isinstance(self.config['advanced_settings'][key], float):
                self.config['advanced_settings'][key] = float(value_input.text())
            else:
                self.config['advanced_settings'][key] = value_input.text()
        # Determine the base path for saving the configuration file
        if getattr(sys, 'frozen', False):  # Running as a packaged executable
            base_path = os.path.dirname(sys.executable)  # Directory of the .exe
        else:  # Running in development mode
            base_path = os.path.dirname(os.path.abspath(__file__))  # Script directory

        # Construct the full path to save the configuration file
        config_path = os.path.join(base_path, 'config.json')

        # Save the configuration to the specified path
        try:
            with open(config_path, 'w') as file:
                json.dump(self.config, file, indent=4)
                file.flush()  # Ensure data is flushed to disk
                os.fsync(file.fileno())  # Force the OS to sync the file
            print(f"Configuration saved successfully to: {config_path}")
        except Exception as e:
            print(f"Error saving configuration: {e}")
        # Debug print the final configuration
        print(f"Saving configuration to: config.json")
        print("Final configuration before saving:", json.dumps(self.config, indent=4))

        # Now that the config is saved, update the light icon's IP and thread
        self.update_light_ip(self.config['lights'][0]['ip'])  # Update the light thread with the new IP





    def toggle_advanced_settings(self):
        # Toggle visibility of advanced settings
        if self.advanced_group.isVisible():
            self.advanced_group.setVisible(False)
            self.toggle_advanced_button.setText("Show Advanced Settings")
        else:
            self.advanced_group.setVisible(True)
            self.toggle_advanced_button.setText("Hide Advanced Settings")


    def start_program(self):
        self.save_config()

        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        time.sleep(0.2)  # Add a 500ms delay before starting the program
        executable_name = "wiz_visualizer_freq.exe" if sys.platform == "win32" else "wiz_visualizer_freq"
        executable_path = os.path.join(base_path, executable_name)

        print(f"Executable path: {executable_path}")  # Debug print
        print(f"Config being used: {self.config}")    # Debug print

        self.process.setProgram(executable_path)
        self.process.setProcessChannelMode(QProcess.ForwardedChannels)

        self.process.started.connect(lambda: print("Program started."))
        self.visualizer_running = True
        self.set_light_icon_active()  # Set icon to active when visualizer starts
        self.process.finished.connect(lambda: print("Program stopped."))
        self.process.errorOccurred.connect(lambda error: print(f"Error: {error}"))
        
        try:
            self.process.start()
        except Exception as e:
            print(f"Failed to start the program: {e}")



    def get_default_output_device():
        sessions = AudioUtilities.GetAllSessions()
        default_device = AudioUtilities.GetDefaultRenderDevice()
        return default_device.FriendlyName







    def stop_program(self):
        if self.process.state() == QProcess.Running:
            print("Stopping the program...")

            # Terminate and set a shorter timeout
            self.process.terminate()
            if not self.process.waitForFinished(100):  # Timeout of 1 second
                print("Force killing the program...")
                self.process.kill()

            print("Program stopped.")
        self.visualizer_running = False
        self.set_light_icon_grey()


    def closeEvent(self, event):
        """Handle the window close event."""
        if self.light_thread:
            self.light_thread.stop()
        event.accept()


    def on_program_stopped(self):
        """
        Handle post-stopping cleanup and UI updates.
        """
        print("Program has stopped successfully.")
        # Perform any UI updates or cleanup as needed
        self.start_button.setEnabled(True)  # Re-enable the Start button
        self.stop_button.setEnabled(False)  # Disable the Stop button


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pyi_splash.close()
    # Get theme from argument, default to "dark" if not provided
    theme_name = sys.argv[1] if len(sys.argv) > 1 else "dark"
    pyi_splash.close()
    load_stylesheet(app, theme_name)
    window = ConfigEditor()
    window.show()
    sys.exit(app.exec_())

