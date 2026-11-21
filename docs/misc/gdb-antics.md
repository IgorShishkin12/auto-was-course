---
title: "gdb — anti-debug + self-decrypting payload"
category: Reverse
artifact: gdb (22 KB ELF)
tags: [anti-debug, ptrace, ld-preload, unpacking]
technique: "anti-debug tricks bypassed"
status: solved
---

# gdb

## Behaviour
The binary refuses to run under a debugger (`ptrace` based anti-debug) and never exposes the flag in
its static image: a compressed/encrypted blob is decoded at runtime and copied into an anonymous
mapping before being executed/checked. `strings` shows nothing useful.

## Bypass
Instead of fighting the debugger, hook libc with `LD_PRELOAD` (`hook.c`):

```c
long ptrace(int req, ...) { return 0; }              // neuter anti-debug

void *mmap(void *a, size_t l, int p, int f, int fd, off_t o) {
    void *r = real_mmap(a,l,p,f,fd,o);
    g_map = r; g_len = l;                             // remember the mapping
    return r;
}

void *memcpy(void *d, const void *s, size_t n) {      // snapshot the unpacked blob
    if (g_map && d >= g_map && d < g_map + g_len) {
        fwrite(s, 1, n, fopen("/tmp/blob.bin","wb"));
        fprintf(fopen("/tmp/blob.meta","w"), "len=%zu\n", n);
    }
    ...
}
```

```bash
gcc -shared -fPIC -o hook.so hook.c -ldl
LD_PRELOAD=./hook.so ./gdb
# /tmp/blob.bin now holds the decrypted payload
```

The dumped blob is then analysed statically (it contains the flag material / the real check).

## Takeaway
Anti-debugging is a speed bump, not protection: if the program must decrypt itself to run, the plaintext
must exist in memory. Intercepting `memcpy` into a fresh `mmap` is a debugger-free way to obtain it.
