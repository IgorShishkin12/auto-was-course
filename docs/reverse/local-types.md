---
title: "Local types — wire protocol RE + type confusion"
category: Reverse / Pwn
host: is-course.ru:2600
tags: [protocol-reversing, type-confusion, vtable, fnv1a]
technique: "unchecked `TYPE` dispatch into a shared connection state"
status: solved
---

# Local types

## Recon
Stripped, forking TCP server (`PORT`, default 1234). Reads `flag.txt` at startup into a connection
object of 0xA8 bytes with a 10-entry vtable:

```
+0x80 fd   +0x84 seq   +0x88 seqval   +0x8c ts   +0x90 TYPE   +0x94 cksum
```

<svg viewBox="0 0 760 170" width="100%" role="img" aria-label="local_types frame format">
<g font-family="ui-monospace,monospace" font-size="12">
  <rect x="0" y="20" width="120" height="34" rx="7" fill="#1a2230" stroke="#232c3a"/>
  <text x="10" y="42" fill="#e6edf3">u32 len</text>
  <g fill="#141a23" stroke="#232c3a">
    <rect x="128" y="20" width="88" height="34" rx="7"/><rect x="222" y="20" width="88" height="34" rx="7"/>
    <rect x="316" y="20" width="88" height="34" rx="7"/><rect x="410" y="20" width="88" height="34" rx="7"/>
  </g>
  <g fill="#e6edf3">
    <text x="138" y="42">1 seq</text><text x="232" y="42">2 ts</text><text x="326" y="42">3 TYPE</text><text x="420" y="42">4 cksum</text>
  </g>
  <text x="510" y="42" fill="#6e7681">← all four mandatory</text>
  <text x="0" y="82" fill="#8b949e">cksum = FNV-1a-32 over the frame with the cksum field zeroed</text>
  <text x="0" y="106" fill="#f0883e">dispatch: vtable[6 + TYPE] with no bounds check</text>
  <text x="0" y="130" fill="#7ee787">TYPE=2 open(flag.txt) → TYPE=3 lseek → TYPE=4 read → TYPE=1 echo ⇒ flag in the echo frame</text>
  <text x="0" y="152" fill="#6e7681">the connection object is shared between "commands", so state from one handler survives into the next</text>
</g></svg>

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
