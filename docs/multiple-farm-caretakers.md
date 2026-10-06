# Multiple caretakers per farm

Run `python setup_farm_caretakers.py` before deploying the API and UI. It creates an optional string-array `caretaker_ids` attribute on the farm collection without changing existing assignments. Older farms fall back to `caretakerID`.

Admin and Super Admin farm forms select multiple active users who have the Caretaker role, including users for whom it is a secondary role. Existing assignments remain selected on edit. Farm writes require an authenticated administrator. The API validates newly added members and writes the array and its first member to the legacy `caretakerID` field together. Old clients omitting the array preserve the existing team on status updates.

All current farm caretakers can see its dashboard, calendar, IoT readings, batches and team membership, control its switches, and submit records for open batches. Record authors are taken from the authenticated account, not the submitted author fields. Removing a caretaker removes their permission to submit records or control farm switches. Completed batches continue to reject records. A batch's existing primary caretaker remains a historical/contact reference, not an exclusive permission to record work.

Farm notifications and production reminders fan out to all current caretakers. Newly added members receive assignment notifications. Personally assigned tasks and input confirmations remain addressed to their designated person.

The shared form uses a compact desktop dialog or mobile bottom sheet with fixed actions, validation and loading feedback. Errors retain the form values. Owner and farm manager team views show every assigned caretaker.
