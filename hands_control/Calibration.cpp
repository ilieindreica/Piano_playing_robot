#include "Calibration.h"

// Forward declarations of globals from .ino
extern Hand left_hand;
extern Hand right_hand;
int current_angles_left[NUM_OF_FINGERS][ROT_COLS];
int current_angles_right[NUM_OF_FINGERS][ROT_COLS];

void initCalibration(){
  memcpy(current_angles_right, RIGHT_ROTATION_ANGLES, sizeof(current_angles_right));
  memcpy(current_angles_left, LEFT_ROTATION_ANGLES, sizeof(current_angles_left));
}

void calibrateFingers(Hand* hand, int (*current_angles)[ROT_COLS],
                      int f_idx, int col, int delta) {
  int mid = ROT_COLS / 2;

  current_angles[f_idx][col] += delta;
  hand->getFinger(f_idx).rotate(current_angles[f_idx][col]);
  if (col % 2 == 0 && col != mid)
      hand->getFinger(f_idx).extendOrRetract(HIGH);

  if (col < mid) {
    for (int i = f_idx - 1; i >= 0; i--)
      hand->getFinger(i).rotate(current_angles[i][col]);
  } else if (col > mid) {
      for (int i = f_idx + 1; i < NUM_OF_FINGERS; i++)
        hand->getFinger(i).rotate(current_angles[i][col]);
  }

  Serial.print("angle="); Serial.println(current_angles[f_idx][col]);

  delay(200);
  hand->getFinger(f_idx).press_white_key(HIGH);
  delay(600);
  hand->getFinger(f_idx).press_white_key(LOW);
  hand->getFinger(f_idx).extendOrRetract(LOW);

  // Return all other fingers to equilibrium
  for (int i = 0; i < NUM_OF_FINGERS; i++)
    hand->getFinger(i).rotate(hand->getFinger(i).getEquilibriumAngle());
}

void autoTestOneFinger(int f_idx, Hand* hand, int (*current_angles)[ROT_COLS]) {
  int mid = ROT_COLS / 2;
  int col_start = (f_idx == NUM_OF_FINGERS - 1) ? 2 : 1;
  int col_end   = (f_idx == 0) ? mid + 3 : ROT_COLS - 1;

  for (int col = col_start; col < col_end; col++) {
    // Check for stop command between steps
    if (Serial.available()) {
      String input = Serial.readStringUntil('\n');
      input.trim();
      if (input[0] == 's') return;
    }

    calibrateFingers(hand, current_angles, f_idx, col, 0);
    delay(300);
  }

  hand->getFinger(f_idx).rotate(hand->getFinger(f_idx).getEquilibriumAngle());
  delay(300);

}


void autoTestFingers(Hand* hand, int (*current_angles)[ROT_COLS]) {
  int mid = ROT_COLS / 2;

  for (int f_idx = 0; f_idx < NUM_OF_FINGERS; f_idx++) {
    autoTestOneFinger(f_idx, hand, current_angles);
  }
}

void printAngles(int (*angles)[ROT_COLS]) {
  for (int i = 0; i < NUM_OF_FINGERS; i++) {
    for (int j = 0; j < ROT_COLS; j++) {
      Serial.print(angles[i][j]);
      Serial.print(",   ");
    }
    Serial.println();
  }
  Serial.println();
}

void handleSerialCalibration() {
    if (!Serial.available()) return;

    String input = Serial.readStringUntil('\n');
    input.trim();

    char cmd = input[0];

    Hand* hand;
    int (*current_angles)[ROT_COLS];

    auto selectHand = [&](char side) {
        hand           = (side == 'l') ? &left_hand : &right_hand;
        current_angles = (side == 'l') ? current_angles_left : current_angles_right;
    };

    // "p l" / "p r" - print current angle matrix
    if (cmd == 'p') {
        selectHand(input[2]);
        printAngles(current_angles);
        return;
    }

    // "t l a" / "t r a" - auto test all fingers
    // "t l 0" / "t r 0" - auto test finger of specified index
    if (cmd == 't') {
        selectHand(input[2]);
        if(input[4] == 'a'){
          autoTestFingers(hand, current_angles);        
        }
        else{
          int f_idx = input.substring(4).toInt();
          autoTestOneFinger(f_idx, hand, current_angles);
        }
        return;
    }

    // "m l 3.5" - move hand motor to key position
    if (cmd == 'm') {
        selectHand(input[2]);
        float key_pos = input.substring(4).toFloat();
        hand->moveToKey(key_pos);
        return;
    }

    // "l 2 5 -1" - manual calibration: hand, finger, col of angle matrix, delta
    selectHand(cmd);
    int first_space  = input.indexOf(' ');
    int second_space = input.indexOf(' ', first_space + 1);
    int third_space  = input.indexOf(' ', second_space + 1);

    int f_idx = input.substring(first_space + 1, second_space).toInt();
    int col   = input.substring(second_space + 1, third_space).toInt();
    int delta = input.substring(third_space + 1).toInt();

    calibrateFingers(hand, current_angles, f_idx, col, delta);
}