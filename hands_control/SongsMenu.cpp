#include "SongsMenu.h"

static LiquidCrystal_I2C* lcd = nullptr;
static SdFile* file = nullptr;
static SdFile dir;

static int jstk_x_pin;
static int jstk_btn_pin;
static int lcd_cols;
static int lcd_rows;
static int button_pressed_level;
static const char* folderPath;

// --- Exposed state ---
char** fileNames = nullptr;
int fileCount = 0;
int currentIndex = 0;

// --- Internal state ---
static int topIndex = 0;  // first visible item on lcd
static int filenameCharIdx = 0;
static unsigned long lastScrollTime = 0;
static const int SCROLL_DELAY = 400;
static const int JOYSTICK_THRESHOLD = 200;

static String selector = "->";
static String paddedName;
static int maxSelectedChars;

static unsigned long button_lastDebounceTime = 0;
static const int debounceDelay = 50;
static bool lastButtonState = LOW;
static bool buttonState;


void songsMenuInit(LiquidCrystal_I2C &lcdRef, SdFile &fileRef,
                   int joystickXPin, int joystickButtonPin,
                   int lcdCols, int lcdRows, int buttonPressedLevel,
                   const char* songFolderPath){
  lcd = &lcdRef;
  file = &fileRef;
  jstk_x_pin = joystickXPin;
  jstk_btn_pin = joystickButtonPin;
  lcd_cols = lcdCols;
  lcd_rows = lcdRows;
  button_pressed_level = buttonPressedLevel;
  folderPath = songFolderPath;
  maxSelectedChars = lcd_cols - selector.length();
}


void loadFileNames() {
  dir.open(folderPath);
  while (file->openNext(&dir, O_READ)) {
    if (file->isDir()) { file->close(); continue; }
    char name[64];
    file->getName(name, sizeof(name));
    file->close();

    // filter .txt files
    String n = String(name);
    if(!file->isDir() && (n.endsWith(".TXT") || n.endsWith(".txt"))){
      int dotIdx = n.lastIndexOf('.');
      name[dotIdx] = '\0';  // Remove extension from name
      fileNames = (char**)realloc(fileNames, (fileCount + 1) * sizeof(char*));
      fileNames[fileCount] = (char*)malloc(strlen(name) + 1);
      strcpy(fileNames[fileCount], name);
      fileCount++;
    }
    
  }
  dir.close();
}


// Reads button from Joystick. Returns the reading. Updates lastButtonState.
int readButton(){
  bool reading = digitalRead(jstk_btn_pin);

  if (reading != lastButtonState) button_lastDebounceTime = millis();

  if ((millis() - button_lastDebounceTime) > debounceDelay) {
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == button_pressed_level) return reading;
    }
  }

  lastButtonState = reading;
  return !button_pressed_level;
}


void songsMenu(){
  int x = analogRead(jstk_x_pin);
  bool moved = false;

  if(x < JOYSTICK_THRESHOLD){
    if(currentIndex > 0){
      currentIndex--;
      if(currentIndex < topIndex) topIndex--;
      moved = true;
    }
    else{
      currentIndex = fileCount;
      topIndex = currentIndex - 1;
    }
  }
  else if(x > (1023 - JOYSTICK_THRESHOLD)){
    if(currentIndex < fileCount - 1){
      currentIndex++;
      
      if(currentIndex >= topIndex + lcd_rows) topIndex++;
      moved = true;
    }
    else{
      currentIndex = 0;
      topIndex = currentIndex;
    }
  }

  if(moved){
    displayList();
    delay(SCROLL_DELAY);
    moved = false;
    filenameCharIdx = 0;
  }

  scrollName(currentIndex - topIndex, maxSelectedChars);
}


// Prints two mesages on LCD. Updates paddedName
void displayList(){
  lcd->clear();
  for(int row = 0; row < lcd_rows; row++){
    int idx = topIndex + row;
    if (idx >= fileCount) break;
    
    lcd->setCursor(0, row);

    String name = String(fileNames[idx]);
    if(idx == currentIndex){
      lcd->print(selector);
      lcd->print(name.substring(0, maxSelectedChars));
      paddedName = name + "   " + name.substring(0, maxSelectedChars);  // trailing spaces for clean end
    }
    else{
      lcd->print(name.substring(0, lcd_cols));
    }
  }
}


void scrollName(int row, int maxChars) {
  String name = fileNames[currentIndex];
  int len = name.length();
  if (len <= maxChars) {
    // fits, no scroll needed
    lcd->setCursor(2, row);
    lcd->print(name);
    return;
  }

  // scroll across
  int total = paddedName.length();

  if(millis() - lastScrollTime > SCROLL_DELAY){
    if(filenameCharIdx < total - maxChars - 1){
      filenameCharIdx++;
    }
    else{
      filenameCharIdx = 0;
    }
    lcd->setCursor(2, row);
    lcd->print(paddedName.substring(filenameCharIdx, filenameCharIdx + maxChars));
    lastScrollTime = millis();
  }
}

