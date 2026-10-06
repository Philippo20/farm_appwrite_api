# Multiple user roles

Deploy the API and UI together. Run `python setup_user_roles.py` before enabling assignment; it adds an optional string-array `roles` field to the users collection. The migration is idempotent and preserves existing accounts. An absent or empty array falls back to `role`.

Administrators select assigned roles and a primary role in the shared Add/Edit User form. Only a Super Admin can grant or modify accounts with Super Admin membership. User creation and full user editing require a verified administrator session; submitted actor identity fields do not authorize an operation.

Login returns the assigned roles. A single role opens its dashboard directly. Multiple roles open `/select-role`; a choice is verified at `POST /account/roles/{role}` and is saved for the local session. A fresh login asks again. The account menu allows switching workspaces without logging out. Existing first-login password-change requirements still run before workspace selection.

The UI sends `X-Active-Role` alongside its authenticated requests to the configured API origin. Authentication dependencies verify membership against the database on each request. Choosing a role never overwrites the user's primary role and does not alter sessions on other devices. Authenticated farm record access, maintenance, switch control and approvals use the selected role. Farm assignment and notification recipient lists recognise every assigned role. This feature does not replace existing farm assignment restrictions or retrofit authentication to unrelated legacy endpoints.

Validation: backend role membership/assignment and endpoint tests; Flutter login, saved session, rejected selection, responsive chooser and API header isolation tests. Never put service-account credentials in this feature's source files.
