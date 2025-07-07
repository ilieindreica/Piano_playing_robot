#ifndef HAND_H
#define HAND_H
#include <Arduino.h>
#include "Finger.h"
#include <AccelStepper.h>
#include "Piano-robot_setup_config.h"

class Hand{
  public:
    // A way to store more commands with less memory; float numbers (which for our purpose have decimal part .5 only) 
    // "encoded" into ints such that their information can be retrieved 
    // (note: angles in command are just an index determining how far away is the key to which to rotate, and in which direction)
    struct CommandStruct{
      uint8_t position;
      int8_t angles[NUM_OF_FINGERS];
      uint8_t back_solenoids_states[NUM_OF_FINGERS];
      uint8_t front_solenoids_states[NUM_OF_FINGERS];
      uint8_t durations[NUM_OF_FINGERS];
    };

    // A way to store the decoded commands for easier access and to prevent forgetting decoding
    struct DecodedCommand{
      float position;
      float angles[NUM_OF_FINGERS];
      uint8_t back_solenoids_states[NUM_OF_FINGERS];
      uint8_t front_solenoids_states[NUM_OF_FINGERS];
      float durations[NUM_OF_FINGERS];
    } decoded_command;

    enum class State {
      IDLE,
      WAITING,
      CHANGING_POSTURE,
      READY_TO_PLAY,
      PRESSING,
      PLAYING,
      FINISHED
    };

    AccelStepper motor;
    int command_list_length = 0;
    CommandStruct* commands = nullptr;
    int command_index = 0;
    unsigned long start = 0, stop = 0, ellapsed = 0;
    Hand* the_other_hand = nullptr;
    
    // Constructors
    Hand();
    Hand(int interface, int step, int dir);
    Hand(int interface, int step, int dir, int *solenoid_pins, int *servo_pins);

    // Setters
    void setFingers(int *solenoid_pins, int *servo_pins);
    void setEquilibriumAngles(int *angles);
    void setLimitSwitch(int pin);
    void setMotorParams(int acc, int maxSpeed);
    void setKeyIndex(float index);
    void setState(State newState);
    void setCommand();
    void setTimePerBeat(float tpb);
    void setHandedness(char h);
    void setTheOtherHand(Hand& other);

    // Getters
    State getState() const;
    Finger& getFinger(int finger_index);
    void getFingersInNormalPosition();
    float getCompensation();
    char getHandedness();

    // Actions
    void rotateFinger(int finger_index, int newAngle);
    void rotateFingerToKey(int finger_index, float key_index);
    void moveToKey(float key_index);
    DecodedCommand decodeCommand(CommandStruct cmd);
    void resetDecodedCommand();
    void increaseCommandIndex();
    void increaseFingerDuration(float);
    void resetCompensation();
    
    bool isPlaying();
    int readLimitSwitch();

    void update(unsigned long reference_time=millis());
    void demo();
    const char* Hand::stateToStr(State s);

  private:
    Finger fingers[NUM_OF_FINGERS];
    int limit_switch_pin;
    float current_key_index;
    State current_state = State::IDLE;
    unsigned long waiting_start;
    float waiting_time;
    State state_after_waiting;
    float compensation = 0;
    float time_per_beat = 0;
    char handedness_character;
    int previous_angles[NUM_OF_FINGERS];
  
};


#endif

