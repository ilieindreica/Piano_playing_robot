#ifndef SETUP_CONFIG.H
#define SETUP_CONFIG.H
/* --- This file contains parameters for piano-robot setup --- */
#define TMC2208_DRIVER 0
#define A4988_DRIVER 1
#define INSTALLED_DRIVER A4988_DRIVER

#define NUM_OF_OCTAVES 5
#define NUM_OF_WHITE_KEYS 36  // Needed to know the distance the robot can travel
#define NUM_OF_WHITE_KEYS_IN_OCTAVE 7
#define MAIN_OCTAVE 3  // Should be at least 2, to also make room for the hand that plays the bass
#define TEMPO 20  // Considered for the whole note
#define TIME_PER_BEAT (60000 / TEMPO)  // milliseconds

  /* CALCULATION EXAMPLE for one_key_step: 
    In full-step mode, it takes 200 steps for 1 revolution. The GT2-gear has, for example, 20 theet, with 2mm step.
    That means that 200 steps of the motor coresponds to 40mm (20teeth * 2mm) linear displacement.
    From one center of the key to another is 23mm, resulting in 115 steps of the motor for one key step */
#define NUM_OF_TEETH 36
#define TEETH_STEP 2  // mm
#define STEPS_PER_REVOLUTION 200
#define DISTANCE_BETWEEN_KEYS 23  // mm
#if INSTALLED_DRIVER == A4988_DRIVER
  #define MICROSTEP 1
#else
  #define MICROSTEP 2
#endif
#define ONE_KEY_STEP (STEPS_PER_REVOLUTION * DISTANCE_BETWEEN_KEYS / (NUM_OF_TEETH * TEETH_STEP)) * MICROSTEP
#define ONE_KEY_ROTATION 20  // num of degrees to rotate one key to the left or to the right
#define LIMIT_ANGLE_DEVIATION 50
#define ANGLE_THRESHOLD_TO_EXTEND 20  // Extend finger if it rotates above this angle, because otherwise it can press the wrong key or 2 keys simultaneously
#define LIMIT_OVERLAP_ANGLE 5


// 1/2 because the middles of the fingers stay at integer indices (the keys coordinates, counted in ONE_KEY_STEPs) 
// and the edge is 1/2*ONE_KEY_STEP from the middle of a finger
#define RIGHT_LIMIT_EDGE ((NUM_OF_WHITE_KEYS + 1/2))  // the coordinate of hitting the right limit switch
#define LEFT_LIMIT_EDGE 1/2  // the coordinate of hitting the left limit switch

#define NUM_OF_FINGERS 5
#define ROTATIONAL_REACH_OF_ONE_FINGER 2
#define SPAN_OF_HAND (NUM_OF_FINGERS + 2 * ROTATIONAL_REACH_OF_ONE_FINGER)   // The number of keys a hand can reach by just rotating fingers
#define START_POS_RIGHT_HAND (((2 * MAIN_OCTAVE - 1) * NUM_OF_WHITE_KEYS_IN_OCTAVE + 1) / 2)
#define START_POS_LEFT_HAND (START_POS_RIGHT_HAND - NUM_OF_WHITE_KEYS_IN_OCTAVE)

#define SAFETY_DISTANCE_BETWEEN_HANDS (SPAN_OF_HAND) // Calculated between the centers of hands
#define MAX_HAND_CENTER_POSITION (NUM_OF_WHITE_KEYS - (int)(NUM_OF_FINGERS/2))
#define MIN_HAND_CENTER_POSITION ((int)((NUM_OF_FINGERS + 1) / 2))
#define MAX_STEPPER_TRAVEL_DISTANCE (MAX_HAND_CENTER_POSITION * ONE_KEY_STEP)
#define MIN_STEPPER_TRAVEL_DISTANCE (MIN_HAND_CENTER_POSITION * ONE_KEY_STEP)

#define TIME_FOR_SOLENOID_RETRACTION 10 // A small time delay to give solenoids that press the keys time to retract (useful when needed to press same key multimple times in a row) 
#define TIME_FOR_ROTATION 60
#define TIME_FOR_EXTENSION 60
#define MINIMUM_TIME_FOR_PRESSING 0


#define ROT_COLS 11
// LEFT HAND ANGLES
// index:      
//  +2.5   +2    +1.5   +1   +0.5   0    -0.5   -1   -1.5   -2   -2.5
const int LEFT_ROTATION_ANGLES[NUM_OF_FINGERS][ROT_COLS] = {
    {116,  120,  104,  101,   88,   83,   74,   64,   59,   45,   48},  // finger 0, 
    {112,  115,   96,   88,   80,   73,   65,   57,   50,   41,   44},  // finger 1, 
    {122,  131,  114,  108,   96,   88,   80,   74,   69,   51,   54},  // finger 2, 
    {118,  121,  109,  102,   93,   84,   78,   70,   63,   51,   50},  // finger 3, 
    {106,  109,   95,   92,   82,   72,   67,   58,   53,   42,   38},  // finger 4, 
};


// RIGHT HAND ANGLES
// index:      
//  +2.5   +2    +1.5   +1   +0.5   0   -0.5   -1    -1.5   -2   -2.5
const int RIGHT_ROTATION_ANGLES[NUM_OF_FINGERS][ROT_COLS] = {
    {113,  118,  100,   95,   84,   71,   65,   54,   51,   37,   40},  // finger 0, 
    {100,  103,   86,   81,   71,   66,   62,   50,   43,   32,   32},  // finger 1, 
    {113,  116,  102,   99,   87,   79,   70,   55,   52,   38,   45},  // finger 2, 
    {121,  124,  106,  102,   94,   85,   79,   68,   63,   50,   53},  // finger 3, 
    {124,  127,  107,  100,   92,   82,   77,   66,   63,   50,   50},  // finger 4, 
};

/* --------------------------------------------- */


#endif