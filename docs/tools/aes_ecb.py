import requests, re, sys
from concurrent.futures import ThreadPoolExecutor
URL="https://aes.is-course.ru/"
S=requests.Session()
def enc(inp: bytes) -> bytes:
    r=requests.post(URL, data={"userinput": inp.decode("latin1")}, timeout=20)
    hs=re.findall(r'\b[0-9a-f]{32,}\b', r.text)
    return bytes.fromhex(hs[-1])
BS=16
def blocks(b): return [b[i:i+BS] for i in range(0,len(b),BS)]
ALPHA=bytes(range(32,127))
def recover(n_target):
    known=b""
    pool=ThreadPoolExecutor(max_workers=16)
    for i in range(n_target):
        prefix=b"A"*(BS-1-(i%BS))
        target=blocks(enc(prefix))[i//BS]
        tail=(prefix+known)[-15:]
        cands=[bytes([c]) for c in ALPHA]
        def test(c):
            p=tail+c
            try:
                return c, blocks(enc(p))[0]==target
            except Exception:
                return c, False
        found=None
        for c,ok in pool.map(test, cands):
            if ok: found=c; break
        if found is None:
            # fallback: full byte range
            def test2(c):
                p=tail+bytes([c])
                return bytes([c]), blocks(enc(p))[0]==target
            for c,ok in pool.map(test2, [x for x in range(256)]):
                if ok: found=c; break
        if found is None:
            print("\n[!] stuck at byte", i, "known so far:", known); return known
        known+=found
        try:
            print("\r"+known.decode('latin1','replace'), end="", flush=True)
        except Exception: pass
    return known
if __name__=="__main__":
    n=int(sys.argv[1]) if len(sys.argv)>1 else 112
    out=recover(n)
    print("\nRESULT:", out)
