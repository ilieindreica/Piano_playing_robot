#include <Servo.h>
#include <AccelStepper.h>
#include "Hand.h"
#include "Piano-robot_setup_config.h"
#include "SerialCommunication.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <SPI.h>
#include <SdFat.h>
#include "Calibration.h"


/* ======= DEFINE STATEMENTS ======= */
  #define dir_right 4
  #define step_right 5
  #define dir_left 2
  #define step_left 3
  #define right_button_pin 6
  #define left_button_pin 7
  #define motorInterfaceType 1  // for drivers that use only dir and step
  #define MS1_right 10
  #define MS2_right 11
  #define MS1_left 8
  #define MS2_left 9
  #define MS_level 2  // Microstepping factor
  #define SD_CARD_READING_MODE 0
  #define SERIAL_READING_MODE 1
  #define BUTTON_PRESSED 0  // I use Pull-up resistor, so logic is inverted
  #define JOYSTICK_THRESHOLD 200  // deadzone
  #define DEBOUNCE_MS 500
  #define SCROLL_DELAY  400  // ms between moves
  #define LCD_ROWS 2  // how many rows the LCD has
  #define LCD_COLS 16
  #define RIGHT_ENABLE_PIN 14
  #define LEFT_ENABLE_PIN 15
/* ================================================================= */

/* Class objects */
  Hand right_hand(motorInterfaceType, step_right, dir_right);
  Hand left_hand(motorInterfaceType, step_left, dir_left);
  LiquidCrystal_I2C lcd(0x27, LCD_COLS, LCD_ROWS);
  SdFat sd_card;
  SdFile dir, file;
/***************************/

/* Structs */

/* ********************** */

/* Pin lists */
  int right_solenoid_pins[] = {40, 41, 42, 43, 44, 45, 46, 47, 48, 49};   // {44, 45, 46, 47, 48, 49, 50, 51, 52, 53};
  int right_servo_pins[] = {34, 35, 36, 37, 38};     // {39, 40, 41, 42, 43};
  int left_solenoid_pins[] =  {24, 25, 26, 27, 28, 29, 30, 31, 32, 33};  // {29, 30, 31, 32, 33, 34, 35, 36, 37, 38};
  int left_servo_pins[] = {39, 17, 18, 22, 23};      // {24, 25, 26, 27, 28};
  const int jstk_x = A0, jstk_y = A1, jstk_btn_pin = 19;
  // int active_mode = SERIAL_READING_MODE;
  int active_mode = SD_CARD_READING_MODE;
  int CS_pin = 53;
/* ***************** */

/* Global variables */
  unsigned long lastScrollTime = 0;
  int duration = 0;
  volatile unsigned long lastDebounceTime = 0;;
  const int debounceDelay = 50;
  bool lastButtonState = LOW;
  bool buttonState;
  char** fileNames = nullptr;
  int fileCount = 0;
  const char* folderPath = "/PianoCommands";
  String selector = "->", paddedName;
  int currentIndex = 0;
  int topIndex = 0;        // first visible item on lcd
  int filenameCharIdx = 0;
  const int maxSelectedChars = LCD_COLS - selector.length();
  volatile bool isPlaying = false, stopRequested = false;
/* **************** */

/* Declarations for functions */
  void homing(int speed=-1);
  void readCommands(Hand &hand);
  void moveToKey(AccelStepper &motor, int key_index);
  void move_hands(int pos_left, int pos_right);
  void runMotorsTogether();
  int readButton();
  void loadFileNames();
  void displayList();
  void songsMenu();
  void scrollName(int row, int maxChars);
/* ************************ */


void stopISR() {
  unsigned long now = millis();
  if(!isPlaying) return;

  if(now - lastDebounceTime < DEBOUNCE_MS) return;
  lastDebounceTime = now;
  stopRequested = true;
}

