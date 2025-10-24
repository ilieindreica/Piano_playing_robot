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


def keep_notes_in_span(notes, center_pos, span):
    """If there are more notes than the span can handle, this function trims the excess of notes so that
    a maximum number of notes is played and that they are closest to the center_pos, ensuring no more notes than
    the number of fingers."""
    if not notes:
        return []

    filtered_notes = [n for n in notes if n.pos != 'REST']
    if not filtered_notes:
        return notes

    # print(notes)
    notes = sorted(notes, key=lambda x: x.pos)
    best = []
    best_dist = float('inf')
    left = 0

    for right in range(len(notes)):
        while notes[right].pos - notes[left].pos > span:
            left += 1

        window = notes[left:right+1]

        # Sort by distance to center_pos, keeping the closest notes if too many
        if len(window) > cfg.config['NUM_OF_FINGERS']:
            window = sorted(window, key=lambda n: abs(n.pos - center_pos))[:cfg.config['NUM_OF_FINGERS']]

        # Evaluate how well this window is centered
        center = sum(n.pos for n in window) / len(window)
        dist = abs(center_pos - center)
        if len(window) > len(best) or (len(window) == len(best) and dist < best_dist):
            best_dist, best = dist, window

    return best


def schedule_actions(time_series, is_double_handed=True):
    span = cfg.config['SPAN_OF_HAND']
    half_span = math.ceil(span / 2)
    safety_distance = cfg.config['SAFETY_DISTANCE_BETWEEN_HANDS']

    right_hand = Hand()
    left_hand = Hand()
    right_hand.set_position_by_center(cfg.config['START_POS_RIGHT_HAND'])
    left_hand.set_position_by_center(cfg.config['START_POS_LEFT_HAND'])

    for time, hands in time_series.items():
        left_notes = hands['left']
        right_notes = hands['right']
        print(time, hands)
        left_notes = keep_notes_in_span(left_notes, left_hand.center, span)
        right_notes = keep_notes_in_span(right_notes, right_hand.center, span)
        # print(time, left_notes, right_notes)

    # for com in left_actions:
    #     print(com)
    # print()
    # for com in right_actions:
    #     print(com)

    return None, None


def rearrange_actions(actions):
    rearranged_actions = []
    for pos, fingers in actions:
        rotations, back, front, duration = zip(
            *[(r, b, f, d) for b, f, r, d in fingers])
        rearranged_actions.append([pos, list(rotations), list(back), list(front), list(duration)])

    return rearranged_actions


def get_action_commands(time_series, is_double_handed=True, adjust_for_octave=True):
    left_actions, right_actions = schedule_actions(time_series, is_double_handed=is_double_handed)
    # left_actions = rearrange_actions(left_actions)
    # right_actions = rearrange_actions(right_actions)

    # for com in left_actions:
    #     print(com)
    # print()
    # for com in right_actions:
    #     print(com)
    return left_actions, right_actions

