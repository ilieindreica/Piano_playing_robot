#include "HardwareSerial.h"
#include "Arduino.h"
#include "Hand.h"

//
Hand::Hand() {
  
}

//
Hand::Hand(int interface, int step, int dir) : motor(interface, step, dir){
 
}

//
Hand::Hand(int interface, int step, int dir, int *solenoid_pins, int *servo_pins) : motor(interface, step, dir) {
  initializeFingers(solenoid_pins, servo_pins);
}

// 
void Hand::initializeFingers(int *solenoid_pins, int *servo_pins) {
  for (int i = 0, j = 0; i < nr_fingers; i++, j+=2){
    fingers[i].initialize_finger(solenoid_pins[j], solenoid_pins[j+1], servo_pins[i]);

    // Assign neighbors
    Finger* left = (i > 0) ? &fingers[i - 1] : nullptr;
    Finger* right = (i < nr_fingers - 1) ? &fingers[i + 1] : nullptr;
    fingers[i].setNeighbors(left, right);
    
    getFingersInNormalPosition();
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

// Returns the Finger object at "index" in the list of fingers
Finger Hand::getFinger(int index){
  return fingers[index];
}

// Rotates the finger at "index" in the list of fingers to newAngle
void Hand::rotateFinger(int index, int newAngle){
  fingers[index].rotate(newAngle);
}

// Resets finger rotation angle to EQUILIBRIUM_ANGLE
void Hand::getFingersInNormalPosition(){
  for (int i = 0; i < nr_fingers; i++){
    fingers[i].rotate(EQUILIBRIUM_ANGLE);
  }
}

//
void Hand::moveToKey(float key_index){
  waitToFinishPlay();
  current_key_index = key_index;
  key_index = constrain(key_index, 0, NUM_OF_WHITE_KEYS);
  motor.moveTo(key_index * ONE_KEY_STEP);
  motor.runToPosition();
}

// Returns true if any finger is playing a note, false otherwise
bool Hand::isPlaying(){
  for (int i = 0; i < nr_fingers; i++){
    if(fingers[i].isPlaying) return true;
  }
  return false;
}

// 
int Hand::readLimitSwitch(){
  return digitalRead(limit_switch_pin);
}

// Update function; needs to be called in a loop; Ensures correct duration of notes without blocking
void Hand::update() {
  for (int i = 0; i < nr_fingers; i++) {
    fingers[i].update();
  }
}

// Used primarily before moving the hand, to prevent collision of fingers with the keys if they are still active
void Hand::waitToFinishPlay(){
  while(isPlaying()){
    update();
  }
}


unsigned long previousMillis = 0;  
const long interval = 200;         
int currentFinger = 0; 
bool pressBlack = false;            
float aux = 0.5;

void Hand::demo() {
  unsigned long currentMillis = millis();
  
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    
    if (!pressBlack){
      fingers[currentFinger].press_black_key(interval);
    }
    else{
      fingers[currentFinger].press_white_key(interval); 
    }
    
    currentFinger++;
    
    if (currentFinger >= nr_fingers) {
      moveToKey(current_key_index+aux);
      currentFinger = 0;
      pressBlack = !pressBlack;
      aux = -aux;
    }
  }
}


// void Hand::demo() {
  //   // int time_ct = 300;
  //   // for (int i = 0; i < nr_fingers; i++){
  //   //   if (millis() % ((i+1) * time_ct * 2) < 50) {
  //   //     fingers[i].press_white_key((i+1)*time_ct);
  //   //   }
  //   // }

  //    unsigned long currentMillis = millis();
  //   int baseInterval = 200;  // Base interval between key presses
  //   int delayTime;
    
  //   for (int i = 0; i < nr_fingers; i++) {
  //     delayTime = baseInterval * i + (currentMillis % 500); 
      
  //     if (delayTime < 0) delayTime = 0;

  //     if (currentMillis >= delayTime) {
  //       fingers[i].press_white_key(200);  
  //     }
  //   }
  // }