void setup() {
  Serial.begin(115200);
  while(!Serial){ ; }

  // LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);

  // SD card
  Serial.print("Initializing SD card...");
  if (!sd_card.begin(CS_pin, SD_SCK_MHZ(4))) {
    Serial.println("initialization failed!");
    lcd.print("SD not found!");
    sd_card.initErrorPrint(&Serial);
    while (1);
  }
  Serial.println("initialization done.");

  loadFileNames();

  Serial.println("Arduino Ready!");

  // Joystick
  pinMode(jstk_x, INPUT);
  pinMode(jstk_y, INPUT);
  pinMode(jstk_btn_pin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(jstk_btn_pin), stopISR, FALLING);

  if(digitalRead(jstk_btn_pin) == BUTTON_PRESSED){
    active_mode = SERIAL_READING_MODE;
  }

  if(INSTALLED_DRIVER == TMC2208_DRIVER){
    pinMode(MS1_right, OUTPUT);
    pinMode(MS2_right, OUTPUT);
    digitalWrite(MS1_right, HIGH);
    digitalWrite(MS2_right, LOW);

    pinMode(MS1_left, OUTPUT);
    pinMode(MS2_left, OUTPUT);
    digitalWrite(MS1_left, HIGH);
    digitalWrite(MS2_left, LOW);
  }

  // Initialize hands
  float maxSpeed, acc;
  if(INSTALLED_DRIVER == TMC2208_DRIVER){
    maxSpeed = 4000.0; acc = 10000.0;
  }
  else if(INSTALLED_DRIVER == A4988_DRIVER){
    maxSpeed = 2000.0; acc = 8000.0;
  }

  right_hand.setFingers(right_solenoid_pins, right_servo_pins);
  right_hand.setRotationAngles(&RIGHT_ROTATION_ANGLES[0][0]);
  right_hand.putFingersInNormalPosition();
  right_hand.setLimitSwitch(right_button_pin);
  right_hand.setMotorParams(acc, maxSpeed);
  right_hand.motor.setEnablePin(RIGHT_ENABLE_PIN);
  right_hand.motor.setPinsInverted(false, false, true);

  left_hand.setFingers(left_solenoid_pins, left_servo_pins);
  left_hand.setRotationAngles((const int*)LEFT_ROTATION_ANGLES);
  left_hand.putFingersInNormalPosition();
  left_hand.setLimitSwitch(left_button_pin);
  left_hand.setMotorParams(acc, maxSpeed);
  left_hand.motor.setEnablePin(LEFT_ENABLE_PIN);
  left_hand.motor.setPinsInverted(false, false, true);

  // Serial reading mode
  if(active_mode == SERIAL_READING_MODE){
    lcd.setCursor(0, 0);
    lcd.print("Serial reading");
    lcd.setCursor(0, 1);
    lcd.print("mode");

    homing();
    Serial.println("R");
    duration = read_int_from_serial();
    left_hand.requestCommand();
    right_hand.requestCommand();
  }

  // initCalibration();
  // homing();
}

// void loop(){
//   right_hand.motor.disableOutputs();
//   left_hand.motor.disableOutputs();
//   handleSerialCalibration();  
// }


void loop() {

  if (isPlaying == false && active_mode == SD_CARD_READING_MODE){
    left_hand.stopAndReset();
    right_hand.stopAndReset();
    right_hand.motor.disableOutputs();
    left_hand.motor.disableOutputs();
    displayList();
    while(readButton() != BUTTON_PRESSED){
      songsMenu();
    }

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(selector); lcd.print("Stop");

    isPlaying = true;
    homing();

    String path = String(folderPath) + '/' + String(fileNames[currentIndex]) + ".txt";
    file.open(path.c_str());

    readCommandFromFile(duration, left_hand.command, right_hand.command);
  }


  int delayTime = 0;

  left_hand.releaseFingers();
  right_hand.releaseFingers();
  delay(TIME_FOR_SOLENOID_RETRACTION);

  bool l_needs_ext = left_hand.extendFingers();
  bool r_needs_ext = right_hand.extendFingers();

  // bool l_needs_rot = false;
  int l_rot_delay = left_hand.rotateFingers();
  int r_rot_delay = right_hand.rotateFingers();

  unsigned long start = millis();
  left_hand.setTargetPosition();
  right_hand.setTargetPosition();
  runMotorsTogether();
  unsigned long end = millis();

  int move_time = end - start;


  if((l_rot_delay || r_rot_delay) && TIME_FOR_ROTATION > move_time){
    delayTime = max(l_rot_delay, r_rot_delay);
  }

  if(l_needs_ext || r_needs_ext){
    delayTime = max(delayTime, TIME_FOR_EXTENSION);
  }
  delay(delayTime);

  bool does_left_press = left_hand.press();
  bool does_right_press = right_hand.press();

  if(does_left_press || does_right_press){
    delay(MINIMUM_TIME_FOR_PRESSING);
  }

  start = millis();
  int next_duration;
  if(active_mode == SERIAL_READING_MODE){
    Serial.println('R');  // ready for next command
    next_duration = read_int_from_serial();
    left_hand.requestCommand();
    right_hand.requestCommand();
  } 
  else if(active_mode == SD_CARD_READING_MODE){
    isPlaying = readCommandFromFile(next_duration, left_hand.command, right_hand.command);
  }
  
  end = millis();
  int ellapsed = end - start;
  
  // if(right_hand.allFingersOff()){
  //   Serial.print(move_time);
  //   Serial.print("  "); Serial.print(duration); Serial.print("  ");
  //   ellapsed += move_time;
  //   Serial.println(duration - ellapsed);
  // }

  // Serial.print(duration); Serial.print("  "); Serial.print(ellapsed);  Serial.print("  "); Serial.println(duration - ellapsed);
  
  delayTime = max(duration - ellapsed, 0);
  delay(delayTime);
  duration = next_duration;

  if (stopRequested) {
    stopRequested = false;
    isPlaying = false;
    file.close();
    duration = 0;
    left_hand.stopAndReset();
    right_hand.stopAndReset();    
  }

}


