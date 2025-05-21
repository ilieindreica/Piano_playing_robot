import re
import numpy as np
import math
from scipy.optimize import linear_sum_assignment

from sheet_detection.Notes import NoteWithPosition

# Parameters for the robot setup
config = {
    'NUM_OF_OCTAVES': 0,
    'NUM_OF_WHITE_KEYS': 0,
    'NUM_OF_TEETH': 0,
    'TEETH_STEP': 0,
    'STEPS_PER_REVOLUTION': 0,
    'DISTANCE_BETWEEN_KEYS': 0,
    'ONE_KEY_STEP': 0,
    'RIGHT_LIMIT_EDGE': 0,
    'LEFT_LIMIT_EDGE': 0,
    'NUM_OF_FINGERS': 0,
    'SPAN_OF_HAND': 0,
    'MAIN_OCTAVE': 0,
    'NUM_OF_WHITE_KEYS_IN_OCTAVE': 0,
    'START_POS_LEFT_HAND': 0,
    'START_POS_RIGHT_HAND': 0,
    'SAFETY_DISTANCE_BETWEEN_HANDS': 0,
    'ROTATIONAL_REACH_OF_ONE_FINGER': 0,
    'POS_BIT_LENGTH': 0,
    'UNSIGNED_ANGLE_BIT_LENGTH': 0,
    'ANGLE_BIT_LENGTH': 0,
    'SOLENOIDS_BIT_LENGTH': 0,
    'DURATION_BIT_LENGTH': 0,
    'POS_AND_ANGLE_COMMAND_BIT_LENGTH': 0,
    'SOLENOIDS_AND_DURATION_COMMAND_BIT_LENGTH': 0
}


# Scores for each finger
FINGER_SCORES = [10, 10, 10, 10, 10]
# Scores based on the distance the finger must rotate to reach the key
ROTATION_SCORES = [(0, 10), (1, 8), (0, 6)]
# Scores based on the distance the hand must travel
HAND_MOVEMENT_SCORES = [(0, 15), (2, 10), (5, 8), (10, 5), (20, 2), (float("inf"), 0)]  # (distance, score)
# Scores based on available time for moving hand
TIME_SCORES = [(500, 10), (300, 8), (150, 5), (0, 2)]  # (time, score)


def get_hand_score(distance):
    """Returns the score for hand movement based on distance"""
    for dist, score in HAND_MOVEMENT_SCORES:
        if distance <= dist:
            return score
    return 0


def get_time_score(available_time):
    """Returns the score based on the available time for hand movement."""
    for time, score in TIME_SCORES:
        if available_time >= time:
            return score
    return 0


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
        self.fingers = [Finger(i) for i in range(config['NUM_OF_FINGERS'])]

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
            finger.position = pos
            pos += 1

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
            self.fingers[finger_idx].angle = cost_matrix[note_idx][finger_idx]
            self.fingers[finger_idx].duration = notes_duration[note_idx]

        # print([f.get_finger_state() for f in self.fingers])
        return [f.get_finger_state() for f in self.fingers]

    @property
    def offset(self):
        return int(config['NUM_OF_FINGERS'] / 2)


def load_config(file_path="../hands_control/Piano-robot_setup_config.h"):
    """Loads the parameters on which the robot setup depends, and which are written in a separate file, to which Arduino
    also has access. This way is ensured that the parameters need to be modified in only one place."""
    expressions = {}  # Store expressions separately

    with open(file_path, "r") as file:
        for line in file:
            # Remove inline comments
            line = line.split("//")[0].strip()
            if not line:
                continue  # Skip empty lines

            match_define = re.match(r"#define (\w+) ([\d.]+)", line)
            if match_define:
                key, value = match_define.groups()
                config[key] = float(value) if "." in value else int(value)

            match_expression = re.match(r"#define (\w+|\d+\.\d+) \((.+)\)", line)
            if match_expression:
                key, expr = match_expression.groups()
                expressions[key] = expr

    # Evaluate expressions
    for key, expr in expressions.items():
        try:
            # Replace variables in expression with actual values
            eval_expr = expr
            for var in config.keys():
                eval_expr = re.sub(rf'\b{var}\b', str(config[var]), eval_expr)  # Replace whole words only

            # Evaluate the expression
            config[key] = eval(eval_expr)
        except Exception as e:
            print(f"Error evaluating {key}: {e}")


