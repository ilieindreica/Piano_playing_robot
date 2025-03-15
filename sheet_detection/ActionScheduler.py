import re
import numpy as np


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
    'SAFETY_DISTANCE_BETWEEN_HANDS': 0
}


# Scores for each finger
FINGER_SCORES = [10, 10, 10, 10, 10]
# Scores based on the distance the finger must rotate to reach the key
ROTATION_SCORES = [(0, 10), (1, 8), (0, 6)]
# Scores based on the distance the hand must travel
HAND_MOVEMENT_SCORES = [(0, 15), (2, 10), (5, 8), (10, 5), (20, 2), (float("inf"), 0)]  # (distance, score)
# Scores based on available time for moving hand
TIME_SCORES = [(500, 10), (300, 8), (150, 5), (0, 2)]  # (time, score)


class Finger:
    def __init__(self):
        self.available = True
        self.occupied_start_time = 0  # Time when the finger becomes occupied
        self.occupied_duration = 0  # Duration for which the resource remains occupied
        self.angle = 0


class Hand:
    def __init__(self):
        self.center = 0
        self.left_edge = 0
        self.right_edge = 0

    def set_position_by_center(self, pos):
        self.center = pos
        self.left_edge = pos - self.offset
        self.right_edge = pos + self.offset

    def set_position_by_right_edge(self, pos):
        self.center = pos - self.offset
        self.right_edge = pos
        self.left_edge = pos - 2 * self.offset

    def set_position_by_left_edge(self, pos):
        self.center = pos + self.offset
        self.right_edge = pos + 2 * self.offset
        self.left_edge = pos

    @property
    def offset(self):
        return config['NUM_OF_FINGERS'] / 2


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
            # match_expression = re.match(r"#define (\w+) ([^\n]+)", line)
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


def schedule_actions(time_series):
    octave_shift = config['MAIN_OCTAVE'] * config['NUM_OF_WHITE_KEYS_IN_OCTAVE']
    span = config['SPAN_OF_HAND']
    right_hand = Hand()
    left_hand = Hand()

    right_hand.set_position_by_center(config['START_POS_RIGHT_HAND'])
    left_hand.set_position_by_center(config['START_POS_LEFT_HAND'])
    print(left_hand.center, right_hand.center)

    for time_stamp, notes in time_series:
        left_notes = []
        right_notes = []
        for _, note_pos, duration in notes:
            if note_pos != 'REST':
                note_pos += octave_shift
                # Distribute notes to the closest hand
                (left_notes if abs(left_hand.center - note_pos) < abs(right_hand.center - note_pos)
                 else right_notes).append((note_pos, duration))

        print(left_notes, right_notes)



