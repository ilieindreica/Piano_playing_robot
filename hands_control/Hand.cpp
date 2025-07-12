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
  command_index = 0;
  commands = nullptr;
  command_list_length = 0;
  compensation = 0;
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    previous_angles[i] = 0;
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


void Hand::setState(State newState){
  current_state = newState;
}


void Hand::setTimePerBeat(float tpb){
  time_per_beat = tpb;
}


void Hand::setEquilibriumAngles(int *angles){
  for (int i = 0; i < NUM_OF_FINGERS; i++){
    fingers[i].setEquilibriumAngle(angles[i]);
  }
}


void Hand::setHandedness(char h){
  handedness_character = h;
}


void Hand::setTheOtherHand(Hand &other){
  the_other_hand = &other;
}


Hand::State Hand::getState() const{
  return current_state;
}


// Returns the Finger object at "index" in the list of fingers
Finger& Hand::getFinger(int finger_index){
  return fingers[finger_index];
}


char Hand::getHandedness(){
  return handedness_character;
}


// Rotates the finger at "index" in the list of fingers to newAngle
void Hand::rotateFinger(int finger_index, int newAngle){
  fingers[finger_index].rotate(newAngle);
}

// Rotates the finger at "index" to reach the key at "key_index" away from finger's equilibrium position
// Negative numbers -> rotation to the right; Positive numbers -> rotation to the left
void Hand::rotateFingerToKey(int finger_index, float key_index){
  // float becausehere may be half rotations, to rotate to black_keys
  int eq_angle = fingers[finger_index].getEquilibriumAngle();
  float angle = eq_angle + key_index * ONE_KEY_ROTATION;
  // if(angle != eq_angle){
  //   Serial.print(command_index); Serial.print("-> ");
  //   Serial.println(angle);
  // }
  fingers[finger_index].rotate(angle, true);
}

// Resets finger rotation angle to EQUILIBRIUM_ANGLE
void Hand::getFingersInNormalPosition(){
  for (int i = 0; i < NUM_OF_FINGERS; i++){
    int eq_angle = fingers[i].getEquilibriumAngle();
    fingers[i].rotate(eq_angle, true);
  }
}

//
void Hand::moveToKey(float key_index){
  current_key_index = key_index;
  key_index = constrain(key_index, 0, NUM_OF_WHITE_KEYS);
  motor.moveTo(key_index * ONE_KEY_STEP);
  motor.runToPosition();
}

// Returns true if any finger is playing a note, false otherwise
bool Hand::isPlaying(){
  for (int i = 0; i < NUM_OF_FINGERS; i++){
    if(fingers[i].isPlaying) return true;
  }
  return false;
}

// 
int Hand::readLimitSwitch(){
  return digitalRead(limit_switch_pin);
}


///Perform necessary operations to decode commands
Hand::DecodedCommand Hand::decodeCommand(Hand::CommandStruct cmd){
  DecodedCommand output;

  output.position = cmd.position / 2.0f;
  for(int i = 0; i < NUM_OF_FINGERS; i++){
    output.angles[i] = cmd.angles[i] / 2.0f;
    output.durations[i] = cmd.durations[i];
    output.back_solenoids_states[i] = cmd.back_solenoids_states[i];
    output.front_solenoids_states[i] = cmd.front_solenoids_states[i];
  }

  return output;
}


void Hand::resetDecodedCommand() {
  decoded_command.position = 0;
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    decoded_command.angles[i] = 0;
    decoded_command.back_solenoids_states[i] = 0;
    decoded_command.front_solenoids_states[i] = 0;
    decoded_command.durations[i] = 0;
  }
}


void Hand::increaseCommandIndex(){
  command_index++;
}


void Hand::increaseFingerDuration(float increase){
  for (int i = 0; i < NUM_OF_FINGERS; i++){
    fingers[i].increaseDuration(increase);
  }
}


float Hand::getCompensation(){
  return compensation;
}


void Hand::resetCompensation(){
  compensation = 0;
}

