#include <Servo.h>
#include <AccelStepper.h>
#include "Hand.h"
#include "Piano-robot_setup_config.h"
#include "Communication.h"
#include "SongsMenu.h"
#include <SdFat.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <SPI.h>
#include "Calibration.h"
#include <TMCStepper.h>


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
  #define TMC2209_CURRENT_MA 1200
  #define SD_CARD_READING_MODE 0
  #define SERIAL_READING_MODE 1
  #define BUTTON_PRESSED 0  // I use Pull-up resistor, so logic is inverted
  #define JOYSTICK_THRESHOLD 200  // deadzone
  #define DEBOUNCE_MS 500
  #define LCD_ROWS 2  // how many rows the LCD has
  #define LCD_COLS 16
  #define RIGHT_ENABLE_PIN A2   // former 14
  #define LEFT_ENABLE_PIN  A3  // former 15
  #define jstk_x A0
  #define jstk_y A1
  #define jstk_btn_pin 19
  #define r_driver_address 0b00
  #define l_driver_address 0b00
  #define R_SENSE 0.11f
/* ================================================================= */

/* Class objects */
  Hand right_hand(motorInterfaceType, step_right, dir_right);
  Hand left_hand(motorInterfaceType, step_left, dir_left);
  LiquidCrystal_I2C lcd(0x27, LCD_COLS, LCD_ROWS);
  SdFat sd_card;
  SdFile file;
  #if INSTALLED_DRIVER == TMC2209_DRIVER
    TMC2209Stepper right_driver(&Serial2, R_SENSE, r_driver_address);
    TMC2209Stepper left_driver(&Serial3, R_SENSE, l_driver_address);
  #endif
/***************************/

/* Structs */

/* ********************** */

/* Pin lists */
  int right_solenoid_pins[] = {40, 41, 42, 43, 44, 45, 46, 47, 48, 49};   // {44, 45, 46, 47, 48, 49, 50, 51, 52, 53};
  int right_servo_pins[] = {34, 35, 36, 37, 38};     // {39, 40, 41, 42, 43};
  int left_solenoid_pins[] =  {24, 25, 26, 27, 28, 29, 30, 31, 32, 33};  // {29, 30, 31, 32, 33, 34, 35, 36, 37, 38};
  int left_servo_pins[] = {39, 12, 13, 22, 23};      // {24, 25, 26, 27, 28};
  // int active_mode = SERIAL_READING_MODE;
  int active_mode = SD_CARD_READING_MODE;
  int CS_pin = 53;
/* ***************** */

/* Global variables */
  int duration = 0;
  volatile unsigned long isr_lastDebounceTime = 0;
  String selector = "->";
  const char* folderPath = "/PianoCommands";
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
  void setMicrostepPins(int ms1_pin, int ms2_pin, int ms1_val, int ms2_val);
/* ************************ */


void stopISR() {
  unsigned long now = millis();
  if(!isPlaying) return;

  if(now - isr_lastDebounceTime < DEBOUNCE_MS) return;
  isr_lastDebounceTime = now;
  stopRequested = true;
}

