#ifndef HAND_H
#define HAND_H
#include <Arduino.h>
#include "Finger.h"
#include <AccelStepper.h>
#include "Piano-robot_setup_config.h"

class Hand{
  private:
    static const int nr_fingers = 5;
    Finger fingers[nr_fingers];
    int limit_switch_pin;
    float current_key_index;
  
  public:
    AccelStepper motor;

    Hand();
    Hand(int interface, int step, int dir);
    Hand(int interface, int step, int dir, int *solenoid_pins, int *servo_pins);
    void initializeFingers(int *solenoid_pins, int *servo_pins);
    void setLimitSwitch(int pin);
    void setMotorParams(int acc, int maxSpeed);
    void setKeyIndex(float index);

    Finger getFinger(int index);
    void getFingersInNormalPosition();
    void rotateFinger(int index, int newAngle);

    void moveToKey(float key_index);
    void waitToFinishPlay();

    bool isPlaying();
    int readLimitSwitch();

    void update();
    void demo();
};


#endif

