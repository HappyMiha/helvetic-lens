# Notes for app review

Enter these in App Store Connect (App Review Information) and Google Play
Console (App access). Fill in the demo account before submitting.

- Demo account: `<email>` / `<password>` (an account with a few monitored
  sources so the feed, registry and comparisons have content)
- The app requires an account; registration and account deletion are both
  available in the app (Account → "Delete my account"), as Apple guideline
  5.1.1(v) requires.
- The app uses no tracking, no advertising identifiers, and no device
  permissions beyond network access.

## App privacy answers (Apple) / Data safety (Google)

Based on what helveticlens.ch processes; confirm before submitting.

| Data | Collected | Purpose | Linked to user | Tracking |
| --- | --- | --- | --- | --- |
| Email address | Yes | Account, email digests | Yes | No |
| Name / organization name | Optional | Account | Yes | No |
| User content (watchlists, uploaded documents, questions) | Yes | App functionality | Yes | No |
| Diagnostics, location, contacts, identifiers | No | | | |

Data is encrypted in transit (HTTPS). Users can delete their account in the app.

## Risk: Apple guideline 4.2 (minimum functionality)

Apple sometimes rejects apps that mainly display a website. The app's native
offline handling, deep links and in-app browser help, but the strongest
argument would be native push notifications for new changes on a user's
topics. That needs a small server addition (device registration and sending)
and is the recommended next step if review pushes back.
