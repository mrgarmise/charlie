void DeviceDriverSet_Servo::DeviceDriverSet_Servo_controls(uint8_t Servo, unsigned int Position_angle)
{
  if (Servo == 1 || Servo == 3) //Servo_z
  {
    if (Position_angle <= 1) //下限控制
    {
      Position_angle = 1;
    }
    if (Position_angle >= 17) //上下限控制
    {
      Position_angle = 17;
    }
    myservo.attach(PIN_Servo_z);
    myservo.write(10 * Position_angle);
    _delay(500);
  }
  if (Servo == 2 || Servo == 3) //Servo_y
  {

    if (Position_angle <= 3) //下限控制
    {
      Position_angle = 3;
    }
    if (Position_angle >= 11) //上下限控制
    {
      Position_angle = 11;
    }
    myservo.attach(PIN_Servo_y);
    myservo.write(10 * Position_angle);
    _delay(500);
  }
  myservo.detach();
}
