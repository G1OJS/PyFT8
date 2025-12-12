const int MotorA = 10;
const int MotorB = 9;
const int RxAnt = 4;
const int MainAnt = 3;
const int TIMEOUT = 60000;

unsigned int CurrStep = 500;
int TargetStep;
String cmd = "";

void setup() {
  Serial.begin(9600);

  Serial.println("READY");
  pinMode(MotorA, OUTPUT);
  pinMode(MotorB, OUTPUT);
  pinMode(RxAnt, OUTPUT);
  pinMode(MainAnt, OUTPUT);
  getAndPrintCurrStep();
}

void motor_stop(){
  digitalWrite(MotorA, LOW);
  digitalWrite(MotorB, LOW);
}

void loop() {
  
  if (readSerialCommand()) {
    char cmd_ = cmd.charAt(0);
    if (cmd_ == 'T') {
      TargetStep = cmd.substring(1).toInt();
      Serial.print("Tune to: "); Serial.println(TargetStep);
      tuneToStep();
    }
    if (cmd_ == 'M') {digitalWrite(MainAnt, (cmd.charAt(1) == 'L') );}
    if (cmd_ == 'R') {digitalWrite(RxAnt, (cmd.charAt(1) == 'M') );}
    if (cmd_ == 'Q') {getAndPrintCurrStep();}
    if (cmd_ == 'N') {nudge(cmd.charAt(1) == 'U');}
  }
  delay(500);
}

bool readSerialCommand() {
  if (Serial.available()) {
    cmd = Serial.readStringUntil('>');     // Read until end marker
    int start = cmd.indexOf('<');
    if (start >= 0) {
      cmd = cmd.substring(start + 1);      // Strip start marker
      cmd.trim();                          // Clean up whitespace
      return true;
    }
  }
  return false;
}

void tuneToStep() {
  getAndPrintCurrStep();
  if (CurrStep < TargetStep) {
    Serial.println("TUNING UP");
    moveToTarget(true);
  } else {
    const int reverse = 5;
    TargetStep -= reverse;
    Serial.println("TUNING DOWN");
    moveToTarget(false);
    delay(250);
    TargetStep += reverse;
    Serial.println("TUNING UP (fine)");
    moveToTarget(true);
  }
  printTUNED();
}

void moveToTarget(bool directionUp) {
  int PWM = 150;
  int lastStep = CurrStep;
  unsigned long t0 = millis();
  motor_stop();
  while (true) {
    getAndPrintCurrStep();
    // Adjust speed
    if (abs(CurrStep - lastStep) < 1) {
      if (PWM < 250) PWM++;
    } else {
      if (PWM > 150) PWM--;
    }
    lastStep = CurrStep;
    // Drive motor
    if (CurrStep != TargetStep) {
      int power = (abs(CurrStep - TargetStep) > 20 || !directionUp) ? 255 : PWM;
      analogWrite(directionUp ? MotorA : MotorB, power);
    }
    // Break conditions
    if ((CurrStep >= TargetStep && directionUp) ||
        (CurrStep <= TargetStep && !directionUp) ||
        (millis() - t0 > TIMEOUT)) {
      break;
    }
  }
  motor_stop();
}

void nudge(bool directionUp){
  getAndPrintCurrStep();
  const int delta = 1;
  TargetStep = directionUp? CurrStep + delta : CurrStep - delta;
  analogWrite(directionUp? MotorA:MotorB,200) ;
  while (directionUp? analogRead(A0) < TargetStep : analogRead(A0) > TargetStep) {
    delay(directionUp? 60:30);
    motor_stop();
    delay(50);
  }
  motor_stop();
  getAndPrintCurrStep();
}

void getAndPrintCurrStep() {
  CurrStep = analogRead(A0);
  Serial.println();
  Serial.print("CurrStep ");
  Serial.println(CurrStep);
}

void printTUNED() {
  Serial.println();
  Serial.print("TUNED ");
  Serial.println(CurrStep);
}
