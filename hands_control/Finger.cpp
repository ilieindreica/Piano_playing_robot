#include "HardwareSerial.h"
#include "Arduino.h"
#include "Finger.h"


Finger::Finger(): angle(EQUILIBRIUM_ANGLE), leftNeighbor(nullptr), rightNeighbor(nullptr) {}

void Finger::initialize_finger(int front_solenoid_pin, int back_solenoid_pin, int servo_pin) {
  this->front_solenoid_pin = front_solenoid_pin;
  this->back_solenoid_pin = back_solenoid_pin;
  this->servo_pin = servo_pin;
  
  pinMode(this->front_solenoid_pin, OUTPUT);
  pinMode(this->back_solenoid_pin, OUTPUT);
  pinMode(this->servo_pin, OUTPUT);

  front_on = false;
  back_on = false;
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

void Finger::press_white_key(int duration){
  // Make sure method doesn't get called till it finished playing
  if (isPlaying == false){
    this->duration = duration;
    startTime = millis();
    digitalWrite(front_solenoid_pin, HIGH);
    front_on = true;
    isPlaying = true;
  }
}

void Finger::press_black_key(int duration){
  this->duration = duration;
  back_on = true;
  waitingStart = millis();
  waiting_on = true;
  digitalWrite(back_solenoid_pin, HIGH);
}

bool Finger::canRotate(int newAngle) {
  // Prevent overlap with neighbors
  if (leftNeighbor && newAngle >= leftNeighbor->angle + LIMIT_OVERLAP_ANGLE) return false;
  if (rightNeighbor && newAngle <= rightNeighbor->angle - LIMIT_OVERLAP_ANGLE) return false;
  return true;
}

void Finger::rotate(int newAngle) {
  newAngle = constrain(newAngle, EQUILIBRIUM_ANGLE - LIMIT_ANGLE_DEVIATION, EQUILIBRIUM_ANGLE + LIMIT_ANGLE_DEVIATION);
  if (canRotate(newAngle)) {
    angle = newAngle;
    servo.write(newAngle);
  }
}

void Finger::update() {
  if (front_on && (millis() - startTime >= duration)){
    digitalWrite(front_solenoid_pin, LOW);
    digitalWrite(back_solenoid_pin, LOW);
    front_on = false;
    isPlaying = false;
  }

  if (waiting_on && (millis() - waitingStart >= waiting_offset)){
    waiting_on = false;
    press_white_key(duration);
  }
}





