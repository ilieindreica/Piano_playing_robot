import copy
import math
import struct
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QLabel, QFileDialog, QScrollArea, QGridLayout, QSpinBox, QComboBox, QCheckBox, QMessageBox
)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from sheet_detector import MusicSheet
import time
from Notes import NoteWithPosition
import cv2
import logging
import os
import ActionScheduler
import ActionScheduler2
import serial
import serial.tools.list_ports
import midi2notes_converter as midconv
import configLib as cfg
import threading
from collections.abc import Iterable


def extract_file_name_from_path(path):
    return os.path.splitext(os.path.basename(path))[0]


def line_to_dict(nums):
    # indexes
    left_pos = nums[0]
    left_lists = nums[1:16]  # 15 numbers

    right_pos = nums[16]
    right_lists = nums[17:32]  # 15 numbers

    # split the 15-number blocks into 3 lists of 5
    def chunk5(lst):
        return [lst[i:i + 5] for i in range(0, 15, 5)]

    return {
        "left": [left_pos] + chunk5(left_lists),
        "right": [right_pos] + chunk5(right_lists)
    }


class GUI(QWidget):
    # noinspection PyUnresolvedReferences
    def __init__(self):
        super().__init__()
        # ----------- CONFIG -------------------
        self.left_durations_copy = None
        self.right_durations_copy = None
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_note_path = self.script_dir + '\\best.pt'
        self.default_media_folder = self.script_dir + '\\sheets'
        self.default_image_folder = self.default_media_folder + '\\images'
        self.default_pdf_folder = self.default_media_folder + '\\pdfs'
        self.default_midi_folder = self.default_media_folder + '\\midi'
        self.default_txt_folder = self.default_media_folder + '\\txt'
        self.default_tempo = 200
        self.baud_rate = 115200
        # -------------------------------------

        self.image_path = ''
        self.music_sheet = None
        self.commands = {}
        self.is_double_handed = False
        self.ser = None
        self.mode = None
        self.com_opened = False
        self.com_thread = None
        self.tempo_changed = False
        self.IMAGE_MODE = 0
        self.MIDI_MODE = 1
        self.PDF_MODE = 2
        self.TXT_MODE = 3
        self.filename = None

        self.setWindowTitle("Music Sheet Recognition")
        self.setGeometry(500, 100, 800, 900)

        main_layout = QGridLayout(self)
        buttons_layout = QGridLayout(self)
        options_layout = QGridLayout(self)
        com_layout = QGridLayout(self)
        control_menu_layout = QGridLayout(self)

        # Add image button
        self.add_image_button = QPushButton("Add Image")
        self.add_image_button.clicked.connect(self.process_image)
        buttons_layout.addWidget(self.add_image_button, 0, 0, 1, 1)

        # Add PDF button
        self.add_pdf_button = QPushButton('Add PDF')
        self.add_pdf_button.clicked.connect(self.load_pdf)
        buttons_layout.addWidget(self.add_pdf_button, 0, 1, 1, 1)

        # Add MIDI button
        self.add_midi_button = QPushButton('Add MIDI')
        self.add_midi_button.clicked.connect(self.load_midi)
        buttons_layout.addWidget(self.add_midi_button, 0, 2, 1, 1)

        # Add Txt button
        self.add_txt_button = QPushButton('Add Txt')
        self.add_txt_button.clicked.connect(self.load_txt)
        buttons_layout.addWidget(self.add_txt_button, 0, 3, 1, 1)

        # Tempo Box
        self.tempo_box = QSpinBox()
        self.tempo_box.setMinimum(1)
        self.tempo_box.setMaximum(500)
        self.tempo_box.setValue(self.default_tempo)
        self.tempo_box.setSingleStep(5)
        self.tempo_box.valueChanged.connect(lambda _: setattr(self, 'tempo_changed', True))
        options_layout.addWidget(QLabel('Tempo'), 0, 0, 1, 1)
        options_layout.addWidget(self.tempo_box, 0, 1, 1, 1)

        # Tempo-note menu
        self.note_options_dict = {'whole note': 1, 'half-note': 2, 'quarter-note': 4, 'quarter-dot': 3/8,
                                  'eight-note': 8}
        self.note_options = QComboBox()
        self.note_options.addItems(self.note_options_dict.keys())
        self.note_options.setCurrentIndex(2)
        options_layout.addWidget(self.note_options, 0, 2, 1, 1)

        # Skip hand checkbox
        self.checkbox_skip_hand = QCheckBox('Skip Left Hand')
        self.checkbox_skip_hand.stateChanged.connect(self.on_checkbox_toggled)
        options_layout.addWidget(self.checkbox_skip_hand, 1, 0, 1, 1)

        # Number of lines to Pad around staff
        self.number_of_pad_lines_box = QSpinBox()
        self.number_of_pad_lines_box.setMaximum(5)
        self.number_of_pad_lines_box.setMinimum(0)
        self.number_of_pad_lines_box.setValue(5)
        options_layout.addWidget(self.number_of_pad_lines_box, 1, 1, 1, 1)

        # Recalculate Button
        self.recalculate_button = QPushButton('Recalculate')
        self.recalculate_button.setStyleSheet("""
                                                 QPushButton {
                                                    background-color: #dae9f7;
                                                    border: 1px solid #8f8f8f;
                                                    padding: 4px 8px;
                                                }
                                                QPushButton:hover {
                                                    background-color: #cfdafc;
                                                }
                                                QPushButton:pressed {
                                                    background-color: #acbffa;
                                                }
                                              """)
        self.recalculate_button.clicked.connect(self.recalculate)
        options_layout.addWidget(self.recalculate_button, 1, 2, 1, 1)

        # Skip black-keys checkbox
        self.checkbox_skip_black = QCheckBox('Skip Black Keys')
        options_layout.addWidget(self.checkbox_skip_black, 2, 0, 1, 1)

        # Save commands to .txt
        self.save_commands_checkbox = QCheckBox('Save commands to .txt file')
        self.save_commands_checkbox.stateChanged.connect(self.ulterior_save)
        # self.save_commands_checkbox.setChecked(True)
        options_layout.addWidget(self.save_commands_checkbox, 3, 0, 1, 1)

        # COM port selection
        self.port_box = QComboBox()
        ports = serial.tools.list_ports.comports()
        real_ports = []  # Some ghosted ports where shown, so I filtered them
        for p in ports:
            if "Bluetooth" not in p.description:
                real_ports.append(p.device)
        port_list = [port for port in real_ports]
        self.port_box.addItems(port_list)
        self.refresh_button = QPushButton('Refresh')
        self.refresh_button.clicked.connect(self.refresh_com_ports)
        com_layout.addWidget(QLabel('COM Port'), 0, 0, 1, 1)
        com_layout.addWidget(self.port_box, 0, 1, 1, 1)
        com_layout.addWidget(self.refresh_button, 0, 2, 1, 1)

        # Stop Button
        self.stop_button = QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop_serial_listener)
        control_menu_layout.addWidget(self.stop_button, 0, 0, 1, 1)

        # Run button
        self.run_button = QPushButton('Run')
        self.run_button.clicked.connect(self.send_commands)
        control_menu_layout.addWidget(self.run_button, 0, 2, 1, 1)

        # Add layouts
        main_layout.addLayout(buttons_layout, 0, 0, 1, 3)
        main_layout.addLayout(options_layout, 1, 0, 1, 3)
        main_layout.addLayout(com_layout, 2, 0, 1, 1)
        main_layout.addLayout(control_menu_layout, 3, 2, 1, 1)

        # Scroll area for images
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area, 4, 0, 2, 3)

        # QLabel for image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False)
        font = self.image_label.font()
        font.setPointSize(15)
        self.image_label.setFont(font)

        self.scroll_area.setWidget(self.image_label)

    def process_image(self, recalculating=False):
        self.mode = self.IMAGE_MODE

        # Create MusicSheet object
        self.music_sheet = MusicSheet()
        self.music_sheet.set_model_note(self.model_note_path)

        if recalculating or self.load_image():
            self.image_label.setText("Processing Image...")
            # Refresh the Label
            self.image_label.repaint()

            self.music_sheet.set_image(self.image_path)
            # At the moment, there is some fine-tuning that works better with this scale
            self.music_sheet.resize_image(height=900)

            self.music_sheet.run_detection(self.number_of_pad_lines_box.value())
            self.is_double_handed = self.music_sheet.is_double_handed
            image = self.music_sheet.get_results_image(show_noteheads_centroids=True,
                                                       show_bounding_boxes=True,
                                                       show_noteheads_contours=False,
                                                       show_barlines=True,
                                                       show_class_label=False,
                                                       show_noteheads_pitch=True,
                                                       height=900)
            self.display_cv_image(image)
            self.compute_commands_for_image()
            self.filename = extract_file_name_from_path(self.image_path)
            self.save_commands_to_txt(self.filename)

    def compute_commands_for_image(self):
        """Helper function that accommodates note durations to selected tempo and then computes commands.\n\n
        Created for the purpose of recalculating commands if tempo is changed from GUI."""

        time_series = {}
        # Transform durations according to selected tempo (necessary for computing commands algorithm)
        print(self.music_sheet.time_series)
        for key, value in self.music_sheet.time_series_dict.items():
            t = self.calculate_tempo(key)
            time_series[t] = value

        keys = list(time_series.keys())
        keys.sort()
        # for k in keys:
        #     print(k, " -> ", time_series[k])

        self.commands = (ActionScheduler2.schedule_actions(time_series))
        if self.checkbox_skip_black.isChecked():
            self.remove_black_keys()
        # New tempo was considered, so it is not 'changed' anymore
        self.tempo_changed = False

    def remove_black_keys(self):
        for _, hands in self.commands.items():
            for _, hand in hands.items():
                hand[1] = [int(a) for a in hand[1]]  # Remove rotation towards black keys
                hand[2] = [0 for _ in hand[2]]  # Suppress extensions

    def calculate_tempo(self, duration):
        note_name = self.note_options.currentText()
        note_modifier = self.note_options_dict[note_name]
        whole_note_duration = int(60000 / self.tempo_box.value() * note_modifier)  # in milliseconds

        return duration * whole_note_duration

    def load_image(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Music Sheet", self.default_image_folder, "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if image_path:
            self.image_path = image_path
            return True
        else:
            return False

    def load_pdf(self):
        print('pdf')
        self.mode = self.PDF_MODE

    def load_midi(self):
        """Loads midi file, extracts notes and computes commands.\n
        Return True if file opened correctly, false otherwise."""

        self.image_label.setText("Processing MIDI...")
        midi_path, _ = QFileDialog.getOpenFileName(self, "Select MIDI File", self.default_midi_folder, "MIDI (*.mid)")
        if midi_path:
            self.filename = extract_file_name_from_path(midi_path)
            time_series = midconv.extract_notes_from_midi(midi_path)
            self.commands = (ActionScheduler2.schedule_actions(time_series))
            self.image_label.setText(f"\"{self.filename}\"\n\n ready to go!")
            self.mode = self.MIDI_MODE
            self.save_commands_to_txt(self.filename)
            return True
        else:
            return False

    def load_txt(self):
        self.image_label.setText("Processing txt file...")
        txt_path, _ = QFileDialog.getOpenFileName(self, "Select txt File", self.default_txt_folder, "txt (*.txt)")
        commands = {}

        if not txt_path:
            self.image_label.setText('')
            return

        self.mode = self.TXT_MODE
        with open(txt_path, 'r') as file:
            lines = [list(map(float, line.split())) for line in file if line.strip()]

            for line in lines:
                key = line[0]
                nums = line[1:]
                commands[key] = line_to_dict(nums)

        self.commands = copy.deepcopy(commands)
        self.filename = extract_file_name_from_path(txt_path)
        self.image_label.setText(f"\"{self.filename}\"\n\n ready to go!")

    def recalculate(self):
        cfg.load_config()
        if self.mode == self.IMAGE_MODE:
            self.process_image(recalculating=True)

    def write_commands_to_file(self, txt_path):
        num_fingers = cfg.config['NUM_OF_FINGERS']
        min_position = cfg.config['MIN_HAND_CENTER_POSITION']
        skip_left = self.checkbox_skip_hand.isChecked()

        with open(txt_path, "w") as file:
            for timestamp, command in self.commands.items():
                if timestamp < 0:
                    continue

                line = [str(round(timestamp, 2))]

                for hand_name, hand_content in command.items():
                    skipCond = hand_name == 'left' and skip_left
                    for elem in hand_content:
                        if isinstance(elem, Iterable) and not isinstance(elem, (str, bytes)):
                            values = [0] * num_fingers if skipCond else elem
                            line.extend(str(v) for v in values)
                        else:
                            line.append(str(min_position if skipCond else elem))
                file.write(' '.join(line) + '\n')
            print('File saved to txt')

    def save_commands_to_txt(self, name: str):
        if self.save_commands_checkbox.isChecked():
            txt_path = self.default_txt_folder + '\\' + name + '.txt'
            if not os.path.exists(txt_path):
                self.write_commands_to_file(txt_path)
            else:
                msg = QMessageBox(self)
                msg.setWindowTitle("File already exists")
                msg.setText(f"The file:\n{txt_path}\nalready exists.\nWhat do you want to do?")

                overwrite_btn = msg.addButton("Overwrite", QMessageBox.DestructiveRole)
                save_new_btn = msg.addButton("Save separately", QMessageBox.ActionRole)
                discard_btn = msg.addButton("Discard", QMessageBox.RejectRole)
                msg.setDefaultButton(save_new_btn)

                msg.setIcon(QMessageBox.Warning)
                msg.exec_()
                clicked = msg.clickedButton()

                if clicked == discard_btn:
                    pass
                elif clicked == save_new_btn:
                    counter = 1
                    while os.path.exists(self.default_txt_folder + '\\' + name + f' ({counter})' + '.txt'):
                        counter += 1
                    self.write_commands_to_file(self.default_txt_folder + '\\' + name + f' ({counter})' + '.txt')
                elif clicked == overwrite_btn:
                    self.write_commands_to_file(txt_path)

    def ulterior_save(self):
        if self.save_commands_checkbox.isChecked() and self.commands:
            choice = QMessageBox.question(None, ' ', 'Save current commands?', QMessageBox.Yes | QMessageBox.No)
            if choice == QMessageBox.Yes:
                self.save_commands_to_txt(self.filename)

    def send_commands(self):
        if self.tempo_changed and self.mode == self.IMAGE_MODE:
            self.compute_commands_for_image()
        try:
            # Open Serial
            selected_port = self.port_box.currentText()
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = serial.Serial(selected_port, self.baud_rate)
            time.sleep(1)

            # Send commands in another thread
            self.com_opened = True
            self.com_thread = threading.Thread(target=self.serial_listener, daemon=True)
            self.com_thread.start()

        except serial.SerialException as e:
            print(f'Serial error: {e}')
        except Exception as e:
            print(f"Unexpected error: {e}")

    def serial_listener(self):
        """Thread worker: listens to serial and sends data"""
        serial_line = ''
        communication_messages = [b'R']
        time_keys = list(self.commands.keys())

        for com_idx, current_time in enumerate(time_keys):
            if com_idx < len(time_keys) - 1:
                next_time = time_keys[com_idx+1]
                duration = next_time - current_time
            else:
                duration = 0
            hands = self.commands[current_time]
            l_command = hands['left']
            r_command = hands['right']

            while self.com_opened:
                serial_line = self.ser.readline().strip()
                if serial_line in communication_messages:
                    break
                else:
                    print(serial_line)

            if serial_line == b'R':
                duration = int(duration)
                self.ser.write(duration.to_bytes(4, 'big'))
                self.send_serial_data(l_command)
                self.send_serial_data(r_command)

            if not self.com_opened:
                break

        self.com_opened = False
        self.ser.close()

    def stop_serial_listener(self):
        self.com_opened = False
        if self.com_thread:
            self.com_thread.join()
        if self.ser:
            self.ser.close()
        print('Stopped')

    def send_serial_data(self, command):
        pos, rotations, back_s, front_s = command
        F = cfg.config['NUM_OF_FINGERS']

        self.ser.write(int(pos).to_bytes(1, 'big'))
        for i in range(F):
            self.ser.write(struct.pack('<f', rotations[i]))
            # self.ser.write(math.ceil(rotations[i]*2).to_bytes(4, 'big', signed=True))
        for i in range(F):
            back_s[i] = int(back_s[i])
            self.ser.write(back_s[i].to_bytes(1, 'big'))
        for i in range(F):
            front_s[i] = int(front_s[i])
            self.ser.write(front_s[i].to_bytes(1, 'big'))

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
        real_ports = []  # Some ghosted ports where shown, so I filtered them
        for p in ports:
            if "Bluetooth" not in p.description:
                real_ports.append(p.device)
        port_list = [port for port in real_ports]
        self.port_box.addItems(port_list)

        # Restore selection if still present
        if current in port_list:
            index = self.port_box.findText(current)
            self.port_box.setCurrentIndex(index)

        self.port_box.blockSignals(False)

    def on_checkbox_toggled(self, state):
        if state:  # Checkbox was checked
            pass


if __name__ == "__main__":
    # Suppress YOLO logging, all but errors
    logging.getLogger("ultralytics").setLevel(logging.ERROR)

    app = QApplication(sys.argv)
    window = GUI()
    window.show()
    sys.exit(app.exec_())
