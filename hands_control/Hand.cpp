#include "pins_arduino.h"
#include "HardwareSerial.h"
#include "Arduino.h"
#include "Hand.h"
#include "SerialCommunication.h"

//
Hand::Hand() {
  
}

//
Hand::Hand(int interface, int step, int dir) : motor(interface, step, dir){
 
}

//
Hand::Hand(int interface, int step, int dir, int *solenoid_pins, int *servo_pins) : motor(interface, step, dir) {
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    previous_angles[i] = 0;
    previous_extensions[i] = 0;
    command.angles[i] = 0;
    command.back_solenoids_states[i] = 0;
  }
  setFingers(solenoid_pins, servo_pins);
}


// 
void Hand::setFingers(int *solenoid_pins, int *servo_pins) {
  for (int i = 0, j = 0; i < NUM_OF_FINGERS; i++, j+=2){
    fingers[i].setFinger(solenoid_pins[j], solenoid_pins[j+1], servo_pins[i]);

    // Assign neighbors
    Finger* left = (i > 0) ? &fingers[i - 1] : nullptr;
    Finger* right = (i < NUM_OF_FINGERS - 1) ? &fingers[i + 1] : nullptr;
    fingers[i].setNeighbors(left, right);
  }
}


// Set the pin for the limit switch
void Hand::setLimitSwitch(int pin){
  limit_switch_pin = pin;
  pinMode(limit_switch_pin, INPUT_PULLUP);
}


void Hand::setKeyIndex(float index){
  current_key_index = index;
}


// Set Acceleration and MaxSpeed for motor
void Hand::setMotorParams(int acc, int maxSpeed){
  motor.setAcceleration(acc);
  motor.setMaxSpeed(maxSpeed);
}


void Hand::setTimePerBeat(float tpb){
  time_per_beat = tpb;
}


void Hand::setRotationAngles(const int* matrix){
  rotationAngles = matrix;
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    fingers[i].setEquilibriumAngle(rotationAngles[i * ROT_COLS + (ROT_COLS / 2)]);
  }
}


// Returns the Finger object at "index" in the list of fingers
Finger& Hand::getFinger(int finger_index){
  return fingers[finger_index];
}


const int* Hand::getRotationAngles() {
  return rotationAngles;
}


// Rotates all fingers according to command. Returns the biggest delay needed for the maximum rotation angle.
int Hand::rotateFingers(){
  int maxDiff = 0;
  for(int i = 0; i < NUM_OF_FINGERS; i++){
    float newAngle = command.angles[i];
    if(newAngle != previous_angles[i]){
      int diff = rotateFingerToKey(i,newAngle);
      if(diff > maxDiff) maxDiff = diff;
    }
  }

  int delayMs = (int)((maxDiff / 60.0f) * 100.0f);  // 0.1s per 60°
  return delayMs;
}


// Rotates the finger at "index" in the list of fingers to newAngle
void Hand::rotateFinger(int finger_index, int newAngle){
  fingers[finger_index].rotate(newAngle);
}


// Rotates the finger at "index" to reach the key at "key_index" away from finger's equilibrium position
// Negative numbers -> rotation to the right; Positive numbers -> rotation to the left
// Returns the difference between new and old angles
int Hand::rotateFingerToKey(int finger_index, float key_index) {
  int col = (int)(-key_index * 2) + (ROT_COLS / 2);
  int target_angle = rotationAngles[finger_index * ROT_COLS + col];
  return fingers[finger_index].rotate(target_angle);
}


bool Hand::extendFingers(){
  bool needs_ext = false;

  for(int i = 0; i < NUM_OF_FINGERS; i++){
    uint8_t state = command.back_solenoids_states[i];
    
    if(state != previous_extensions[i]){
      fingers[i].extendOrRetract(state);
      needs_ext = true;
    }
  }

  return needs_ext;
}

// Activate fingers to press keys, according to command. Returns true if at least one pressing takes place.
bool Hand::press(){
  bool does_press = false;
  for(int i = 0; i < NUM_OF_FINGERS; i++){
    if (command.front_solenoids_states[i] == 1){
      does_press = true;
    }
    fingers[i].press_white_key(command.front_solenoids_states[i]);
  }

  return does_press;
}


// Resets finger rotation angle to EQUILIBRIUM_ANGLE
void Hand::putFingersInNormalPosition(){
  for (int i = 0; i < NUM_OF_FINGERS; i++){
    int eq_angle = fingers[i].getEquilibriumAngle();
    fingers[i].rotate(eq_angle);
  }
}


//
void Hand::moveToKey(float key_index){
  motor.enableOutputs();
  current_key_index = key_index;
  key_index = constrain(key_index, 0, NUM_OF_WHITE_KEYS);
  motor.moveTo(key_index * ONE_KEY_STEP);
  motor.runToPosition();
  motor.disableOutputs();
}


void Hand::move(){
  motor.run();
}


// Sets moveTo target for motor from command. Needs run() call separatelly to allow 
// both hands be called together
void Hand::setTargetPosition(){
  current_key_index = command.position;
  float key_index = constrain(command.position, 0, NUM_OF_WHITE_KEYS);
  motor.moveTo(key_index * ONE_KEY_STEP);
}


void Hand::releaseFingers(){
  for(int i = 0; i < NUM_OF_FINGERS; i++){
    if(command.front_solenoids_states[i] == 0){
      fingers[i].release();
    }
  }
}


// 
int Hand::readLimitSwitch(){
  return digitalRead(limit_switch_pin);
}


void Hand::resetCommand() {
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    command.angles[i] = 0;
    command.back_solenoids_states[i] = 0;
    command.front_solenoids_states[i] = 0;
  }
}


void Hand::requestCommand(){
  // Save the current command states into relevant previous_ variables
  for(int i = 0; i < NUM_OF_FINGERS; i++){
    previous_angles[i] = command.angles[i];
    previous_extensions[i] = command.back_solenoids_states[i];
  }
  // Read the commands for hand
  readCommandStruct(command);
}


bool Hand::allFingersOff(){

  for(int i = 0; i < NUM_OF_FINGERS; i++){
    if(command.front_solenoids_states[i] == 1){
      return false;
    }
  }

  return true;

}


// Stop pressing, reset angles, clear command
void Hand::stopAndReset(){
  resetCommand();
  releaseFingers();
  extendFingers();
  bool ok = rotateFingers();
}


