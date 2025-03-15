#ifndef SETUP_CONFIG.H
#define SETUP_CONFIG.H
/* --- This file contains parameters for piano-robot setup --- */
#define NUM_OF_OCTAVES 5
#define NUM_OF_WHITE_KEYS 36  // Needed to know the distance the robot can travel
#define NUM_OF_WHITE_KEYS_IN_OCTAVE 7
#define MAIN_OCTAVE 3  // Should be at least 2, to also make room for the hand that plays the bass

  /* CALCULATION EXAMPLE for one_key_step: 
    In full-step mode, it takes 200 steps for 1 revolution. The GT2-gear has, for example, 20 theet, with 2mm step.
    That means that 200 steps of the motor coresponds to 40mm (20teeth * 2mm) linear displacement.
    From one center of the key to another is 23mm, resulting in 115 steps of the motor for one key step */
#define NUM_OF_TEETH 20
#define TEETH_STEP 2  // mm
#define STEPS_PER_REVOLUTION 200
#define DISTANCE_BETWEEN_KEYS 23  // mm
#define ONE_KEY_STEP (STEPS_PER_REVOLUTION * DISTANCE_BETWEEN_KEYS / (NUM_OF_TEETH * TEETH_STEP))

// 1/2 because the middles of the fingers stay at integer indices (the keys coordinates, counted in ONE_KEY_STEPs) 
// and the edge is 1/2*ONE_KEY_STEP from the middle of a finger
#define RIGHT_LIMIT_EDGE ((NUM_OF_WHITE_KEYS + 1/2))  // the coordinate of hitting the right limit switch
#define LEFT_LIMIT_EDGE 1/2  // the coordinate of hitting the left limit switch

#define NUM_OF_FINGERS 5
#define SPAN_OF_HAND 7  // The number of keys a hand can reach by just rotating fingers
#define START_POS_RIGHT_HAND (((2 * MAIN_OCTAVE - 1) * NUM_OF_WHITE_KEYS_IN_OCTAVE + 1) / 2)
#define START_POS_LEFT_HAND (START_POS_RIGHT_HAND - NUM_OF_WHITE_KEYS_IN_OCTAVE)

#define SAFETY_DISTANCE_BETWEEN_HANDS 3
/* --------------------------------------------- */


#endif