---
title: "simple — straight-line comparison checker"
category: Reverse
artifact: simple (ELF x86-64, not stripped)
---

# simple

## Recon
```bash
$ file simple
ELF 64-bit LSB executable, x86-64 ... with debug_info, not stripped
$ ./simple
Enter flag:
```
`main` is one long straight-line checker: `fgets` → `strcspn("\n")` → **`strlen == 0x2d`** (45 characters,
exactly `YDS{` + 40 hex + `}`) followed by a chain of

```
movzbl -0x7b(%rbp),%eax     ; byte 21 of the buffer
cmp    $0x64,%al
jne    <incorrect>
```

## Solving
Because the binary is not stripped and the comparisons are constant-time-free, the flag falls out of the
disassembly: every `cmp $imm` against `buffer[i]` is one known plaintext byte. Extract the pairs
(`offset, imm`) from `objdump -d ./simple` and reassemble the string.

```bash
objdump -d --no-show-raw-insn simple | sed -n '/<main>:/,/^$/p' \
 | grep -E 'movzbl|movb.*\$0x' -A1
```

Equivalently: run it under gdb, break on the branch, or patch each `jne` to a `nop` and read the
`correct` path — but with the constants visible there is nothing to patch.

## Takeaway
Debug symbols + `cmp`-per-byte is the "read the answer off the listing" tier of reversing. Always start
with `file`, `strings`, `nm`, and a quick `objdump` of `main` before reaching for a decompiler.
