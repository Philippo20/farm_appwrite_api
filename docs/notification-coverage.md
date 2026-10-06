# Notification event coverage

The shared Flutter notification host delivers persisted recipient notifications
locally on Android, Windows and supported web browsers. Android also supports
FCM background delivery with the private push_devices registry and server
credentials described in [Android push setup](android-push.md). Deploy the API
and UI together: notification reads and read receipts now require the signed-in
user's Bearer token and reject requests for other recipients.

| Event | Recipients | Source |
| --- | --- | --- |
| Incoming chat | Message recipient | Existing persistent messages |
| Task assignment, updates, completion, cancellation | Assignee / assigning manager | Existing farm task actions |
| Task due today / overdue | Assignee and assigning manager | Operational reminder worker |
| Input confirmation and decision | Existing workflow recipients | Input confirmations |
| New fund request | Admins and accountant | Successful fund request audit |
| Fund decision / disbursement | Requesting user | Status transition |
| Withdrawal request | Owner, admins and accountant | Successful withdrawal audit |
| Farm assignment | Newly assigned member | Successful farm create/update audit |
| New account / account role or approval change | Admins / affected active user | Successful user audit |
| Batch creation, production or delivery status changes | Assigned farm team | Batch actions and audits |
| Caretaker issues, including daily monitoring without batch progress | Farm team and admins | Successful farm record audit |
| Growth stages, harvest, staggered batch dates | Admins, farm manager and caretaker | Existing production reminder worker |
| Maintenance assignment / plan change | Assigned technician | Device save |
| Maintenance due soon (7 days), due today, overdue | Assigned technician and admins | Operational reminder worker |
| Maintenance completed | Farm team and admins | Successful completion |
| Sensor enters/exits configured range | Farm team and admins | Ingested reading crossing inclusive low/high limits |
| Persisted unresolved farm alert | Farm team and admins | Operational reminder worker |
| Low stock, out of stock, expired stock status | Farm team and admins | Inventory transition |
| Fulfillment inspection, release and packaging completion | Existing fulfillment/packaging recipients | Existing fulfillment workflows |
| Driver assignment, delivery changes and handover | Existing assigned sales/delivery recipients | Existing sales workflows |
| Off-taker request and review | Existing sales recipients | Existing off-taker workflows |
| Backup and restore completion | Super admin | Successful backup/restore audit |

New event rules are explicit in `workflow_notifications.py`. Ordinary field
edits, reads, exports and telemetry samples staying in the same range do not
create repeated alerts. Deterministic notification IDs suppress duplicate
reminder passes and equivalent retried transitions. Recipient resolution drops
missing/unassigned identities and inactive accounts. Events never include
passwords, API keys, payment account details or raw audit payloads.

Operational reminders run every five minutes alongside production reminders,
including when no batch has a production plan. The API must remain running.
Existing unresolved alerts are converted into recipient inbox records on the
first pass. New alert creation requires a real `farmID` instead of generating
an unrelated ID. Existing sensor offline indicators are not themselves
persisted alerts; this change does not invent connectivity incidents from
stale dashboard data. Weather warnings likewise require a backend weather
alert source, which this project does not currently provide.

New business events use local/in-app delivery, without enabling additional
email categories. Existing email-producing workflows retain their email
behavior. Caretaker chat/task/anomaly and sound preferences are returned with
inbox records and control presentation; muted items remain in the inbox.

Notification persistence errors are logged and do not undo a saved business
action. Deadline and persisted-alert workers retry on the next pass. Immediate
business transitions are best effort; there is no transactional outbox yet.
Catalog edits and failure-only backup jobs are not converted into synthetic
success notifications.
