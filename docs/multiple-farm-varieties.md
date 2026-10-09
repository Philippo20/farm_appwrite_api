# Multiple crop varieties per farm

In the Admin and Super Admin farm editor, choose a plant type and tick all
varieties grown on that farm. At least one variety is required. Changing the
plant type clears the selection to prevent assigning varieties from another
plant type. Assign crop varieties to their plant type in Crop Varieties first.

Farm records store `plant_type_ID`, `crop_variety_ids` and `plant_varieties`.
The legacy `plant_variety` remains the first selected variety. Farm cards and
details show the complete selection. Catalog IDs remain authoritative after
renaming a plant or variety.

Run `python setup_farm_varieties.py` before deploying the updated API. It creates
the optional farm attributes and batch `crop_variety_id`, then preserves each
legacy farm's variety only when its plant and variety match uniquely. It leaves
unmatched farms unchanged for manual selection and is safe to rerun.

Farm create/update accepts `crop_variety_ids` as a JSON array and `plant_type_ID`
as form fields. The server validates the plant relationship, rejects missing or
invalid choices, and stores canonical names. Legacy updates that leave the
plant and primary variety unchanged preserve existing multiple selections.
Legacy clients cannot silently replace a multiple selection with another single
variety.

Admin, Super Admin and Farm Manager batch forms offer the farm's assigned
varieties. Each batch still represents one variety and can join a shared growing
group. The API validates assigned varieties when creating a batch or changing
its variety. Historical batches remain editable without reassigning their
variety when it has since been removed from the farm.
