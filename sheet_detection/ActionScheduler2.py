from collections import deque
import numpy as np
import math
from scipy.optimize import linear_sum_assignment
import configLib as cfg
import pickle
from itertools import product
import copy
from tkinter import messagebox


class Finger:
    def __init__(self, pos, parent):
        self.__parent = parent
        self.index = pos
        # Symbolic, just to represent how many keys it rotated to, to the left or to the right
        self.angle = 0  # Negative numbers to the right, positive to the left

    @property
    def available(self):
        return False if self.index in self.__parent.note_assignments else True

    @property
    def pos(self):
        return self.__parent.leftmost_pos + self.index - self.angle


class Hand:
    def __init__(self):
        self.center = 0
        self.leftmost_pos = 0
        self.rightmost_pos = 0
        self.fingers = [Finger(i, self) for i in range(cfg.config['NUM_OF_FINGERS'])]
        self.last_idle_time = 0
        self.note_assignments = {}  # finger_index : note_pos

    def set_position_by_center(self, pos):
        self.center = pos
        self.leftmost_pos = pos - self.offset
        self.rightmost_pos = pos + self.offset

    def set_position_by_rightmost(self, pos):
        self.center = pos - self.offset
        self.rightmost_pos = pos
        self.leftmost_pos = pos - 2 * self.offset

    def set_position_by_leftmost(self, pos):
        self.center = pos + self.offset
        self.rightmost_pos = pos + 2 * self.offset
        self.leftmost_pos = pos

    def set_angles(self, angles):
        for i, a in enumerate(angles):
            self.fingers[i].angle = a

    def update_assignments(self, assignments):
        self.note_assignments.update(assignments)

    def set_state(self, state, replace_assignments=False):
        if isinstance(state, (list, tuple)) and len(state) == 3:
            center, angles, assignments = state
        else:
            raise ValueError(f"Invalid state format {type(state)} {state}")

        self.set_position_by_center(center)
        self.set_angles(angles)

        if replace_assignments:
            self.note_assignments.clear()
        self.update_assignments(assignments)

    def get_state(self):
        return [self.center, list(self.get_angles()), dict(self.note_assignments)]

    def get_full_state(self):
        back = [1 if self.is_finger_to_black_key(f) else 0 for f in self.fingers]
        front = [1 if not f.available else 0 for f in self.fingers]
        return [self.center, self.get_angles(), back, front]

    def release_notes(self, notes_to_release):
        for f_idx, note in list(self.note_assignments.items()):
            if note in notes_to_release:
                del self.note_assignments[f_idx]

    def is_finger_used(self, finger):
        """
        finger: index of finger or Finger() instance.\n
        Returns True if the finger is in `note_assignments`
        """
        if isinstance(finger, int):
            return finger in self.note_assignments.keys()
        elif isinstance(finger, Finger):
            return finger.index in self.note_assignments.keys()

    def is_finger_to_black_key(self, finger):
        """
        finger: index of finger or Finger() instance.\n
        Returns True if the finger is assigned to a black key (note with decimal part != 0)
        """
        if isinstance(finger, int):
            return self.note_assignments[finger] % 1 != 0
        elif isinstance(finger, Finger):
            return self.is_finger_used(finger) and self.note_assignments[finger.index] % 1 != 0

    def get_angles(self):
        return [f.angle for f in self.fingers]

    def get_availability_list(self):
        return [True if f.available else False for f in self.fingers]

    @property
    def offset(self):
        return int(cfg.config['NUM_OF_FINGERS'] / 2)


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


def check_active_angles(angles, assignment):
    num_of_f = cfg.config['NUM_OF_FINGERS']
    positions = []
    for i in range(num_of_f):
        if i in assignment:
            positions.append(i + angles[i])

    if all(a >= b for a, b in zip(positions, positions[1:])):
        return True
    else:
        return False


