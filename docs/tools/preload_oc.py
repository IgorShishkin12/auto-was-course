#!/usr/bin/env python3
"""Emulate preload's obfuscated `check(u64) -> u64` with unicorn and probe its structure."""
from unicorn import *
from unicorn.x86_const import *

PATH = "/home/user/ctf/preload"
CODE = open(PATH, "rb").read()

BASE = 0
STACK = 0x300000
STACK_SZ = 0x20000
SENTINEL = STACK + 0x10
CHECK = 0x1480

mu = Uc(UC_ARCH_X86, UC_MODE_64)

def run_check(x):
    mu = Uc(UC_ARCH_X86, UC_MODE_64)
    mu.mem_map(0, 0x100000, UC_PROT_ALL)
    # load PT_LOAD segments
    for off, vaddr, fsz in [(0x0, 0x0, 0x928), (0x1000, 0x1000, 0x4c15),
                            (0x6000, 0x6000, 0x190), (0x6d90, 0x7d90, 0x280)]:
        mu.mem_write(vaddr, CODE[off:off + fsz])
    mu.mem_map(STACK, STACK_SZ, UC_PROT_ALL)
    rsp = STACK + STACK_SZ - 0x1000
    mu.mem_write(rsp, SENTINEL.to_bytes(8, "little"))
    mu.reg_write(UC_X86_REG_RSP, rsp)
    mu.reg_write(UC_X86_REG_RDI, x)
    mu.reg_write(UC_X86_REG_RBP, 0)
    mu.reg_write(UC_X86_REG_RIP, CHECK)
    mu.emu_start(CHECK, SENTINEL, count=200_000_000)
    return mu.reg_read(UC_X86_REG_RAX), mu

if __name__ == "__main__":
    import sys
    v, _ = run_check(int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x1122334455667788)
    print(hex(v))
