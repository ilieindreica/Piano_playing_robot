import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QLabel, QFileDialog, QScrollArea, QGridLayout, QSpinBox, QComboBox, QCheckBox
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from sheet_detector import MusicSheet
import time
from Notes import NoteWithPosition
import cv2
import logging
import os
import ActionScheduler
import serial
import serial.tools.list_ports
import SerialCommands


class SerialListener(QThread):
    data_received = pyqtSignal(str)

    def __init__(self, ser, checkbox):
        super().__init__()
        self.ser = ser
        self.checkbox = checkbox
        self._running = True

    def run(self):
        while self._running:
            if not self.checkbox.checkState():
                break
            if self.ser.in_waiting > 0:
                data = self.ser.readline().strip().decode()
                self.data_received.emit(data)

    def stop(self):
        self._running = False


class GUI(QWidget):
    def __init__(self):
        super().__init__()
        # ----------- CONFIG -------------------
        # The pretrained model for notes
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_note_path = self.script_dir + '\\best.pt'
        self.default_image_folder = self.script_dir + '\\sheets'
        self.default_tempo = 60
        self.baud_rate = 115200
        # -------------------------------------

        self.image_path = ''
        self.music_sheet = None
        self.left_commands = []
        self.right_commands = []
        self.ser = None
        self.listener_thread = None

        self.setWindowTitle("Music Sheet Recognition")
        self.setGeometry(500, 100, 800, 900)

        main_layout = QGridLayout(self)

        # Add image button
        self.add_image_button = QPushButton("Add Image")
        self.add_image_button.clicked.connect(self.process_image)
        main_layout.addWidget(self.add_image_button, 0, 0, 1, 3)

        # Tempo Box
        self.tempo_box = QSpinBox()
        self.tempo_box.setMinimum(1)
        self.tempo_box.setMaximum(200)
        self.tempo_box.setValue(self.default_tempo)
        self.tempo_box.setSingleStep(10)
        main_layout.addWidget(QLabel('Tempo'), 1, 0, 1, 1)
        main_layout.addWidget(self.tempo_box, 1, 1, 1, 1)

        # COM port selection
        self.port_box = QComboBox()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_box.addItem(port.device)
        self.refresh_button = QPushButton('Refresh')
        self.refresh_button.clicked.connect(self.refresh_com_ports)
        main_layout.addWidget(QLabel('COM Port'), 2, 0, 1, 1)
        main_layout.addWidget(self.port_box, 2, 1, 1, 1)
        main_layout.addWidget(self.refresh_button, 2, 2, 1, 1)

        # Check box for printing Serial
        self.checkbox = QCheckBox('Open Serial Monitor')
        self.checkbox.stateChanged.connect(self.on_checkbox_toggled)
        main_layout.addWidget(self.checkbox, 3, 1, 1, 1)

        # Run button
        self.run_button = QPushButton('Run')
        self.run_button.clicked.connect(self.send_commands)
        main_layout.addWidget(self.run_button, 3, 2, 1, 1)

        # Scroll area for images
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area, 4, 0, 2, 3)

        # QLabel for image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False)

        self.scroll_area.setWidget(self.image_label)

    def process_image(self):
        # Create MusicSheet object
        self.music_sheet = MusicSheet()
        self.music_sheet.set_model_note(self.model_note_path)

        self.load_image()
        self.image_label.setText("Processing...")
        # Refresh the Label
        self.image_label.repaint()

        self.music_sheet.set_image(self.image_path)
        # At the moment, there is some fine-tuning that is dependent on this scale
        self.music_sheet.resize_image(height=900)

        self.music_sheet.run_detection()
        image = self.music_sheet.get_results_image(show_noteheads_centroids=True,
                                                   show_bounding_boxes=True,
                                                   show_noteheads_contours=False,
                                                   show_barlines=True,
                                                   height=900)
        self.display_cv_image(image)
        self.left_commands, self.right_commands = ActionScheduler.get_action_commands(self.music_sheet.time_series,
                                                                                      self.music_sheet.is_double_handed)

    def send_commands(self):
        max_len = max(len(self.left_commands), len(self.right_commands))
        for i in range(max_len):
            com1 = self.left_commands[i] if i < len(self.left_commands) else None
            com2 = self.right_commands[i] if i < len(self.right_commands) else None
            print(f'{com1}      {com2}')
        if self.right_commands:
            try:
                selected_port = self.port_box.currentText()
                if self.ser and self.ser.is_open:
                    self.ser.close()
                self.ser = serial.Serial(selected_port, self.baud_rate)
                time.sleep(1)

                # Send data
                self.ser.write(self.tempo_box.value().to_bytes(4, byteorder='big'))
                self.ser.write(self.music_sheet.is_double_handed.to_bytes(1, byteorder='big'))
                SerialCommands.send_serial_data(self.right_commands, self.ser)
                SerialCommands.send_serial_data(self.left_commands, self.ser)

                if self.checkbox.isChecked():
                    if not self.listener_thread or not self.listener_thread.isRunning():
                        self.start_serial_listener()
                else:
                    self.ser.close()

            except serial.SerialException as e:
                print(f'Serial error: {e}')
            except Exception as e:
                print(f"Unexpected error: {e}")

    def load_image(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Music Sheet", self.default_image_folder, "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if image_path:
            self.image_path = image_path

    def display_cv_image(self, cv_img):
        # Convert to RGB
        cv_img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        height = cv_img.shape[0]
        width = cv_img.shape[1]
        bytes_per_line = 3 * width

        # Convert to QImage
        q_image = QImage(cv_img_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)

        # Convert to QPixmap and display
        pixmap = QPixmap.fromImage(q_image)
        self.image_label.setPixmap(pixmap)
        self.image_label.adjustSize()

    def refresh_com_ports(self):
        current = self.port_box.currentText()
        self.port_box.blockSignals(True)  # prevent signal triggering
        self.port_box.clear()

        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_box.addItems(port_list)

        # Restore selection if still present
        if current in port_list:
            index = self.port_box.findText(current)
            self.port_box.setCurrentIndex(index)

        self.port_box.blockSignals(False)

    def start_serial_listener(self):
        self.listener_thread = SerialListener(self.ser, self.checkbox)
        self.listener_thread.data_received.connect(self.handle_serial_data)
        self.listener_thread.start()

    def handle_serial_data(self, data):
        print(f"Received: {data}")

    def closeEvent(self, event):
        if self.listener_thread and self.listener_thread.isRunning():
            self.listener_thread.stop()
            self.listener_thread.wait()
        if self.ser and self.ser.is_open:
            self.ser.close()
        event.accept()

    def on_checkbox_toggled(self, state):
        if state:  # Checkbox was checked
            if self.ser and self.ser.is_open and (not self.listener_thread or not self.listener_thread.isRunning()):
                self.start_serial_listener()
        else:  # Checkbox was unchecked
            if self.listener_thread and self.listener_thread.isRunning():
                self.listener_thread.stop()
                self.listener_thread.wait()
                self.listener_thread = None
            if self.ser and self.ser.is_open:
                self.ser.close()


if __name__ == "__main__":
    # Suppress YOLO logging, all but errors
    logging.getLogger("ultralytics").setLevel(logging.ERROR)

    app = QApplication(sys.argv)
    window = GUI()
    window.show()
    sys.exit(app.exec_())
