#include "HardwareSerial.h"
#include "SerialCommunication.h"
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
  return (int)data.f;  // daca nu apesi pe clapele negre, sa nu existe pericol de a se ciocni degetele intre ele
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

  for (int i = 0; i < NUM_OF_FINGERS; i++) {
      command.durations[i] = read_int_from_serial();
  }

  command.note_rank = read_int_from_serial();

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