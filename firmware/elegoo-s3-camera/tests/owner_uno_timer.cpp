// Execute the owner-modified ELEGOO timer function verbatim with fake time/motors.
// Provenance and limits: ../../UNO_ACK_REVIEW.md. No hardware interfaces.
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>
using boolean=bool;
constexpr int CMD_CarControl_TimeLimit=1,CMD_Programming_mode=2,stop_it=0;
static uint32_t now=0;
static uint32_t _millis(){return now;}
static struct {int Functional_Mode=CMD_Programming_mode;uint32_t CMD_CarControl_Millis=0;} Application_SmartRobotCarxxx0;
static uint32_t CMD_is_CarTimer=100;
static int CMD_is_CarDirection=3,CMD_is_CarSpeed=20;
static std::string CommandSerialNumber="pulse1";
static std::vector<std::string> actions;
static struct {void print(const std::string& value){actions.push_back(value);}} Serial;
static void ApplicationFunctionSet_SmartRobotCarMotionControl(int direction,int speed){assert(direction==stop_it && speed==0);actions.push_back("stop");}
static void CMD_CarControl(int,int){actions.push_back("drive");}
struct ApplicationFunctionSet {void CMD_CarControlTimeLimit_xxx0();};
#define _is_print 1
#include "fixtures/owner_uno_timer.inc"
int main(){
 ApplicationFunctionSet uno;
 Application_SmartRobotCarxxx0.CMD_CarControl_Millis=50;
 Application_SmartRobotCarxxx0.Functional_Mode=CMD_CarControl_TimeLimit;
 now=150;uno.CMD_CarControlTimeLimit_xxx0();assert(actions.back()=="drive");
 // Old ESP32 deadline150: N100 parsed160, before next UNO iteration161.
 Application_SmartRobotCarxxx0.Functional_Mode=CMD_Programming_mode;
 now=161;uno.CMD_CarControlTimeLimit_xxx0();assert(actions.size()==1);
 actions.clear();
 Application_SmartRobotCarxxx0.CMD_CarControl_Millis=200;
 Application_SmartRobotCarxxx0.Functional_Mode=CMD_CarControl_TimeLimit;
 now=300;uno.CMD_CarControlTimeLimit_xxx0();assert(actions.back()=="drive");
 now=311;uno.CMD_CarControlTimeLimit_xxx0();
 assert(actions.size()==3 && actions[1]=="stop" && actions[2]=="{pulse1_ok}");
 // Completing switches mode, so a further iteration cannot drive again.
 uno.CMD_CarControlTimeLimit_xxx0();assert(actions.size()==3);
}
