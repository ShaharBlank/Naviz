# Naviz Android releases

## 0.5.3 Israel preview (version code 10)

- File: `Naviz-0.5.3-israel.apk`
- Size: 158,029,847 bytes
- SHA-256: `6D278B107933F74673C5ABE50EC7BEB192C3739D55451C5DF0DE7C3942858673`
- Package: `app.naviz.mobile`
- Android SDK: minimum 24, target 36
- Expo SDK: 57
- Source commit: `8a39c78bfae7c39a588341b540a6313a927df521`
- Backend embedded at bundle time: <https://naviz-api.onrender.com>
- Backend image pinned on Render:
  `ghcr.io/shaharblank/naviz-api:9c911a909c05eee4a0369c6c188999a96d1b3ae6`
- CI: <https://github.com/ShaharBlank/Naviz/actions/runs/34932749284>

This universal APK contains ARM64, ARMv7, x86, and x86_64 native libraries and
passes APK Signature Scheme v2 verification. It is signed with the local Android
debug certificate for direct installation and field testing, not Play Store
distribution; signer certificate SHA-256:
`FAC61745DC0903786FB9EDE62A962B399F7348F0BB6F899B8332667591033B9C`.

Version 0.5.3 adds a non-current starting point and a single modern trip-time
control with Leave now, Depart at, and Arrive by. Trip times are pinned to
`Asia/Jerusalem` even when the device is in another time zone. Emulator QA used
a GMT Android 16 Pixel and verified that selecting 12:00 remains 12:00, the
compact card does not truncate the time, and an arrive-by request from HaYarkon
168 returns hosted road alternatives that all arrive at 12:00. The validated
comparison showed Fastest with 11 signals and Fewer Lights with 9 signals, and
the pitched 3D preview remained stable. Native and React Native crash logs were
clean. Mobile gates passed strict TypeScript, ESLint, and 45 Jest tests; the
final source CI passed.

## 0.5.2 Israel preview (version code 9)

- File: `Naviz-0.5.2-israel.apk`
- Size: 157,854,663 bytes
- SHA-256: `AADED4EDD9C3F44688C4D7386705464599E881A00806253AB672F57D5A8EC2F6`
- Package: `app.naviz.mobile`
- Android SDK: minimum 24, target 36
- Expo SDK: 57
- Source commit: `a42efd894804d700ec8e846c9c3bd0d3652abed2`
- Backend embedded at bundle time: <https://naviz-api.onrender.com>
- Backend image pinned on Render:
  `ghcr.io/shaharblank/naviz-api:a42efd894804d700ec8e846c9c3bd0d3652abed2`
- EAS mirror build:
  <https://expo.dev/accounts/shaharblank/projects/naviz/builds/36a1a248-c1e4-48ce-900e-16cc57cda92a>
- CI: <https://github.com/ShaharBlank/Naviz/actions/runs/34860729773>
- Container publication:
  <https://github.com/ShaharBlank/Naviz/actions/runs/34860729722>

This universal APK contains ARM64, ARMv7, x86, and x86_64 native libraries. Its
Hermes bundle contains the production API URL exactly once and contains neither
the localhost nor Android-emulator Naviz API fallback. APK Signature Scheme v2
verification passes. It is signed with the local Android debug certificate for
direct installation and field testing, not Play Store distribution; signer
certificate SHA-256:
`FAC61745DC0903786FB9EDE62A962B399F7348F0BB6F899B8332667591033B9C`.

The exact release APK was clean-installed on an Android 16 Pixel emulator and
run with Metro stopped against API `0.3.1` on Render. Validation covered fresh
location acquisition, richer live place search, distinct midday walking route
alternatives, traffic-signal route metrics, preview, active pitched navigation,
the heading-aware no-circle walking avatar, synthetic GPS progress from 750 m to
360 m, maneuver changes, and arrival at 0 m. Native and React Native crash logs
remained clean. Backend release gates passed 88 pytest tests plus Ruff and mypy;
mobile gates passed strict TypeScript, ESLint, and 37 Jest tests.

## 0.5.1 Israel preview (version code 8)

- File: `Naviz-0.5.1-israel.apk`
- Size: 151,504,156 bytes
- SHA-256: `A29DD9A14E421B69BD845F2567C02B610884B7FA53EB2BCA3EABDCDE65C126F0`
- Package: `app.naviz.mobile`
- Android SDK: minimum 24, target 36
- Expo SDK: 57
- Backend embedded at bundle time: <https://naviz-api.onrender.com>

This universal APK contains ARM64, ARMv7, x86, and x86_64 native libraries. Its
Hermes bundle contains the production API URL exactly once and contains no
localhost API URL. APK Signature Scheme v2 verification passes. It is signed
with the local Android debug certificate for direct installation and field
testing, not Play Store distribution; signer certificate SHA-256:
`FAC61745DC0903786FB9EDE62A962B399F7348F0BB6F899B8332667591033B9C`.

An equivalent x86_64-only build was clean-installed on an Android 16 Pixel
emulator and exercised against the deployed backend. Validation covered
automatic foreground-location acquisition, live Tel Aviv GPS injection,
nationwide Haifa search, a successful 94.2 km Tel Aviv-to-Haifa driving route,
route comparison with traffic-light counts, and active navigation. The 3D
navigation run included extruded buildings, route rendering, a heading-aware
vehicle marker, synthetic GPS progress, and repeated live 2D/3D switching. The
native and React Native crash logs remained clean. The intercity test also found
a server-side signal-enrichment performance defect; the corresponding source
release fixes it and includes a real-bundle regression benchmark.

## 0.5.0 Israel preview (version code 7)

