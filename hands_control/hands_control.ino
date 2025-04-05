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

/* Structs */
  struct command_struct{
    uint8_t position;
    int8_t angles[NUM_OF_FINGERS];
    uint8_t back_solenoids_states[NUM_OF_FINGERS];
    uint8_t front_solenoids_states[NUM_OF_FINGERS];
    uint8_t durations[NUM_OF_FINGERS];
  };
  command_struct* left_commands = nullptr;
  command_struct* right_commands = nullptr;
/* ********************** */

/* Pin lists */
  int right_solenoid_pins[] = {44, 45, 46, 47, 48, 49, 50, 51, 52, 53};
  int right_servo_pins[] = {39, 40, 41, 42, 43};
  int left_solenoid_pins[] = {29, 30, 31, 32, 33, 34, 35, 36, 37, 38};
  int left_servo_pins[] = {24, 25, 26, 27, 28};
/* ***************** */

/* Global variables */
  int left_list_length = 0;
  int right_list_length = 0;
  int left_command_index = 0;
  int right_command_index = 0;
/* **************** */

/* Declarations for functions */
  void homing(int speed=500);
  void moveToKey(AccelStepper &motor, int key_index);
  void execute_command(Hand &hand, command_struct &command);
  void move_hands(int pos_left, int pos_right);
/* ************************ */

void setup() {
  Serial.begin(115200);
  Serial.println("Arduino Ready!");
  Serial.print("Free Mem: ");
  Serial.println(freeMemory());

  // READ DATA from Serial
  readCommands();

  // Initialize hands
  float maxSpeed = 4000.0, acc = 10000.0;
  right_hand.initializeFingers(right_solenoid_pins, right_servo_pins);
  right_hand.setLimitSwitch(right_button_pin);
  right_hand.setMotorParams(acc, maxSpeed);

  left_hand.initializeFingers(left_solenoid_pins, left_servo_pins);
  left_hand.setLimitSwitch(left_button_pin);
  left_hand.setMotorParams(acc, maxSpeed);
  
  homing();

  // move_hands(left_commands[0].position / 2.0f, right_commands[0].position / 2.0f);
//   right_hand.motor.moveTo(right_commands[0].position / 2.0f * ONE_KEY_STEP);
//   while(right_hand.motor.distanceToGo() != 0){
// right_hand.motor.run();
//   }

  Serial.print("Free mem: ");
  Serial.println(freeMemory());
  Serial.println("Exit setup");
}


void loop() {

  if (!right_hand.isPlaying() && right_command_index < right_list_length){
    right_hand.moveToKey(right_commands[right_command_index].position / 2.0f);
  }

  if (!left_hand.isPlaying() && left_command_index < left_list_length){
    left_hand.moveToKey(left_commands[left_command_index].position / 2.0f);
  }

  if (!right_hand.isPlaying() && right_command_index < right_list_length){
    execute_command(right_hand, right_commands[right_command_index]);
    right_command_index++;
    Serial.println(right_command_index);
  }

  if (!left_hand.isPlaying() && left_command_index < left_list_length){
    execute_command(left_hand, left_commands[left_command_index]);
    left_command_index++;
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


void readCommands(){
  byte one_byte = 8;
  
  while (Serial.available() < one_byte) {
    // Wait until data arrives
  }
  
  for (int i = 0; i < 4; i++) {
    left_list_length = (left_list_length << one_byte) | Serial.read();  
  }

  for (int i = 0; i < 4; i++) {
    right_list_length = (right_list_length << one_byte) | Serial.read();  
  }

  left_commands = new command_struct[left_list_length];
  right_commands = new command_struct[right_list_length];

  for (int i = 0; i < left_list_length; i++){
    readCommandStruct(left_commands[i]);
  }
  for (int i = 0; i < right_list_length; i++){
    readCommandStruct(right_commands[i]);
  }
}


void readCommandStruct(command_struct &command) {
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


void printCommandStruct(const command_struct &cmd) {
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


// void move_hands(float pos_left, float pos_right){
//   left_hand.motor.moveTo(pos_left * ONE_KEY_STEP);
//   right_hand.motor.moveTo(pos_right * ONE_KEY_STEP);
  
//   while (left_hand.motor.distanceToGo() != 0 || right_hand.motor.distanceToGo() != 0) {
//     left_hand.motor.run();
//     right_hand.motor.run();
//   }
// }


void execute_command(Hand &hand, command_struct &command){
  // hand.moveToKey(command.position / 2.0f);
  // Serial.print("Pos: "); Serial.println(command.position / 2.0f);

  // Rotate the fingers
  // for (int i = 0; i < NUM_OF_FINGERS; i++){
  //   // Angles where multiplied by 2 to make them ints for easier storage and to preserve the data at the same time
  //   // (note: angles in command are just an index determining how far away is the key to which to rotate, and in which direction)
  //   float key_index = command.angles[i] / 2.0f;  
  //   hand.rotateFingerToKey(i, key_index);
  // }

  // Press black keys
  // for (int i = 0; i < NUM_OF_FINGERS; i++){
  //   if (command.back_solenoids_states[i]){
  //     float duration = 0;
  //     if (command.durations[i] != 0){
  //       duration = 1.0f / command.durations[i] * TIME_PER_BEAT;
  //     }
  //     hand.getFinger(i).press_black_key(duration);
  //   }
  // }

  // Press white keys; As press_black_key() takes care of the state for the front solenoid, don't activate it again
  for (int i = 0; i < NUM_OF_FINGERS; i++){
    // if (!command.back_solenoids_states[i]){
      float duration = 0;
      if (command.durations[i] != 0){
        duration = 1.0f / command.durations[i] * TIME_PER_BEAT;
      }
      hand.getFinger(i).press_white_key(duration, command.front_solenoids_states[i]);
    // }
  }
}


extern char __bss_end;
extern char *__brkval;
// Tells how much RAM is available
int freeMemory() {
    char top;
    return &top - (__brkval == 0 ? &__bss_end : __brkval);
}


