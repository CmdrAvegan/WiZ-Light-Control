import sys
import json
import asyncio
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QListWidget, QPushButton, QLabel,
    QColorDialog, QVBoxLayout, QWidget, QComboBox, QLineEdit, QSpinBox,
    QDialog, QColorDialog, QSlider, QHBoxLayout, QListWidgetItem, QFileDialog, QCheckBox, QMessageBox, QSpacerItem, QSizePolicy, QAbstractItemView
)
from PyQt5.QtGui import QColor, QFont, QPalette, QIntValidator, QIcon
from PyQt5.QtCore import Qt
from preview_pattern import PatternPreview

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




class StepDialog(QDialog):
    def __init__(self, step=None, available_lights=None, discovered_lights=None, step_number=None):
        super().__init__()
        self.setWindowTitle("Edit Step")
        self.setGeometry(300, 300, 400, 300)
        self.step = step or {}
        self.step_number = step_number

        self.available_lights = available_lights or []
        self.discovered_lights = discovered_lights or []

        self.pattern_name = ""
        self.pattern_description = ""
        self.pattern_steps = []
        self.initUI()

    def initUI(self):
                # Ensure step_number is set before using it
        if self.step_number is None:
            self.step_number = "Unknown" 
        layout = QVBoxLayout()

        # Step number label before color section
        self.stepNumberLabel = QLabel(f"Step {self.step_number}:", self)
        self.stepNumberLabel.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.stepNumberLabel)

        # Light selection list
        self.lightList = QListWidget(self)
        self.lightList.setSelectionMode(QListWidget.MultiSelection)
        for light in self.discovered_lights:
            item = QListWidgetItem(f"{light['name']} ({light['ip']})")
            item.setData(Qt.UserRole, light["ip"])
            self.lightList.addItem(item)
        layout.addWidget(QLabel("Select Lights (or check 'All Lights')"))
        layout.addWidget(self.lightList)

        # "All Lights" checkbox
        self.allLightsCheck = QCheckBox("All Lights", self)
        self.allLightsCheck.stateChanged.connect(self.toggle_all_lights)
        layout.addWidget(self.allLightsCheck)

        # Color picker and preview
        color_layout = QHBoxLayout()
        self.colorButton = QPushButton("Select Color", self)
        self.colorButton.clicked.connect(self.select_color)
        color_layout.addWidget(self.colorButton)

        self.colorPreview = QLabel()
        self.colorPreview.setFixedSize(40, 20)
        self.update_color_preview()
        color_layout.addWidget(self.colorPreview)

        layout.addLayout(color_layout)


        # Brightness slider and text input
        brightness_layout = QHBoxLayout()
        self.brightnessSlider = QSlider(Qt.Horizontal, self)
        self.brightnessSlider.setRange(0, 255)
        self.brightnessSlider.setValue(self.step.get("brightness", 255))
        self.brightnessSlider.valueChanged.connect(self.update_brightness_text)
        brightness_layout.addWidget(QLabel("Brightness"))
        brightness_layout.addWidget(self.brightnessSlider)

        self.brightnessInput = QLineEdit(self)
        self.brightnessInput.setFixedWidth(50)
        self.brightnessInput.setText(str(self.brightnessSlider.value()))
        self.brightnessInput.setValidator(QIntValidator(0, 255))
        self.brightnessInput.textChanged.connect(self.update_brightness_slider)
        brightness_layout.addWidget(self.brightnessInput)

        layout.addLayout(brightness_layout)

        # Duration input
        self.durationSpin = QSpinBox(self)
        self.durationSpin.setRange(-2147483648, 2147483647)  # milliseconds
        self.durationSpin.setValue(self.step.get("duration", 1000))
        layout.addWidget(QLabel("Duration (ms)"))
        layout.addWidget(self.durationSpin)

        # Turn Off Light checkbox
        self.turnOffCheck = QCheckBox("Turn Off", self)
        self.turnOffCheck.stateChanged.connect(self.toggle_turn_off)
        layout.addWidget(self.turnOffCheck)

        # Save button
        self.saveButton = QPushButton("Save", self)
        self.saveButton.clicked.connect(self.save_step)
        layout.addWidget(self.saveButton)

        self.setLayout(layout)
        self.update_ui()

    def update_color_preview(self):
        """Update the color preview label to reflect the selected color or black if the light is off."""
        if self.step.get("action") == "turn_off":
            color_rgb = "rgb(0, 0, 0)"  # Set to black if the action is to turn off the light
        else:
            color = self.step.get("color", {"r": 255, "g": 255, "b": 255})
            if isinstance(color, dict):
                color_rgb = f"rgb({color['r']}, {color['g']}, {color['b']})"
            elif isinstance(color, list):
                color_rgb = f"rgb({color[0]}, {color[1]}, {color[2]})"
            else:
                color_rgb = "rgb(255, 255, 255)"  # Default to white if unexpected

        self.colorPreview.setStyleSheet(f"background-color: {color_rgb}; border: 1px solid #000000;")



    def toggle_all_lights(self):
        """Enable/disable individual light selection based on the 'All Lights' checkbox."""
        self.lightList.setDisabled(self.allLightsCheck.isChecked())

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.step["color"] = {"r": color.red(), "g": color.green(), "b": color.blue()}
            self.update_color_preview()


    def update_brightness_text(self):
        """Update the brightness text input to match the slider value."""
        self.brightnessInput.setText(str(self.brightnessSlider.value()))

    def update_brightness_slider(self):
        """Update the brightness slider to match the text input value."""
        if self.brightnessInput.text().isdigit():
            self.brightnessSlider.setValue(int(self.brightnessInput.text()))

    def update_ui(self):
        """Update UI elements based on the action."""
        is_turn_off = self.step.get("action") == "turn_off"
        self.colorButton.setVisible(not is_turn_off)
        self.colorPreview.setVisible(not is_turn_off)
        self.brightnessSlider.setVisible(not is_turn_off)
        self.brightnessInput.setVisible(not is_turn_off)


    def toggle_all_lights(self):
        """Enable/disable individual light selection based on the 'All Lights' checkbox."""
        self.lightList.setDisabled(self.allLightsCheck.isChecked())

    def toggle_turn_off(self):
        """Enable/disable color and brightness controls based on the 'Turn Off Light' checkbox."""
        if self.turnOffCheck.isChecked():
            self.step["action"] = "turn_off"
        else:
            self.step["action"] = "set_color"
        self.update_ui()
        self.update_color_preview()  # Update color preview when toggling the action


    def save_step(self):
        """Save the step, including light selection."""
        if self.allLightsCheck.isChecked():
            self.step["light_ip"] = "all"
        else:
            selected_lights = [
                self.lightList.item(i).data(Qt.UserRole)
                for i in range(self.lightList.count())
                if self.lightList.item(i).isSelected()
            ]
            if len(selected_lights) == 1:
                self.step["light_ip"] = selected_lights[0]  # Store as a single string if only one light is selected
            else:
                self.step["light_ip"] = selected_lights  # Store as a list if multiple lights are selected

        self.step["brightness"] = int(self.brightnessSlider.value())  # Ensure integer
        self.step["duration"] = int(self.durationSpin.value())  # Ensure integer
        self.accept()



