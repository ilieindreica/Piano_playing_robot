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
    int waiting_offset;   // front_solenoid needs an offset from back_solenoid in activation, otherwise it could jam in the keys
    Servo servo;
    Finger* leftNeighbor = nullptr;
    Finger* rightNeighbor = nullptr;
  
  public:
    bool isPlaying;
    Finger();
    // Setters
    void setFinger(int front_solenoid_pin, int back_solenoid_pin, int servo_pin);
    void setNeighbors(Finger* left, Finger* right);
    void setWaitingOffset(int value);
    void setEquilibriumAngle(int angle);
    
    // Getters
    int getEquilibriumAngle();
    int getCurrentAngle();
    
    // Actions
    void press_white_key(byte state);
    int rotate(int newAngle);
    void release();
    void extendOrRetract(bool state);

    bool doesAngleNeedExtension();
};


#endif