void setup() {
  Serial.begin(115200);
  while(!Serial){ ; }

  // LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);

  // // SD card
  // Serial.print("Initializing SD card...");
  // if (!sd_card.begin(CS_pin, SD_SCK_MHZ(4))) {
  //   Serial.println("initialization failed!");
  //   lcd.print("SD not found!");
  //   sd_card.initErrorPrint(&Serial);
  //   while (1);
  // }
  Serial.println("initialization done.");

  songsMenuInit(lcd, file, jstk_x, jstk_btn_pin, LCD_COLS, LCD_ROWS, BUTTON_PRESSED, folderPath);
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
    setMicrostepPins(MS1_right, MS2_right, HIGH, LOW);
    setMicrostepPins(MS1_left, MS2_left, HIGH, LOW);
  }

  if(INSTALLED_DRIVER == TMC2209_DRIVER){
    setMicrostepPins(MS1_right, MS2_right, r_driver_address & 1, (r_driver_address >> 1) & 1);
    setMicrostepPins(MS1_left, MS2_left, l_driver_address & 1, (l_driver_address >> 1) & 1);
    setupUARTDrivers();
  }

  // --- Initialize hands ---
  float maxSpeed, acc;
  if(INSTALLED_DRIVER == TMC2208_DRIVER){
    maxSpeed = 4000.0; acc = 10000.0;
  }
  else if(INSTALLED_DRIVER == TMC2209_DRIVER){
    maxSpeed = 4000.0; acc = 10000.0;
  }
  else if(INSTALLED_DRIVER == A4988_DRIVER){
    maxSpeed = 2000.0; acc = 8000.0;
  }

  // Init Right hand
  right_hand.setFingers(right_solenoid_pins, right_servo_pins);
  right_hand.setRotationAngles(&RIGHT_ROTATION_ANGLES[0][0]);
  right_hand.putFingersInNormalPosition();
  right_hand.setLimitSwitch(right_button_pin);
  right_hand.setMotorParams(acc, maxSpeed);
  right_hand.motor.setEnablePin(RIGHT_ENABLE_PIN);  

  // Init Left hand
  left_hand.setFingers(left_solenoid_pins, left_servo_pins);
  left_hand.setRotationAngles((const int*)LEFT_ROTATION_ANGLES);
  left_hand.putFingersInNormalPosition();
  left_hand.setLimitSwitch(left_button_pin);
  left_hand.setMotorParams(acc, maxSpeed);
  left_hand.motor.setEnablePin(LEFT_ENABLE_PIN);

  // Invert pins
  bool inverted = (INSTALLED_DRIVER == TMC2209_DRIVER);
  right_hand.motor.setPinsInverted(inverted, false, true);
  left_hand.motor.setPinsInverted(inverted, false, true);

  // Serial Reading Mode
  if(active_mode == SERIAL_READING_MODE){
    lcd.setCursor(0, 0); lcd.print("Serial reading");
    lcd.setCursor(0, 1); lcd.print("mode");
    lcd.print("Homing...");
   
    homing();
    // initCalibration();   
    Serial.println("R");
    duration = read_int_from_serial();
    left_hand.requestCommand();
    right_hand.requestCommand();
  }

  // SD Card Reading Mode
  if(active_mode == SD_CARD_READING_MODE){
    lcd.print("Homing...");
    // homing();
  }
}


void loop() {
  #if INSTALLED_DRIVER == TMC2209_DRIVER
    uint16_t msread_r = right_driver.microsteps();
    uint16_t msread_l = left_driver.microsteps();
    Serial.print("MS_r: "); Serial.println(msread_r);
    Serial.print("MS_l: "); Serial.println(msread_l);
  #endif

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

    readCommandFromFile(duration, left_hand, right_hand);
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
    isPlaying = readCommandFromFile(next_duration, left_hand, right_hand);
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


// void loop(){
//   right_hand.motor.disableOutputs();
//   left_hand.motor.disableOutputs();
//   handleSerialCalibration();  
// }


void homing(int speed){
  if(speed == -1){  // If no speed was provided
    if(INSTALLED_DRIVER == TMC2208_DRIVER){
      speed = 2000;
    } else if(INSTALLED_DRIVER == TMC2209_DRIVER){
      speed = 2000;
    } else if(INSTALLED_DRIVER == A4988_DRIVER) {
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


void setMicrostepPins(int ms1_pin, int ms2_pin, int ms1_val, int ms2_val){
  pinMode(ms1_pin, OUTPUT);
  pinMode(ms2_pin, OUTPUT);
  digitalWrite(ms1_pin, ms1_val);
  digitalWrite(ms2_pin, ms2_val);
}


#if INSTALLED_DRIVER == TMC2209_DRIVER
  void configDriver(TMC2209Stepper &drv, const char* label){
    drv.begin();
    drv.toff(5);
    drv.rms_current(TMC2209_CURRENT_MA);
    drv.microsteps(MICROSTEP);
    drv.pwm_autoscale(true);
    drv.en_spreadCycle(true);

    uint8_t version = drv.version();
    Serial.print(label); Serial.print(" version: 0x"); Serial.println(version, HEX);
    Serial.println(version == 0x21 ? "UART OK" : "UART FAILED");
  }

  void setupUARTDrivers(){
    Serial2.begin(115200);
    Serial3.begin(115200);
    delay(500);
    
    configDriver(right_driver, "Right");
    configDriver(left_driver, "Left");
  }
#endif



