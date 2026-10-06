# Android Firebase push delivery

Android now uses Firebase Cloud Messaging alongside the existing Flutter inbox.
Firebase Analytics is not installed. Web and native desktop keep local notifications.

## Server deployment

1. Install requirements.txt (includes firebase-admin).
2. Run `python setup_push_notifications.py` once against the target Appwrite database.
   The new push_devices collection has no client permissions. Routes require the
   existing Appwrite JWT; recipients are determined by that authenticated account.
3. Configure these API environment variables:
   - `FCM_ENABLED=true`
   - `FIREBASE_PROJECT_ID=farmestatesltd-f8616`
   - `FIREBASE_SERVICE_ACCOUNT_JSON`: the complete service-account JSON, entered
     as an encrypted SECRET environment variable in the hosting dashboard.
   Alternatively mount the key file and set `GOOGLE_APPLICATION_CREDENTIALS` to
   its path. Never commit this private key or include it in the Flutter APK.
4. Redeploy the API. The Android app registers its token on login/resume and
   refreshes its binding while active. Install the new APK, sign in, and allow
   Android notification permission.

The local API .env references the supplied key in Downloads. This Windows path
cannot be used by the hosted API; configure the encrypted server secret there.
The Android google-services.json contains client configuration, not the private key.

## Behavior and limits

Newly persisted messages, workflow notifications and production reminders enqueue
FCM data messages. Background Android code checks the recipient and displays a
private generic notification. Taps reuse the app's authenticated notification/chat
navigation. Foreground alerts continue through the existing poller; delivered event
IDs prevent a second alert on resume. Signing out clears the native recipient and
attempts to unregister the device. Account switching rebinds that installation.
Invalid FCM tokens are removed; bindings unused for 30 days are skipped until renewed.
Caretaker notification/sound preferences are applied by the server before delivery.

FCM requires Google Play services and network access. Permission denial, force-stop,
manufacturer restrictions and FCM throttling can prevent immediate delivery. The
persistent inbox remains authoritative. Push sending is best effort with a bounded
in-process queue, not a durable outbox; server restarts or delivery failures may lose
a push while the inbox entry remains available. Token changes are reconciled when
the app runs again. No remote alert is guaranteed while an app is force-stopped.

## Device acceptance test

After deployment, use two test accounts on separate installations: keep the receiver
in the background or lock its phone, create a real test message, verify one alert,
tap it, then confirm no duplicate on resume. Repeat with a workflow alert, denied
permission, muted preferences, logout, account switching, and expired sessions.
Mocked tests and an APK build cannot prove delivery on a real phone.
