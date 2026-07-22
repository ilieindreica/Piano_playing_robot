#ifndef COMMUNICATION_H
#define COMMUNICATION_H
#include "Hand.h"
#include <SdFat.h>


int read_int_from_serial();
void readCommandStruct(Hand::CommandStruct &command);
void printCommandStruct(const Hand::CommandStruct &cmd);
bool readCommandFromFile(int &duration, Hand &left_hand, Hand &right_hand);

extern SdFile file;

#endif