import bim_client as bc


def check(label, expected, actual):
    assert expected == actual, (
        f"[FAIL] {label}\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )
    print(f"[PASS] {label}")


# ============================================================
# 1. Doors — is_null on Fire Rating
# ============================================================

results = bc.query_elements(
    "Doors",
    [
        {
            "param": "Fire Rating",
            "op": "is_null"
        }
    ],
    ["Mark"]
)

marks = sorted(r["Mark"] for r in results)

expected_marks = sorted(["104"
    # YOU enter your Case 1 Marks here
])

check(
    "Doors is_null Fire Rating -> Marks",
    expected_marks,
    marks
)


# ============================================================
# 2. Doors — eq on selected Mark
# ============================================================

results = bc.query_elements(
    "Doors",
    [
        {
            "param": "Mark",
            "op": "eq",
            "value": "100"
        }
    ],
    ["Mark"]
)

check(
    "Doors eq selected Mark -> single result",
    1,
    len(results)
)


# ============================================================
# 3. Rooms — aggregate sum Area
# ============================================================

result = bc.aggregate_elements(
    "Rooms",
    [],
    None,
    "sum",
    "Area"
)

expected_total = 565.44

check(
    "Rooms sum Area",
    round(expected_total, 2),
    round(result["result"], 2)
)


# ============================================================
# 4. Rooms — aggregate avg Area grouped by Level
# ============================================================

result = bc.aggregate_elements(
    "Rooms",
    [],
    "Level",
    "avg",
    "Area"
)

expected_by_level = {
    
    "L1": 565.44

}

for level, exp_avg in expected_by_level.items():

    check(
        f"Rooms avg Area on level {level}",
        round(exp_avg, 2),
        round(result["groups"][level], 2)
    )
# ============================================================
# 5. Walls — contains on Type Name
# ============================================================

results = bc.query_elements(
    "Walls",
    [
        {
            "param": "Type Name",
            "op": "contains",
            "value": "Generic"
        }
    ],
    ["Type Name"]
)

check(
    "Walls contains 'Generic' -> count",
    0,
    len(results)
)


# ============================================================
# 6. Walls — gt on Length
# ============================================================

threshold = 0

results = bc.query_elements(
    "Walls",
    [
        {
            "param": "Length",
            "op": "gt",
            "value": threshold
        }
    ],
    ["Mark"]
)

expected_marks_6 = sorted([
    # YOU enter your Case 6 Marks here
])

actual_marks_6 = sorted(
    r["Mark"]
    for r in results
    if r["Mark"] is not None
)

check(
    "Walls gt Length",
    expected_marks_6,
    actual_marks_6
)


# ============================================================
# 7. Columns — eq on Level
# ============================================================

results = bc.query_elements(
    "Columns",
    [
        {
            "param": "Level",
            "op": "eq",
            "value": "Level 1"
        }
    ],
    ["Mark"]
)

check(
    "Columns eq Level=Level 1 -> count",
    0,
    len(results)
)


# ============================================================
# 8. Columns — aggregate count
# ============================================================

result = bc.aggregate_elements(
    "Columns",
    [],
    None,
    "count",
    None
)

check(
    "Columns count",
    0,
    result["result"]
)


# ============================================================
# 9. Doors — neq on Fire Rating
# ============================================================

results = bc.query_elements(
    "Doors",
    [
        {
            "param": "Fire Rating",
            "op": "neq",
            "value": "1 hr"
        }
    ],
    ["Mark"]
)

expected_marks_9 = sorted([
    "100",
    "101",
    "102",
    "103",
    "104"
])

check(
    "Doors neq Fire Rating=1hr",
    expected_marks_9,
    sorted(r["Mark"] for r in results)
)


# ============================================================
# 10. Manual ElementId cross-check
# ============================================================

results = bc.query_elements(
    "Doors",
    [
        {
            "param": "Mark",
            "op": "eq",
            "value": "100"
        }
    ],
    ["Mark", "_id"]
)

print(
    f"[MANUAL CHECK] Returned _id: {results[0]['_id']}"
)

print(
    "Go to Revit and confirm this ElementId belongs to your selected door."
)