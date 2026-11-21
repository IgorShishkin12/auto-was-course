---
title: "Local types — wire protocol RE + type confusion"
category: Reverse / Pwn
host: is-course.ru:2600
tags: [protocol-reversing, type-confusion, vtable, fnv1a]
---

# Local types

## Recon
Stripped, forking TCP server (`PORT`, default 1234). Reads `flag.txt` at startup into a connection
object of 0xA8 bytes with a 10-entry vtable:

```
+0x80 fd   +0x84 seq   +0x88 seqval   +0x8c ts   +0x90 TYPE   +0x94 cksum
```

## Protocol
```
frame = u32le(len = 4 + payload) || TLV* 
TLV   = [vlen][type][value]
type 1: seq (u16)      type 2: ts (u32)
type 3: TYPE (u8)      type 4: cksum (u32)
```
All four TLVs are mandatory (otherwise the connection is dropped), and
`cksum = FNV-1a-32(frame)` computed with the checksum field itself zeroed.

## The bug
`TYPE` is dispatched into `vtable[6 + type]` with **no bounds check**, and the handlers are independent
of each other: `2 = open("flag.txt")`, `3 = lseek`, `4 = read`, `1 = echo`. The connection object is
never reset between "states", so a single connection can chain them:

```
send TYPE=2  (open flag.txt)
send TYPE=3  (lseek 0)
send TYPE=4  (read len)
send TYPE=1  (echo buffer)   -> the flag is returned in the echo frame
```

No memory corruption needed — the "local type" (the `TYPE` TLV) is trusted as a *command* while the
object's state is shared.

```bash
python3 local_types_exploit.py is-course.ru 2600
YDS{…redacted…}
```

## Takeaway
When a struct is both a *type tag holder* and a *state machine*, validating only the checksum and the
TLV set leaves the command sequence entirely attacker-controlled.
