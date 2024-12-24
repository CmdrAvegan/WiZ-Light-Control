import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QFrame, QListWidget, 
                             QListWidgetItem, QAbstractItemView, QGraphicsView, 
                             QGraphicsScene, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsRectItem)
from PyQt5.QtGui import QBrush, QColor, QFont, QPalette, QPainter, QPen, QIcon
from PyQt5.QtCore import Qt, QTimer

def load_icon():
    """
    Load the program's icon dynamically, considering both development and packaged environments.
    """
    if getattr(sys, '_MEIPASS', False):  # If running as a packaged app
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")

    icon_path = os.path.join(base_path, 'icon', 'pattern.ico')
    print(f"Trying to load icon from: {icon_path}")  # Debug statement

    return QIcon(icon_path)

class LightIcon(QGraphicsEllipseItem):
    def __init__(self, light_name, color=(128, 128, 128)):
        super().__init__(0, 0, 50, 50)  # Initialize as a 50x50 ellipse
        self.setBrush(QBrush(QColor(*color)))  # Set the icon's color
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)  # Make it movable

        # Create background rectangle for text visibility (semi-transparent black)
        self.rect_item = QGraphicsRectItem(-30, -30, 60, 20, self)  # Positioned above the icon
        self.rect_item.setBrush(QBrush(QColor(0, 0, 0, 180)))  # Semi-transparent black background
        self.rect_item.setPen(QPen(Qt.white))  # White border for better contrast

        # Display light name above the icon, centered
        self.text_item = QGraphicsTextItem(light_name, self)
        self.text_item.setDefaultTextColor(Qt.white)  # White text for contrast
        self.text_item.setFont(QFont("Arial", 10))

        # Center the text item above the icon
        text_rect = self.text_item.boundingRect()  # Get bounding box of the text
        text_width = text_rect.width()
        text_height = text_rect.height()

        # Adjust position of the text to be centered above the icon
        self.text_item.setPos(-text_width / 2, -30)  # Horizontally centered, placed above

        # Adjust the position of the rectangle behind the text
        self.rect_item.setRect(-text_width / 2 - 10, -30, text_width + 20, text_height + 10)  # Rectangle to fit the text


    def set_color(self, color):
        if len(color) == 4:  # RGBA color
            self.setBrush(QBrush(QColor(color[0], color[1], color[2], color[3])))
        elif len(color) == 3:  # RGB color without alpha
            self.setBrush(QBrush(QColor(color[0], color[1], color[2])))
        else:
            # Default to gray if an invalid color is passed
            self.setBrush(QBrush(QColor(128, 128, 128)))

