# Personal text sizes

All roles can open Personal text sizes in Settings or Profile. Page headings
and large values, section/card titles, body/actions and labels can be adjusted
independently from 85% to 135%. The sample preview changes immediately; the rest
of the app changes only after Save succeeds. Cancel discards edits. Reset to
default sizes is also a preview until saved. Existing device accessibility
text scaling is preserved.

The authenticated `GET /me/appearance` and `PUT /me/appearance` endpoints use the
signed-in profile ID, never a caller-supplied user ID. PUT accepts the four
numeric multipliers `headings`, `titles`, `body`, `labels` and validates them.
Run `python setup_personal_appearance.py` before deploying the API. The optional
users attribute `typography_preferences` stores JSON; missing values keep the
standard shared typography. Existing users are not modified by the migration.

Each client caches by user ID, loads preferences on login, and synchronizes
on resume and every five foreground minutes. Logging out restores default text
sizes; switching roles keeps the same account's choices. Failed saves preserve
the draft and show an error inside the modal.

# Persistent technician maintenance warnings

`GET /device-maintenance/due-reminders` derives pending work from live device
plans/history and farm tasks, scoped to the technician's assigned farms and
task assignments. It includes overdue and due-today work, excludes completed,
cancelled and future work, and advances recurring maintenance after completion.
Due dates use the same UTC day as device schedules.

A non-dismissible warning remains above the technician's pages, with View
opening Maintenance. Completion triggers an immediate refresh; other devices'
updates are picked up every 30 foreground seconds and on resume. Failed refreshes
keep the last warning until the API confirms no pending work. Logout and changing
to another role hide it. The banner consumes layout space and keeps navigation
and unfinished page input intact when it appears or disappears.
