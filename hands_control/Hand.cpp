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
  command_index = 0;
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


// bool Hand::isCompensationRequested(){
//   for (int i = 0; i < NUM_OF_FINGERS; i++){
//     if(fingers[i].requestCompensation) return true;
//   }
//   return false;
// }


// 
int Hand::readLimitSwitch(){
  return digitalRead(limit_switch_pin);
}


void Hand::resetCommand() {
  command.position = 0;
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    command.angles[i] = 0;
    command.back_solenoids_states[i] = 0;
    command.front_solenoids_states[i] = 0;
    command.durations[i] = 0;
  }
  command.note_rank = 0;
}


// void Hand::increaseFingerDuration(float increase){
//   for (int i = 0; i < NUM_OF_FINGERS; i++){
//     // if(fingers[i].requestCompensation){
//       fingers[i].increaseDuration(increase);
//     //   fingers[i].requestCompensation = false;
//     //   fingers[i].stopPressing = true;
//     // }
//   }
// }


void Hand::stopPressing(){
  for(int i = 0; i < NUM_OF_FINGERS; i++){
    fingers[i].stopPressing();
  }
}


float Hand::getCompensation(){
  return compensation;
}


void Hand::resetCompensation(){
  compensation = 0;
}

bool recalculatingWaiterNeeded = false;
// Update function; needs to be called in a loop; Updates the hand state and ensures correct duration of notes without blocking
void Hand::update(unsigned long reference_time=millis()) {
  // Serial.print("STATE: "); Serial.print(static_cast<int>(current_state)); Serial.println(stateToStr(current_state));
  
  // Update fingers
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    fingers[i].update();
  }
  
  // STATE MACHINE
  switch(current_state){
    // IDLE
    case State::IDLE:{
        if (command_index < command_list_length){
          requestCommand();
          command_index++;
          current_state = State::CHANGING_POSTURE;
        }
        else{
          resetCommand();
          current_state = State::FINISHED;
        }
      break;
    }

    // CHANGING POSTURE
    case State::CHANGING_POSTURE:{
      /// add rotation
      start = millis();
      bool needs_waiting = false;
      for (int i = 0; i < NUM_OF_FINGERS; i++){
        int angle = command.angles[i];
        if (angle != previous_angles[i]){
          rotateFingerToKey(i, angle);
          needs_waiting = true;
          previous_angles[i] = angle;
        }
       
        // extension
        // if(command.back_solenoids_states[i] == 1){
        //   fingers[i].extend();
        //   needs_waiting = true;
        // }
      }

      waiting_start = millis();

      moveToKey(command.position);
      stop = millis();  

      // Wait only if fingers need to rotate
      if(needs_waiting){
        // Serial.print(handedness_character); Serial.println(" needs waiting ");
        /// put it in int cause otherwise, because the other variables are unsigned, it will be interpreted as unsigned as well
        int aux = 70 - (stop - waiting_start); 

        // Because moveToKey() is blocking, some waiting time needed for servo rotation already passed. So we have to wait only
        // the difference time. But if more than enough time passed, no need for any more waiting (so waiting_time = 0 to not be negative)
        waiting_time = max(0, aux); 
      }
      else{
        waiting_time = 0;
      }

      current_state = State::WAITING;
      state_after_waiting = State::READY_TO_PLAY;
      // current_state = State::READY_TO_PLAY;
      break;
    }

    // READY TO PLAY
    case State::READY_TO_PLAY:{
        State other_state = the_other_hand->getState();
        // Serial.print(handedness_character); Serial.print(" "); Serial.print(command_index);
        // Serial.print(stateToStr(current_state)); Serial.print("   "); Serial.print(stateToStr(other_state)); Serial.print("  ");
        // Serial.println(command.note_rank);
        if (other_state == State::READY_TO_PLAY || other_state == State::PLAYING || other_state == State::FINISHED ||
            other_state == State::PRESSING) {
          current_state = State::PRESSING;
        }

        if(recalculatingWaiterNeeded){
          // Serial.print(handedness_character);Serial.print(command.note_rank); Serial.print(" "); 
          // Serial.print(isTheWaiter); Serial.print(" ");Serial.println(the_other_hand->command.note_rank);
          if(command.note_rank > the_other_hand->command.note_rank){
            isTheWaiter = true;
            the_other_hand->isTheWaiter = false;
          }
          else{
            the_other_hand->isTheWaiter = true;
            isTheWaiter = false;
          }

          recalculatingWaiterNeeded = false;
        }
      break;
    }

    // PRESSING
    case State::PRESSING:{
      for (int i = 0; i < NUM_OF_FINGERS; i++){
        fingers[i].press_white_key(command.durations[i], command.front_solenoids_states[i]);
      }
      current_state = State::PLAYING;
      break;
    }

    // PLAYING
    case State::PLAYING:{
      if (!isPlaying()){
        
        if(!isSolo){
          if(the_other_hand->command.note_rank >= command.note_rank && !isTheWaiter){
            Serial.print(command_index);Serial.print(handedness_character);Serial.print(command.note_rank); Serial.print(" "); 
            Serial.print(isTheWaiter); Serial.print(" ");Serial.println(the_other_hand->command.note_rank);
            the_other_hand->command.note_rank -= command.note_rank;
            command.note_rank = 0;
         }
        }
        else{
          command.note_rank = 0;
        }
       
        if(command.note_rank <= 0){
          waiting_start = reference_time;
          stopPressing();
          current_state = State::WAIT_FOR_SOLENOID_RETRACTION; 
        }
      }
      break;
    }
    
    // WAITING
    case State::WAITING:{
      if (millis() - waiting_start >= waiting_time){
        current_state = state_after_waiting;
        waiting_start = 0;
        waiting_time = 0;
      }
      break;
    }

    case State::WAIT_FOR_SOLENOID_RETRACTION:{
      if(millis() - waiting_start >= TIME_FOR_SOLENOID_RETRACTION){
        current_state = State::IDLE;
        waiting_start = 0;
      }
      break;
    }
  }

}


bool Hand::isWaiting(){
  if (millis() - waiting_start >= waiting_time){
    waiting_time = 0;
    return false;
  }
  return true;
}


void Hand::giveCompensation(float comp){
  Serial.println(stateToStr(the_other_hand->getState()));
  if(the_other_hand->getState() == State::PLAYING || the_other_hand->getState() == State::IDLE){
    the_other_hand->increaseFingerDuration(comp);
  }
}


void Hand::requestCommand(){
  // Tell which hand is requesting
  Serial.println(handedness_character);
  // Read the commands for hand
  readCommandStruct(command);
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
    case State::WAIT_FOR_SOLENOID_RETRACTION: return "WAIT_FOR_SOLENOID_RETRACTION";
    default: return "UNKNOWN";
  }
}

