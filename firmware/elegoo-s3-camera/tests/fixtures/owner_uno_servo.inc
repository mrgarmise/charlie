void ApplicationFunctionSet::CMD_ServoControl_xxx0(void)
{
  if (Application_SmartRobotCarxxx0.Functional_Mode == CMD_ServoControl)
  {
    AppServo.DeviceDriverSet_Servo_controls(/*uint8_t Servo*/ CMD_is_Servo, /*unsigned int Position_angle*/ CMD_is_Servo_angle / 10);
    Application_SmartRobotCarxxx0.Functional_Mode = CMD_Programming_mode; /*进入编程模式提示符<等待下一组控制命令的到来>*/
  }
}
