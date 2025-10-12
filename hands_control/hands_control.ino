#include <Servo.h>
#include <AccelStepper.h>
#include "Hand.h"
#include "Piano-robot_setup_config.h"
#include "SerialCommunication.h"

using State = Hand::State;

/* ======= DEFINE STATEMENTS ======= */
  #define dir_right 4
  #define step_right 5
  #define dir_left 2
  #define step_left 3
  #define right_button_pin 7
  #define left_button_pin 8
  #define motorInterfaceType 1  // for drivers that use only dir and step
  #define MS1_right 10
  #define MS2_right 11
  #define MS1_left 12
  #define MS2_left 13
  #define MS_level 2  // Microstepping factor
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
  int right_equilibrium_angles[] = {78, 80, 82, 80, 85};
  int left_solenoid_pins[] = {29, 30, 31, 32, 33, 34, 35, 36, 37, 38};
  int left_servo_pins[] = {24, 25, 26, 27, 28};
  int left_equilibrium_angles[] = {78, 73, 82, 85, 82};
/* ***************** */

/* Global variables */
bool is_double_handed = true;
/* **************** */

/* Declarations for functions */
  void homing(int speed=2000);
  void readCommands(Hand &hand);
  void moveToKey(AccelStepper &motor, int key_index);
  void move_hands(int pos_left, int pos_right);
/* ************************ */

void setup() {
  Serial.begin(115200);
  Serial.println("Arduino Ready!");

  pinMode(MS1_right, OUTPUT);
  pinMode(MS2_right, OUTPUT);
  digitalWrite(MS1_right, HIGH);
  digitalWrite(MS2_right, LOW);

  pinMode(MS1_left, OUTPUT);
  pinMode(MS2_left, OUTPUT);
  digitalWrite(MS1_left, HIGH);
  digitalWrite(MS2_left, LOW);

  // Initialize hands
  float maxSpeed = 5000.0, acc = 30000.0;
  right_hand.setFingers(right_solenoid_pins, right_servo_pins);
  right_hand.setEquilibriumAngles(right_equilibrium_angles);
  right_hand.getFingersInNormalPosition();
  right_hand.setLimitSwitch(right_button_pin);
  right_hand.setMotorParams(acc, maxSpeed);
  right_hand.setHandedness('r');
  right_hand.setTheOtherHand(left_hand);

  left_hand.setFingers(left_solenoid_pins, left_servo_pins);
  left_hand.setEquilibriumAngles(left_equilibrium_angles);
  left_hand.getFingersInNormalPosition();
  left_hand.setLimitSwitch(left_button_pin);
  left_hand.setMotorParams(acc, maxSpeed);
  left_hand.setHandedness('l');
  left_hand.setTheOtherHand(right_hand);

  homing();

  // READ DATA from Serial
  while(!Serial.available());
  is_double_handed = Serial.read();
  right_hand.command_list_length = read_int_from_serial();
  left_hand.command_list_length = read_int_from_serial();

  if (!is_double_handed){
    right_hand.isSolo = true;
  }
  
}

State r_prev=right_hand.getState(), l_prev=left_hand.getState();
void loop() {

  if (is_double_handed){
    unsigned long reference_time=millis();
    right_hand.update(reference_time);
    left_hand.update(reference_time);

    if(left_hand.command.note_rank == 0 && right_hand.command.note_rank == 0){
      recalculatingWaiterNeeded = true;
    }

    // if(r_prev != right_hand.getState()){
    //   r_prev = right_hand.getState();
    //   Serial.print('r'); Serial.println(right_hand.stateToStr(r_prev));
    // }
    // if(l_prev != left_hand.getState()){
    //   l_prev = left_hand.getState();
    //   Serial.print('l'); Serial.println(left_hand.stateToStr(l_prev));
    // }
  }

  else{
    if(right_hand.getState() == State::READY_TO_PLAY){
      right_hand.setState(State::PRESSING);
    }
    right_hand.update();
  }


  if (right_hand.getState() == State::FINISHED && left_hand.getState() == State::FINISHED){
    right_hand.command_index = 0;
    left_hand.command_index = 0;
    right_hand.setState(State::IDLE);
    left_hand.setState(State::IDLE);
    right_hand.resetCompensation();
    left_hand.resetCompensation();
    Serial.println("FINISHED");
    delay(2000);
  }
  else if(right_hand.getState() == State::FINISHED && !is_double_handed){
    right_hand.command_index = 0;
    right_hand.setState(State::IDLE);
    right_hand.resetCompensation();
    Serial.println("FINISHED solo");
    delay(2000);
  }

}


void homing(int speed){

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







