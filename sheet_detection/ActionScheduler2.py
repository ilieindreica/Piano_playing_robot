from collections import deque
import numpy as np
import math
from scipy.optimize import linear_sum_assignment
import configLib as cfg
import pickle
from itertools import product
import copy
from tkinter import messagebox
import time

_angles_cache = {}
_generate_hand_states_cache = {}


class Finger:
    def __init__(self, pos, parent):
        self.__parent = parent
        self.index = pos
        # Symbolic, just to represent how many keys it rotated to, to the left or to the right
        self.angle = 0  # Negative numbers to the right, positive to the left
        self.last_active_count = 0  # Counts events since it was last used
        self.last_released_time = 0

    @property
    def available(self):
        return False if self.index in self.__parent.note_assignments else True

    @property
    def busy(self):
        return 1 if self.index in self.__parent.note_assignments else 0

    @property
    def pos(self):
        return self.__parent.leftmost_pos + self.index - self.angle


class Hand:
    def __init__(self):
        self.center = 0
        self.leftmost_pos = 0
        self.rightmost_pos = 0
        self.fingers = [Finger(i, self) for i in range(cfg.config['NUM_OF_FINGERS'])]
        self.last_active = float('-inf')
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

    def update_last_active(self, t, inactive_notes):
        if not self.note_assignments and inactive_notes:
            self.last_active = t
        for f in self.fingers:
            if f.index not in self.note_assignments:
                f.last_active_count += 1
            else:
                f.last_active_count = 0

    def set_state_of_last_active(self, state):
        if isinstance(state, (list, tuple)) and len(state) == 2:
            la, fla = state
        else:
            raise ValueError(f"Invalid state format {type(state)} {state}")

        self.last_active = la
        for i, f in enumerate(self.fingers):
            f.last_active_count = fla[i]

    def get_fingers_last_use_count(self):
        return [f.last_active_count for f in self.fingers]

    def get_state(self):
        return [self.center, list(self.get_angles()), dict(self.note_assignments)]

    def get_full_state(self):
        back = [1 if f.angle % 1 != 0 else 0 for f in self.fingers]
        front = [f.busy for f in self.fingers]
        return [self.center, self.get_angles(), back, front]

    def get_state_for_pause(self, t):
        back = [1 if f.angle % 1 != 0 else 0 for f in self.fingers]
        front = [f.busy if f.last_released_time != t else 0 for f in self.fingers]
        return [self.center, self.get_angles(), back, front]

    def get_state_of_last_active(self):
        return [self.last_active, [f.last_active_count for f in self.fingers]]

    def release_notes(self, notes_to_release, time_to_mark=None):
        for f_idx, note in list(self.note_assignments.items()):
            if note in notes_to_release:
                del self.note_assignments[f_idx]
                if time_to_mark is not None:
                    self.fingers[f_idx].last_released_time = time_to_mark

    def needs_pause_between_commands(self, at_time):
        """Verifies if at_time there's a finger that was both inactivated and reactivated"""
        needs_pause = False

        for f in self.fingers:
            if f.last_released_time == at_time and f.busy:
                needs_pause = True
                break

        return needs_pause

    def get_angles(self):
        return [f.angle for f in self.fingers]

    def get_availability_list(self):
        return [f.available for f in self.fingers]

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

        window = notes[left:right + 1]

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


def adjust_angles(angles, assignment, threshold=0.5):
    """Make neutral fingers adjust their angles to comply to neighbours so to avoid collision"""
    angles = angles[:]
    n = len(angles)
    assignment = set(assignment)
    q = deque(assignment)
    while q:
        i = q.popleft()
        a = angles[i]
        # Propagate positive angles to the left
        if i > 0:
            j = i - 1
            # If propagation hits a fixed finger, mark as impossible move (ok=False)
            if j in assignment and angles[j] < a:
                return {"ok": False}
            if j not in assignment and angles[j] < a and abs(a - angles[j]) > threshold:
                angles[j] = a
                q.append(j)  # to propagate further
        # Propagate negative angles to the right
        if i < n - 1:
            j = i + 1
            if j in assignment and angles[j] > a:
                return {"ok": False}
            if j not in assignment and angles[j] > a and abs(a - angles[j]) > threshold:
                angles[j] = a
                q.append(j)
    return {"ok": True, "angles": angles}


def generate_hand_centers(notes, half_span):
    if notes:
        minim = math.floor(min(notes))
        maxim = math.floor(max(notes))
        max_pos = cfg.config['MAX_HAND_CENTER_POSITION']
        min_pos = cfg.config['MIN_HAND_CENTER_POSITION']

        a = list(range(max(maxim - half_span + 1, min_pos), min(minim + half_span, max_pos)))
        return list(range(max(maxim - half_span + 1, min_pos), min(minim + half_span, max_pos)))
    else:
        return []


