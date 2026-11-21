"""Decrypt the mario.pcap TLS1.2 ECDHE-AES256-GCM-SHA384 session using the
nginx keylog line CLIENT_RANDOM <cr> <master_secret>."""
import struct, hmac, hashlib, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PCAP = "/home/user/ctf/mario.pcap"
KEYLOG = "/home/user/ctf/mario/sslkeys.log"


def parse_pcap(fn):
    f = open(fn, "rb").read()
    off = 24
    out = []
    while off + 16 <= len(f):
        ts, tu, incl, orig = struct.unpack("<IIII", f[off:off + 16]); off += 16
        pkt = f[off:off + incl]; off += incl
        ip = pkt[14:]
        if ip[9] != 6:
            continue
        ihl = (ip[0] & 0xF) * 4
        sp, dp = struct.unpack(">HH", ip[ihl:ihl + 4])
        doff = (ip[ihl + 12] >> 4) * 4
        data = ip[ihl + doff:]
        if data:
            out.append((sp, dp, data))
    return out


def records(stream):
    i = 0
    while i + 5 <= len(stream):
        t = stream[i]
        v = stream[i + 1:i + 3]
        l = struct.unpack(">H", stream[i + 3:i + 5])[0]
        yield t, v, stream[i + 5:i + 5 + l]
        i += 5 + l


def p_hash(secret, seed, n, algo=hashlib.sha384):
    out = b""
    a = seed
    while len(out) < n:
        a = hmac.new(secret, a, algo).digest()
        out += hmac.new(secret, a + seed, algo).digest()
    return out[:n]


def prf(secret, label, seed, n, algo=hashlib.sha384):
    return p_hash(secret, label + seed, n, algo)


def main():
    pkts = parse_pcap(PCAP)
    # rebuild the two byte streams in order
    c2s = b""
    s2c = b""
    for sp, dp, d in pkts:
        if dp == 443:
            c2s += d
        else:
            s2c += d

    # client random + server random from the handshake
    hs = b""
    for t, v, p in records(c2s):
        if t == 22:
            hs += p
    client_random = hs[4 + 2:4 + 2 + 32]
    hs2 = b""
    for t, v, p in records(s2c):
        if t == 22:
            hs2 += p
    server_random = hs2[4 + 2:4 + 2 + 32]
    print("client_random", client_random.hex())
    print("server_random", server_random.hex())

    # master secret from the keylog
    master = None
    for line in open(KEYLOG, "rb").read().split(b"\n"):
        parts = line.strip().split()
        if len(parts) == 3 and parts[0] == b"CLIENT_RANDOM" and parts[1].decode() == client_random.hex():
            master = bytes.fromhex(parts[2].decode())
            break
    if master is None:
        print("no master secret found")
        return
    print("master", master.hex(), len(master))

    kb = prf(master, b"key expansion", server_random + client_random, 72)
    cw_key, sw_key = kb[0:32], kb[32:64]
    cw_iv, sw_iv = kb[64:68], kb[68:72]

    def decrypt_dir(stream, key, iv, tag):
        out = b""
        seq = 0
        started = False
        for t, v, p in records(stream):
            if t == 20:      # change_cipher_spec (plaintext)
                started = True
                continue
            if not started:
                continue
            nonce = iv + p[:8]
            aad = struct.pack(">QBHH", seq, t, v[0] * 256 + v[1], len(p) - 8 - 16)
            try:
                pt = AESGCM(key).decrypt(nonce, p[8:], aad)
            except Exception as e:
                print(" [%s] seq %d type %d FAILED: %s" % (tag, seq, t, e))
                seq += 1
                continue
            print("--- [%s] seq %d type %d len %d" % (tag, seq, t, len(pt)))
            out += pt
            seq += 1
        return out

    print("\n===== CLIENT -> SERVER plaintext")
    print(decrypt_dir(c2s, cw_key, cw_iv, "C2S").decode("utf-8", "replace"))
    print("\n===== SERVER -> CLIENT plaintext")
    print(decrypt_dir(s2c, sw_key, sw_iv, "S2C").decode("utf-8", "replace"))


main()
