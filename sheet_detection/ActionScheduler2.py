import copy

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
        self.index = pos
        # Symbolic, just to represent how many keys it rotated to, to the left or to the right
        self.angle = 0  # Negative numbers to the right, positive to the left

    def get_finger_state(self):
        state = 0 if self.available else 1  # 0 and 1 in terms if it should be activated or not
        press_black_key = 1 if self.press_black_key else 0
        return press_black_key, state, self.angle


class Hand:
    def __init__(self):
        self.center = 0
        self.leftmost_pos = 0
        self.rightmost_pos = 0
        self.fingers = [Finger(i) for i in range(cfg.config['NUM_OF_FINGERS'])]
        self.last_idle_time = 0
        self.note_assignments = {}

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

    def calculate_finger_states(self, notes_pos):
        states, assignments = assign_fingers_to_notes(self.fingers, notes_pos)
        for s in states:
            f = self.fingers[s["finger_idx"]]
            f.angle = s["angle"]
            f.press_black_key = s["press_black_key"]
            f.available = s["available"]
        self.note_assignments.update(assignments)
        return [f.get_finger_state() for f in self.fingers]

    def release_notes(self, notes_to_release):
        for f_idx, note in list(self.note_assignments.items()):
            if note in notes_to_release:
                self.fingers[f_idx].available = True
                self.fingers[f_idx].press_black_key = False
                del self.note_assignments[f_idx]

    @property
    def offset(self):
        return int(cfg.config['NUM_OF_FINGERS'] / 2)


def compute_future_demand(fingers, future_notes_seq, hand_center):
    """
    Simple heuristic: for each future note in `future_notes_seq`, find the nearest finger
    index and increment demand for that finger. Returns a dict {finger_idx: demand_count}.
    """
    if not future_notes_seq:
        return {}

    # compute absolute positions of fingers for the given hand_center (
    offset = int(cfg.config['NUM_OF_FINGERS'] / 2)
    leftmost = hand_center - offset
    finger_positions = [leftmost + f.index - f.angle for f in fingers]

    demand = [0] * len(fingers)

    for note in future_notes_seq:
        # find nearest finger (ties break by lower idx)
        dists = [abs(f_pos - note) for f_pos in finger_positions]
        j = int(min(range(len(dists)), key=lambda k: dists[k]))
        demand[j] += 1

    return {i: c for i, c in enumerate(demand) if c}


def assign_fingers_to_notes(fingers, notes_pos, offset=0, future_demand=None):
    available = [{'idx': i, 'pos': f.position + offset, 'angle': f.angle, 'black': f.press_black_key}
                 for i, f in enumerate(fingers) if f.available]
    if not available or not notes_pos:
        return [], {}

    # map available columns back to original finger indices for demand lookup
    col_to_fidx = [f['idx'] for f in available]

    # Create a cost matrix (rows: notes, cols: fingers)
    cost_matrix = np.zeros((len(notes_pos), len(available)))
    for i, note_pos in enumerate(notes_pos):
        for j, f in enumerate(available):
            base_cost = abs(f['angle'] + f['pos'] - note_pos)
            demand_penalty = 0
            if future_demand:
                demand_penalty = future_demand.get(col_to_fidx[j], 0) * cfg.config['FUTURE_DEMAND_PENALTY']
            cost_matrix[i][j] = base_cost + demand_penalty

    # Solve optimal assignment problem (a modified Jonker-Volgenant algorithm with no initialization)
    note_indices, finger_indices = linear_sum_assignment(cost_matrix)  # Minimize absolute cost

    states, assignments = [], {}
    for note_idx, j in zip(note_indices, finger_indices):
        f = available[j]
        finger_idx = f['idx']
        new_angle = f['angle'] + f['pos'] - notes_pos[note_idx]

        # MAX_ANGLE = cfg.config['ROTATIONAL_REACH_OF_ONE_FINGER']
        # if abs(new_angle) > MAX_ANGLE:
        #     new_angle = max(min(new_angle, MAX_ANGLE), -MAX_ANGLE)

        # Check if note has decimal part in its position; that means it is a black key
        press_black_key = notes_pos[note_idx] % 1 != 0
        assignments[finger_idx] = notes_pos[note_idx]
        states.append({
            'finger_idx': finger_idx,
            'angle': new_angle,
            'press_black_key': press_black_key,
            'available': False
        })

    return states, assignments


