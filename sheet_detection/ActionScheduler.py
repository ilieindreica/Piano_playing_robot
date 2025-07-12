import numpy as np
import math
from scipy.optimize import linear_sum_assignment
from tkinter import messagebox
from sheet_detection.Notes import NoteWithPosition
import configLib as cfg


class Finger:
    def __init__(self, pos):
        self.available = True
        self.press_black_key = False
        self.position = pos
        self.duration = 0
        self.occupied_start_time = 0  # Time when the finger becomes occupied
        self.occupied_duration = 0  # Duration for which the resource remains occupied
        # Symbolic, just to represent how many keys it rotated to, to the left or to the right
        self.angle = 0  # Negative numbers to the left, positive to the right

    def get_finger_state(self):
        state = 0 if self.available else 1  # 0 and 1 in terms if it should be activated or not
        press_black_key = 1 if self.press_black_key else 0
        return press_black_key, state, self.angle, self.duration


class Hand:
    def __init__(self):
        self.center = 0
        self.leftmost_pos = 0
        self.rightmost_pos = 0
        self.fingers = [Finger(i) for i in range(cfg.config['NUM_OF_FINGERS'])]

    def set_position_by_center(self, pos):
        self.center = pos
        self.leftmost_pos = pos - self.offset
        self.rightmost_pos = pos + self.offset
        self.update_finger_positions()

    def set_position_by_rightmost(self, pos):
        self.center = pos - self.offset
        self.rightmost_pos = pos
        self.leftmost_pos = pos - 2 * self.offset
        self.update_finger_positions()

    def set_position_by_leftmost(self, pos):
        self.center = pos + self.offset
        self.rightmost_pos = pos + 2 * self.offset
        self.leftmost_pos = pos
        self.update_finger_positions()

    def update_finger_positions(self):
        pos = self.leftmost_pos
        for finger in self.fingers:
            finger.position = pos - int(finger.angle)
            pos += 1

    def reset_durations_and_activations(self):
        for finger in self.fingers:
            finger.duration = 0
            finger.press_black_key = False
            finger.available = True

    def calculate_finger_states(self, notes_pos, notes_duration):
        notes_pos = [pos for pos in notes_pos if pos != 'REST']

        if len(notes_pos) == 0:
            if notes_duration:
                for f in self.fingers:
                    f.duration = notes_duration[0]
            return [f.get_finger_state() for f in self.fingers]

        # Create a cost matrix (rows: notes, cols: fingers)
        cost_matrix = np.zeros((len(notes_pos), len(self.fingers)))

        for i, note_pos in enumerate(notes_pos):
            for j, finger in enumerate(self.fingers):
                cost_matrix[i][j] = finger.position - note_pos

        # Solve optimal assignment problem (a modified Jonker-Volgenant algorithm with no initialization)
        note_indices, finger_indices = linear_sum_assignment(np.abs(cost_matrix))  # Minimize absolute cost

        for note_idx, finger_idx in zip(note_indices, finger_indices):
            # Check if note has decimal part in its position; that means it is a black key
            if notes_pos[note_idx] % 1 != 0:
                self.fingers[finger_idx].press_black_key = True
            self.fingers[finger_idx].available = False
            self.fingers[finger_idx].angle += cost_matrix[note_idx][finger_idx]
            self.fingers[finger_idx].duration = notes_duration[note_idx]

        return [f.get_finger_state() for f in self.fingers]

    @property
    def offset(self):
        return int(cfg.config['NUM_OF_FINGERS'] / 2)


def group_notes_by_span(sequence, span):
    """Group notes into "clusters" that can all be contained by the span of one hand.
    'sequence' should be a list of lists of objects of class NoteWithPosition.\n
    It ensures that all notes that play at the same time are in span, as they cannot be in separate groups
    (i.e. having a hand transition between them)"""

    min_pos = cfg.config['NUM_OF_WHITE_KEYS']
    max_pos = 0
    groups = []
    mean_pos_sequence = []
    cluster = []

    for notes_at_k in sequence:
        # Filter out 'REST' values before finding min/max positions
        valid_notes = [note for note in notes_at_k if note.pos != 'REST']

        if valid_notes:
            # Get the extreme positions at the current time step
            min_pos_at_time_k = min(valid_notes, key=lambda note: note.pos).pos
            max_pos_at_time_k = max(valid_notes, key=lambda note: note.pos).pos

            # Check if the span fits the notes at current time step and all the previous ones
            # The reason for +1: if keys are 1,2,3,4 and span 3, 4-1=3, but there are 4 keys, and that is out of span
            if max(max_pos, max_pos_at_time_k) - min(min_pos, min_pos_at_time_k) + 1 <= span:
                max_pos = max(max_pos, max_pos_at_time_k)
                min_pos = min(min_pos, min_pos_at_time_k)
                cluster.append(notes_at_k)
            # If not, begin a new cluster
            else:
                if cluster:
                    groups.append(cluster)
                    mean_pos = math.ceil((max_pos + min_pos) / 2)
                    mean_pos_sequence.extend([mean_pos] * len(cluster))
                max_pos = max_pos_at_time_k
                min_pos = min_pos_at_time_k
                cluster = [notes_at_k]
        else:
            # If all notes in this time step are REST, or an empty list, just add them to the cluster
            cluster.append(notes_at_k)

    if cluster:
        groups.append(cluster)
        mean_pos = math.ceil((max_pos + min_pos) / 2)
        mean_pos_sequence.extend([mean_pos] * len(cluster))

    return groups, mean_pos_sequence