def adjust_angles(angles, assignment):
    """Make neutral fingers adjust their angles to comply to neighbours so to avoid collision"""
    angles = angles[:]; n = len(angles); assignment = set(assignment); q = deque(assignment)
    while q:
        i = q.popleft()
        a = angles[i]
        # Propagate positive angles to the right
        if a > 0 and i > 0:
            j = i-1
            # If propagation hits a fixed finger, mark as impossible move (ok=False)
            if j in assignment and angles[j] < a: return{"ok": False}
            if j not in assignment and angles[j] < a:
                angles[j] = a
                q.append(j)  # to propagate further
        # Propagate negative angles to the left
        if a < 0 and i < n-1:
            j = i+1
            if j in assignment and angles[j] > a: return{"ok": False}
            if j not in assignment and angles[j] > a:
                angles[j] = a
                q.append(j)
    return{"ok": True, "angles": angles}


def generate_hand_centers(notes, half_span):
    if notes:
        minim = math.floor(min(notes))
        maxim = math.floor(max(notes))
        return list(range(maxim - half_span + 1, minim + half_span))
    else:
        return []


def generate_angles_and_assignments(notes, center, availability_list):
    nof = cfg.config['NUM_OF_FINGERS'] // 2
    f_positions = [center + i for i in range(-nof, nof+1)]
    notes_to_fingers = {n: [i for i, pos in enumerate(f_positions)
                            if abs(pos - n) <= cfg.config['ROTATIONAL_REACH_OF_ONE_FINGER'] and availability_list[i]]
                        for n in notes}
    results = []

    def backtrack(idx, current, used_fingers):
        if idx == len(notes):
            angles = [0] * cfg.config['NUM_OF_FINGERS']
            for i, n in current.items():
                angles[i] = f_positions[i] - n
            results.append((angles, current.copy()))
            return

        note = notes[idx]
        for f_idx in notes_to_fingers[note]:
            if f_idx in used_fingers:
                continue

            valid = True
            for prev_f, prev_n in current.items():
                if prev_f < f_idx and prev_n >= note:
                    valid = False
                    break
                if prev_f > f_idx and prev_n <= note:
                    valid = False
                    break

            if not valid:
                continue

            used_fingers.add(f_idx)
            current[f_idx] = note

            backtrack(idx+1, current, used_fingers)

            used_fingers.remove(f_idx)
            del current[f_idx]

    backtrack(0, {}, set())
    return results


def generate_hand_states(hand, active_notes, time):
    span = cfg.config['SPAN_OF_HAND']
    half_span = math.ceil(span / 2)

    # Lock hand if fingers still active
    locked = bool(hand.note_assignments)

    if locked and any(abs(n - hand.center) > half_span for n in active_notes):
        r = hand.get_state()
        r.extend([float('inf')])
        return [r]

    # Keep notes in span
    active = keep_notes_in_span(active_notes, hand.center, span)

    # Determine possible centers for hands
    centers = [hand.center] if locked else (generate_hand_centers(active, half_span) or
                                            [hand.center])
    bests = []
    for c in centers:
        generated = generate_angles_and_assignments(active, c, hand.get_availability_list())
        for angles, assignment in generated:
            old_angles = hand.get_angles()
            for i, a in enumerate(old_angles):
                angles[i] = angles[i] if angles[i] != 0 else old_angles[i]

            # if check_active_angles(angles, assignment):
                # result = adjust_angles(angles, hand.note_assignments)
                # if result['ok']:
                #     cost = cost_for_move(hand, c, result['angles'], time)
                #     bests.append([c, result['angles'], assignment, cost])
            cost = cost_for_move(hand, c, angles, time)
            bests.append([c, angles, assignment, cost])

    return bests if bests else [[hand.center, hand.get_angles(), hand.note_assignments, float('inf')]]


def cost_for_move(hand, new_center, new_angles, timestamp):
    """Computes translation + rotation + posture cost"""
    t_relax = cfg.config['POSTURE_RELAX_TIME_MS']
    alpha = 1.0 - min(max(0, timestamp - hand.last_idle_time) / t_relax, 1.0)
    trans_cost = abs(hand.center - new_center) * cfg.config['COST_PER_KEY_TRANSLATION']
    rot_cost = (max(abs(a - b) for a, b in zip(new_angles, hand.get_angles())) *
                cfg.config['COST_PER_KEY_ROTATION'])
    posture = sum(abs(a) for a in new_angles) * cfg.config['COST_POSTURE_DEVIATION']

    # uses max(trans, rot) for concurrency of those motions
    return max(trans_cost, rot_cost) + alpha * posture