def group_notes_by_span(sequence, span):
    """Group notes into "clusters" that can all be contained by the span of one hand.
    'sequence' should be a list of lists of objects of class NoteWithPosition.\n
    It ensures that all notes that play at the same time are in span, as they cannot be in separate groups
    (i.e. having a hand transition between them)"""

    min_pos = config['NUM_OF_WHITE_KEYS']
    max_pos = 0
    groups = []
    mean_pos_sequence = []
    cluster = []

    for notes in sequence:
        # Filter out 'REST' values before finding min/max positions
        valid_notes = [note for note in notes if note.pos != 'REST']

        if valid_notes:
            # Get the extreme positions at the current time step
            min_pos_at_time_k = min(valid_notes, key=lambda note: note.pos).pos
            max_pos_at_time_k = max(valid_notes, key=lambda note: note.pos).pos

            # Check if the span fits the notes at current time step and all the previous ones
            # The reason for +1: if keys are 1,2,3,4 and span 3, 4-1=3, but there are 4 keys, and that is out of span
            if max(max_pos, max_pos_at_time_k) - min(min_pos, min_pos_at_time_k) + 1 <= span:
                max_pos = max(max_pos, max_pos_at_time_k)
                min_pos = min(min_pos, min_pos_at_time_k)
                cluster.append(notes)
            # If not, begin a new cluster
            else:
                if cluster:
                    groups.append(cluster)
                    mean_pos = math.ceil((max_pos + min_pos) / 2)
                    mean_pos_sequence.extend([mean_pos] * len(cluster))
                max_pos = max_pos_at_time_k
                min_pos = min_pos_at_time_k
                cluster = [notes]
        else:
            # If all notes in this time step are REST, or an empty list, just add them to the cluster
            cluster.append(notes)

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
        if notes_at_k:
            hand = Hand()
            hand.set_position_by_center(pos_at_k)
            notes_pos_at_k = [n.pos for n in notes_at_k]
            notes_duration_at_k = [n.duration for n in notes_at_k]
            finger_pos_series.append(hand.calculate_finger_states(notes_pos_at_k, notes_duration_at_k))

    return finger_pos_series


def schedule_actions(time_series, adjust_for_octave=True, is_double_handed=True):
    octave_shift = config['MAIN_OCTAVE'] * config['NUM_OF_WHITE_KEYS_IN_OCTAVE']
    span = config['SPAN_OF_HAND']
    half_span = math.ceil(span / 2)
    safety_distance = config['SAFETY_DISTANCE_BETWEEN_HANDS']

    # Lists of lists; each sublist represent a moment in time, and its elements are all occurring at that time
    left_notes = []
    right_notes = []

    for time, hands in time_series.items():
        for hand, notes in hands.items():
            # If the info is processed from a MIDI file, this adjustment is not necessary
            if adjust_for_octave:
                for note in notes:
                    if note.pos != 'REST':
                        note.pos += octave_shift

        # This approach was chosen to maintain equal lengths for both hands
        # (avoiding discrepancies due to varying note durations) and ensure synchronization across time beats.
        # It simplifies collision checking and allows for easier tracking of both hands'
        # positions at each specific time/beat.
        left_notes.append(hands['left'])
        right_notes.append(hands['right'])

    right_groups, right_hand_positions = group_notes_by_span(right_notes, span)
    left_groups, left_hand_positions = group_notes_by_span(left_notes, span)

    # Collision checking
    # It assumes left_ and right_ have the same number of elements, for a direct correlation
    try:
        if is_double_handed:
            for i, (l_pos, r_pos) in enumerate(zip(left_hand_positions, right_hand_positions)):
                difference = safety_distance - (r_pos - l_pos)  # Amount by which hands are too close

                if difference > 0:  # Collision detected
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
                        print(f"Warning: Could not maintain safety distance at index {i}")

                    right_hand_positions[i] = r_pos
                    left_hand_positions[i] = l_pos
    except Exception as e:
        print(f'Exceptie: {e}')

    right_finger_states = get_finger_pos_series(right_hand_positions, right_notes)
    left_finger_states = get_finger_pos_series(left_hand_positions, left_notes)

    right_actions = list(zip(right_hand_positions, right_finger_states))
    left_actions = list(zip(left_hand_positions, left_finger_states))

    return left_actions, right_actions


