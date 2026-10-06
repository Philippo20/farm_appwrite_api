# Plant growth and staggered production

Run `python migrate_production_plans.py` before deploying this API and the matching Flutter app. The migration adds optional `production_plan` JSON strings to plant types and batches and allows the `days` maturity unit. It does not modify existing documents.

Plant types can optionally define 1–20 ordered stages, each with a name and duration in days. Their total duration is the expected maturity. Staggered production is independent: without custom stages it snapshots the plant's maximum maturity value and unit (days, weeks, or calendar months), preserving the catalog maturity range. Calendar-month dates clamp to the last valid day of the target month. A positive `interval_days` enables staggered production (14 means separate batches every two weeks); zero disables it. `reminder_days` configures advance notice, from 0 to 30 days and shorter than an enabled production interval.

New batches snapshot the selected plant's plan on the server. Their expected harvest is calculated from their start date plus the saved maturity duration (or the sum of stage durations), regardless of the date submitted by an older client. Changing a batch start recalculates dates from its snapshot. Changing the catalog or crop variety does not replace an existing batch's snapshot. Legacy batches without a plan retain their existing behavior. Dates are planning estimates, not observed growth or actual harvest records.

While the API is running, its lifespan worker checks reminders every five minutes. It saves in-app notifications for active admins/superadmins and the farm's currently assigned manager and caretaker. It does not send email or Android push notifications. The app notification badge refreshes every minute while foregrounded and on resume.

Growth-stage transitions and expected harvest have upcoming/due/overdue notices. Completed, delivered, or harvested batches no longer produce stage or harvest reminders. Next-batch reminders remain until a newer batch exists for the same farm and plant type. The newest batch starts the next interval. Different farms and plant types are independent; crop varieties share their plant-type cadence.

Deterministic notification IDs prevent duplicates across retries and multiple workers. Each event can generate one advance, one due-day, and one overdue notification; old notifications remain as history. Checks after downtime catch currently applicable and overdue events. No batches are created automatically.

Validation: `python -m unittest tests.test_production_planning`.
