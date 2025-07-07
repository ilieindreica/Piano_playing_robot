#ifndef FINGER_H
#define FINGER_H
#include <Arduino.h>
#include <Servo.h>

class Finger{
  private:
    int equilibrium_angle = 80;
    int front_solenoid_pin;
    int back_solenoid_pin;
    int servo_pin;
    int angle;
    unsigned long startTime, waitingStart;
    bool front_on, waiting_on;
    float duration;
    int waiting_offset;   // front_solenoid needs an offset from back_solenoid in activation, otherwise it could jam in the keys
    Servo servo;
    Finger* leftNeighbor = nullptr;
    Finger* rightNeighbor = nullptr;
  
  public:
    bool isPlaying;
    Finger();
    void setFinger(int front_solenoid_pin, int back_solenoid_pin, int servo_pin);
    void setNeighbors(Finger* left, Finger* right);
    void setWaitingOffset(int value);
    void setEquilibriumAngle(int angle);
    int getEquilibriumAngle();
    void press_white_key(int duration, byte state=HIGH, unsigned long reference_time=millis());
    void extend();
    bool canRotate(int newAngle);
    void rotate(int newAngle, bool bypass_constraint=false);
    void increaseDuration(float increase);
    void update();
};


#endif