class PatternPreview(QWidget):
    def __init__(self, lights, pattern_steps, pattern_name="Pattern"):
        super().__init__()
        print(f"Pattern Name: {pattern_name}")  # Debugging print statement
        self.lights = lights
        self.pattern_steps = pattern_steps
        self.pattern_name = pattern_name  # Store the pattern name
        self.current_step = 0
        self.is_playing = False  # Track if the preview is playing
        self.timer = QTimer()
        self.setWindowIcon(load_icon())  # Load the icon dynamically

        # Check if the entire pattern uses "all"
        all_lights_used = all(step.get("light_ip") == "all" for step in pattern_steps)
        unique_lights = {}

        if all_lights_used:
            # Add all discovered lights if the pattern applies to "all" for every step
            for light in lights:
                light_ip = light.get("name", "Unknown Light")
                unique_lights[light_ip] = light
        else:
            # Otherwise, add only lights referenced in the pattern steps
            for step in pattern_steps:
                light_ip = step.get("light_ip", "Unknown Light")
                if light_ip == "all":
                    continue
                elif isinstance(light_ip, list):
                    # Handle multiple lights in the form of a list
                    for ip in light_ip:
                        if ip not in unique_lights:
                            unique_lights[ip] = {"name": ip}
                elif light_ip not in unique_lights:
                    unique_lights[light_ip] = {"name": light_ip}

        # Main layout
        main_layout = QHBoxLayout(self)

        # Left side for light display with QGraphicsView
        self.light_display = QGraphicsView()
        self.light_display.setRenderHint(QPainter.Antialiasing)
        self.light_scene = QGraphicsScene(self)
        self.light_display.setScene(self.light_scene)
        main_layout.addWidget(self.light_display)

        # Create light icons and add them to the scene
        self.light_icons = {}
        for light in unique_lights.values():
            icon = LightIcon(light["name"])
            self.light_scene.addItem(icon)
            icon.setPos(50 * len(self.light_icons), 50)
            self.light_icons[light["name"]] = icon

        # Right side for steps display and controls
        right_layout = QVBoxLayout()

        # Step list display
        self.stepsList = QListWidget()
        self.stepsList.setSelectionMode(QAbstractItemView.SingleSelection)
        self.stepsList.currentRowChanged.connect(self.update_preview_from_selection)  # Connect row change
        right_layout.addWidget(self.stepsList)
        self.update_steps_display()

        # Step number display
        self.step_number_label = QLabel(f"Step {self.current_step + 1}", self)  # Display step number (1-based)
        right_layout.addWidget(self.step_number_label)

        # Playback controls
        controls_layout = QHBoxLayout()
        play_button = QPushButton("Play")
        play_button.clicked.connect(self.start_preview)
        controls_layout.addWidget(play_button)

        pause_button = QPushButton("Pause")
        pause_button.clicked.connect(self.pause_preview)
        controls_layout.addWidget(pause_button)

        restart_button = QPushButton("Restart")
        restart_button.clicked.connect(self.restart_preview)
        controls_layout.addWidget(restart_button)

        right_layout.addLayout(controls_layout)
        main_layout.addLayout(right_layout)

        self.setLayout(main_layout)

        # Set the window title to include the pattern name
        self.update_window_title()  # Update window title here
        self.resize(800, 500)

    # You can add this method if you ever need to update the title later on
    def update_window_title(self):
        self.setWindowTitle(f"{self.pattern_name} - Pattern Preview")

    def apply_theme(self, palette):
        """Apply the main program theme to the preview."""
        self.setPalette(palette)

        # Apply theme colors to stepsList
        self.stepsList.setPalette(palette)
        self.update_steps_display()

    def update_steps_display(self):
        self.stepsList.clear()
        palette = self.stepsList.palette()

        # Retrieve theme colors
        background_color = palette.color(QPalette.Base).name()
        alternate_background_color = palette.color(QPalette.AlternateBase).name()
        text_color = palette.color(QPalette.Text).name()
        selection_color = palette.color(QPalette.Highlight).name()
        selection_text_color = palette.color(QPalette.HighlightedText).name()

        for index, step in enumerate(self.pattern_steps):
            # Configure light, action, color, and other information
            light_info = step.get("light_ip", "Unknown Light")
            action = step.get("action", "Unknown Action")
            color = step.get("color", [255, 255, 255])
            brightness = step.get("brightness", 255)
            duration = step.get("duration", 0)
            
            # Format color information
            color_rgb = f"rgb({color[0]}, {color[1]}, {color[2]})" if isinstance(color, list) else "rgb(255, 255, 255)"
            color_text = f"({color[0]}, {color[1]}, {color[2]})" if isinstance(color, list) else "(255, 255, 255)"

            step_text = f"Light: <b>{light_info}</b>, Action: <b>{action}</b>, Color: <b>{color_text}</b>, Brightness: <b>{brightness}</b>, Duration: <b>{duration}ms</b>"
            
            # Create QWidget and layout for displaying step
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)

            # Step number label
            step_number_label = QLabel(f"{index + 1}")
            step_number_label.setFont(QFont("Arial", 10, QFont.Bold))
            item_layout.addWidget(step_number_label)

            # Color indicator
            color_indicator = QLabel()
            color_indicator.setFixedSize(20, 20)
            color_indicator.setStyleSheet(f"background-color: {color_rgb}; border-radius: 10px;")
            item_layout.addWidget(color_indicator)

            # Step text label
            item_label = QLabel(step_text)
            item_label.setTextFormat(Qt.RichText)
            item_label.setStyleSheet(f"color: {text_color};")
            item_layout.addWidget(item_label)
            item_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            # Alternate background color
            background = background_color if index % 2 == 0 else alternate_background_color
            item_widget.setStyleSheet(f"background-color: {background}; color: {text_color};")
            
            # Add widget to stepsList
            item = QListWidgetItem(self.stepsList)
            item.setSizeHint(item_widget.sizeHint())
            self.stepsList.addItem(item)
            self.stepsList.setItemWidget(item, item_widget)

            # Store step data for further use
            item.setData(Qt.UserRole, step)

        # Ensure consistent selection and hover styling
        self.stepsList.setSelectionMode(QAbstractItemView.SingleSelection)
        self.stepsList.setStyleSheet(f"""
            QListWidget::item {{
                padding: 5px;
                border: none;
            }}
            QListWidget::item:selected {{
                background-color: {selection_color};
                color: {selection_text_color};
            }}
            QListWidget::item:hover {{
                background-color: {selection_color};
                color: {selection_text_color};
            }}
        """)





    def update_preview_from_selection(self, row):
        """Update preview to start from the selected step."""
        if row >= 0 and row < len(self.pattern_steps):
            self.current_step = row
            if self.is_playing:  # If playing, continue from the current step
                self.update_pattern_step()

    def update_pattern_step(self):
        """Update the current step and display the changes."""
        # Stop the timer to prevent overlap
        if self.timer.isActive():
            print(f"Stopping timer at step {self.current_step}")
            self.timer.stop()

        # Get the current step data
        if self.current_step < len(self.pattern_steps):
            step_data = self.pattern_steps[self.current_step]
        else:
            # If we've reached the end, reset to start
            print("Resetting to start")
            self.current_step = 0
            step_data = self.pattern_steps[self.current_step]

        # Display the current step in the GUI
        self.stepsList.setCurrentRow(self.current_step)
        self.step_number_label.setText(f"Step {self.current_step + 1}")

        # Determine color and action for lights
        action = step_data.get("action", "set_color")
        if action == "turn_off":
            rgba_color = [0, 0, 0, 0]  # Transparent
        else:
            color = step_data.get("color", [255, 255, 255])
            if isinstance(color, dict):
                color = [color.get("r", 255), color.get("g", 255), color.get("b", 255)]
            brightness = step_data.get("brightness", 255)
            alpha = int(brightness / 255 * 255)
            rgba_color = color + [alpha]

        # Apply color to specified lights
        light_ip = step_data.get("light_ip")
        if light_ip == "all":
            for icon in self.light_icons.values():
                icon.set_color(rgba_color)
        elif isinstance(light_ip, list):
            for ip in light_ip:
                if ip in self.light_icons:
                    self.light_icons[ip].set_color(rgba_color)
        elif light_ip in self.light_icons:
            self.light_icons[light_ip].set_color(rgba_color)

        print(f"Current step: {self.current_step}, Action: {action}, Duration: {step_data.get('duration', 1000)}ms")

        # Ensure GUI updates are processed
        self.repaint()

        # Start the timer for the next step's duration
        duration = step_data.get("duration", 1000)
        self.start_timer(duration)

        # Increment the current step for the next cycle
        self.current_step += 1
        if self.current_step >= len(self.pattern_steps):
            print("Reached the end of steps, looping back to 0")
            self.current_step = 0

    def start_timer(self, duration):
        """Start the timer for the current step's duration."""
        print(f"Starting timer for step {self.current_step} with duration {duration}ms")
        try:
            self.timer.timeout.disconnect(self.update_pattern_step)
        except TypeError:
            pass
        self.timer.timeout.connect(self.update_pattern_step)
        self.timer.setSingleShot(True)
        self.timer.start(duration)

    def start_preview(self):
        """Start preview and play from the selected step."""
        if not self.is_playing:
            self.is_playing = True
            if not self.timer.isActive():
                self.update_pattern_step()

    def pause_preview(self):
        """Pause preview."""
        self.is_playing = False
        self.timer.stop()

    def restart_preview(self):
        """Restart the preview from the first step."""
        self.current_step = 0
        if self.is_playing:
            self.update_pattern_step()


if __name__ == "__main__":
    lights = [{"name": "Light 1"}, {"name": "Light 2"}, {"name": "Light 3"}]
    pattern_steps = [
        {"light_ip": "Light 1", "action": "set_color", "color": [255, 0, 0], "brightness": 255, "duration": 1000},
        {"light_ip": "Light 2", "action": "set_color", "color": [0, 255, 0], "brightness": 255, "duration": 1000},
        {"light_ip": "Light 3", "action": "set_color", "color": [0, 0, 255], "brightness": 255, "duration": 1000},
        {"light_ip": "all", "action": "set_color", "color": [255, 255, 0], "brightness": 255, "duration": 1000},
    ]
    app = QApplication(sys.argv)
    window = PatternPreview(lights, pattern_steps)
    window.show()
    sys.exit(app.exec_())
