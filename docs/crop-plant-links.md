# Crop varieties and plant types

Each crop variety stores its parent plant's document ID in `plant_type_ID`.
One plant type can have many varieties, for example Lettuce → Batavia and
Lettuce → Lollo Rosso. Categories are not selectable parent plant types.

In Admin or Super Admin → Crop Varieties, use Add Variety or Edit Variety
and select **Plant type**. New links require an active plant type. Editing a
linked variety can retain its existing inactive parent. The API stores the
selected plant's current name in the legacy `crop_name` field for compatibility.
The ID remains the authoritative link when a plant is renamed.

Farm and batch variety selectors use this relationship. Admin and Super Admin
can select multiple varieties belonging to the farm's plant type. Each batch
chooses one of those assigned varieties. See [farm variety assignments](multiple-farm-varieties.md).

Run `python setup_crop_plant_links.py` before deploying the updated API.
The migration creates the optional string attribute and links legacy varieties
only when their crop name exactly matches one active, non-category plant type
(ignoring case and repeated whitespace). Ambiguous and unmatched varieties
require manual selection in Edit Variety. The migration is safe to rerun.
The initial migration found four varieties needing manual selection.

Crop catalog reads now load every page, avoiding Appwrite's default list limit.
Legacy clients without `plant_type_ID` may save only when the crop name resolves
to one exact plant type; otherwise the API returns a validation error requiring
an explicit selection. Unknown IDs, categories and new inactive assignments
are rejected before uploading an image or writing a crop document.
