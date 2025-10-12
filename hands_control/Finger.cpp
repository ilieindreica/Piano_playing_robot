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

  front_on = false;
  waiting_on = false;
  isPlaying = false;

  startTime = 0;
  waitingStart = 0;
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

void Finger::increaseDuration(float increase){
  duration += increase;
}

void Finger::press_white_key(int duration, byte state=HIGH, unsigned long reference_time=millis()){
  // Make sure method doesn't get called till it finished playing
  if (isPlaying == false){
    this->duration = duration;
    startTime = millis();
    digitalWrite(front_solenoid_pin, state);
    front_on = true;
    isPlaying = true;
  }
}

void Finger::extend(){
  digitalWrite(back_solenoid_pin, HIGH);
}

/// !!! NEEDS REFACTORING TO SUIT FOR DIFFERENT EQUILIBRIUM ANGLES OF FINGER !!!
bool Finger::canRotate(int newAngle) {
  // Prevent overlap with neighbors
  if (leftNeighbor && newAngle >= leftNeighbor->angle + LIMIT_OVERLAP_ANGLE) return false;
  if (rightNeighbor && newAngle <= rightNeighbor->angle - LIMIT_OVERLAP_ANGLE) return false;
  return true;
}

///Rotates finger to specified angle. Checks its neighbors to see if it can rotate, unless bypass_constraint=True
void Finger::rotate(int newAngle, bool bypass_constraint=false) {
  newAngle = constrain(newAngle, equilibrium_angle - LIMIT_ANGLE_DEVIATION, equilibrium_angle + LIMIT_ANGLE_DEVIATION);
  if (canRotate(newAngle) || bypass_constraint) {
    angle = newAngle;
    servo.write(newAngle);
  }
}

void Finger::update() {
  // Serial.print("start time: "); Serial.print(startTime); Serial.print("   duration: "); Serial.println(duration);

  // Check if the duration of note completed
  if (front_on && (millis() - startTime >= duration)){
    isPlaying = false;
  }

  if (waiting_on && (millis() - waitingStart >= waiting_offset)){
    waiting_on = false;
    press_white_key(duration);
  }
}


void Finger::stopPressing(){
  digitalWrite(front_solenoid_pin, LOW);
  digitalWrite(back_solenoid_pin, LOW);
  front_on = false;
}