def encode_actions(actions):
    commands = []
    # Multiply by 2 so float numbers can be preserved; needs to divide by 2 at receiver end or to move by
    # half the distance between keys
    pos_bit_length = config['POS_BIT_LENGTH']
    unsigned_angle_bit_length = config['UNSIGNED_ANGLE_BIT_LENGTH']
    # Needs to be signed, to account for direction of rotation
    angle_bit_length = config['ANGLE_BIT_LENGTH']
    solenoids_bit_length = config['SOLENOIDS_BIT_LENGTH']
    duration_bit_length = config['DURATION_BIT_LENGTH']
    pos_and_angle_command_bit_length = config['POS_AND_ANGLE_COMMAND_BIT_LENGTH']
    solenoids_and_duration_command_bit_length = config['SOLENOIDS_AND_DURATION_COMMAND_BIT_LENGTH']
    pos_and_angle_command_bit_length += solenoids_and_duration_command_bit_length
    for pos, fingers in actions:
        shift = pos_and_angle_command_bit_length - 1
        command = int(pos * 2) << (shift - pos_bit_length)
        shift -= pos_bit_length
        angles = [a for _, _, a, _ in fingers]
        for angle in angles:
            sign = 1 if angle < 0 else 0
            angle = abs(angle) * 2
            command |= sign << shift | int(angle) << (shift - unsigned_angle_bit_length)
            shift -= angle_bit_length
        for back_s, front_s, _, duration in fingers:
            command |= back_s << shift
            shift -= 1
            command |= front_s << shift
            shift -= 1
            # To be better transmitted (int instead of float), encode duration as its inverse
            if duration != 0:
                duration = int(1/duration)
            if shift - duration <= 0:
                command |= duration << (shift - duration_bit_length)
                shift -= duration_bit_length
            else:
                command |= duration

        # print(f'{command:0{pos_and_angle_command_bit_length}b}')
        # command_bit_length = ((left_commands[0]).bit_length() + 7) // 8
        commands.append(command)
    return pos_and_angle_command_bit_length, commands


def rearrange_actions(actions):
    rearranged_actions = []
    for pos, fingers in actions:
        rotations, back, front, duration = zip(
            *[(int(r*2), b, f, int(1 / d) if d != 0 else 0) for b, f, r, d in fingers])
        rearranged_actions.append((int(pos * 2), list(rotations), list(back), list(front), list(duration)))
    return rearranged_actions


def get_action_commands(time_series, is_double_handed=True):
    load_config()
    left_actions, right_actions = schedule_actions(time_series, is_double_handed=is_double_handed)
    # return encode_actions(left_actions), encode_actions(right_actions)
    left_actions = rearrange_actions(left_actions)
    right_actions = rearrange_actions(right_actions)

    return left_actions, right_actions