void homing(int speed){
  if(speed == -1){  // If no speed was provided
    if(INSTALLED_DRIVER == TMC2208_DRIVER){
      speed = 2000;
    }
    else if(INSTALLED_DRIVER == A4988_DRIVER) {
      speed = 500;
    }
  }

  //
  right_hand.motor.enableOutputs();
  left_hand.motor.enableOutputs();
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
    if(left_button_value != LOW){    
      left_hand.motor.runSpeedToPosition();
      left_button_value = left_hand.readLimitSwitch();
    }
    delay(1);  // Without, left hand stops prematurely
  }
 
  right_hand.motor.setCurrentPosition(MAX_STEPPER_TRAVEL_DISTANCE);
  right_hand.setKeyIndex(NUM_OF_WHITE_KEYS);

  left_hand.motor.setCurrentPosition(MIN_STEPPER_TRAVEL_DISTANCE);
  left_hand.setKeyIndex(0);
}


void runMotorsTogether(){  
  while (left_hand.motor.distanceToGo() != 0 || right_hand.motor.distanceToGo() != 0) {
    right_hand.motor.run();
    left_hand.motor.run();
  }
}


void loadFileNames() {
   
  dir.open(folderPath);
  while (file.openNext(&dir, O_READ)) {
    if (file.isDir()) { file.close(); continue; }
    char name[64];
    file.getName(name, sizeof(name));
    file.close();


    // filter .txt files
    String n = String(name);
    if(!file.isDir() && (n.endsWith(".TXT") || n.endsWith(".txt"))){
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

  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (reading != buttonState) {
      buttonState = reading;

      if (buttonState == BUTTON_PRESSED) {
        return reading;
      }
    }
  }

  lastButtonState = reading;
  return !BUTTON_PRESSED;
}


void songsMenu(){
  int x = analogRead(jstk_x);
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
      
      if(currentIndex >= topIndex + LCD_ROWS) topIndex++;
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
  lcd.clear();
  for(int row = 0; row < LCD_ROWS; row++){
    int idx = topIndex + row;
    if (idx >= fileCount) break;
    
    lcd.setCursor(0, row);

    String name = String(fileNames[idx]);
    if(idx == currentIndex){
      lcd.print(selector);
      lcd.print(name.substring(0, maxSelectedChars));
      paddedName = name + "   " + name.substring(0, maxSelectedChars);  // trailing spaces for clean end
    }
    else{
      lcd.print(name.substring(0, LCD_COLS));
    }
  }
}


void scrollName(int row, int maxChars) {
  String name = fileNames[currentIndex];
  int len = name.length();
  if (len <= maxChars) {
    // fits, no scroll needed
    lcd.setCursor(2, row);
    lcd.print(name);
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
    lcd.setCursor(2, row);
    lcd.print(paddedName.substring(filenameCharIdx, filenameCharIdx + maxChars));
    lastScrollTime = millis();
  }
}


bool readCommandFromFile(int &duration, Hand::CommandStruct &leftCmd, Hand::CommandStruct &rightCmd){
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




