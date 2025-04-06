#include <Servo.h>
#include <AccelStepper.h>
#include "Hand.h"
#include "Piano-robot_setup_config.h"

using State = Hand::State;

/* ======= DEFINE STATEMENTS ======= */
  #define dir_right 4
  #define step_right 5
  #define dir_left 2
  #define step_left 3
  #define right_button_pin 7
  #define left_button_pin 8
  #define motorInterfaceType 1  // for drivers that use only dir and step
/* ================================================================= */

/* Class objects */
  Hand right_hand(motorInterfaceType, step_right, dir_right);
  Hand left_hand(motorInterfaceType, step_left, dir_left);
/***************************/

/* Structs */

/* ********************** */

/* Pin lists */
  int right_solenoid_pins[] = {44, 45, 46, 47, 48, 49, 50, 51, 52, 53};
  int right_servo_pins[] = {39, 40, 41, 42, 43};
  int left_solenoid_pins[] = {29, 30, 31, 32, 33, 34, 35, 36, 37, 38};
  int left_servo_pins[] = {24, 25, 26, 27, 28};
/* ***************** */

/* Global variables */

/* **************** */

/* Declarations for functions */
  void homing(int speed=500);
  void readCommands(Hand &hand);
  void moveToKey(AccelStepper &motor, int key_index);
  void move_hands(int pos_left, int pos_right);
/* ************************ */

void setup() {
  Serial.begin(115200);
  Serial.println("Arduino Ready!");

  // READ DATA from Serial
  readCommands(left_hand);
  readCommands(right_hand);

  // Initialize hands
  float maxSpeed = 4000.0, acc = 10000.0;
  right_hand.setFingers(right_solenoid_pins, right_servo_pins);
  right_hand.setLimitSwitch(right_button_pin);
  right_hand.setMotorParams(acc, maxSpeed);

  left_hand.setFingers(left_solenoid_pins, left_servo_pins);
  left_hand.setLimitSwitch(left_button_pin);
  left_hand.setMotorParams(acc, maxSpeed);
  
  homing();

}


void loop() {

  State leftState  = left_hand.getState();
  State rightState = right_hand.getState();

  if (rightState == State::READY_TO_PLAY &&
      (leftState == State::READY_TO_PLAY || leftState == State::PLAYING)) {
      right_hand.setState(State::PRESSING);
  }

  if (leftState == State::READY_TO_PLAY &&
      (rightState == State::READY_TO_PLAY || rightState == State::PLAYING)) {
      left_hand.setState(State::PRESSING);
  }

  right_hand.update();
  left_hand.update();
}


void homing(int speed=500){

  //
  right_hand.motor.moveTo(100000);
  right_hand.motor.setSpeed(speed);
  left_hand.motor.moveTo(-100000);
  left_hand.motor.setSpeed(speed);
  
  int right_button_value = right_hand.readLimitSwitch();
  int left_button_value = left_hand.readLimitSwitch();

  while(right_button_value != LOW || left_button_value != LOW){
    if(right_button_value != LOW){
      right_hand.motor.runSpeedToPosition();
      right_button_value = right_hand.readLimitSwitch();
    }
    if(left_button_value){    
      left_hand.motor.runSpeedToPosition();
      left_button_value = left_hand.readLimitSwitch();
    }
  }
 
  right_hand.motor.setCurrentPosition(MAX_STEPPER_TRAVEL_DISTANCE);
  right_hand.setKeyIndex(NUM_OF_WHITE_KEYS);

  left_hand.motor.setCurrentPosition(MIN_STEPPER_TRAVEL_DISTANCE);
  left_hand.setKeyIndex(0);
  // delay(500);

}


void readCommands(Hand &hand){
  byte one_byte = 8;
  const int timeoutIterations = 1000;  // 1000 iterations * 1ms delay = approx. 1 second
  int counter = 0;

  // Wait for position byte
  while (Serial.available() < one_byte && counter < timeoutIterations) {
    delay(1);  
    counter++;
  }

  // Exit if no data is available
  if (counter > timeoutIterations){
    return;  // It may happen that left_hand has no commands (for songs played with only one hand); return if waiting is too long
  }
  
  // Read the length of hand commands
  for (int i = 0; i < 4; i++) {
    hand.command_list_length = (hand.command_list_length << one_byte) | Serial.read();  
  }

  hand.commands = new Hand::CommandStruct[hand.command_list_length];

  // Read the commands for hand
  for (int i = 0; i < hand.command_list_length; i++){
    readCommandStruct(hand.commands[i]);
  }
}


void readCommandStruct(Hand::CommandStruct &command) {
    // Wait for position byte
    while (Serial.available() < 1);
    command.position = Serial.read();

    // Wait for NUM_OF_FINGERS bytes
    while (Serial.available() < NUM_OF_FINGERS);
    for (int i = 0; i < NUM_OF_FINGERS; i++) {
        command.angles[i] = Serial.read();
    }

    while (Serial.available() < NUM_OF_FINGERS);
    for (int i = 0; i < NUM_OF_FINGERS; i++) {
        command.back_solenoids_states[i] = Serial.read();
    }

    while (Serial.available() < NUM_OF_FINGERS);
    for (int i = 0; i < NUM_OF_FINGERS; i++) {
        command.front_solenoids_states[i] = Serial.read();
    }

    while (Serial.available() < NUM_OF_FINGERS);
    for (int i = 0; i < NUM_OF_FINGERS; i++) {
        command.durations[i] = Serial.read();
    }
}


void printCommandStruct(const Hand::CommandStruct &cmd) {
    Serial.print("Position: ");
    Serial.println(cmd.position);

    Serial.println("Angles: ");
    for (int i = 0; i < NUM_OF_FINGERS; i++) {
        Serial.print(cmd.angles[i]);
        Serial.print(" ");
    }
    Serial.println();

    Serial.println("Back Solenoids: ");
    for (int i = 0; i < NUM_OF_FINGERS; i++) {
        Serial.print(cmd.back_solenoids_states[i]);
        Serial.print(" ");
    }
    Serial.println();

    Serial.println("Front Solenoids: ");
    for (int i = 0; i < NUM_OF_FINGERS; i++) {
        Serial.print(cmd.front_solenoids_states[i]);
        Serial.print(" ");
    }
    Serial.println();

    Serial.println("Durations: ");
    for (int i = 0; i < NUM_OF_FINGERS; i++) {
        Serial.print(cmd.durations[i]);
        Serial.print(" ");
    }
    Serial.println();
}