def generate_angles_and_assignments(notes, center, availability_list):
    key = (tuple(notes), center, tuple(availability_list))
    if key in _angles_cache:
        return _angles_cache[key]

    nof = cfg.config['NUM_OF_FINGERS'] // 2
    f_positions = [center + i for i in range(-nof, nof + 1)]
    notes_to_fingers = {n: [i for i, pos in enumerate(f_positions)
                            if abs(pos - n) <= cfg.config['ROTATIONAL_REACH_OF_ONE_FINGER'] and availability_list[i]]
                        for n in notes}
    results = []

    def backtrack(idx, current, used_fingers):
        """ current : current assignments """
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

            backtrack(idx + 1, current, used_fingers)

            used_fingers.remove(f_idx)
            del current[f_idx]

    backtrack(0, {}, set())

    _angles_cache[key] = results
    return results


def generate_hand_states(hand, active_notes, time):
    key = (tuple(active_notes), hand.center, tuple(hand.get_angles()), frozenset(hand.note_assignments.items()))

    if key in _generate_hand_states_cache:
        return _generate_hand_states_cache[key]

    span = cfg.config['SPAN_OF_HAND']
    half_span = math.ceil(span / 2)

    # Lock hand if fingers still active
    locked = bool(hand.note_assignments)

    # Mark as impossible if hand is locked and there's a note out of span
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
    old_assignments = hand.note_assignments
    old_angles = hand.get_angles()
    luc = hand.get_fingers_last_use_count()

    for c in centers:
        generated = generate_angles_and_assignments(active, c, hand.get_availability_list())
        for angles, new_assignments in generated:
            # int(): Remap angles assigned to black keys to white keys as soon as they are out of use
            angles = [
                angles[i] if i in new_assignments else old_angles[i] if i in old_assignments else int(old_angles[i])
                          if luc[i] < cfg.config['EVENTS_TO_RESET_ANGLE'] else 0
                for i in range(cfg.config['NUM_OF_FINGERS'])
            ]

            result = adjust_angles(angles, old_assignments | new_assignments)
            if result['ok']:
                angles = result['angles']
                cost = cost_for_move(hand, c, angles, time)
            else:
                cost = float('inf')
            bests.append([c, angles, new_assignments, cost])

    result = bests if bests else [[hand.center, old_angles, old_assignments, float('inf')]]
    _generate_hand_states_cache[key] = result

    return result


