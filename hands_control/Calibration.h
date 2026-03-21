// Calibration.h
#pragma once
#include "Hand.h"

void initCalibration();
void calibrateFingers(Hand* hand, int (*current_angles)[ROT_COLS],
                      int f_idx, int col, int delta);
void autoTestFingers(Hand* hand, int (*current_angles)[ROT_COLS]);
void printAngles(int (*angles)[ROT_COLS]);
void handleSerialCalibration();