def find_sublist_idx(lists, idx):
    """
        Finds the sublist containing the given global index and returns the minimum
        and maximum `.pos` values of non-'REST' notes within that sublist.

        Parameters:
            lists (list of list of list): A nested list where each top-level sublist contains
                                          sublists of note objects.
            idx (int): A global index representing a flattened position across all sublists.

        Returns:
            tuple (minim, maxim):
                - minim (any): Minimum `.pos` value among non-'REST' notes in the matched sublist.
                - maxim (any): Maximum `.pos` value among non-'REST' notes in the matched sublist.
                - Returns (None, None) if index is out of bounds or sublist contains only 'REST' notes.
    """
    count = 0
    for sublist_idx, sublist in enumerate(lists):
        count += len(sublist)
        if idx < count:
            notes = [note for mini_sublist in sublist for note in mini_sublist if note.pos != 'REST']
            if not notes:
                return None, None
            minim = min(notes, key=lambda note: note.pos).pos
            maxim = max(notes, key=lambda note: note.pos).pos
            return minim, maxim
    return None, None


def get_finger_pos_series(hand_positions, notes):
    """Generates a series with finger postures.\n"""
    finger_pos_series = []
    for i, (pos_at_k, notes_at_k) in enumerate(zip(hand_positions, notes)):
        # The if is to eliminate empty lists; They were needed for collision checking,
        # but in Arduino may worsen things
        hand = Hand()  # If you want fingers to remain in position after rotating, move hand outside for
        if notes_at_k:
            hand.reset_durations_and_activations()
            hand.set_position_by_center(pos_at_k)
            notes_pos_at_k = [n.pos for n in notes_at_k]
            notes_duration_at_k = [n.duration for n in notes_at_k]
            finger_states = hand.calculate_finger_states(notes_pos_at_k, notes_duration_at_k)
            finger_pos_series.append(finger_states)

    return finger_pos_series


def schedule_actions(time_series, is_double_handed=True):
    span = cfg.config['SPAN_OF_HAND']
    half_span = math.ceil(span / 2)
    safety_distance = cfg.config['SAFETY_DISTANCE_BETWEEN_HANDS']

    # Lists of lists; each sublist represent a moment in time, and its elements are all occurring at that time
    right_notes = time_series[0]
    left_notes = time_series[1]

    right_groups, right_hand_positions = group_notes_by_span(right_notes, span)
    left_groups, left_hand_positions = group_notes_by_span(left_notes, span)

                                                            # Collision checking
                                                            # It assumes left_ and right_ have the same number of elements, for a direct correlation
    try:
        if is_double_handed:
            failed_safety_indices = []
            for i, (l_pos, r_pos) in enumerate(zip(left_hand_positions, right_hand_positions)):
                difference = (r_pos - l_pos)  # Distance between hands

                if difference < safety_distance:  # Collision detected
                    difference = safety_distance - difference  # How much it has to move to ensure safety

                    _, left_max = find_sublist_idx(left_groups, i)
                    # Distance from the rightmost reachable position of the left_hand from current position and the
                    # rightmost note at current time. This distance gives the room for adjusting for safety distance
                    left_wiggle = abs(l_pos + half_span - left_max) if left_max is not None else 0

                    right_min, _ = find_sublist_idx(right_groups, i)
                    right_wiggle = abs(r_pos - half_span - right_min) if right_min is not None else 0

                    total_wiggle = left_wiggle + right_wiggle

                    if total_wiggle >= difference:
                        # Distribute movement between hands
                        right_shift = min(right_wiggle, difference // 2)
                        left_shift = abs(difference - right_shift)
                        l_pos -= left_shift  # In case of collision, left_hand will move only to the left
                        r_pos += right_shift  # In case of collision, right_hand will move only to the right
                    else:
                        # Move as much as possible, but not enough to fix the issue
                        l_pos -= left_wiggle
                        r_pos += right_wiggle
                        failed_safety_indices.append(i)

                    right_hand_positions[i] = r_pos
                    left_hand_positions[i] = l_pos

            if failed_safety_indices:
                messagebox.showwarning(f"Warning",
                                       f"Could not maintain safety distance at index {failed_safety_indices}")
    except Exception as e:
        print(f'Exceptie: {e}')

    right_finger_states = get_finger_pos_series(right_hand_positions, right_notes)
    left_finger_states = get_finger_pos_series(left_hand_positions, left_notes)

    right_actions = list(zip(right_hand_positions, right_finger_states))
    left_actions = list(zip(left_hand_positions, left_finger_states))

    # for com in left_actions:
    #     print(com)
    # print()
    # for com in right_actions:
    #     print(com)

    return left_actions, right_actions


def rearrange_actions(actions):
    rearranged_actions = []
    for pos, fingers in actions:
        rotations, back, front, duration = zip(
            *[(int(math.ceil(r) * 2), b, f, d) for b, f, r, d in fingers])             # !!!!REMOVE CEIL WHEN U WANT BLACK KEYS BACK
        rearranged_actions.append([int(pos * 2), list(rotations), list(back), list(front), list(duration)])

    return rearranged_actions


def get_action_commands(time_series, is_double_handed=True, adjust_for_octave=True):
    left_actions, right_actions = schedule_actions(time_series, is_double_handed=is_double_handed)
    left_actions = rearrange_actions(left_actions)
    right_actions = rearrange_actions(right_actions)

    # for com in left_actions:
    #     print(com)
    # print()
    # for com in right_actions:
    #     print(com)
    return left_actions, right_actions

