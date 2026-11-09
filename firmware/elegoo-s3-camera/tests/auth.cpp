#include "../ElegooS3Camera/AuthPolicy.h"
#include <cassert>
#include <string>
int main(){assert(confirmOnTarget(2,2,1));assert(!confirmOnTarget(1,2,1));assert(!confirmOnTarget(1,1,1));assert(!confirmOnTarget(0,0,1));char token[65]{};for(unsigned i=0;i<43;++i)token[i]=char('a'+i%26);
 const char* transaction="0123456789abcdef0123456789abcdef";
 assert(completedReceipt(true,true,true,transaction,transaction));
 assert(!completedReceipt(true,true,false,transaction,transaction));
 assert(!completedReceipt(false,true,true,transaction,transaction));
 assert(!completedReceipt(true,true,true,transaction,"stale"));
 char header[80]{};strcpy(header,(std::string("Bearer ")+token).c_str());assert(validBearer(header,token));
 for(unsigned i=7;i<50;++i){const char original=header[i];header[i]='!';assert(!validBearer(header,token));header[i]=original;}
 header[49]=0;assert(!validBearer(header,token));
 strcpy(header,(std::string("Bearer ")+token+"x").c_str());assert(!validBearer(header,token));
 strcpy(header,(std::string("Basic ")+token).c_str());assert(!validBearer(header,token));
 memset(header,'x',sizeof(header));assert(!validBearer(header,token));}
