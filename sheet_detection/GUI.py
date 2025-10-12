import math
import struct
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
import midi2notes_converter as midconv
import configLib as cfg
import threading


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
    # noinspection PyUnresolvedReferences
    def __init__(self):
        super().__init__()
        # ----------- CONFIG -------------------
        # The pretrained model for notes
        self.left_durations_copy = None
        self.right_durations_copy = None
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_note_path = self.script_dir + '\\best.pt'
        self.default_media_folder = self.script_dir + '\\sheets'
        self.default_image_folder = self.default_media_folder + '\\images\\new'
        self.default_pdf_folder = self.default_media_folder + '\\pdfs'
        self.default_midi_folder = self.default_media_folder + '\\midi'
        self.default_tempo = 200
        self.baud_rate = 115200
        # -------------------------------------

        self.image_path = ''
        self.music_sheet = None
        self.left_commands = []
        self.right_commands = []
        self.is_double_handed = False
        self.ser = None
        self.listener_thread = None
        self.mode = None
        self.com_opened = False
        self.com_thread = None

        self.setWindowTitle("Music Sheet Recognition")
        self.setGeometry(500, 100, 800, 900)

        main_layout = QGridLayout(self)

        # Add image button
        self.add_image_button = QPushButton("Add Image")
        self.add_image_button.clicked.connect(self.process_image)
        main_layout.addWidget(self.add_image_button, 0, 0, 1, 1)

        # Add PDF button
        self.add_pdf_button = QPushButton('Add PDF')
        self.add_pdf_button.clicked.connect(self.load_pdf)
        main_layout.addWidget(self.add_pdf_button, 0, 1, 1, 1)

        # Add MIDI button
        self.add_midi_button = QPushButton('Add MIDI')
        self.add_midi_button.clicked.connect(self.load_midi)
        main_layout.addWidget(self.add_midi_button, 0, 2, 1, 1)

        # Tempo Box
        self.tempo_box = QSpinBox()
        self.tempo_box.setMinimum(1)
        self.tempo_box.setMaximum(500)
        self.tempo_box.setValue(self.default_tempo)
        self.tempo_box.setSingleStep(5)
        main_layout.addWidget(QLabel('Tempo'), 1, 0, 1, 1)
        main_layout.addWidget(self.tempo_box, 1, 1, 1, 1)

        # Tempo-note menu
        self.note_options_dict = {'whole note': 1, 'half-note': 2, 'quarter-note': 4, 'eight-note': 8}
        self.note_options = QComboBox()
        self.note_options.addItems(self.note_options_dict.keys())
        self.note_options.setCurrentIndex(2)
        main_layout.addWidget(self.note_options, 1, 2, 1, 1)

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

        # Stop Button
        self.stop_button = QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop_serial_listener)
        main_layout.addWidget(self.stop_button, 3, 0, 1, 1)

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

        if self.load_image():
            self.image_label.setText("Processing Image...")
            # Refresh the Label
            self.image_label.repaint()

            self.music_sheet.set_image(self.image_path)
            # At the moment, there is some fine-tuning that works better with this scale
            self.music_sheet.resize_image(height=900)

            self.music_sheet.run_detection()
            self.is_double_handed = self.music_sheet.is_double_handed
            image = self.music_sheet.get_results_image(show_noteheads_centroids=True,
                                                       show_bounding_boxes=True,
                                                       show_noteheads_contours=False,
                                                       show_barlines=True,
                                                       show_class_label=False,
                                                       show_noteheads_pitch=True,
                                                       height=900)
            self.display_cv_image(image)
            self.left_commands, self.right_commands = (ActionScheduler.get_action_commands
                                                       (self.music_sheet.time_series,
                                                        self.is_double_handed))
            # self.left_commands = []
            # self.is_double_handed = False
            self.right_durations_copy = [com[4] for com in self.right_commands]
            self.left_durations_copy = [com[4] for com in self.left_commands]

            # Add note rank; newer implementation, that's why it is made here
            for com in self.right_commands:
                com.append(0)
            for com in self.left_commands:
                com.append(0)

            self.mode = 'image'

    def send_commands(self):
        # Calculate tempo; only for songs extracted from image; MIDI accounts for its own tempo
        if self.mode == 'image':
            note_name = self.note_options.currentText()
            note_modifier = self.note_options_dict[note_name]
            whole_note_duration = int(60000 / self.tempo_box.value() * note_modifier)  # in milliseconds

            for i, com in enumerate(self.right_commands):
                com[4] = [d * whole_note_duration for d in self.right_durations_copy[i]]
                com[5] = int(16 * next((d for d in self.right_durations_copy[i] if d != 0), 0))  # calculate note_rank

            for i, com in enumerate(self.left_commands):
                com[4] = [d * whole_note_duration for d in self.left_durations_copy[i]]
                com[5] = int(16 * next((d for d in self.left_durations_copy[i] if d != 0), 0))  # calculate note_rank

        # Print command lists
        max_len = max(len(self.left_commands), len(self.right_commands))
        for i in range(max_len):
            com1 = self.left_commands[i] if i < len(self.left_commands) else None
            com2 = self.right_commands[i] if i < len(self.right_commands) else None
            print(f'{i}   {com1}      {com2}')

        # !!! REVISE AFTER MIDI IMPLEMENTATION -> MAYBE right_commands MAY BE EMPTY AND left_commands NOT !!!
        if self.left_commands and not self.right_commands:
            for com in self.left_commands:
                self.right_commands.append([32, [0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0], com[4], com[5]])
        if self.right_commands:
            try:
                # Open Serial
                selected_port = self.port_box.currentText()
                if self.ser and self.ser.is_open:
                    self.ser.close()
                self.ser = serial.Serial(selected_port, self.baud_rate)
                time.sleep(1)

                # Send data
                self.ser.write(self.is_double_handed.to_bytes(1, byteorder='big'))
                self.ser.write(len(self.right_commands).to_bytes(4, 'big'))
                self.ser.write(len(self.left_commands).to_bytes(4, 'big'))

                # Send commands in another thread
                self.com_opened = True
                self.com_thread = threading.Thread(target=self.serial_listener, daemon=True)
                self.com_thread.start()

                # # Print or not what is received from Serial
                # if self.checkbox.isChecked():
                #     if not self.listener_thread or not self.listener_thread.isRunning():
                #         self.start_serial_listener()
                # else:
                #     self.ser.close()

            except serial.SerialException as e:
                print(f'Serial error: {e}')
            except Exception as e:
                print(f"Unexpected error: {e}")

    def serial_listener(self):
        """Thread worker: listens to serial and sends data"""
        right_index = 0
        left_index = 0
        serial_line = ''

        while self.com_opened:
            # print('in while')
            while self.com_opened:
                serial_line = self.ser.readline().strip()
                print(serial_line)
                if serial_line:
                    # print('exited')
                    break

            if serial_line == b'r':
                self.send_serial_data(self.right_commands[right_index])
                right_index += 1
            elif serial_line == b'l':
                self.send_serial_data(self.left_commands[left_index])
                left_index += 1
            elif serial_line == b'FINISHED':
                self.com_opened = False
                self.ser.close()
                break
                # right_index = 0
                # left_index = 0

    def stop_serial_listener(self):
        self.com_opened = False
        if self.com_thread:
            self.com_thread.join()
        if self.ser:
            self.ser.close()
        print('Stopped')

    def send_serial_data(self, command):
        pos, rotations, back_s, front_s, durations, note_rank = command
        F = cfg.config['NUM_OF_FINGERS']

        self.ser.write(int(pos).to_bytes(1, 'big'))
        for i in range(F):
            self.ser.write(struct.pack('<f', rotations[i]))
            # self.ser.write(math.ceil(rotations[i]*2).to_bytes(4, 'big', signed=True))
        for i in range(F):
            self.ser.write(int(back_s[i]).to_bytes(1, 'big'))
        for i in range(F):
            self.ser.write(int(front_s[i]).to_bytes(1, 'big'))
        for i in range(F):
            self.ser.write(int(durations[i]).to_bytes(4, 'big'))
        self.ser.write(note_rank.to_bytes(4, 'big'))

    def load_image(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Music Sheet", self.default_image_folder, "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if image_path:
            self.image_path = image_path
            return True
        else:
            return False

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

    def load_pdf(self):
        print('pdf')
        self.mode = 'image'

    def load_midi(self):
        self.image_label.setText("Processing MIDI...")
        midi_path, _ = QFileDialog.getOpenFileName(
            self, "Select MIDI File", self.default_midi_folder, "MIDI (*.mid)"
        )
        if midi_path:
            time_series, self.is_double_handed = midconv.extract_notes_from_midi(midi_path)
            self.left_commands, self.right_commands = (ActionScheduler.get_action_commands(time_series, False))
            self.image_label.setText("MIDI ready to go!")
            self.mode = 'midi'
            return True
        else:
            return False

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
