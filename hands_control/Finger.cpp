#include "HardwareSerial.h"
#include "Arduino.h"
#include "Finger.h"
#include "Piano-robot_setup_config.h"


Finger::Finger(): angle(equilibrium_angle), leftNeighbor(nullptr), rightNeighbor(nullptr) {}

void Finger::setFinger(int front_solenoid_pin, int back_solenoid_pin, int servo_pin) {
  this->front_solenoid_pin = front_solenoid_pin;
  this->back_solenoid_pin = back_solenoid_pin;
  this->servo_pin = servo_pin;
  
  pinMode(this->front_solenoid_pin, OUTPUT);
  pinMode(this->back_solenoid_pin, OUTPUT);
  pinMode(this->servo_pin, OUTPUT);

  isPlaying = false;
  waiting_offset = 150;

  servo.attach(servo_pin);
}

void Finger::setNeighbors(Finger *left, Finger *right){
  leftNeighbor = left;
  rightNeighbor = right;
}

void Finger::setWaitingOffset(int value) {
  waiting_offset = value;
}

void Finger::setEquilibriumAngle(int angle){
  equilibrium_angle = angle;
}

int Finger::getEquilibriumAngle(){
  return equilibrium_angle;
}

int Finger::getCurrentAngle(){
  return angle;
}


void Finger::press_white_key(byte state=HIGH){
  // Make sure method doesn't get called till it finished playing
  digitalWrite(front_solenoid_pin, state);
}


///Rotates finger to specified angle. Returns the difference between new and old angles
int Finger::rotate(int newAngle) {
  int diff = abs(newAngle - angle);
  angle = newAngle;
  servo.write(newAngle);

  return diff;
}


void Finger::release(){
  digitalWrite(front_solenoid_pin, LOW);
}

/// Retracts if state==0 and extend if state==1
void Finger::extendOrRetract(bool state){
  digitalWrite(back_solenoid_pin, state);
}


bool Finger::doesAngleNeedExtension(){
  bool ok = false;
  if(angle > ANGLE_THRESHOLD_TO_EXTEND){
    ok = true;
  }
  
  return ok;
}





