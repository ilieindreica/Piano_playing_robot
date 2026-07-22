#ifndef HAND_H
#define HAND_H
#include <Arduino.h>
#include "Finger.h"
#include <AccelStepper.h>
#include "Piano-robot_setup_config.h"

extern bool recalculatingWaiterNeeded;

class Hand{
  public:
    // A way to store more commands with less memory; float numbers (which for our purpose have decimal part .5 only) 
    // (note: angles in command are just an index determining how far away is the key to which to rotate, and in which direction)
    struct CommandStruct{
      float position;
      float angles[NUM_OF_FINGERS];
      uint8_t back_solenoids_states[NUM_OF_FINGERS];
      uint8_t front_solenoids_states[NUM_OF_FINGERS];
    } command;

    AccelStepper motor;
    unsigned long start = 0, stop = 0, ellapsed = 0;
    Hand* the_other_hand = nullptr;
    float previous_angles[NUM_OF_FINGERS];
    uint8_t previous_extensions[NUM_OF_FINGERS];
    
    // Constructors
    Hand();
    Hand(int interface, int step, int dir);
    Hand(int interface, int step, int dir, int *solenoid_pins, int *servo_pins);

    // Setters
    void setFingers(int *solenoid_pins, int *servo_pins);
    void setLimitSwitch(int pin);
    void setMotorParams(int acc, int maxSpeed);
    void setKeyIndex(float index);
    void setTimePerBeat(float tpb);
    void setTheOtherHand(Hand& other);
    void setRotationAngles(const int* matrix);

    // Getters
    Finger& getFinger(int finger_index);
    float getCompensation();
    const int* Hand::getRotationAngles();

    // Actions
    int rotateFingers();
    void rotateFinger(int finger_index, int newAngle);
    int rotateFingerToKey(int finger_index, float key_index);
    bool extendFingers();
    void moveToKey(float key_index);
    void move();
    void setTargetPosition();
    void resetCommand();
    void putFingersInNormalPosition();
    void releaseFingers();
    bool press();
    void stopAndReset();

    // Communication
    void requestCommand();
    bool allFingersOff();

    int readLimitSwitch();

  private:
    int limit_switch_pin;
    float current_key_index;
    float time_per_beat = 0;
    Finger fingers[NUM_OF_FINGERS];
    const int* rotationAngles;
};


#endif

