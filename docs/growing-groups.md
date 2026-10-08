# Linked growing groups

Run `python setup_growing_groups.py` before deploying. It adds optional attributes on batches and farm records, and a batch group lookup index. Existing batches and records are unchanged. Array membership queries do not need an explicit array index on the deployed Appwrite version.

Admins and the assigned farm manager create a group or join an existing group in batch creation/editing. Each group belongs to one farm and represents a room/shared water system. Batch numbers, crop types, varieties, start dates, stage plans and harvest totals remain separate. Unlinking a batch affects future records; historical records keep their membership snapshot. Completed batches cannot change group.

Caretakers select a batch, enable linked recording, and select 2–20 active members of its growing group. Daily monitoring, watering, feeding, pruning and pest control support shared recording. Transplanting, harvesting and other individual workflows retain individual records. Water/environment quantities and purchase costs are stored once in the master farm record. No per-batch record copies are created.

`batch_entries` is a JSON snapshot of each included batch's ID, number, computed growth stage, health, observations and issue details. The API checks farm membership, growing group membership, completion, record date, payload size and issue validation before any write. Group recording cannot change cumulative production totals. Each entry's stage is calculated using its own batch plan and start date. Issue notifications use the existing farm team notification policy, once per event.

The batch caretaker-record endpoint queries both individual records and shared membership. It projects the selected batch's observations and issue flags so the issues-only filter does not flag an unaffected batch. Details also show the other included batches and shared observations. Farm reports should aggregate original `/farm-records` events once, not sum projected batch logs; the batch views are for review, not financial aggregation.
