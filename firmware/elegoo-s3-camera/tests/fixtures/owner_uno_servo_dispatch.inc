      case 5:                                                             /*<命令：N 5> */
        Application_SmartRobotCarxxx0.Functional_Mode = CMD_ServoControl; /*编程控制舵机*/
        CMD_is_Servo = doc["D1"];
        CMD_is_Servo_angle = doc["D2"];
#if _is_print
        Serial.print('{' + CommandSerialNumber + "_ok}");
#endif
        break;