def keep_notes_in_span(notes, center_pos, span):
    """If there are more notes than the span can handle, this function trims the excess of notes so that
    a maximum number of notes is played and that they are closest to the center_pos, ensuring no more notes than
    the number of fingers."""
    if not notes:
        return []

    # print(notes)
    notes.sort()
    best = []
    best_dist = float('inf')
    left = 0

    for right in range(len(notes)):
        while notes[right] - notes[left] > span:
            left += 1

        window = notes[left:right+1]

        # Sort by distance to center_pos, keeping the closest notes if too many
        if len(window) > cfg.config['NUM_OF_FINGERS']:
            # Keep only the first NUM_OF_FINGERS closest notes
            window = sorted(window, key=lambda n: abs(n - center_pos))[:cfg.config['NUM_OF_FINGERS']]

        # Evaluate how well this window is centered
        center = sum(n for n in window) / len(window)
        dist = abs(center_pos - center)
        if len(window) > len(best) or (len(window) == len(best) and dist < best_dist):
            best_dist, best = dist, window

    return best


def generate_hand_centers(notes, half_span):
    if notes:
        minim = math.floor(min(notes))
        maxim = math.floor(max(notes))
        return list(range(maxim - half_span + 1, minim + half_span))
    else:
        return []


def simulate_finger_angles(hand, notes_pos, candidate_center, demands=None):
    """
    Simulate finger angles for a candidate hand center.
    Uses a deep copy of hand to preserve full state consistency.
    """

    states, _ = assign_fingers_to_notes(hand.fingers, notes_pos, candidate_center - hand.center, demands)
    angles = [f.angle for f in hand.fingers]
    for s in states:
        angles[s["finger_idx"]] = s["angle"]
    return angles


