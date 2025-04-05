#ifndef HAND_H
#define HAND_H
#include <Arduino.h>
#include "Finger.h"
#include <AccelStepper.h>
#include "Piano-robot_setup_config.h"

class Hand{
  public:
    AccelStepper motor;

    enum class State {
      IDLE,
      CHANGING_POSTURE,
      READY_TO_PLAY,
      PLAYING
    };

    Hand();
    Hand(int interface, int step, int dir);
    Hand(int interface, int step, int dir, int *solenoid_pins, int *servo_pins);
    void initializeFingers(int *solenoid_pins, int *servo_pins);
    void setLimitSwitch(int pin);
    void setMotorParams(int acc, int maxSpeed);
    void setKeyIndex(float index);

    Finger& getFinger(int finger_index);
    void getFingersInNormalPosition();
    void rotateFinger(int finger_index, int newAngle);
    void rotateFingerToKey(int finger_index, float key_index);

    void moveToKey(float key_index);
    void waitToFinishPlay();

    bool isPlaying();
    int readLimitSwitch();

    void update();
    void demo();

  private:
    Finger fingers[NUM_OF_FINGERS];
    int limit_switch_pin;
    float current_key_index;
    State current_state = State::IDLE;
  
};


#endif

