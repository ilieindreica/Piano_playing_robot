#ifndef FINGER_H
#define FINGER_H
#include <Arduino.h>
#include <Servo.h>

#define EQUILIBRIUM_ANGLE 80  // Chosen such that it was easier to allign all servos correctly
#define LIMIT_ANGLE_DEVIATION 15
#define LIMIT_OVERLAP_ANGLE 5

class Finger{
  private:
    int front_solenoid_pin;
    int back_solenoid_pin;
    int servo_pin;
    int angle;
    unsigned long startTime, waitingStart;
    bool front_on, back_on, waiting_on;
    int duration;
    int waiting_offset;   // front_solenoid needs an offset from back_solenoid in activation, otherwise it could jam in the keys
    Servo servo;
    Finger* leftNeighbor = nullptr;
    Finger* rightNeighbor = nullptr;
  
  public:
    bool isPlaying;
    Finger();
    void initialize_finger(int front_solenoid_pin, int back_solenoid_pin, int servo_pin);
    void setNeighbors(Finger* left, Finger* right);
    void setWaitingOffset(int value);
    void press_white_key(int duration);
    void press_black_key(int duration);
    bool canRotate(int newAngle);
    void rotate(int newAngle);
    void update();
};


#endif

