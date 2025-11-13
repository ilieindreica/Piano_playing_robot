import re
from typing import TypedDict

# Parameters for the robot setup
config = {
    'NUM_OF_OCTAVES': 0,
    'NUM_OF_WHITE_KEYS': 0,
    'NUM_OF_TEETH': 0,
    'TEETH_STEP': 0,
    'STEPS_PER_REVOLUTION': 0,
    'DISTANCE_BETWEEN_KEYS': 0,
    'TIME_FOR_SOLENOID_RETRACTION': 0,
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
    'MAX_HAND_CENTER_POSITION': 0,
    'MIN_HAND_CENTER_POSITION': 0,
    'COST_PER_KEY_TRANSLATION': 20,
    'COST_PER_KEY_ROTATION': 20,
    'POSTURE_RELAX_TIME_MS': 1500,
    'COST_POSTURE_DEVIATION': 20,
    'FUTURE_DEMAND_PENALTY': 1,
    'FUTURE_WINDOW_SIZE': 1
}


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


load_config()