def simulate_future(future, idx, left_hand, right_hand, beam_width=5):
    safety_distance = cfg.config['SAFETY_DISTANCE_BETWEEN_HANDS']

    if idx >= len(future):
        return 0.0, left_hand.get_state(), right_hand.get_state()

    time, hands = future[idx]
    l_inactive = hands['left']['inactive']
    r_inactive = hands['right']['inactive']
    l_active = hands['left']['active']
    r_active = hands['right']['active']
    list_of_bests = []

    if l_active or r_active:
        l_bests = generate_hand_states(left_hand, l_active, time)
        r_bests = generate_hand_states(right_hand, r_active, time)
        for (lc, l_angles, l_asgn, l_cost), (rc, r_angles, r_asgn, r_cost) in product(l_bests, r_bests):
            if abs(rc - lc) < safety_distance:
                continue  # skip too-close hands

            total_cost = l_cost + r_cost
            list_of_bests.append([total_cost, [lc, l_angles, l_asgn], [rc, r_angles, r_asgn]])

    # Mark the last event where it finished playing all notes (rests between active events)
    if not l_active and l_inactive:
        left_hand.last_idle_time = time
    if not r_active and r_inactive:
        right_hand.last_idle_time = time

    left_hand.release_notes(l_inactive)
    right_hand.release_notes(r_inactive)

    list_of_bests.sort(key=lambda x: x[0])

    l_state_copy = left_hand.get_state()
    r_state_copy = right_hand.get_state()

    if list_of_bests:
        i = 0
        while i < beam_width and i < len(list_of_bests):
            option = list_of_bests[i]
            total_cost, l_state, r_state = option
            left_hand.set_state(l_state)
            right_hand.set_state(r_state)

            future_cost, _, _ = simulate_future(future, idx + 1, left_hand, right_hand)
            left_hand.set_state(l_state_copy, replace_assignments=True)
            right_hand.set_state(r_state_copy, replace_assignments=True)

            option[0] += future_cost
            i += 1

            if future_cost == float('inf'):
                beam_width += 1
            else:
                break

        list_of_bests = list_of_bests[:i]
        list_of_bests.sort(key=lambda x: x[0])

        best_cost = list_of_bests[0][0]
        l_state = list_of_bests[0][1]
        r_state = list_of_bests[0][2]

        return best_cost, l_state, r_state

    else:
        best_cost, l_state, r_state = simulate_future(future, idx + 1, left_hand, right_hand)
        left_hand.set_state(l_state_copy, replace_assignments=True)
        right_hand.set_state(r_state_copy, replace_assignments=True)

        # When no new notes are happening, propagate a future state only if the hand is idle
        l_state = [l_state[0], l_state[1], {}] if not left_hand.note_assignments else left_hand.get_state()
        r_state = [r_state[0], r_state[1], {}] if not right_hand.note_assignments else right_hand.get_state()

        return best_cost, l_state, r_state


def schedule_actions(time_series):
    right_hand, left_hand = Hand(), Hand()
    left_hand.set_position_by_center(cfg.config['MIN_HAND_CENTER_POSITION'])
    # right_hand.set_position_by_center(cfg.config['MAX_HAND_CENTER_POSITION'])
    right_hand.set_position_by_center(20)

    sorted_time_keys = sorted(time_series.keys())
    window_size = cfg.config['FUTURE_WINDOW_SIZE']

    for current_idx, current_time in enumerate(sorted_time_keys):
        future = [(t, time_series[t]) for t in sorted_time_keys[current_idx: current_idx + window_size]]
        _, l_state, r_state = simulate_future(future, 0, left_hand, right_hand)
        left_hand.set_state(l_state)
        right_hand.set_state(r_state)

        print(time_series[sorted_time_keys[current_idx]]['left']['active'],
              left_hand.get_state(), '  ',  right_hand.get_full_state(), right_hand.note_assignments, '  ',
              time_series[sorted_time_keys[current_idx]]['right']['active'],)

    return None, None


