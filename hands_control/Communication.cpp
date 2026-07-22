#include "HardwareSerial.h"
#include "Communication.h"
#include <Arduino.h>
#include <math.h>


int read_int_from_serial(){
  while(Serial.available() < 4);
  byte one_byte = 8;
  int result = 0;
  for (int i = 0; i < 4; i++) {
    result = (result << one_byte) | Serial.read();  
  }

  return result;
}


float read_float_from_serial() {
  while (Serial.available() < 4); // wait 4 bytes

  union {
    byte b[4];
    float f;
  } data;

  for (int i = 0; i < 4; i++) {
    data.b[i] = Serial.read();
  }

  // return round(data.f);
  return data.f;  // pune (int) daca nu apesi pe clapele negre, sa nu existe pericol de a se ciocni degetele intre ele
}


void readCommandStruct(Hand::CommandStruct &command) {
  // Wait for position byte
  while (Serial.available() < 1);
  command.position = Serial.read();

  for (int i = 0; i < NUM_OF_FINGERS; i++) {
      command.angles[i] = read_float_from_serial();
  }

  // Wait for NUM_OF_FINGERS bytes
  while (Serial.available() < NUM_OF_FINGERS);
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
      command.back_solenoids_states[i] = Serial.read();
  }

  while (Serial.available() < NUM_OF_FINGERS);
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
      command.front_solenoids_states[i] = Serial.read();
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
}


bool readCommandFromFile(int &duration, Hand &left_hand, Hand &right_hand){
  Hand::CommandStruct &leftCmd = left_hand.command, &rightCmd = right_hand.command;

  if (!file || !file.available()) return false;
  // read one line
  char line[128];
  int len = 0;
  while (file.available()) {
    char c = file.read();
    if (c == '\n') break;
    if (c != '\r') line[len++] = c;
  }
  line[len] = '\0';
  if (len == 0) return false;

  char* token = strtok(line, " ");
  long currentTimestamp = atol(token); token = strtok(NULL, " ");

  // left hand
  leftCmd.position = atoi(token); token = strtok(NULL, " ");
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    left_hand.previous_angles[i] = leftCmd.angles[i];
    leftCmd.angles[i] = atof(token); token = strtok(NULL, " ");
  }
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    left_hand.previous_extensions[i] = leftCmd.back_solenoids_states[i];
    leftCmd.back_solenoids_states[i] = atoi(token); token = strtok(NULL, " ");
  }
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    leftCmd.front_solenoids_states[i] = atoi(token); token = strtok(NULL, " ");
  }

  // right hand
  rightCmd.position = atoi(token); token = strtok(NULL, " ");
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    right_hand.previous_angles[i] = rightCmd.angles[i];
    rightCmd.angles[i] = atof(token); token = strtok(NULL, " ");
  }
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    right_hand.previous_extensions[i] = rightCmd.back_solenoids_states[i];
    rightCmd.back_solenoids_states[i] = atoi(token); token = strtok(NULL, " ");
  }
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    rightCmd.front_solenoids_states[i] = atoi(token); token = strtok(NULL, " ");
  }

  // Peek just the timestamp from the next line
  long peekTimestamp = 0;
  long savedPos = file.curPosition();
  char peek[20];
  int pi = 0;
  while (file.available()) {
    char c = file.read();
    if (c == ' ' || c == '\n' || c == '\r') break;
    peek[pi++] = c;
  }
  peek[pi] = '\0';
  file.seekSet(savedPos);  // rewind to where next line started

  duration = (int)(atol(peek) - currentTimestamp);

  return true;
}