- File: `Naviz-0.5.0-israel.apk`
- Size: 148,432,770 bytes
- SHA-256: `E3D6B1C047173795ABC14D6432489279F908F65C83CA2F97686F53231A6A37B6`
- Package: `app.naviz.mobile`
- Android SDK: minimum 24, target 36
- Expo SDK: 57
- Backend embedded at bundle time: <https://naviz-api.onrender.com>

This universal local release build contains all four Android native
architectures. Verification confirmed version `0.5.0`, version code `7`, the
production API URL, absence of emulator/localhost API URLs, and a valid APK v2
signature. It is signed with the local Android debug certificate, so it is
installable for preview and field testing but is not a Play Store release
artifact. The hosted backend must be upgraded from metropolitan API `0.2.0` to
the nationwide API `0.3.0` before this build can provide nationwide behavior.
The signer certificate SHA-256 is
`FAC61745DC0903786FB9EDE62A962B399F7348F0BB6F899B8332667591033B9C`.
Emulator validation covered clean installation, hosted search and routing,
walking and driving 3D navigation, direction-aware person/vehicle markers,
synthetic GPS progress, and ten repeated live 2D/3D switches without a native
or JavaScript crash.

## 0.4.0 (version code 6)

- File: `Naviz-0.4.0-metropolitan.apk`
- Size: 148,408,034 bytes
- SHA-256: `B7E7E558E5736580EA3C62AE80B2DB606F076AF66DC6B5F2C2369842D6C3CED3`
- Package: `app.naviz.mobile`
- Android SDK: minimum 24, target 36
- Expo SDK: 57
- Build profile: `preview` (internal APK distribution)
- Build ID: `b63f768f-ad39-4cc0-89e5-36477836675f`
- Source commit: `703ff4e211f2c04e4f5e1132a54e2b1887061a80`
- Backend embedded at bundle time: <https://naviz-api.onrender.com>
- Backend image pinned on Render:
  `ghcr.io/shaharblank/naviz-api:703ff4e211f2c04e4f5e1132a54e2b1887061a80`
- Build page:
  <https://expo.dev/accounts/shaharblank/projects/naviz/builds/b63f768f-ad39-4cc0-89e5-36477836675f>
- CI:
  <https://github.com/ShaharBlank/Naviz/actions/runs/32049700971>
- Container publication:
  <https://github.com/ShaharBlank/Naviz/actions/runs/32049700964>

Local verification confirmed the manifest, version, all four Android native
architectures, location/background permissions, production API URL, and APK v2
signature. `apksigner` reports the same RSA-2048 release signer as prior builds,
with certificate SHA-256
`0A982BB78F2E1223947EE210431522DD8011CC98B03650D6F57B3C22795673CE`.
The exact APK was clean-installed on an Android 16 Pixel emulator and exercised
against the commit-pinned Render backend. Device validation covered complete
multiline combined-mode labels, automatic selector collapse, route-preference
comparison, total traffic-light counts, live GPS progress, three-fix reroute
hysteresis, recalculation, background-location handling, and arrival.

## 0.3.1 (version code 5)

- File: `Naviz-0.3.1-metropolitan.apk`
- Size: 148,404,890 bytes
- SHA-256: `E354F69307389A659FC2971666889567CD154C5C85AC6DC74710242D2A49F118`
- Package: `app.naviz.mobile`
- Android SDK: minimum 24, target 36
- Expo SDK: 57
- Build profile: `preview` (internal APK distribution)
- Build ID: `be90e304-e999-463c-9f53-b6364c519c2c`
- Source commit: `ae6f5d3fa46d6de8f668efe0e43c1fe97713bbf0`
- Backend embedded at bundle time: <https://naviz-api.onrender.com>
- Build page:
  <https://expo.dev/accounts/shaharblank/projects/naviz/builds/be90e304-e999-463c-9f53-b6364c519c2c>
- CI:
  <https://github.com/ShaharBlank/Naviz/actions/runs/32004099712>

Local verification confirmed the manifest, version, all four Android native
architectures, location/background permissions, production API URL, corrected
bilingual shared-mobility messaging, and APK v2 signature. `apksigner` reports
one RSA-2048 signer with certificate SHA-256
`0A982BB78F2E1223947EE210431522DD8011CC98B03650D6F57B3C22795673CE`.
The exact APK was clean-installed on an Android 16 Pixel emulator and exercised
against the deployed backend for GPS permissions, route comparison, active and
background navigation, progress, rerouting, and live Dott/transit presentation.

## 0.2.0 (version code 2)

- File: `Naviz-0.2.0-metropolitan.apk`
- Size: 146,856,462 bytes
- SHA-256: `02FF47614ABC3DF33DE21D8970828F2D2A617F448170F9A3CF8A3378AD20A8CD`
- Package: `app.naviz.mobile`
- Android SDK: minimum 24, target 36
- Expo SDK: 56
- Build profile: `preview` (internal APK distribution)
- Build ID: `89413540-34e6-4894-88a8-12f360f39d60`
- Source commit: `ad4c43532eb91f237b10af6afeb2bf8de577e4ce`
- Backend embedded at bundle time: <https://naviz-api.onrender.com>
- Build page:
  <https://expo.dev/accounts/shaharblank/projects/naviz/builds/89413540-34e6-4894-88a8-12f360f39d60>

Local verification confirmed the manifest, all four Android native architectures,
location/background permissions, Hermes bundle, production API URL, and APK v2
signature. The API-specific localhost fallbacks are absent. `apksigner` reports
one RSA-2048 signer with certificate SHA-256
`0A982BB78F2E1223947EE210431522DD8011CC98B03650D6F57B3C22795673CE`.

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