def cost_for_move(hand, new_center, new_angles, timestamp):
    """Computes translation + rotation + posture cost"""
    t_relax = cfg.config['POSTURE_RELAX_TIME_MS']
    alpha = min(max(0, timestamp - hand.last_active) / t_relax, 1.0)
    beta = math.exp((1-alpha)**2)
    trans_cost = abs(hand.center - new_center) * cfg.config['COST_PER_KEY_TRANSLATION']
    rot_cost = max((cfg.config['COST_PER_KEY_ROTATION'] if abs(a - b) > 0 else 0)
                   for a, b in zip(new_angles, hand.get_angles()))

    rotated_finger_penalty = sum([abs(a) * b for a, b in zip(new_angles, cfg.config['FINGER_ROTATED_PENALTY_COST'])])

    # uses max(trans, rot) for concurrency of those motions
    return beta * max(trans_cost, rot_cost) + alpha * rotated_finger_penalty


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

    # Release notes
    left_hand.release_notes(l_inactive)
    right_hand.release_notes(r_inactive)

    # Generate states and verify safety distance between centers
    if l_active or r_active:
        l_bests = generate_hand_states(left_hand, l_active, time)
        r_bests = generate_hand_states(right_hand, r_active, time)
        for (lc, l_angles, l_asgn, l_cost), (rc, r_angles, r_asgn, r_cost) in product(l_bests, r_bests):
            if abs(rc - lc) < safety_distance:
                continue  # skip too-close hands

            total_cost = l_cost + r_cost
            list_of_bests.append([total_cost, [lc, l_angles, l_asgn], [rc, r_angles, r_asgn]])

    list_of_bests.sort(key=lambda x: x[0])

    # Release notes
    left_hand.release_notes(l_inactive)
    right_hand.release_notes(r_inactive)

    l_state_copy = left_hand.get_state()
    r_state_copy = right_hand.get_state()

    l_state_of_last_active = left_hand.get_state_of_last_active()
    r_state_of_last_active = right_hand.get_state_of_last_active()

    # Mark the last event where it finished playing all notes (rests between active events)
    left_hand.update_last_active(time, l_inactive)
    right_hand.update_last_active(time, r_inactive)

    if list_of_bests:
        i = 0
        counter = 0
        while counter < beam_width and i < len(list_of_bests):
            option = list_of_bests[i]
            total_cost, l_state, r_state = option
            left_hand.set_state(l_state)
            right_hand.set_state(r_state)

            future_cost, _, _ = simulate_future(future, idx + 1, left_hand, right_hand)

            left_hand.set_state(l_state_copy, replace_assignments=True)
            right_hand.set_state(r_state_copy, replace_assignments=True)
            left_hand.set_state_of_last_active(l_state_of_last_active)
            right_hand.set_state_of_last_active(r_state_of_last_active)

            option[0] += future_cost
            i += 1

            if future_cost != float('inf'):
                counter += 1
            # else:  # THIS WAS FOR future_cost == inf
            #     break

        list_of_bests = list_of_bests[:i]
        list_of_bests.sort(key=lambda x: x[0])

        best_cost = list_of_bests[0][0]
        l_state = list_of_bests[0][1]
        r_state = list_of_bests[0][2]

        left_hand.update_last_active(time, l_inactive)
        right_hand.update_last_active(time, r_inactive)

        return best_cost, l_state, r_state

    else:
        best_cost, l_state, r_state = simulate_future(future, idx + 1, left_hand, right_hand)
        left_hand.set_state(l_state_copy, replace_assignments=True)
        right_hand.set_state(r_state_copy, replace_assignments=True)

        # When no new notes are happening, propagate a future state only if the hand is idle
        l_state = [l_state[0], l_state[1], {}] if not left_hand.note_assignments else left_hand.get_state()
        r_state = [r_state[0], r_state[1], {}] if not right_hand.note_assignments else right_hand.get_state()

        left_hand.update_last_active(time, l_inactive)
        right_hand.update_last_active(time, r_inactive)

        return best_cost, l_state, r_state


def schedule_actions(time_series):
    start = time.perf_counter()

    commands = {}
    right_hand, left_hand = Hand(), Hand()
    left_hand.set_position_by_center(cfg.config['MIN_HAND_CENTER_POSITION'])
    right_hand.set_position_by_center(cfg.config['MAX_HAND_CENTER_POSITION'])
    # right_hand.set_position_by_center(20)

    sorted_time_keys = sorted(time_series.keys())
    window_size = cfg.config['FUTURE_WINDOW_SIZE']

    for current_idx, current_time in enumerate(sorted_time_keys):
        if len(_generate_hand_states_cache) > 1000:
            _generate_hand_states_cache.clear()
        if len(_angles_cache) > 1000:
            _angles_cache.clear()

        hands = time_series[current_time]
        l_inactive = hands['left']['inactive']
        l_active = hands['left']['active']
        r_inactive = hands['right']['inactive']
        r_active = hands['right']['active']

        left_hand.release_notes(l_inactive, current_time)
        right_hand.release_notes(r_inactive, current_time)

        future = [(t, time_series[t]) for t in sorted_time_keys[current_idx: current_idx + window_size]]
        _, l_state, r_state = simulate_future(future, 0, left_hand, right_hand)
        left_hand.set_state(l_state)
        right_hand.set_state(r_state)

        if (left_hand.needs_pause_between_commands(at_time=current_time) or
                right_hand.needs_pause_between_commands(at_time=current_time)):
            commands[current_time - 1] = {'left': left_hand.get_state_for_pause(current_time)}
            commands[current_time - 1].update({'right': right_hand.get_state_for_pause(current_time)})
            print('###', current_time, ' -> ', commands[current_time - 1])

        commands[current_time] = {'left': left_hand.get_full_state()}
        commands[current_time].update({'right': right_hand.get_full_state()})

        print(current_time, ' -> ', commands[current_time], '  ', r_active, r_inactive, right_hand.note_assignments)

        # print(
        #     # time_series[sorted_time_keys[current_idx]]['left']['active'], left_hand.get_state(), '  ',
        #     right_hand.get_full_state(), right_hand.note_assignments, '  ',
        #     time_series[sorted_time_keys[current_idx]]['right']['active'], '  ',
        #     # current_time, '<->', right_hand.last_active
        # )

    _generate_hand_states_cache.clear()
    _angles_cache.clear()

    end = time.perf_counter()
    print(f"Execution time: {end - start:.6f} seconds")

    # for c in commands.items():
    #     print(c)

    return commands
