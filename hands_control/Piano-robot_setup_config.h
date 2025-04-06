#ifndef SETUP_CONFIG.H
#define SETUP_CONFIG.H
/* --- This file contains parameters for piano-robot setup --- */
#define NUM_OF_OCTAVES 5
#define NUM_OF_WHITE_KEYS 36  // Needed to know the distance the robot can travel
#define NUM_OF_WHITE_KEYS_IN_OCTAVE 7
#define MAIN_OCTAVE 3  // Should be at least 2, to also make room for the hand that plays the bass
#define TEMPO 20  // Considered for the whole note
#define TIME_PER_BEAT (60000 / TEMPO)  // milliseconds

#define TIME_FOR_SOLENOID_RETRACTION 100  // A small time delay to give solenoids that press the keys time to retract (useful when needed to press same key multimple times in a row) 

  /* CALCULATION EXAMPLE for one_key_step: 
    In full-step mode, it takes 200 steps for 1 revolution. The GT2-gear has, for example, 20 theet, with 2mm step.
    That means that 200 steps of the motor coresponds to 40mm (20teeth * 2mm) linear displacement.
    From one center of the key to another is 23mm, resulting in 115 steps of the motor for one key step */
#define NUM_OF_TEETH 20
#define TEETH_STEP 2  // mm
#define STEPS_PER_REVOLUTION 200
#define DISTANCE_BETWEEN_KEYS 23  // mm
#define ONE_KEY_STEP (STEPS_PER_REVOLUTION * DISTANCE_BETWEEN_KEYS / (NUM_OF_TEETH * TEETH_STEP))
#define ONE_KEY_ROTATION 10  // num of degrees to rotate one key to the left or to the right

// 1/2 because the middles of the fingers stay at integer indices (the keys coordinates, counted in ONE_KEY_STEPs) 
// and the edge is 1/2*ONE_KEY_STEP from the middle of a finger
#define RIGHT_LIMIT_EDGE ((NUM_OF_WHITE_KEYS + 1/2))  // the coordinate of hitting the right limit switch
#define LEFT_LIMIT_EDGE 1/2  // the coordinate of hitting the left limit switch

#define NUM_OF_FINGERS 5
#define ROTATIONAL_REACH_OF_ONE_FINGER 2
#define SPAN_OF_HAND (NUM_OF_FINGERS + 2 * ROTATIONAL_REACH_OF_ONE_FINGER)   // The number of keys a hand can reach by just rotating fingers
#define START_POS_RIGHT_HAND (((2 * MAIN_OCTAVE - 1) * NUM_OF_WHITE_KEYS_IN_OCTAVE + 1) / 2)
#define START_POS_LEFT_HAND (START_POS_RIGHT_HAND - NUM_OF_WHITE_KEYS_IN_OCTAVE)

#define SAFETY_DISTANCE_BETWEEN_HANDS (int(SPAN_OF_HAND / 2))  // Calculated between the centers of hands
#define MAX_HAND_CENTER_POSITION (NUM_OF_WHITE_KEYS - (int)(NUM_OF_FINGERS/2))
#define MIN_HAND_CENTER_POSITION ((int)((NUM_OF_FINGERS + 1) / 2))
#define MAX_STEPPER_TRAVEL_DISTANCE (MAX_HAND_CENTER_POSITION * ONE_KEY_STEP)
#define MIN_STEPPER_TRAVEL_DISTANCE (MIN_HAND_CENTER_POSITION * ONE_KEY_STEP)

#define POS_BIT_LENGTH 7
#define UNSIGNED_ANGLE_BIT_LENGTH 3
#define ANGLE_BIT_LENGTH (UNSIGNED_ANGLE_BIT_LENGTH + 1)
#define SOLENOIDS_BIT_LENGTH 3
#define DURATION_BIT_LENGTH 5
#define POS_AND_ANGLE_COMMAND_BIT_LENGTH (POS_BIT_LENGTH + ANGLE_BIT_LENGTH * NUM_OF_FINGERS)
#define SOLENOIDS_AND_DURATION_COMMAND_BIT_LENGTH (2 * SOLENOIDS_BIT_LENGTH + DURATION_BIT_LENGTH * NUM_OF_FINGERS)
/* --------------------------------------------- */


#endif