def schedule_actions(time_series):
    span = cfg.config['SPAN_OF_HAND']
    half_span = math.ceil(span / 2)
    safety_distance = cfg.config['SAFETY_DISTANCE_BETWEEN_HANDS']

    right_hand, left_hand = Hand(), Hand()
    right_hand.set_position_by_center(cfg.config['MAX_HAND_CENTER_POSITION'])
    left_hand.set_position_by_center(cfg.config['MIN_HAND_CENTER_POSITION'])

    t_relax = cfg.config['POSTURE_RELAX_TIME_MS']
    posture_cost = cfg.config['COST_POSTURE_DEVIATION']
    sorted_times = sorted(time_series.keys())

    for time, hands in time_series.items():
        inactive_left_notes = hands['left']['inactive']
        inactive_right_notes = hands['right']['inactive']

        active_left_notes = hands['left']['active']
        active_right_notes = hands['right']['active']

        current_idx = sorted_times.index(time)
        future_indices = range(current_idx, min(current_idx + cfg.config['FUTURE_WINDOW_SIZE'], len(sorted_times)))

        l_future, r_future = [], []
        for i in future_indices:
            l_future.extend(time_series[sorted_times[i]]['left']['active'])
            r_future.extend(time_series[sorted_times[i]]['right']['active'])

        if active_left_notes or active_right_notes:
            # Lock hand if fingers still active
            left_locked = any(not f.available for f in left_hand.fingers)
            right_locked = any(not f.available for f in right_hand.fingers)

            # compute dt for each hand: time since it last became idle
            dt_left = max(0, time - left_hand.last_idle_time)
            dt_right = max(0, time - right_hand.last_idle_time)

            # alpha: how strongly to penalize posture change (1 = strong, 0 = none)
            alpha_left = 1.0 - min(dt_left / t_relax, 1.0)
            alpha_right = 1.0 - min(dt_right / t_relax, 1.0)

            # Keep notes in span
            active_left_notes = keep_notes_in_span(active_left_notes, left_hand.center, span)
            active_right_notes = keep_notes_in_span(active_right_notes, right_hand.center, span)

            # Determine possible centers for hands
            left_centers = [left_hand.center] if left_locked else generate_hand_centers(active_left_notes, half_span)
            right_centers = [right_hand.center] if right_locked else generate_hand_centers(active_right_notes, half_span)

            best_lc, best_rc = left_hand.center, right_hand.center
            best_cost = float('inf')

            # Save current state
            l_current_center = left_hand.center
            r_current_center = right_hand.center
            l_current_angles = [f.angle for f in left_hand.fingers]
            r_current_angles = [f.angle for f in right_hand.fingers]

            # print(l_future, r_future)
            for lc in left_centers or [l_current_center]:
                for rc in right_centers or [r_current_center]:
                    if abs(rc - lc) < safety_distance:
                        continue

                    left_demands = compute_future_demand(left_hand.fingers, l_future, lc)
                    right_demands = compute_future_demand(right_hand.fingers, r_future, rc)

                    # Simulate angles
                    l_angles = simulate_finger_angles(left_hand, active_left_notes, lc, left_demands)
                    r_angles = simulate_finger_angles(right_hand, active_right_notes, rc, right_demands)

                    # MAX_ANGLE = cfg.config['ROTATIONAL_REACH_OF_ONE_FINGER']
                    # if any(abs(a) > MAX_ANGLE for a in l_angles) or any(abs(a) > MAX_ANGLE for a in r_angles):
                    # print(lc, rc, l_angles, r_angles)
                    #     continue

                        # --- Compute the costs for actions ---
                    l_translation_cost = abs(l_current_center - lc) * cfg.config['COST_PER_KEY_TRANSLATION']
                    l_rotation_cost = (max((abs(a - b) for a, b in zip(l_angles, l_current_angles)), default=0)
                                       * cfg.config['COST_PER_KEY_ROTATION'])
                    # posture deviation = magnitude of angles from neutral (0)
                    l_posture_dev = sum(abs(a) for a in l_angles)

                    r_translation_cost = abs(r_current_center - rc) * cfg.config['COST_PER_KEY_TRANSLATION']
                    r_rotation_cost = (max((abs(a - b) for a, b in zip(r_angles, r_current_angles)), default=0)
                                       * cfg.config['COST_PER_KEY_ROTATION'])

                    r_posture_dev = sum(abs(a) for a in r_angles)

                    # uses max(translation, rotation) for concurrency of those motions
                    l_cost = max(l_translation_cost, l_rotation_cost) + alpha_left * (l_posture_dev * posture_cost)
                    r_cost = max(r_translation_cost, r_rotation_cost) + alpha_right * (r_posture_dev * posture_cost)

                    total_cost = l_cost + r_cost

                    if total_cost < best_cost:
                        best_cost = total_cost
                        best_lc, best_rc = lc, rc

            left_hand.set_position_by_center(best_lc)
            left_hand.calculate_finger_states(active_left_notes)

            right_hand.set_position_by_center(best_rc)
            right_hand.calculate_finger_states(active_right_notes)

            # print(best_rc, left_hand.note_assignments, ' ', [f.angle for f in left_hand.fingers]
            #       , ' ', right_hand.note_assignments, ' ', [f.angle for f in right_hand.fingers])

        # Mark the last event where it finished playing all notes (rests between active events)
        if not active_left_notes and inactive_left_notes:
            left_hand.last_idle_time = time
        if not active_right_notes and inactive_right_notes:
            right_hand.last_idle_time = time

        left_hand.release_notes(inactive_left_notes)
        right_hand.release_notes(inactive_right_notes)

        # print(time, active_left_notes, active_right_notes)

    return None, None


def rearrange_actions(actions):
    rearranged_actions = []
    for pos, fingers in actions:
        rotations, back, front, duration = zip(
            *[(r, b, f, d) for b, f, r, d in fingers])
        rearranged_actions.append([pos, list(rotations), list(back), list(front), list(duration)])

    return rearranged_actions


def get_action_commands(time_series):
    left_actions, right_actions = schedule_actions(time_series)
    # left_actions = rearrange_actions(left_actions)
    # right_actions = rearrange_actions(right_actions)

    return left_actions, right_actions

