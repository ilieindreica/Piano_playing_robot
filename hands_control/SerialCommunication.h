#ifndef SERIAL_COM_H
#define SERIAL_COM_H
#include "Hand.h"

int read_int_from_serial();
void readCommandStruct(Hand::CommandStruct &command);
void printCommandStruct(const Hand::CommandStruct &cmd);

#endif