la_primavera = {0: {'left': [NoteWithPosition(position='REST', duration=0.25)],
             'right': [NoteWithPosition(position=-5, duration=0.25)]}, 0.25: {
            'left': [NoteWithPosition(position=-10, duration=1), NoteWithPosition(position=-8, duration=1),
                     NoteWithPosition(position=-12, duration=1)],
            'right': [NoteWithPosition(position=-2.5, duration=0.25)]},
         0.5: {'left': [], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
         0.75: {'left': [], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
         1.0: {'left': [], 'right': [NoteWithPosition(position=-4, duration=0.125)]},
         1.125: {'left': [], 'right': [NoteWithPosition(position=-5, duration=0.125)]},
         1.25: {'left': [NoteWithPosition(position=-8, duration=1), NoteWithPosition(position=-12, duration=1)],
                'right': [NoteWithPosition(position=-1, duration=0.5)]}, 1.75: {'left': [], 'right': [
            NoteWithPosition(position=5, duration=0.125), NoteWithPosition(position=-1, duration=0.125)]},
         1.875: {'left': [], 'right': [NoteWithPosition(position=-2, duration=0.125)]},
         2.0: {'left': [], 'right': [NoteWithPosition(position='REST', duration=0.25)]},
         2.25: {'left': [NoteWithPosition(position=-10, duration=1), NoteWithPosition(position=-12, duration=1)],
                'right': [NoteWithPosition(position=-2.5, duration=0.25)]},
         2.5: {'left': [], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
         2.75: {'left': [], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
         3.0: {'left': [], 'right': [NoteWithPosition(position=-4, duration=0.125)]},
         3.125: {'left': [], 'right': [NoteWithPosition(position=-5, duration=0.125)]},
         3.25: {'left': [NoteWithPosition(position=-8, duration=1), NoteWithPosition(position=-12, duration=1)],
                'right': [NoteWithPosition(position=-1, duration=0.5)]},
         3.75: {'left': [], 'right': [NoteWithPosition(position=-1, duration=0.125)]},
         3.875: {'left': [], 'right': [NoteWithPosition(position=-2, duration=0.125)]},
         4.0: {'left': [], 'right': [NoteWithPosition(position='REST', duration=0.25)]},
         4.25: {'left': [NoteWithPosition(position=-12, duration=0.5)],
                'right': [NoteWithPosition(position=-2.5, duration=0.25)]},
         4.5: {'left': [], 'right': [NoteWithPosition(position=-2, duration=0.125)]},
         4.625: {'left': [], 'right': [NoteWithPosition(position=-1, duration=0.125)]},
         4.75: {'left': [NoteWithPosition(position=-9, duration=0.25)],
                'right': [NoteWithPosition(position=-2, duration=0.25)]},
         5.0: {'left': [NoteWithPosition(position=-9.5, duration=0.25)],
               'right': [NoteWithPosition(position=-3, duration=0.25)]},
         5.25: {'left': [NoteWithPosition(position=-11, duration=0.5)],
                'right': [NoteWithPosition(position=-4, duration=0.5)]},
         5.75: {'left': [NoteWithPosition(position='REST', duration=0.25)],
                'right': [NoteWithPosition(position='REST', duration=0.25)]},
         6.0: {'left': [NoteWithPosition(position=-12, duration=0.25)],
               'right': [NoteWithPosition(position=-5, duration=0.25)]}}

twinkle_twinkle = {0: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-6, duration=0.25)]},
                   0.25: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-6, duration=0.25)]},
                   0.5: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-2, duration=0.25)]},
                   0.75: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-2, duration=0.25)]},
                   1.0: {'left': [NoteWithPosition(position=-10, duration=0.25)], 'right': [NoteWithPosition(position=-1, duration=0.25)]},
                   1.25: {'left': [NoteWithPosition(position=-10, duration=0.25)], 'right': [NoteWithPosition(position=-1, duration=0.25)]},
                   1.5: {'left': [NoteWithPosition(position=-11, duration=0.5)], 'right': [NoteWithPosition(position=-2, duration=0.5)]},
                   2.0: {'left': [NoteWithPosition(position=-12, duration=0.25)], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
                   2.25: {'left': [NoteWithPosition(position=-12, duration=0.25)], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
                   2.5: {'left': [NoteWithPosition(position=-13, duration=0.25)], 'right': [NoteWithPosition(position=-4, duration=0.25)]},
                   2.75: {'left': [NoteWithPosition(position=-13, duration=0.25)], 'right': [NoteWithPosition(position=-4, duration=0.25)]},
                   3.0: {'left': [NoteWithPosition(position=-14, duration=0.25)], 'right': [NoteWithPosition(position=-5, duration=0.25)]},
                   3.25: {'left': [NoteWithPosition(position=-14, duration=0.25)], 'right': [NoteWithPosition(position=-5, duration=0.25)]},
                   3.5: {'left': [NoteWithPosition(position=-13, duration=0.5)], 'right': [NoteWithPosition(position=-6, duration=0.5)]},
                   4.0: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-2, duration=0.25)]},
                   4.25: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-2, duration=0.25)]},
                   4.5: {'left': [NoteWithPosition(position=-12, duration=0.25)], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
                   4.75: {'left': [NoteWithPosition(position=-12, duration=0.25)], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
                   5.0: {'left': [NoteWithPosition(position=-13, duration=0.25)], 'right': [NoteWithPosition(position=-4, duration=0.25)]},
                   5.25: {'left': [NoteWithPosition(position=-13, duration=0.25)], 'right': [NoteWithPosition(position=-4, duration=0.25)]},
                   5.5: {'left': [NoteWithPosition(position=-14, duration=0.5)], 'right': [NoteWithPosition(position=-5, duration=0.5)]},
                   6.0: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-2, duration=0.25)]},
                   6.25: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-2, duration=0.25)]},
                   6.5: {'left': [NoteWithPosition(position=-12, duration=0.25)], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
                   6.75: {'left': [NoteWithPosition(position=-12, duration=0.25)], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
                   7.0: {'left': [NoteWithPosition(position=-13, duration=0.25)], 'right': [NoteWithPosition(position=-4, duration=0.25)]},
                   7.25: {'left': [NoteWithPosition(position=-13, duration=0.25)], 'right': [NoteWithPosition(position=-4, duration=0.25)]},
                   7.5: {'left': [NoteWithPosition(position=-16, duration=0.5)], 'right': [NoteWithPosition(position=-5, duration=0.5)]},
                   8.0: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-7, duration=0.25)]},
                   8.25: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-6, duration=0.25)]},
                   8.5: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-2, duration=0.25)]},
                   8.75: {'left': [NoteWithPosition(position=-11, duration=0.25)], 'right': [NoteWithPosition(position=-2, duration=0.25)]},
                   9.0: {'left': [NoteWithPosition(position=-10, duration=0.125)], 'right': [NoteWithPosition(position=-1, duration=0.25)]},
                   9.25: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=-1, duration=0.25)]},
                   9.5: {'left': [NoteWithPosition(position=-6, duration=0.5)], 'right': [NoteWithPosition(position=-2, duration=0.5)]},
                   10.0: {'left': [NoteWithPosition(position=-12, duration=0.25)], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
                   10.25: {'left': [NoteWithPosition(position=-8, duration=0.25)], 'right': [NoteWithPosition(position=-3, duration=0.25)]},
                   10.5: {'left': [NoteWithPosition(position=-9, duration=0.25)], 'right': [NoteWithPosition(position=-4, duration=0.25)]},
                   10.75: {'left': [NoteWithPosition(position=-13, duration=0.25)], 'right': [NoteWithPosition(position=-4, duration=0.25)]},
                   11.0: {'left': [NoteWithPosition(position=-9, duration=0.25)], 'right': [NoteWithPosition(position=-5, duration=0.25)]},
                   11.25: {'left': [NoteWithPosition(position=-16, duration=0.25)], 'right': [NoteWithPosition(position=-5, duration=0.25)]},
                   11.5: {'left': [NoteWithPosition(position=-13, duration=0.5)], 'right': [NoteWithPosition(position=-6, duration=0.5)]},
                   9.125: {'left': [NoteWithPosition(position=-9, duration=0.125)], 'right': []},
                   9.375: {'left': [NoteWithPosition(position=-7, duration=0.125)], 'right': []}}


