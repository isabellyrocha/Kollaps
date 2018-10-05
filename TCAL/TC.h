//
// Created by joao on 1/21/18.
//

#ifndef TC_H
#define TC_H


#include "Destination.h"
#include "uthash/uthash.h"

#define TXQUEUELEN 1000

#define TC_BIN "tc"
#define FIRST_HASH_MASK "0x0000ff00"
#define SECOND_HASH_MASK "0x000000ff"


#define TC_H_MIN_MASK (0x0000FFFFU)
#define TC_H_MIN(h) ((h)&TC_H_MIN_MASK)
#define TC_H_MAJ_MASK (0xFFFF0000U)
#define TC_H_MAJ(h) ((h)&TC_H_MAJ_MASK)

typedef struct {
    unsigned int handle;
    unsigned long usage;
    UT_hash_handle hh;
}Usage;


void TC_init(char* interface, short controllPort);
void TC_initDestination(Destination *dest, char* interface);
void TC_changeBandwidth(Destination *dest, char* interface);
void TC_updateUsage(char* interface);
unsigned long TC_queryUsage(Destination *dest, char* interface);

void TC_destroy(char* interface);

#endif //TC_H
