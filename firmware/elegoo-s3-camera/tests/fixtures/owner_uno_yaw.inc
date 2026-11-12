      case 24: /* Charlie: read-only MPU6050 integrated yaw */
      {
        float CharlieYaw = 0.0;
        AppMPU6050getdata.MPU6050_dveGetEulerAngles(&CharlieYaw);

        Serial.print("{");
        Serial.print(CommandSerialNumber);
        Serial.print("_");
        Serial.print(CharlieYaw, 2);
        Serial.print("}");
      }
        break;