// Update function; needs to be called in a loop; Updates the hand state and ensures correct duration of notes without blocking
void Hand::update(unsigned long reference_time=millis()) {
  // Serial.print("STATE: "); Serial.print(static_cast<int>(current_state)); Serial.println(stateToStr(current_state));

  // STATE MACHINE
  switch(current_state){
    // IDLE
    case State::IDLE:{
      start = millis();
      if (command_index < command_list_length){
        decoded_command = decodeCommand(commands[command_index]);
        current_state = State::CHANGING_POSTURE;
      }
      else{
        current_state = State::FINISHED;
      }
      break;
    }

    // CHANGING POSTURE
    case State::CHANGING_POSTURE:{
      /// add rotation
      unsigned long compensation_start = millis();
      bool needs_waiting = false;
      for (int i = 0; i < NUM_OF_FINGERS; i++){
        int angle = decoded_command.angles[i];

        if (angle != previous_angles[i]){
          rotateFingerToKey(i, angle);
          needs_waiting = true;
          previous_angles[i] = angle;
        }
       

        /// extension
        // if(decoded_command.back_solenoids_states[i] == 1){
        //   fingers[i].extend();
        //   needs_waiting = true;
        // }
      }

      waiting_start = millis();
      if(needs_waiting){
        // Wait only if fingers need to rotate
        waiting_time = 70;
        // delay(70);
      }
      else{
        waiting_time = 0;
      }

      moveToKey(decoded_command.position);

      unsigned long compensation_end = millis();
      compensation += compensation_end - compensation_start + waiting_time;

      current_state = State::WAITING;
      state_after_waiting = State::READY_TO_PLAY;
      // current_state = State::READY_TO_PLAY;
      break;
    }

    // READY TO PLAY
    case State::READY_TO_PLAY:{
      State other_state = the_other_hand->getState();
      if (other_state == State::READY_TO_PLAY || other_state == State::PLAYING || other_state == State::FINISHED ||
          other_state == State::PRESSING) {
        current_state = State::PRESSING;
        resetCompensation();
      }
      break;
    }

    // PRESSING
    case State::PRESSING:{
      // Serial.print(command_index); Serial.print(" "); Serial.print(handedness_character); Serial.println(millis());
      // if (handedness_character == 'l'){
      //   Serial.println();
      // }

      for (int i = 0; i < NUM_OF_FINGERS; i++){
        fingers[i].press_white_key(decoded_command.durations[i], decoded_command.front_solenoids_states[i]);
      }
      current_state = State::PLAYING;
      command_index++;
      break;
    }

    // PLAYING
    case State::PLAYING:{
      // Before exiting PLAYING state, check if there exist some compensations that need to be taken care of (i.e. the state must be prolonged)
      if(the_other_hand->getState() == State::READY_TO_PLAY){
        increaseFingerDuration(the_other_hand->getCompensation());
        the_other_hand->resetCompensation();
      }
      else if (!isPlaying()){
        waiting_start = reference_time;
        waiting_time = TIME_FOR_SOLENOID_RETRACTION;
        compensation += TIME_FOR_SOLENOID_RETRACTION;
        state_after_waiting = State::IDLE;
        current_state = State::WAITING;
      }
      break;
    }
    
    // WAITING
    case State::WAITING:{
      if (millis() - waiting_start >= waiting_time){
        current_state = state_after_waiting;
      }
      break;
    }

  }
  
  // Update fingers
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    fingers[i].update();
  }
}


const char* Hand::stateToStr(State s) {
  switch (s) {
    case State::IDLE: return "IDLE";
    case State::WAITING: return "WAITING";
    case State::CHANGING_POSTURE: return "CHANGING_POSTURE";
    case State::READY_TO_PLAY: return "READY_TO_PLAY";
    case State::PRESSING: return "PRESSING";
    case State::PLAYING: return "PLAYING";
    case State::FINISHED: return "FINISHED";
    default: return "UNKNOWN";
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
      fingers[currentFinger].extend();
      delay(20);
    }
    else{
      fingers[currentFinger].press_white_key(interval); 
    }
    
    currentFinger++;
    
    if (currentFinger >= NUM_OF_FINGERS) {
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