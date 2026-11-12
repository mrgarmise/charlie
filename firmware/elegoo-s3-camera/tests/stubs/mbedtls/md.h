#pragma once
#include <cstddef>
extern "C" {
struct mbedtls_md_info_t;
const mbedtls_md_info_t* mbedtls_md_info_from_string(const char*);
int mbedtls_md_hmac(const mbedtls_md_info_t*,const unsigned char*,size_t,const unsigned char*,size_t,unsigned char*);
}

