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
    // "encoded" into ints such that their information can be retrieved 
    // (note: angles in command are just an index determining how far away is the key to which to rotate, and in which direction)
    struct CommandStruct{
      float position;
      float angles[NUM_OF_FINGERS];
      uint8_t back_solenoids_states[NUM_OF_FINGERS];
      uint8_t front_solenoids_states[NUM_OF_FINGERS];
      float durations[NUM_OF_FINGERS];
      int note_rank = 0;
    } command;

    enum class State {
      IDLE,
      WAITING,
      CHANGING_POSTURE,
      READY_TO_PLAY,
      PRESSING,
      PLAYING,
      WAIT_FOR_SOLENOID_RETRACTION,
      FINISHED
    };

    AccelStepper motor;
    unsigned long start = 0, stop = 0, ellapsed = 0;
    Hand* the_other_hand = nullptr;
    int command_index = 0;
    int command_list_length = 0;
    bool isTheWaiter = false;
    bool isSolo = false;
    
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
      // void setCommand();
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
    void resetCommand();
    void increaseFingerDuration(float);
    void resetCompensation();
    void stopPressing();

    // Communication
    void requestCommand();
    
    bool isPlaying();
    bool isCompensationRequested();
    int readLimitSwitch();
    bool isWaiting();
    void giveCompensation(float comp);

    void update(unsigned long reference_time=millis());
    void demo();
    const char* Hand::stateToStr(State s);

  private:
    Finger fingers[NUM_OF_FINGERS];
    int limit_switch_pin;
    float current_key_index;
    State current_state = State::IDLE;
    unsigned long waiting_start = 0;
    float waiting_time = 0;
    State state_after_waiting;
    float compensation = 0;
    float time_per_beat = 0;
    char handedness_character;
    int previous_angles[NUM_OF_FINGERS];  
};


#endif

