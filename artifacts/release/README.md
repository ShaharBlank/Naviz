# Naviz Android releases

## 0.1.0 (version code 1)

- File: `Naviz-0.1.0-preview.apk`
- Size: 146,784,504 bytes
- SHA-256: `46F31E7CFE4FC0760CF7B345FEFD9C55782046AEE1B391E3CC4B11D7EF96A08B`
- Package: `app.naviz.mobile`
- Expo SDK: 56
- Build profile: `preview` (internal distribution)
- Build ID: `d1adae85-ba7f-46c2-98c7-9de1e8b71860`
- Source commit: `7cfa1629e47f08844914ecac866d3520316950ea`
- Backend embedded at bundle time: <https://naviz-api.onrender.com>
- Build page:
  <https://expo.dev/accounts/shaharblank/projects/naviz/builds/d1adae85-ba7f-46c2-98c7-9de1e8b71860>

Local verification confirmed the ZIP/APK magic, Android manifest, JavaScript
bundle, exact expected byte size, modern Android APK signing block, and embedded
production backend URL. The
API-specific `http://localhost:8000` and `http://10.0.2.2:8000` fallbacks are not
present in the release bundle. Expo's Android build completed successfully using
its managed remote signing credentials; no private signing material is stored in
this repository.

Version 0.1.0 is superseded by the metropolitan 0.2.0 build. The new build uses
the hosted regional provider profile; deterministic fixtures remain CI-only.