swan_lake = {0: {'left': [NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=-2, duration=0.5), NoteWithPosition(position=3, duration=0.5)]},
             0.5: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=-1, duration=0.125)]},
             0.625: {'left': [NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-5, duration=0.125)], 'right': [NoteWithPosition(position=0, duration=0.125)]},
             0.75: {'left': [NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-3, duration=0.125)], 'right': [NoteWithPosition(position=1, duration=0.125)]},
             0.875: {'left': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-5, duration=0.125)], 'right': [NoteWithPosition(position=2, duration=0.125)]},
             1.0: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=-2, duration=0.125), NoteWithPosition(position=1, duration=0.125)]},
             1.125: {'left': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-3, duration=0.125)], 'right': [NoteWithPosition(position=3, duration=0.25)]},
             1.375: {'left': [NoteWithPosition(position=-6, duration=0.125)], 'right': [NoteWithPosition(position=-2, duration=0.125), NoteWithPosition(position=-4, duration=0.125), NoteWithPosition(position=1, duration=0.125)]},
             1.5: {'left': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-10, duration=0.125)], 'right': [NoteWithPosition(position=3, duration=0.25)]},
             1.75: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=-1, duration=0.125)]},
             1.875: {'left': [NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-6, duration=0.125)], 'right': [NoteWithPosition(position=1, duration=0.125)]},
             2.0: {'left': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-3, duration=0.125)], 'right': [NoteWithPosition(position=-1, duration=0.125)]},
             2.125: {'left': [NoteWithPosition(position='REST', duration=0.125), NoteWithPosition(position='REST', duration=0.125)], 'right': [NoteWithPosition(position=-3, duration=0.125), NoteWithPosition(position=4, duration=0.125)]},
             2.25: {'left': [NoteWithPosition(position='REST', duration=0.25)], 'right': [NoteWithPosition(position=1, duration=0.125)]},
             2.375: {'left': [], 'right': [NoteWithPosition(position=-1, duration=0.5), NoteWithPosition(position=4, duration=0.5)]},
             2.875: {'left': [NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-6, duration=0.125)], 'right': [NoteWithPosition(position=-11, duration=0.125)]},
             3.0: {'left': [NoteWithPosition(position=-10, duration=0.125)], 'right': [NoteWithPosition(position='REST', duration=0.125)]},
             3.125: {'left': [NoteWithPosition(position=-6, duration=0.125)], 'right': [NoteWithPosition(position=-2, duration=0.125), NoteWithPosition(position=2, duration=0.125)]},
             3.25: {'left': [NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=-2, duration=0.125), NoteWithPosition(position=1, duration=0.125)]},
             3.375: {'left': [NoteWithPosition(position=-5, duration=0.125)], 'right': [NoteWithPosition(position=-7, duration=0.125), NoteWithPosition(position=-2, duration=0.125), NoteWithPosition(position=-4, duration=0.125), NoteWithPosition(position=0, duration=0.125)]},
             3.5: {'left': [NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-3, duration=0.125)], 'right': [NoteWithPosition(position='REST', duration=0.25)]},
             0.125: {'left': [NoteWithPosition(position=-6, duration=0.125)], 'right': []}, 0.25: {'left': [NoteWithPosition(position=-3, duration=0.125)], 'right': []},
             0.375: {'left': [NoteWithPosition(position=-6, duration=0.125)], 'right': []}, 1.25: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': []},
             1.625: {'left': [NoteWithPosition(position='REST', duration=0.125)], 'right': []}, 2.5: {'left': [NoteWithPosition(position=-8.5, duration=0.25)], 'right': []},
             2.75: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': []},
             3.625: {'left': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-5, duration=0.125)], 'right': []},
             3.75: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=0, duration=0.5), NoteWithPosition(position=3, duration=0.5)]},
             4.25: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=-1, duration=0.125)]},
             4.375: {'left': [NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-5, duration=0.125)], 'right': [NoteWithPosition(position=0, duration=0.125)]},
             4.5: {'left': [NoteWithPosition(position=-6, duration=0.125), NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-3, duration=0.125)], 'right': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-8, duration=0.125)]},
             4.625: {'left': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-5, duration=0.125)], 'right': [NoteWithPosition(position=2, duration=0.125), NoteWithPosition(position=4, duration=0.125)]},
             4.75: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=3, duration=0.25)]},
             5.0: {'left': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-6, duration=0.125), NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=1, duration=0.125), NoteWithPosition(position=-2, duration=0.125)]},
             5.125: {'left': [NoteWithPosition(position='REST', duration=0.125)], 'right': [NoteWithPosition(position=3, duration=0.25)]},
             5.375: {'left': [NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-6, duration=0.125)], 'right': [NoteWithPosition(position=1, duration=0.125), NoteWithPosition(position=-2, duration=0.125)]},
             5.5: {'left': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-6, duration=0.125), NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position='REST', duration=0.25)]},
             5.75: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': [NoteWithPosition(position=0, duration=0.25), NoteWithPosition(position=3, duration=0.25)]},
             6.0: {'left': [NoteWithPosition(position=-11, duration=0.125), NoteWithPosition(position=-4, duration=0.125)], 'right': [NoteWithPosition(position=-1, duration=0.125), NoteWithPosition(position=0, duration=0.125)]},
             6.125: {'left': [NoteWithPosition(position='REST', duration=0.125)], 'right': [NoteWithPosition(position=1, duration=0.125)]},
             6.25: {'left': [NoteWithPosition(position='REST', duration=0.25)], 'right': [NoteWithPosition(position=-1, duration=0.125)]},
             6.375: {'left': [], 'right': [NoteWithPosition(position=-3, duration=0.125)]},
             6.5: {'left': [NoteWithPosition(position=-8.5, duration=0.25)], 'right': [NoteWithPosition(position=1, duration=0.125)]},
             6.625: {'left': [], 'right': [NoteWithPosition(position=-1, duration=0.5)]},
             7.125: {'left': [NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-6, duration=0.125)], 'right': [NoteWithPosition(position=-11, duration=0.0625), NoteWithPosition(position=-9, duration=0.0625)]},
             7.1875: {'left': [], 'right': [NoteWithPosition(position='REST', duration=0.25)]},
             7.4375: {'left': [], 'right': [NoteWithPosition(position=-1, duration=0.25)]},
             7.6875: {'left': [], 'right': [NoteWithPosition(position='REST', duration=0.0625)]},
             7.75: {'left': [NoteWithPosition(position=-9, duration=0.125)], 'right': [NoteWithPosition(position=0, duration=0.25)]},
             8.0: {'left': [NoteWithPosition(position=-5, duration=0.125)], 'right': [NoteWithPosition(position=1, duration=0.25)]},
             8.25: {'left': [NoteWithPosition(position=-10, duration=0.125)], 'right': [NoteWithPosition(position=-4, duration=0.25), NoteWithPosition(position=2, duration=0.25)]},
             8.5: {'left': [NoteWithPosition(position=-13, duration=0.125), NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-12, duration=0.125), NoteWithPosition(position=-5, duration=0.125)], 'right': [NoteWithPosition(position=0, duration=0.125), NoteWithPosition(position=3, duration=0.125)]},
             8.625: {'left': [NoteWithPosition(position='REST', duration=0.125)], 'right': [NoteWithPosition(position=0, duration=0.125), NoteWithPosition(position=4, duration=0.125)]},
             3.875: {'left': [NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-6, duration=0.125)], 'right': []}, 4.0: {'left': [NoteWithPosition(position=-6, duration=0.125), NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-3, duration=0.125)], 'right': []}, 4.125: {'left': [NoteWithPosition(position=-6, duration=0.125)], 'right': []}, 4.875: {'left': [NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-6, duration=0.125)], 'right': []}, 5.25: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': []}, 5.625: {'left': [NoteWithPosition(position='REST', duration=0.125)], 'right': []}, 5.875: {'left': [NoteWithPosition(position=-6, duration=0.125)], 'right': []}, 6.75: {'left': [NoteWithPosition(position=-8, duration=0.125)], 'right': []}, 6.875: {'left': [NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-6, duration=0.125)], 'right': []}, 7.0: {'left': [NoteWithPosition(position=-6, duration=0.125), NoteWithPosition(position=-8, duration=0.125), NoteWithPosition(position=-4, duration=0.125)], 'right': []}, 7.25: {'left': [NoteWithPosition(position=-8, duration=0.25)], 'right': []}, 7.5: {'left': [NoteWithPosition(position='REST', duration=0.25)], 'right': []}, 7.875: {'left': [NoteWithPosition(position=-7, duration=0.125)], 'right': []}, 8.125: {'left': [NoteWithPosition(position=-7, duration=0.125)], 'right': []}, 8.375: {'left': [NoteWithPosition(position=-10, duration=0.125), NoteWithPosition(position=-12, duration=0.125), NoteWithPosition(position=-7, duration=0.125)], 'right': []}}


# get_action_commands(time_series)




