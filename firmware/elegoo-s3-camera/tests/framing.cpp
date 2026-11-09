#include "../ElegooS3Camera/FrameParser.h"
#include <cassert>
#include <string>
using charlie_elegoo::FrameParser;
static auto parse(FrameParser& parser,const std::string& input,uint32_t now=0){auto result=FrameParser::Result::Partial;for(char c:input)result=parser.feed(c,now);return result;}
int main(){FrameParser p;
 assert(parse(p,"noise{Heartbeat}")==FrameParser::Result::Complete);assert(!strcmp(p.frame(),"{Heartbeat}"));
 assert(parse(p,"{\"N\":3, \"S\":\"a } b\"}")==FrameParser::Result::Complete);assert(!strcmp(p.frame(),"{\"N\":3,\"S\":\"a } b\"}"));
 assert(parse(p,"{\"N\":{\"x\":2}}")==FrameParser::Result::Complete);
 assert(parse(p,"{"+std::string(256,'x'))==FrameParser::Result::Error);
 assert(parse(p,"{{{{{{{{{")==FrameParser::Result::Error);
 parse(p,"{",0xfffffff0);assert(!p.expired(20));assert(p.expired(600));p.reset();
 assert(parse(p,std::string("{x\0}",4))!=FrameParser::Result::Complete);
}
