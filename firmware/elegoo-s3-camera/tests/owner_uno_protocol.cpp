// Verbatim owner archive excerpts; provenance in fixtures/owner_uno_provenance.json.
// All acquisition, time, serial and servo interfaces below are host-only fakes.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
using boolean=bool;
static std::string CommandSerialNumber="query1";
static std::vector<std::string> actions;
static struct {
 std::string out;
 void print(const std::string& s){out+=s;actions.push_back(s);}
 void print(float value,int places){std::ostringstream s;s<<std::fixed<<std::setprecision(places)<<value;print(s.str());}
} Serial;
static uint16_t UltrasoundData_cm=0;
static bool UltrasoundDetectionStatus=false;
static int ObstacleDetection=20;
static bool function_xxx(uint16_t value,int,int limit){return value<=limit;}
static struct {uint16_t cm=42;void DeviceDriverSet_ULTRASONIC_Get(uint16_t* p){*p=cm;}} AppULTRASONIC;
static struct {float yaw=-12.34f;void MPU6050_dveGetEulerAngles(float* p){*p=yaw;}} AppMPU6050getdata;
constexpr int CMD_ServoControl=1,CMD_Programming_mode=2,PIN_Servo_z=10,PIN_Servo_y=11;
static struct {int Functional_Mode=CMD_Programming_mode;} Application_SmartRobotCarxxx0;
static uint8_t CMD_is_Servo=1;
static unsigned CMD_is_Servo_angle=95;
static struct {
 void attach(int pin){actions.push_back("attach:"+std::to_string(pin));}
 void write(unsigned angle){actions.push_back("write:"+std::to_string(angle));}
 void detach(){actions.push_back("detach");}
} myservo;
#define TimeCompensation 4
static void delay(unsigned long ms){actions.push_back("delay:"+std::to_string(ms));}
static void wdt_reset(){actions.push_back("wdt_reset");}
#include "fixtures/owner_uno_delay.inc"
struct DeviceDriverSet_Servo {void DeviceDriverSet_Servo_controls(uint8_t,unsigned);};
static DeviceDriverSet_Servo AppServo;
struct ApplicationFunctionSet {
 void CMD_UltrasoundModuleStatus_xxx0(uint8_t);
 void CMD_ServoControl_xxx0();
};
#define _is_print 1
#include "fixtures/owner_uno_ultrasonic.inc"
#include "fixtures/owner_uno_servo.inc"
#include "fixtures/owner_uno_servo_driver.inc"
static void yawQuery(){switch(24){
#include "fixtures/owner_uno_yaw.inc"
}}
static void servoDispatch(){
 struct Doc {int operator[](const char* key){return std::string(key)=="D1"?1:95;}} doc;
 switch(5){
#include "fixtures/owner_uno_servo_dispatch.inc"
 }
}
int main(){
 ApplicationFunctionSet uno;
 uno.CMD_UltrasoundModuleStatus_xxx0(2);assert(Serial.out=="{query1_42}");
 Serial.out.clear();AppULTRASONIC.cm=150;uno.CMD_UltrasoundModuleStatus_xxx0(2);assert(Serial.out=="{query1_150}");
 Serial.out.clear();uno.CMD_UltrasoundModuleStatus_xxx0(1);assert(Serial.out=="{query1_false}");
 Serial.out.clear();AppULTRASONIC.cm=10;uno.CMD_UltrasoundModuleStatus_xxx0(1);assert(Serial.out=="{query1_true}");
 Serial.out.clear();yawQuery();assert(Serial.out=="{query1_-12.34}");
 Serial.out.clear();actions.clear();servoDispatch();assert(Serial.out=="{query1_ok}");
 assert(actions.size()==1); // ACK happens before any servo operation.
 uno.CMD_ServoControl_xxx0();
 assert((actions==std::vector<std::string>{"{query1_ok}","attach:10","write:90","delay:125","wdt_reset","detach"}));
 assert(Application_SmartRobotCarxxx0.Functional_Mode==CMD_Programming_mode);
 for(unsigned angle:{20,29,90,95,159,160}){
  actions.clear();CMD_is_Servo_angle=angle;Application_SmartRobotCarxxx0.Functional_Mode=CMD_ServoControl;
  uno.CMD_ServoControl_xxx0();assert(actions[1]=="write:"+std::to_string(angle/10*10));
 }
}
