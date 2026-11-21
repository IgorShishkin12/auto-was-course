---
title: "Preload — OLLVM flattening beaten by linear algebra"
category: Reverse
tags: [ollvm, control-flow-flattening, emulation, gf2, unicorn]
technique: "emulate `check`, prove it GF(2)-linear, solve by elimination"
status: solved
---

# Preload

## Recon
Stripped ELF with OLLVM-style control-flow flattening: `main` is tiny (540 B), `check` is 18 KB of
dispatcher code, plus junk globals. Static deobfuscation is a trap — instead we treat `check` as a
black box.

## Structure recovered from `main`
```
fgets(buf, 0x80) -> buf[0:4] == "YDS{" -> strlen>5 -> buf[-1] == '}' -> inner length == 0x20
two inline hex decoders at 0x11d7 -> u64 v1 (chars 0..16), u64 v2 (chars 16..32)
must satisfy: check(v1) == 0x27e8db8bcd953688 && check(v2) == 0x327c085f560f96e0
```

## Emulating `check`
Map the ELF at 0 with Unicorn, give it a fake stack, and call `check(x)` for a handful of inputs:

```
f(0) = 0
f(a XOR b) == f(a) XOR f(b)      # linear over GF(2)
rank(columns) = 64               # bijective
```

So `check` is an invertible GF(2)-linear map. Build the 64×64 matrix from `f(1<<i)` and solve
`M x = target` with Gaussian elimination:

```
f^-1(0x27e8db8bcd953688) = 0x2e1111bdc74abfe4
f^-1(0x327c085f560f96e0) = 0x89314e1efcee10e0
```

Concatenating the two 16-hex-digit halves gives the flag; `./preload` prints `correct`.

Tool: `preload_oc.py` (Unicorn harness + GF(2) solver).

## Takeaway
Obfuscation that only hides *control flow* often leaves the *algebraic* structure intact. Identify the
function's mathematical class (linear? affine? permutation?) with a few oracle queries, then solve it
directly instead of reversing instruction by instruction.