class PatternEditor(QMainWindow):
    def __init__(self, available_lights=None, discovered_lights=None):
        super().__init__()
        self.setWindowTitle("WiZ Light Pattern Editor")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(load_icon())  # Load the icon dynamically        
        self.available_lights = available_lights or []  # List of lights from main program
        self.discovered_lights = discovered_lights or []  # List of discovered lights

        self.pattern_name = ""
        self.pattern_description = ""
        self.pattern_steps = []
        self.initUI()


    def initUI(self):
        main_layout = QVBoxLayout()
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Pattern Name Input
        self.nameLabel = QLabel("Pattern Name:", self)
        main_layout.addWidget(self.nameLabel)
        self.nameEdit = QLineEdit(self)
        main_layout.addWidget(self.nameEdit)

        # Pattern Description Input
        self.descriptionLabel = QLabel("Pattern Description:", self)
        main_layout.addWidget(self.descriptionLabel)
        self.descriptionEdit = QLineEdit(self)  # Change QTextEdit if multiline is needed
        main_layout.addWidget(self.descriptionEdit)

        # Create a horizontal layout for the buttons
        button_layout = QHBoxLayout()

        # New Pattern Button
        self.newPatternButton = QPushButton("New Pattern", self)
        self.newPatternButton.clicked.connect(self.new_pattern)
        button_layout.addWidget(self.newPatternButton)

        # Load Pattern Button
        self.loadButton = QPushButton("Load Pattern", self)
        self.loadButton.clicked.connect(self.load_pattern)
        button_layout.addWidget(self.loadButton)

        # Save Pattern Button
        self.saveButton = QPushButton("Save Pattern", self)
        self.saveButton.clicked.connect(self.save_pattern)
        button_layout.addWidget(self.saveButton)

        # Add the horizontal button layout to the main layout
        main_layout.addLayout(button_layout)

        # Button for previewing the pattern
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self.open_preview)
        main_layout.addWidget(self.preview_button)

        # Steps List
        self.stepsList = QListWidget(self)
        self.stepsList.setMinimumHeight(325)  # Set the desired minimum height for the step list
        self.stepsList.setDragDropMode(QAbstractItemView.InternalMove)  # Enable drag-and-drop
        main_layout.addWidget(self.stepsList)

        # Spacer to push buttons further down, giving more space to the step list
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Move up/down buttons
        move_buttons_layout = QHBoxLayout()
        self.moveUpButton = QPushButton("Move Up", self)
        self.moveUpButton.clicked.connect(self.move_step_up)
        move_buttons_layout.addWidget(self.moveUpButton)

        self.moveDownButton = QPushButton("Move Down", self)
        self.moveDownButton.clicked.connect(self.move_step_down)
        move_buttons_layout.addWidget(self.moveDownButton)

        main_layout.addLayout(move_buttons_layout)

        # Add/Edit/Duplicate/Remove buttons
        buttons_layout = QVBoxLayout()
        self.addStepButton = QPushButton("Add Step", self)
        self.addStepButton.clicked.connect(self.add_step)
        buttons_layout.addWidget(self.addStepButton)

        self.editStepButton = QPushButton("Edit Selected Step", self)
        self.editStepButton.clicked.connect(self.edit_step)
        buttons_layout.addWidget(self.editStepButton)

        self.duplicateStepButton = QPushButton("Duplicate Selected Step", self)
        self.duplicateStepButton.clicked.connect(self.duplicate_step)
        buttons_layout.addWidget(self.duplicateStepButton)

        self.removeStepButton = QPushButton("Remove Selected Step", self)
        self.removeStepButton.clicked.connect(self.remove_step)
        buttons_layout.addWidget(self.removeStepButton)

        main_layout.addLayout(buttons_layout)


    def dropEvent(self, event):
        super().dropEvent(event)
        self.update_steps_order()

    def update_steps_order(self):
        new_order = []
        for index in range(self.stepsList.count()):
            item = self.stepsList.item(index)
            step = item.data(Qt.UserRole)
            new_order.append(step)
        self.pattern_steps = new_order

    def duplicate_step(self):
        selected_items = self.stepsList.selectedItems()
        if selected_items:
            row = self.stepsList.row(selected_items[0])
            step = self.pattern_steps[row]
            new_step = step.copy()  # Create a copy of the selected step
            self.pattern_steps.insert(row + 1, new_step)  # Insert the copy right after the original
            self.update_steps_display()


    def clear_pattern(self):
        self.pattern_name = ""
        self.pattern_description = ""
        self.pattern_steps = []
        self.nameEdit.clear()
        self.descriptionEdit.clear()
        self.update_steps_display()

    def load_pattern(self):
        if self.pattern_steps:  # Check if there's an existing pattern loaded
            reply = QMessageBox.question(self, "Save Current Pattern", "Do you want to save the current pattern before loading a new one?",
                                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                if self.save_pattern():
                    self.open_pattern_file()
            elif reply == QMessageBox.No:
                self.open_pattern_file()
        else:
            self.open_pattern_file()

    def open_pattern_file(self):
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Pattern", "", "JSON Files (*.json);;All Files (*)", options=options)
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    pattern_data = json.load(f)

                # Extract name and description
                self.pattern_name = pattern_data.get("name", "")
                self.pattern_description = pattern_data.get("description", "")
                self.nameEdit.setText(self.pattern_name)
                self.descriptionEdit.setText(self.pattern_description)
                self.pattern_steps = pattern_data.get("steps", [])

                # Debugging line to check the pattern name loaded
                print(f"Pattern Name Loaded: {self.pattern_name}")

                # Determine format and normalize to a common structure
                if self.pattern_steps and isinstance(self.pattern_steps[0], dict) and "lights" in self.pattern_steps[0]:  # Format 2
                    self.pattern_steps = self.convert_format_two_to_common(self.pattern_steps)

                # Update display with the loaded pattern
                self.update_steps_display()
            except Exception as e:
                print(f"Error loading pattern file: {e}")



    def save_pattern(self):
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Pattern", "", "JSON Files (*.json);;All Files (*)", options=options)
        if filepath:
            if not filepath.endswith('.json'):
                filepath += '.json'
            self.pattern_name = self.nameEdit.text()
            self.pattern_description = self.descriptionEdit.text()
            with open(filepath, 'w') as f:
                json.dump({
                    "name": self.pattern_name,
                    "description": self.pattern_description,
                    "steps": self.pattern_steps
                }, f, indent=4)
            return True  # Indicate that the pattern was saved
        return False  # Indicate that the save operation was canceled


    def new_pattern(self):
        if self.pattern_steps:  # Check if there's an existing pattern loaded
            reply = QMessageBox.question(self, "Save Current Pattern", "Do you want to save the current pattern before creating a new one?",
                                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                if self.save_pattern():
                    self.clear_pattern()
                # If the save dialog is canceled, do nothing
            elif reply == QMessageBox.No:
                self.clear_pattern()
            # If reply is Cancel or the dialog is closed, do nothing
        else:
            self.clear_pattern()


    def convert_format_two_to_common(self, steps):
        """Convert Format 2 to a common format."""
        common_steps = []
        for step in steps:
            duration = step.get("duration", 1000)
            for light_action in step["lights"]:
                # Ensure color is always stored as a list format
                color = light_action.get("color", [255, 255, 255])
                if isinstance(color, dict):  # Convert dictionary to list if necessary
                    color = [color.get("r", 255), color.get("g", 255), color.get("b", 255)]
                
                common_step = {
                    "light_ip": light_action["light_ip"],
                    "action": light_action["action"],
                    "color": color,
                    "brightness": light_action.get("brightness", 255),
                    "duration": duration
                }
                common_steps.append(common_step)
        return common_steps


    def add_step(self):
        step = {"light_ip": "all", "action": "set_color", "color": {"r": 255, "g": 255, "b": 255}, "brightness": 255, "duration": 1000}
        dialog = StepDialog(step, available_lights=self.available_lights, discovered_lights=self.discovered_lights)
        if dialog.exec_() == QDialog.Accepted:
            self.pattern_steps.append(dialog.step)
            self.update_steps_display()

    def edit_step(self):
        selected_items = self.stepsList.selectedItems()
        if selected_items:
            row = self.stepsList.row(selected_items[0])
            step = self.pattern_steps[row]
            dialog = StepDialog(step, available_lights=self.available_lights, discovered_lights=self.discovered_lights)
            if dialog.exec_() == QDialog.Accepted:
                self.pattern_steps[row] = dialog.step
                self.update_steps_display()


    def remove_step(self):
        selected_items = self.stepsList.selectedItems()
        if selected_items:
            row = self.stepsList.row(selected_items[0])
            del self.pattern_steps[row]
            self.update_steps_display()


    def move_step_up(self):
        current_row = self.stepsList.currentRow()
        if current_row > 0:
            self.pattern_steps.insert(current_row - 1, self.pattern_steps.pop(current_row))
            self.update_steps_display()
            self.stepsList.setCurrentRow(current_row - 1)


    def move_step_down(self):
        current_row = self.stepsList.currentRow()
        if current_row < len(self.pattern_steps) - 1:
            self.pattern_steps.insert(current_row + 1, self.pattern_steps.pop(current_row))
            self.update_steps_display()
            self.stepsList.setCurrentRow(current_row + 1)



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
            light_info = step.get("light_ip", "Unknown Light")
            action = step.get("action", "Unknown Action")
            color = step.get("color", [255, 255, 255])
            print(f"Step Action: {action}, Color before applying: {color}")
            brightness = step.get("brightness", 255)
            duration = step.get("duration", 0)

            # Format color
            if action == "turn_off":
                color_rgb = "rgba(0, 0, 0, 0)"  # Fully transparent
                color_text = "(0, 0, 0)"
            elif isinstance(color, list):
                color_text = f"({color[0]}, {color[1]}, {color[2]})"
                color_rgb = f"rgb({color[0]}, {color[1]}, {color[2]})"
            elif isinstance(color, dict):
                color_text = f"({color.get('r', 255)}, {color.get('g', 255)}, {color.get('b', 255)})"
                color_rgb = f"rgb({color.get('r', 255)}, {color.get('g', 255)}, {color.get('b', 255)})"
            else:
                color_text = "(255, 255, 255)"  # Default to white if unexpected
                color_rgb = "rgb(255, 255, 255)"

            # Create formatted text with HTML
            step_text = (f"Light: <b>{light_info}</b>, Action: <b>{action}</b>, "
                        f"Color: <b>{color_text}</b>, Brightness: <b>{brightness}</b>, Duration: <b>{duration}ms</b>")

            # Create a QWidget for the item
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)

            # Add the step number as a label before the color display
            step_number_label = QLabel(f"{index + 1}")  # Step numbers start from 1
            step_number_label.setFont(QFont("Arial", 10, QFont.Bold))
            item_layout.addWidget(step_number_label)

            # Create a color indicator without a border
            color_indicator = QLabel()
            color_indicator.setFixedSize(20, 20)
            color_indicator.setStyleSheet(f"background-color: {color_rgb}; border-radius: 10px;")
            item_layout.addWidget(color_indicator)

            # Create a label for step text
            item_label = QLabel(step_text)
            item_label.setTextFormat(Qt.RichText)
            item_label.setStyleSheet(f"color: {text_color};")  # Use theme's text color
            item_layout.addWidget(item_label)
            item_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_widget.setLayout(item_layout)

            # Alternate background color
            if index % 2 == 0:
                item_widget.setStyleSheet(f"background-color: {background_color}; color: {text_color};")
            else:
                item_widget.setStyleSheet(f"background-color: {alternate_background_color}; color: {text_color};")

            # Create a QListWidgetItem and set the QWidget as the item
            item = QListWidgetItem(self.stepsList)
            item.setSizeHint(item_widget.sizeHint())
            self.stepsList.addItem(item)
            self.stepsList.setItemWidget(item, item_widget)

            # Store step data for further use
            item.setData(Qt.UserRole, step)

        # Ensure the list widget has a visible selection mode
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
            QListWidget::item:selected:!active {{
                background-color: {selection_color};
                color: {selection_text_color};
            }}
            QListWidget::item:hover {{
                background-color: {selection_color};
                color: {selection_text_color};
            }}
        """)





    def open_preview(self):
        # Initialize and show the preview window
        self.preview_window = PatternPreview(self.discovered_lights, self.pattern_steps, self.pattern_name)
        self.preview_window.setWindowModality(Qt.NonModal)
        
        # Apply the theme from PatternEditor to PatternPreview
        self.preview_window.apply_theme(self.stepsList.palette())  # Pass the current theme palette
        self.preview_window.show()


    def run(self):
        self.show()





    def closeEvent(self, event):
        if self.pattern_steps:  # Check if there's an existing pattern loaded
            reply = QMessageBox.question(self, "Save Current Pattern", "Do you want to save the current pattern before exiting?",
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                if self.save_pattern():
                    event.accept()
                else:
                    event.ignore()  # If the save dialog is canceled, ignore the close event
            elif reply == QMessageBox.No:
                event.accept()
            else:  # If reply is Cancel or the dialog is closed, ignore the close event
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = PatternEditor()
    editor.show()
    sys.exit(app.exec_())
