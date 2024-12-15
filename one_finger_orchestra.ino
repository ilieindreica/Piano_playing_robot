#include <Servo.h>
#include <AccelStepper.h>
#include <MultiStepper.h>
#include <SPI.h>
#include <SD.h>

#define DO 1
#define DO_diez 1.5
#define RE 2
#define RE_diez 2.5
#define MI 3
#define FA 4
#define FA_diez 4.5
#define SOL 5
#define SOL_diez 5.5
#define LA 6
#define LA_diez 6.5
#define SI 7
#define FULL_NOTE_DURATION 2000
#define OCTAVE 7

#define end_of_stroke_button_pin 2
#define servo_pin 9
#define front_solenoid 6
#define back_solenoid 7
#define step 4
#define dir 5
#define motorInterfaceType 1  // for drivers that use only dir and step

File musicSheet;
Servo myservo;
AccelStepper stepper(motorInterfaceType, step, dir);

float notes_in_one_octave[] = {DO, DO_diez, RE, RE_diez, MI, FA, FA_diez, SOL, SOL_diez, LA, LA_diez, SI};

int equilibrium_angle = 95, angle_shift = 20;
volatile bool end_of_stroke_button_value = 1;
uint32_t prev = 0;
int8_t debounce_delay = 50;
int speed;
// Note, octave, duration
const float notes[][3] = {{DO, 0, 4}, {DO_diez, 0, 4}, {RE, 0, 4}, {RE_diez, 0, 4}, {MI, 0, 4}, {FA, 0, 4},
                        {FA_diez, 0, 4}, {SOL, 0, 4}, {SOL_diez, 0, 4}, {LA, 0, 4}, {LA_diez, 0, 4}, {SI, 0, 4}, {DO, 1, 4}};



void homing(){
  int offset = 150;
  //return to the initial position
  stepper.moveTo(-10000);
  stepper.setSpeed(speed);
  
  while(end_of_stroke_button_value){
    stepper.runSpeedToPosition();
    end_of_stroke_button_value = digitalRead(end_of_stroke_button_pin);
  }
 
  // moves works in absolutes, so we make 0 the current position
  stepper.setCurrentPosition(0);

  stepper.moveTo(offset);
  stepper.runToPosition();
  stepper.setCurrentPosition(0);

}

void press_white_key(int note_duration=0){
  digitalWrite(back_solenoid, LOW);
  digitalWrite(front_solenoid, HIGH);
  delay(note_duration);
  rest_finger();
}

void press_black_key(int note_duration=0){
  digitalWrite(back_solenoid, HIGH);
  delay(500);
  digitalWrite(front_solenoid, HIGH);
  delay(note_duration);
  rest_finger();
}

void rest_finger(){
  digitalWrite(back_solenoid, LOW);
  digitalWrite(front_solenoid, LOW);
}

/** key_position is the position of the key
  in full-step mode, it takes 200 steps for 1 revolution. The GT2-pulley has 20 theet, with 2mm step.
  That means that 200 steps of the motor coresponds to 40mm (20teeth * 2mm) linear displacement.
  From one center of the key to another is 23mm, resulting in 115 steps of the motor */
void move_hand(float key_position, int note_duration=0){
  if(key_position == DO){
    key_position = DO_diez;
  }
  else if(key_position == RE){
    key_position = RE_diez;
  }
  else if(key_position == FA){
    key_position = FA_diez;
  }
  else if(key_position == SOL){
    key_position = SOL_diez;
  }
  int is_black_key = int(key_position*10) % 10; // if it has a decimal part, it means is a black key
  float key_step = key_position * 115;
  Serial.println(key_step);

  // Ensures that it does not go lower that the home position
  if(stepper.currentPosition() + key_step < 0){
    key_step = 0;
  }



  stepper.moveTo(key_step);
  stepper.runToPosition();
  delay(50);

  if(!is_black_key){
    press_white_key(note_duration);
  }
  else {
    press_black_key(note_duration);
  }
}

void play_song(){
  int length = sizeof(notes) / sizeof(notes[0]);
  // for(int i = 0; i < length; i++){
  //   move_hand(notes[i][0]+OCTAVE*notes[i][1], FULL_NOTE_DURATION / notes[i][2]);
  // }
      move_hand(notes[0][0]+OCTAVE*notes[0][1], FULL_NOTE_DURATION / notes[0][2]);
    move_hand(notes[12][0]+OCTAVE*notes[12][1], FULL_NOTE_DURATION / notes[12][2]);

}


void setup() {
  //attachInterrupt(digitalPinToInterrupt(end_of_stroke_button_pin), button_interrupt, RISING);
  pinMode(end_of_stroke_button_pin, INPUT);
  Serial.begin(115200);

  Serial.println("ceva");
  myservo.attach(servo_pin);
  myservo.write(equilibrium_angle);

  pinMode(front_solenoid, OUTPUT);
  pinMode(back_solenoid, OUTPUT);

  float maxSpeed = 2000.0, acc = 50000.0;
  speed = 1500;
  // Initialize steppers
  stepper.setMaxSpeed(maxSpeed);
  stepper.setAcceleration(acc);

  homing();
  delay(1500);

  if (!SD.begin()) {
    Serial.println("initialization failed!");
    while (1);
  }

  musicSheet = SD.open("midi.txt");
  if (musicSheet) {
    while (musicSheet.available()) {
      int max_len = musicSheet.available();
      char a[50];
      byte end = musicSheet.readBytesUntil('\n', a, max_len);
      a[end] = 0;
      int index_of_note, octave, duration;
      uint16_t start_time_of_note;

      char* token = strtok(a, ",");
      
      if (token != NULL) {
        index_of_note = atoi(token);  
      }
      token = strtok(NULL, ",");
      if (token != NULL) {
        octave = atoi(token);
      }
      token = strtok(NULL, ",");
      if (token != NULL) {
        duration = atoi(token);
      }
      token = strtok(NULL, ",");
      if (token != NULL) {
        start_time_of_note = atoi(token);
      }

      move_hand(notes_in_one_octave[index_of_note], duration);

      // Serial.print("index_of_note: "); Serial.println(index_of_note);
      // Serial.print("octave: "); Serial.println(octave);
      // Serial.print("duration: "); Serial.println(duration);
      // Serial.print("start_time_of_note: "); Serial.println(start_time_of_note);
      // Serial.println();
      
    }
    musicSheet.close();
  } else {
    Serial.println("error opening midi.txt");
  }

}

void loop() {
  // delay(500);
  // // myservo.write(equilibrium_angle+25);
  // delay(500);
  // press_white_key(500);
  
  // // myservo.write(equilibrium_angle-25);
  // delay(500);
  // press_white_key(500);

  int d = 100;
  // press_black_key(d);
  // delay(d);
  press_white_key(d);
  delay(d); 
  
  
}












