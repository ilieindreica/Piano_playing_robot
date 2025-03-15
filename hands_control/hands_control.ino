#include <Servo.h>
#include <AccelStepper.h>
#include "Hand.h"
#include "Piano-robot_setup_config.h"

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

/* Pins */
  int right_solenoid_pins[] = {44, 45, 46, 47, 48, 49, 50, 51, 52, 53};
  int right_servo_pins[] = {39, 40, 41, 42, 43};
/* ***************** */

/* Declarations for functions */
  void homing(int speed=500);
  void moveToKey(AccelStepper &motor, int key_index);
/* ************************ */

void setup() {
  Serial.begin(115200);

  // Initialize hands
  float maxSpeed = 5000.0, acc = 10000.0;
  right_hand.initializeFingers(right_solenoid_pins, right_servo_pins);
  right_hand.setLimitSwitch(right_button_pin);
  right_hand.setMotorParams(acc, maxSpeed);

  left_hand.setLimitSwitch(left_button_pin);
  left_hand.setMotorParams(acc, maxSpeed);
  
  homing();
  right_hand.moveToKey(35);
}

void loop() {
  right_hand.demo();
  right_hand.update();
  Serial.println(right_hand.isPlaying());
  
}

void homing(int speed=500){

  //
  right_hand.motor.moveTo(MAX_STEPPER_TRAVEL_DISTANCE);
  right_hand.motor.setSpeed(speed);
  left_hand.motor.moveTo(-MAX_STEPPER_TRAVEL_DISTANCE);
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

}


