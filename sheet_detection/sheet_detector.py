import math
from collections import Counter, namedtuple
import cv2
import numpy as np
import bisect
import torch
from Notes import NoteOrRest, NoteWithPosition
from ultralytics import YOLO
import configLib as cfg


PitchInfo = namedtuple("PitchInfo", ["pitch_value", "pitch_name"])


def display_cv_image(image, name='Image name', already_colored=False):
    if not already_colored:
        image = (1 - image) * 255
    cv2.imshow(name, image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


class Staff:
    def __init__(self, music_sheet_parent):
        self.nr_of_lines_above_or_below = 5
        self.music_sheet_parent = music_sheet_parent
        self.x1 = 0
        self.y1 = 0
        self.x2 = 0
        self.y2 = 0
        self.clef = 'Treble-clef'
        self.window_pad = 0  # Padding around the staff to account for notes above or below when cropping the image
        self.barlines_x_coord = []
        self.crop_original = None
        self.crop_binary = None  # The cropped part of the music sheet that contains the staff
        self.detections = None
        self.noteheads_contours = None
        self.noteheads_centroids = []
        self.intervals_idx = []  # Used to determine the pitches of notes
        self.measures = []
        self.pitch_names = ['DO', 'RE', 'MI', 'FA', 'SOL', 'LA', 'SI']
        self.durations_dict = {'Full-note': 1, 'Half-dot': 1/2 + 1/4, 'Half-note': 1/2, 'Quarter-dot': 1/4 + 1/8,
                               'Quarter-note': 1/4, 'Eighth-note': 1/8, 'Sixteenth-note': 1/16, 'Full-rest': 1,
                               'Half-rest': 1/2, 'Quarter-rest': 1/4, 'Eighth-rest': 1/8}

    def get_window(self):
        y1 = max(self.y1 - self.window_pad, 0)
        y2 = self.y2 + self.window_pad
        return y1, y2

    def set_crop(self, crop):
        """*crop* should be taken from the original image (not binary).
        \nIt is used to set both *self.crop_original* and *self.crop_binary*"""
        self.crop_original = crop
        # self.crop_original = cv2.line(self.crop_original, (0, self.y1 - self.window_y1_global), (self.width-1, self.y1 - self.window_y1_global), color=(255, 0, 0), thickness=2)
        # self.crop_original = cv2.line(self.crop_original, (0, self.y2 - self.window_y1_global), (self.width-1, self.y2 - self.window_y1_global), color=(255, 0, 0), thickness=2)
        self.crop_binary = binarize_image(crop, normalize=True, invert=True)

    def detect_with_yolo(self):
        """
        Applies detection with the YOLO model.
        Sorts the detection.boxes by x-coordinate.
        Sets the clef.
        """
        self.detections = self.model_note(self.crop_original, verbose=False)[0]

        # Sort boxes by the x-coord of the center
        boxes = self.detections.boxes
        sorted_indices = torch.argsort(boxes.xywh[:, 0])
        boxes.data = boxes.data[sorted_indices]
        self.detections.boxes = boxes

        # Set the clef
        names = self.detections.names
        self.clef = next((names[box.cls.item()] for box in self.detections.boxes if 'clef' in names[box.cls.item()]),
                         None)

    def detect_noteheads(self):
        crop_binary_copy = np.copy(self.crop_binary)

        # ---- Apply Run Length Encoding for staff removal ----
        # Remove the vertical runs that are thinner than staffline_width
        crop_binary_copy = vertical_rle_removal(crop_binary_copy, self.staffline_width)

        # Operate on a different image to detect notes that get fragmented
        crop_for_fragmented_notes = np.copy(crop_binary_copy)

        # Remove too long or too short horizontal runs
        crop_binary_copy = horizontal_rle_removal(crop_binary_copy, self.max_staffline_width, 2 * self.staffspace_width)

        # ---- Take care of fragmented noteheads ----
        # This is necessary because during staff removal, whole and half note-heads are not well-preserved

        # Dilate to close fragmented notes
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        crop_for_fragmented_notes = cv2.morphologyEx(crop_for_fragmented_notes, cv2.MORPH_CLOSE, kernel)
        crop_for_fragmented_notes = horizontal_rle_removal(crop_for_fragmented_notes, self.max_staffline_width,
                                                           3 * self.staffspace_width)
        # Fill holes, so whole and half notes are correctly detected by elliptical kernel
        contours, _ = cv2.findContours(crop_for_fragmented_notes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(crop_for_fragmented_notes, contours, -1, (1, 0, 0), -1)

        # Save only the bits of image where an ellipse would fit
        kernel = np.array([
            [0, 1, 1, 1, 0],
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [0, 1, 1, 1, 0]], dtype=np.uint8)
        crop_for_fragmented_notes = cv2.morphologyEx(crop_for_fragmented_notes, cv2.MORPH_OPEN, kernel)
        crop_binary_copy = cv2.morphologyEx(crop_binary_copy, cv2.MORPH_OPEN, kernel, iterations=1)

        # Save only the elliptical contours
        filtered_contours = get_elliptical_contours(crop_binary_copy)
        filtered_contours2 = get_elliptical_contours(crop_for_fragmented_notes)
        comb_img = np.zeros(self.crop_binary.shape, dtype=np.uint8)
        cv2.drawContours(comb_img, filtered_contours + filtered_contours2, -1, (1, 0, 0), -1)
        self.noteheads_contours, _ = cv2.findContours(comb_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.noteheads_centroids = calculate_centroids(self.noteheads_contours)
        self.noteheads_centroids.sort()

    def detect_barlines(self):
        # It assumes that the barlines have the same y-coords

        crop = np.copy(self.crop_binary)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (math.ceil(self.staffline_width / 2), self.staff_height))
        barlines_crop = cv2.morphologyEx(crop, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(barlines_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bars = [cv2.boundingRect(cnt) for cnt in contours]
        bars_filtered = [(y, h) for (_, y, _, h) in bars]

        # Get the 2 most common, because it may happen for some note stems to align and be more than the barlines
        most_common_bars = [item[0] for item in Counter(bars_filtered).most_common(2)]

        # Add some tolerance in most_common_bars
        tol = 3
        most_common_bars = [(y - tol, y + tol, h - tol, h + tol) for (y, h) in most_common_bars]

        # Filter bars that fall within tolerance range and do not intersect other elements
        bars_x_coords = [x for (x, y, _, h) in bars if any(y_min <= y <= y_max and h_min <= h <= h_max
                                                           for (y_min, y_max, h_min, h_max) in most_common_bars)
                         and not is_within_any_note_x_range(x, self.detections)
                         and not is_within_any_contour_x_range(x, self.noteheads_contours)]

        # If there are two barlines too close, keep just the last one
        bars_x_coords.sort()
        if bars_x_coords:
            final_bars_x_coords = [bars_x_coords[0]]
            for x in bars_x_coords[1:]:
                if x - final_bars_x_coords[-1] > 5 * self.staffspace_width:  # Check the distance from the last kept x
                    final_bars_x_coords.append(x)
                else:
                    final_bars_x_coords[-1] = x
        else:
            final_bars_x_coords = []

        # If there are no barlines detected, consider one as being the end of the image,
        # otherwise everything will get lost in assign_into_measures
        if not final_bars_x_coords:
            self.barlines_x_coord = [self.crop_original.size]
        else:
            self.barlines_x_coord = final_bars_x_coords
            self.barlines_x_coord.sort()

    def assign_into_measures(self):
        """
            Splits detections and noteheads into measures based on barline x coordinates,
            then uses a two-pointer approach to assign notehead pitches to each detection.
        """
        names = self.detections.names

        # --- Detect the modifiers (diez, bemol) that apply globally for the staff ---
        global_diez = []
        global_bemol = []
        local_modifier_thresh = 4 * self.staffspace_width  # A threshold to determine if a modifier is local or global
        all_boxes = self.detections.boxes.xyxy.tolist()

        cls_ids = self.detections.boxes.cls.tolist()
        detection_names = [names[i] for i in cls_ids]
        for i, box_xyxy in enumerate(all_boxes):
            class_name = detection_names[i]
            (x1, y1, x2, y2) = box_xyxy
            center_x = int((x1 + x2) / 2)

            # Assume that the modifiers (diez, bemol) that apply globally are before any note/rest detected
            # so if the current object is a note/rest, stop looking for global modifiers
            if class_name in self.durations_dict:
                break

            # Check if there is a next element
            if i < len(all_boxes) - 1:
                (next_x1, _, next_x2, _) = all_boxes[i + 1]
                next_class_name = detection_names[i + 1]
                center_next_x = int((next_x1 + next_x2) / 2)

                # Stop processing if the modifier is too close to a note (it means that it applies to that note only)
                if next_class_name in self.durations_dict and (center_next_x - center_x) <= local_modifier_thresh:
                    break

            # Process global modifiers
            if class_name in ["Diez", "Bemol"]:
                # Calculate the "pitch" of diez and bemol by their bounding boxes
                center_y = int((y1 + y2) / 2) if class_name == "Diez" else int(y1 + (2 / 3) * (y2 - y1))
                pitch_name = self.assign_pitch((center_x, center_y)).pitch_name

                # Store pitch in appropriate list
                (global_diez if class_name == "Diez" else global_bemol).append(pitch_name)

                # Draw marker
                cv2.circle(self.crop_original, (center_x, center_y), 2, (255, 0, 0), thickness=-1)

        # --- Assign pitches to boxes and boxes into measures (result: notes with pitch and duration) ---
        box_idx = 0
        notehead_idx = 0
        modifier = 0
        new_noteheads_centroids = []
        # To determine if there are stacked boxes for notes
        # (which would mean they are played together and not one after the other)
        prev_x1x2 = (0, 0)

        for bar_x in self.barlines_x_coord:
            measure = []
            # Add detection boxes if the center falls within the current measure.
            for i in range(box_idx, len(self.detections.boxes)):
                x1, y1, x2, y2 = all_boxes[i]
                box_name = detection_names[i]
                if x2 < bar_x:
                    if box_name in ['Diez', 'Bemol']:
                        modifier = 0.5 if box_name == 'Diez' else -0.5
                    elif box_name in self.durations_dict:
                        note = NoteOrRest()
                        note.duration = self.durations_dict[box_name]
                        if 'rest' in box_name:
                            note.pitch.append('REST')
                        else:
                            pitch_found = False
                            # Add noteheads that fall within the measure (assumes noteheads_with_pitches is sorted by x)
                            for j in range(notehead_idx, len(self.noteheads_centroids)):
                                x = self.noteheads_centroids[j][0]
                                y = self.noteheads_centroids[j][1]
                                if x1 < x < x2 and y1 < y < y2:
                                    pitch_info = self.assign_pitch((x, y))
                                    new_noteheads_centroids.append((x, y))

                                    if pitch_info.pitch_name in global_diez:
                                        modifier = 0.5
                                    elif pitch_info.pitch_name in global_bemol:
                                        modifier = -0.5

                                    note.pitch.append(pitch_info.pitch_value + modifier)
                                    modifier = 0  # Reset the modifier
                                elif x > x2:
                                    notehead_idx = j
                                    break

                            # If no notehead was found and this is a 'Full-note', assign a pitch by center of box.
                            if not pitch_found and box_name == 'Full-note':
                                c = ((x1 + x2) / 2, (y1 + y2) / 2)
                                new_noteheads_centroids.append(c)
                                note.pitch.append(self.assign_pitch(c).pitch_value)

                        # Make the pitches be unique (pitch is a list in order to account for chords;
                        # chords do not contain the same pitch multiple times)
                        # Add the note only if it has pitch detected
                        if note.pitch:
                            note.pitch = list(dict.fromkeys(note.pitch))

                            # Check if there are stacked boxes (this mainly happens for whole-note chords)
                            if prev_x1x2[0] < (x1 + x2) / 2 < prev_x1x2[1]:
                                measure[-1].pitch.extend(note.pitch)
                            else:
                                measure.append(note)

                        prev_x1x2 = (x1, x2)
                else:
                    box_idx = i
                    break

            # Only include measures that have detections.
            # if measure:
            self.measures.append(measure)

        self.noteheads_centroids = new_noteheads_centroids

    def assign_pitch(self, centroid):
        y_ref = bisect.bisect_right(self.intervals_idx, self.y2_local) - 1
        x, y = centroid
        y_aux = bisect.bisect_right(self.intervals_idx, y) - 1
        pitch = y_ref - y_aux
        if self.clef == 'Bass-clef':
            pitch -= 2  # Adjust the pitches so that C3 (DO inside Bass staff) gets the index 1
        else:
            pitch += 3  # Adjust the pitches so that C4 (DO right below Treble staff) gets the index 1

        pitch_name = self.pitch_names[pitch % len(self.pitch_names)]

        return PitchInfo(pitch_value=pitch, pitch_name=pitch_name)

    def assign_line_intervals(self, line_beginnings, line_endings):
        # The lines by which the pitch is detected; any notehead center that falls between
        # two lines, is of that pitch
        tol = 1
        line_beginnings = [max(line - self.window_y1_global - tol, 0) for line in line_beginnings]
        line_endings = [line - self.window_y1_global + tol for line in line_endings]

        ssw_coef = [i for i in range(1, self.nr_of_lines_above_or_below + 1) for _ in range(2)]  # slw = staffline_width
        slw_coef = [0] + ssw_coef[:-1]  # ssw = staffspace_width
        slw_idx = [c * (self.staffline_width + tol) for c in slw_coef]
        ssw_idx = [c * (self.staffspace_width - tol) for c in ssw_coef]

        intervals_above = [max(line_beginnings[0] - (a + b), 0) for a, b in zip(slw_idx, ssw_idx)]
        intervals_below = [line_endings[-1] + a + b for a, b in zip(slw_idx, ssw_idx)]

        self.intervals_idx = line_beginnings + line_endings + intervals_above + intervals_below

        self.intervals_idx.sort()


        # for l in self.intervals_idx:
        #     cv2.line(self.crop_original, (0, l), (100, l), color=(200, 0, 0), thickness=1)
        # display_cv_image(self.crop_original, already_colored=True)

    @property
    def staff_width(self):
        return self.x2 - self.x1

    @property
    def staff_height(self):
        return self.y2 - self.y1

    @property
    def staffline_width(self):
        return self.music_sheet_parent.staffline_width

    @property
    def staffspace_width(self):
        return self.music_sheet_parent.staffspace_width

    @property
    def max_staffline_width(self):
        return self.music_sheet_parent.max_staffline_width

    @property
    def model_note(self):
        return self.music_sheet_parent.model_note

    @property
    def slw_tolerance(self):
        return self.music_sheet_parent.slw_tolerance

    @property
    def window_y1_global(self):
        return self.y1 - self.window_pad

    @property
    def y2_local(self):
        return self.y2 - self.window_y1_global

    @property
    def window_height(self):
        return self.staff_height + 2 * self.window_pad


class MusicSheet:
    def __init__(self, image=None):
        self.folder_path = None
        self.image_path = None
        self.max_staffline_width = 0
        self.staffline_width = 0
        self.staffspace_width = 0
        self.model_clefs = None
        self.model_note = None
        self.slw_tolerance = 4
        self.is_double_handed = True  # True if it contains bass-clef, False if only treble-clef
        self.time_series = []
        if image is None:
            self.original_image = np.zeros((1, 1))
            self.binary_image = np.zeros((1, 1))
            self.height = 1
            self.width = 1
        else:
            self.set_image(image)
        self.all_staves = []

    def set_folder_and_image_paths(self, folder_path, image_path):
        self.folder_path = folder_path
        self.image_path = image_path

    def set_image(self, image_path):
        """Takes the image path. Sets the original image and the binarized one"""
        self.original_image = cv2.imread(image_path)
        self.height = self.original_image.shape[0]
        self.width = self.original_image.shape[1]
        self.binary_image = binarize_image(self.original_image, 210, True, True)

    def set_model_note(self, model_path):
        """Receives the path for the model and sets it."""
        self.model_note = YOLO(model_path)

    def resize_image(self, height):
        self.height = height
        self.original_image, self.width = resize_with_aspect_ratio(self.original_image, height)
        self.binary_image = binarize_image(self.original_image, 210, True, True)

    def _calculate_staffline_and_staffspace_widths(self):
        """Calculates the **staffline_width** and **staffspace_width**
        \nReturns the y-coordinates of the lines considered to be staff lines"""
        # Create row histogram
        row_histogram = np.sum(self.binary_image == 1, axis=1)

        max_row_hist = max(row_histogram)
        staff_line_threshold = round(4 / 5 * max_row_hist)

        # DEFINITION: black_rows= the rows with the highest values in the row histogram (as a fraction of the max value)
        # The indices of the black_rows (the heights at which they appear in the image)
        indices = [i for i, v in enumerate(row_histogram) if v >= staff_line_threshold]
        all_line_widths, space_widths, line_beginnings, line_endings = [], [], [indices[0]], []
        line_width = 1
        # Adjacent black_rows are part of the same line; from this we can determine the average line width
        for j in range(1, len(indices)):
            dif = indices[j] - indices[j - 1]
            if dif == 1:  # Check if lines are within ±1; this means they are part of the same staff line
                line_width += 1
            else:  # If not, it means we hit a space between lines, and 'dif' indicates its width
                all_line_widths.append(line_width)
                line_width = 1
                space_widths.append(dif - 1)  # -1 to not count one of the black_rows as white space
                line_beginnings.append(indices[j])  # A new line begins
                line_endings.append(indices[j-1])  # Previous line ended

        # Append
        line_endings.append(indices[-1])
        all_line_widths.append(line_width)
        self.max_staffline_width = max(all_line_widths)

        # Determine staff line and space widths as the most common value
        self.staffline_width = Counter(all_line_widths).most_common(1)[0][0]
        self.staffspace_width = Counter(space_widths).most_common(1)[0][0]

        return line_beginnings, line_endings

    def detect_staves(self):
        """Detect the y-positions that bound the staves. Staves are described as 5 consecutive stafflines."""
        line_beginnings, line_endings = self._calculate_staffline_and_staffspace_widths()
        # Determine staves as consecutive lines close to each other
        space_between_line_beginnings = self.staffspace_width + self.staffline_width + self.slw_tolerance
        num_of_staff_lines = 5
        consecutives = 1
        beginning_of_staff = line_beginnings[0]
        start_idx = 0

        # Iterate over detected line beginnings, starting from the second one
        for j in range(1, len(line_beginnings)):
            # Create a new Staff object and associate it with the current music sheet
            staff = Staff(music_sheet_parent=self)

            start_of_line = line_beginnings[j]

            # Check if the current line is close enough to the previous one to be considered part of the same staff
            if start_of_line - line_beginnings[j - 1] <= space_between_line_beginnings:
                consecutives += 1  # Increase the count of consecutive lines
            else:
                # If the gap is too big, reset for a new potential staff
                consecutives = 1
                beginning_of_staff = start_of_line
                start_idx = j

            # If we have found the expected number of lines for a staff (e.g., 5)
            if consecutives == num_of_staff_lines:
                staff.x1 = 0
                staff.x2 = self.width
                staff.y1 = beginning_of_staff  # Set the top boundary of the staff
                staff.y2 = line_endings[j]  # Set the bottom boundary of the staff (using corresponding line ending)

                # Calculate how much padding can be added above and below the staff without exceeding image bounds
                max_pad_above = staff.y1
                max_pad_below = self.height - staff.y2

                # Determine padding based on spacing tolerance and max allowable space
                staff.window_pad = min(
                    (space_between_line_beginnings - self.slw_tolerance) * staff.nr_of_lines_above_or_below,
                    max_pad_above,
                    max_pad_below
                )

                # # Assign the list of line intervals that make up this staff
                # staff.assign_line_intervals(line_beginnings[start_idx:j + 1], line_endings[start_idx:j + 1])

                # Define the crop region for the staff image including the padding
                crop_limit_above = staff.y1 - staff.window_pad
                crop_limit_below = staff.y2 + staff.window_pad

                # Crop the staff from the original image and store it
                staff.set_crop(self.original_image[crop_limit_above:crop_limit_below, 0:self.width])

                staff.assign_line_intervals(line_beginnings[start_idx:j + 1], line_endings[start_idx:j + 1])


                # Add the completed staff to the list of all detected staves
                self.all_staves.append(staff)

                # Reset counters and markers for the next potential staff
                beginning_of_staff = start_of_line
                start_idx = j
                consecutives = 1

    def sync_barlines(self):
        # Sync the barlines of treble and bass staves that go hand-in-hand
        for idx, staff in enumerate(self.all_staves[:-1]):
            next_staff = self.all_staves[idx + 1]
            if staff.clef == 'Treble-clef' and next_staff.clef == 'Bass-clef':
                barlines_union = list(set(staff.barlines_x_coord) | set(next_staff.barlines_x_coord))
                barlines_union.sort()
                staff.barlines_x_coord = barlines_union
                next_staff.barlines_x_coord = barlines_union

    def verify_clefs(self):
        """It may happen that clefs are wrongly classified (especially bass-clef). If this happens, syncing barlines
        may be problematic (as a staff syncs with another that it is not paired with). For this, check if the bass-clefs
        are at least 2/3 of treble-clefs (there are music sheets that have more treble staffs than bass, so they are
        not exactly half-and-half). If not, make them all treble-clef"""
        treble_count = 0
        bass_count = 0
        for staff in self.all_staves:
            if staff.clef == 'Bass-clef':
                bass_count += 1
            else:
                treble_count += 1
        if bass_count < 2/3 * treble_count:
            self.is_double_handed = False
            for staff in self.all_staves:
                staff.clef = 'Treble-clef'

    def sync_measures_time(self):
        """If the music score is double-handed, the measures need to stay in sync, because if there are
        undetected notes, they will go out of phase"""
        if self.is_double_handed:
            # Verify if the durations inside the measure of Treble-staff match the durations in Bass-staff measures
            # add a REST to fill in the duration
            for staff, next_staff in zip(self.all_staves[:-1], self.all_staves[1:]):
                if staff.clef == 'Treble-clef' and next_staff.clef == 'Bass-clef':
                    # Assume the measures are synced between Treble and Bass
                    for measure, next_measure in zip(staff.measures, next_staff.measures):
                        treble_duration_sum = sum(note.duration for note in measure)
                        bass_duration_sum = sum(note.duration for note in next_measure)
                        duration_diff = abs(treble_duration_sum - bass_duration_sum)

                        if duration_diff > 0:
                            rest_note = NoteOrRest(['REST'], duration_diff)
                            (measure if treble_duration_sum < bass_duration_sum else next_measure).append(rest_note)

    def calculate_time_series(self):
        treble_time, bass_time = 0, 0
        right_series = []
        left_series = []

        for staff in self.all_staves:
            for measure in staff.measures:
                for note in measure:
                    # Bass is one octave lower
                    time_ref, series, octave = (treble_time, right_series, cfg.config['MAIN_OCTAVE'] - 1) \
                                                        if staff.clef == 'Treble-clef'\
                                                        else (bass_time, left_series, cfg.config['MAIN_OCTAVE'] - 2)
                    chord = []
                    for pitch in note.pitch:
                        piano_key_code = (cfg.config['NUM_OF_WHITE_KEYS_IN_OCTAVE'] * octave + pitch if
                                          pitch != 'REST' else 'REST')
                        chord.append(NoteWithPosition(piano_key_code, note.duration))
                    series.append(chord)

                    if staff.clef == 'Treble-clef':
                        treble_time += note.duration
                    else:
                        bass_time += note.duration

        self.time_series = [right_series, left_series]

    def run_detection(self):
        """Calls every method needed to detect anything necessary. At the end, computes the time series."""
        self.detect_staves()
        for staff in self.all_staves:
            staff.detect_with_yolo()
            staff.detect_noteheads()
            staff.detect_barlines()

        self.verify_clefs()
        self.sync_barlines()

        for staff in self.all_staves:
            staff.assign_into_measures()

        self.sync_measures_time()
        self.calculate_time_series()

    def show_original_image(self):
        cv2.imshow('Original Image', self.original_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def show_binary_image(self):
        cv2.imshow('Binary Image', self.binary_image * 255)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def get_results_image(self, show_noteheads_contours=True, show_bounding_boxes=True,
                          show_barlines=True, show_noteheads_centroids=False, show_class_label=False,
                          show_noteheads_pitch=False, height=550):
        image = np.copy(self.original_image)

        for staff in self.all_staves:
            if show_barlines:
                for x in staff.barlines_x_coord:
                    cv2.line(image, (x, staff.y1), (x, staff.y2), (0, 0, 255), 3)

            if show_noteheads_contours:
                # Contours in staff are with coordinates relative to the crop, translate them relative to original image
                offset = np.array([0, staff.y1 - staff.window_pad])
                shifted_contours = [contour + offset for contour in staff.noteheads_contours]
                cv2.drawContours(image, shifted_contours, -1, (255, 0, 0), 2)

            if show_bounding_boxes:
                offset = staff.y1 - staff.window_pad
                for box in staff.detections.boxes:
                    cls_idx = box.cls.item()
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(image, (x1, y1 + offset), (x2, y2 + offset), (255, 200, 0), 2)

                    if show_class_label:
                        cv2.putText(image, str(int(cls_idx)), (x1, y1 - 5 + offset), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.6, (255, 0, 0), 1, lineType=cv2.LINE_AA)

            if show_noteheads_centroids:
                offset = staff.y1 - staff.window_pad
                for c in staff.noteheads_centroids:
                    image = cv2.circle(image, (int(c[0]), int(c[1]) + offset), 2, (0, 255, 255), thickness=-1)

            if show_noteheads_pitch:
                offset = staff.y1 - staff.window_pad
                for c in staff.noteheads_centroids:
                    pitch, _ = staff.assign_pitch(c)
                    cv2.putText(image, str(pitch), (int(c[0]) + 5, int(c[1]) + offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), thickness=1, lineType=cv2.LINE_AA)

        image, _ = resize_with_aspect_ratio(image, height)

        return image

    def show_results(self, show_noteheads_contours=True, show_bounding_boxes=True,
                     show_barlines=True, show_noteheads_centroids=False, show_class_label=False):

        image = self.get_results_image(show_noteheads_contours, show_bounding_boxes, show_barlines,
                                       show_noteheads_centroids, show_class_label)
        cv2.imshow('img', image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def is_circular_or_elliptical(contour):
    """Determines if a contour is circular, by calculating its circularity.
    Circularity = (4 * pi * Area) / (Perimeter^2)"""
    # Compute the contour's area and perimeter
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)

    # Avoid division by zero (if perimeter is too small)
    if perimeter == 0:
        return False

    # Calculate circularity
    circularity = (4 * np.pi * area) / (perimeter ** 2)

    # Check if circularity is close to 1 (for circular shapes)
    if circularity > 0.7:
        return True


def binarize_image(image, thresh=210, normalize=False, invert=False):
    """Binarize image based on thresh.
    \nNormalize->makes white=1 and black=0.
    \nInvert-> white becomes black and black becomes white """
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, image = cv2.threshold(image, thresh, 255, cv2.THRESH_BINARY)

    if invert:
        image = (255 - image)
    if normalize:
        image //= 255

    return image


def resize_with_aspect_ratio(image, new_h):
    height, width = image.shape[:2]
    ratio = height / width
    new_w = int(new_h / ratio)
    image = cv2.resize(image, (new_w, new_h))
    return image, new_w


def get_elliptical_contours(image):
    """Find contours and keep only those that are circular enough"""
    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filtered_contours = [cnt for cnt in contours if is_circular_or_elliptical(cnt)]
    return filtered_contours


def calculate_centroids(contours):
    """Returns the centers of a list of contours"""
    centroids = []
    for contour in contours:
        moments = cv2.moments(contour)

        # Calculate centroid
        if moments["m00"] != 0:  # Avoid division by zero
            cx = (moments["m10"] / moments["m00"])
            cy = (moments["m01"] / moments["m00"])
        else:
            cx, cy = 0, 0  # If the area is zero, centroid is undefined
        # (cx, cy), radius = cv2.minEnclosingCircle(contour)

        centroids.append((round(cx, 3), round(cy, 3)))

    return centroids


def is_within_any_note_x_range(x, bounding_boxes):
    """Helper function to check if x intersects any detected bounding box"""
    for box in bounding_boxes.boxes.xyxy:
        x1, _, x2, _ = box
        if x1 <= x <= x2:
            return True
    return False


def is_within_any_contour_x_range(x, contours, tolerance=3, min_nr_of_intersections=1):
    """Helper function to check if x intersects any contour's bounding box (within a tolerance)"""
    intersections = 1
    for contour in contours:
        x_contour, y_contour, w_contour, h_contour = cv2.boundingRect(contour)
        if x_contour - tolerance <= x <= (x_contour + w_contour + tolerance):
            if intersections != min_nr_of_intersections:
                intersections += 1
            else:
                return True
    return False


def vertical_rle_removal(image, thresh, background=0, foreground=1):
    """Removes the Vertical Run Lengths of color *foreground* **smaller** than *thresh*"""
    for col_idx in range(image.shape[1]):
        current_run_color = image[0, col_idx]
        beginning_idx = 0
        run_length = 0
        for row_idx in range(image.shape[0]):
            if image[row_idx, col_idx] == current_run_color:
                run_length += 1
            else:
                if current_run_color == foreground and run_length <= 1 * thresh:
                    image[beginning_idx:row_idx, col_idx] = background
                run_length = 0
                beginning_idx = row_idx
                current_run_color = image[row_idx, col_idx]
        if current_run_color == foreground and run_length <= 1 * thresh:
            image[beginning_idx:row_idx, col_idx] = background

    return image


def horizontal_rle_removal(image, lower_thresh=0.0, upper_thresh=1000000, background=0, foreground=1):
    """Removes the Horizontal Run Lengths of color *foreground* **smaller or equal** than *lower_thresh* or
    **larger** than *upper_thresh*"""
    for row_idx in range(image.shape[0]):
        current_run_color = image[row_idx, 0]
        beginning_idx = 0
        run_length = 0
        for col_idx in range(image.shape[1]):
            if image[row_idx, col_idx] == current_run_color:
                run_length += 1
            else:
                if current_run_color == foreground and (run_length > upper_thresh
                                                        or run_length <= lower_thresh):
                    image[row_idx, beginning_idx:col_idx] = background
                run_length = 0
                beginning_idx = col_idx
                current_run_color = image[row_idx, col_idx]
        if current_run_color == foreground and (run_length > upper_thresh
                                                or run_length <= lower_thresh):
            image[row_idx, beginning_idx:col_idx] = background

    return image






