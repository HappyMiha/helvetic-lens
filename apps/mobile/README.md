# Helvetic Lens mobile app

Android and iOS app for [helveticlens.ch](https://helveticlens.ch), built with
Expo (React Native). The app is a native shell around the live site, so every
section, language and account feature works exactly as on the web without a
second implementation to maintain. The shell adds what a browser tab lacks:

- its own icon, splash screen and full-screen dark chrome;
- an offline and "site unreachable" screen with a retry button (EN/DE/FR/IT);
- links to other sites (Fedlex, courts, sources) open in an in-app browser,
  and mail/phone links open the system app, so the session never leaves the site;
- Android back button and iOS swipe navigate the site's history;
- `helveticlens://<path>` deep links open that page of the site;
- pull to refresh, and recovery when the system kills the web view.

Sign-in uses the site's own session cookies; nothing is stored by the app itself.

## Layout

| Path | Purpose |
| --- | --- |
| `App.tsx` | The shell: web view, failure screen, back/deep-link handling |
| `src/navigation.ts` | Which URLs stay in the app, which open outside, deep-link mapping |
| `src/copy.ts` | Text for the native screens |
| `app.json` | Name, bundle id `ch.helveticlens.app`, icons, splash, permissions |
| `eas.json` | Cloud build and store-submission profiles |
| `store/` | Store listing text, privacy-policy draft, review notes |

This folder is a standalone npm project. It is not part of the root workspace
and nothing in it is deployed to the server.

## Develop

```sh
cd apps/mobile
npm ci
npm run check        # typecheck + URL-rule tests
npx expo start       # scan the QR code with Expo Go on a phone
```

## Build

Pull requests that touch `apps/mobile` build an installable Android APK in
GitHub Actions (`Mobile app` workflow); download it from the run's artifacts.
That APK is signed with a development key and is for testing only.

Store builds run in Expo's cloud, which also builds iOS without a Mac:

```sh
npm install -g eas-cli
eas login
eas init                       # links the project to the Expo account, once
eas build --profile preview    # internal test builds (APK + iOS ad hoc)
eas build --profile production # signed store builds (AAB + IPA)
```

EAS creates and keeps the signing keys. Version numbers are kept remotely and
increase on every production build.

## Release checklist

1. **Accounts:** Apple Developer Program (99 USD/year), Google Play Console
   (25 USD once), Expo (free). An organization account in either store needs
   a D-U-N-S number.
2. **Privacy policy:** publish `store/PRIVACY_POLICY.md` (after review) at a
   public URL such as `https://helveticlens.ch/privacy`.
3. **Store listings:** copy text from `store/LISTING.md`, and take screenshots
   from a phone or simulator (iPhone 6.9", iPad 13" if tablets stay enabled,
   Android phone).
4. **Review access:** create a demo account for the reviewers and enter it in
   App Store Connect and Play Console (see `store/REVIEW_NOTES.md`).
5. **Google Play:** new personal developer accounts must run a closed test
   with at least 12 testers for 14 days before production access.
6. **Submit:** `eas submit --platform ios` / `eas submit --platform android`.
   The Android profile uploads to the internal track as a draft.
