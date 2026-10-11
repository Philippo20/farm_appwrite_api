# Farm-owner purchase revenue

Run `python migrate_farm_purchase_pricing.py` before deploying the API. It adds
optional `owner_price_tier` (Regular/Bulk, default Regular) to pricing and
`farm_purchase` (4096-character JSON) to fulfillment. It does not change receipts.

In Admin or Super Admin pricing, choose Regular or Bulk for a farm purchase price.
Admin navigation now includes Pricing on desktop and mobile. Purchase price
changes require an authenticated Admin or Super Admin; Sales Manager retains
access to hub sale prices and cannot overwrite farm purchase prices.
The selected active price is matched by registered farm, plant type and variety.
An exact variety takes precedence over a general crop price. Conflicting active
prices leave a receipt awaiting pricing rather than choosing an arbitrary rate.

At accepted intake, the API saves the price ID, tier, unit, accepted quantity,
unit rate, cedi revenue, accepted weight/heads and capture timestamp on the receipt.
Revenue is quantity multiplied by rate, rounded to two decimal places. Kilograms,
grams and heads are supported; intake does not measure crates, boxes or bunches.
Existing purchase prices in those units must be corrected before use.

Saved valuations never follow later price changes. Accepted quantity, farm and
batch cannot be changed after valuation; a 409 response protects the saved value.
Hub selling prices and off-taker sales remain independent. Revenue means earned
purchase value, not confirmation that the farm owner has received payment.

Older accepted receipts appear as Awaiting pricing and contribute zero until an
administrator explicitly selects **Value existing receipts awaiting pricing**
when saving the appropriate price. This applies the current chosen rate, not an
inferred historical rate. Already valued receipts and duplicate batch receipts
are skipped. The response reports valued/pending counts; unresolved prices or
missing quantities remain pending. Owner dashboards, analytics, reports and
wallet revenue use saved farm purchase receipts.

# Farm task deletion

Admin and Super Admin farm details include Farm tasks. Only an authenticated
active administrator role may delete a task. Farm managers retain task updates
but no delete action. Device maintenance schedules are unchanged.

Before deletion, the API saves a Pending audit entry with the authenticated
administrator, task identity, farm, assignee and request IP. Audit storage failure
prevents deletion. The entry becomes Success after deletion, or Failed if the
delete fails. A failure to finalize the audit leaves a durable Pending entry and
returns an explicit warning. The assignee receives the existing task-removal
notification after successful deletion. No audit schema migration is required.
