#pragma once
#include <LiquidCrystal_I2C.h>
#include <SdFat.h>

void songsMenuInit(LiquidCrystal_I2C &lcdRef, SdFile &fileRef,
                   int joystickXPin, int joystickButtonPin,
                   int lcdCols, int lcdRows, int buttonPressedLevel,
                   const char* songFolderPath);
void loadFileNames();
void songsMenu();
void displayList();
void scrollName(int row, int maxChars);
int readButton();

extern char** fileNames;
extern int fileCount;
extern int currentIndex;



