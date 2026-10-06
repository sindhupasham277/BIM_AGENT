# -*- coding: utf-8 -*-

"""
Phase 2 / Step 3 - Schema introspection

Runs inside pyRevit against the currently open Revit model.
No HTTP, no external calls.
Creates a JSON schema dump for inspection.
"""

import json
from Autodesk.Revit.DB import FilteredElementCollector


# Get the currently open Revit document
from pyrevit import revit

doc = revit.doc


def storage_type_name(st):
    # Convert Revit StorageType enum to text
    return str(st)
# Collect instance elements only
collector = FilteredElementCollector(
    doc
).WhereElementIsNotElementType()


# Category name -> representative element parameter schema
schema = {}

# Count elements that do not have a usable category
skipped_no_category = 0


# Loop through model elements
for el in collector:

    cat = None

    try:
        cat = el.Category
    except Exception:
        cat = None

    # Skip elements without a category
    if cat is None or cat.Name is None:
        skipped_no_category += 1
        continue

    cat_name = cat.Name

    # Only one representative element is needed for each category
    if cat_name in schema:
        continue

    params_info = {}

    # Read parameters of the representative element
    for p in el.Parameters:

        try:
            defn = p.Definition

            if defn is None:
                continue

            pname = defn.Name
            pstorage = storage_type_name(p.StorageType)

            params_info[pname] = {
                "storage_type": pstorage,
                "is_shared": p.IsShared,
                "has_value": p.HasValue
            }

        except Exception:
            # Skip parameters that cannot be read
            continue

    # Store category information
    schema[cat_name] = {
    "sample_element_id": int(el.Id.Value),
        "param_count": len(params_info),
        "parameters": params_info
    }


# --------------------------------------------------
# OUTPUT
# --------------------------------------------------

output_path = r"C:\temp\revit_schema_dump.json"


with open(output_path, "w") as f:
    json.dump(
        schema,
        f,
        indent=2,
        sort_keys=True
    )


# Console output
print("Categories captured: {}".format(len(schema)))
print(
    "Elements skipped (no category): {}".format(
        skipped_no_category
    )
)
print("Wrote: {}".format(output_path))


# Quick preview of first two categories
preview_keys = sorted(schema.keys())[:2]

for k in preview_keys:
    print("---- {} ----".format(k))
    print(
        json.dumps(
            schema[k],
            indent=2,
            sort_keys=True
        )
    )