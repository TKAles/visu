#include <Servo.h>

Servo test_servo;

void setup()
{
    Serial.begin(57600);
    Serial.print("Setting up...");
    Servo.attach(5);

}

void loop()
{
    Serial.print("Cycling Servo Forward");
    for(int i = 90; i < 181; i = i +2)
    {
        Serial.print("Servo Angle: " + String(i) + "deg");
        Servo.write(i);
        delay(50);
    }
    Serial.print("Cycling Servo Backwards");
    for(int i = 90; i > 0; i = i - 2)
    {
        Serial.print("Servo Angle: " + String(i) + "deg");
        Servo.write(i);
        delay(50);
    }
}