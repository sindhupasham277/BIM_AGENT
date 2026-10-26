# -*- coding: utf-8 -*-
import os
import sys

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from pyrevit import revit

from revit_ro import RevitRO


doc = revit.doc

ro = RevitRO(doc)


# ============================================================
# TEST 1 — get_elements
# ============================================================

doors = ro.get_elements("Doors")

print("TEST 1")
print("type:", type(doors))
print("count:", len(doors))

if len(doors) > 0:

    print("first element:", doors[0])
    print("element type:", type(doors[0]))

    assert isinstance(doors, list)
    assert isinstance(doors[0], dict)

    assert "id" in doors[0]
    assert "name" in doors[0]
    assert "category" in doors[0]

    assert not hasattr(doors[0], "Delete")

    print("TEST 1 PASSED")


# ============================================================
# TEST 2 — get_param
# ============================================================

if len(doors) > 0:

    some_id = doors[0]["id"]

    fire_rating = ro.get_param(
        some_id,
        "Fire Rating"
    )

    print("")
    print("TEST 2")
    print("door id:", some_id)
    print("Fire Rating:", fire_rating)
    print("value type:", type(fire_rating))

    assert (
        fire_rating is None
        or isinstance(
            fire_rating,
            (str, int, float)
        )
    )

    print("TEST 2 PASSED")


# ============================================================
# TEST 3 — get_geometry_bbox
# ============================================================

if len(doors) > 0:

    some_id = doors[0]["id"]

    bbox = ro.get_geometry_bbox(some_id)

    print("")
    print("TEST 3")
    print("bbox:", bbox)

    assert (
        bbox is None
        or isinstance(bbox, dict)
    )

    if bbox is not None:

        assert "min" in bbox
        assert "max" in bbox

        assert isinstance(
            bbox["min"],
            tuple
        )

        assert isinstance(
            bbox["max"],
            tuple
        )

    print("TEST 3 PASSED")


# TEST 4 relationship - Revit ground-truth verification

print("")
print("TEST 4")
print("Interior door ID:", 1678957)
print("Exterior door ID:", 1675193)

# Get all actual room IDs from the Revit model
rooms = ro.get_elements("Rooms")
room_ids = [room["id"] for room in rooms]

# ------------------------------------------------------------
# Interior door: must have rooms on both sides
# ------------------------------------------------------------

interior_relationship = ro.get_relationship(
    1678957,
    "rooms_bounding_door"
)

print("")
print("Interior door relationship:")
print(interior_relationship)

assert isinstance(interior_relationship, dict)
assert "from_room_id" in interior_relationship
assert "to_room_id" in interior_relationship

assert interior_relationship["from_room_id"] is not None
assert interior_relationship["to_room_id"] is not None

assert interior_relationship["from_room_id"] in room_ids
assert interior_relationship["to_room_id"] in room_ids

print("Interior door verification PASSED")


# ------------------------------------------------------------
# Exterior door: exactly one side should be a room
# ------------------------------------------------------------

exterior_relationship = ro.get_relationship(
    1675193,
    "rooms_bounding_door"
)

print("")
print("Exterior door relationship:")
print(exterior_relationship)

assert isinstance(exterior_relationship, dict)
assert "from_room_id" in exterior_relationship
assert "to_room_id" in exterior_relationship

from_room = exterior_relationship["from_room_id"]
to_room = exterior_relationship["to_room_id"]

assert (from_room is None) != (to_room is None)

room_side = from_room if from_room is not None else to_room

assert room_side in room_ids

print("Exterior door verification PASSED")

print("")
print("TEST 4 PASSED")


# ============================================================
# TEST 5 — invalid category
# ============================================================

print("")
print("TEST 5")

try:

    ro.get_elements("NotACategory")

    print("TEST 5 FAILED")

except ValueError as e:

    print("Correctly rejected:")
    print(e)

    print("TEST 5 PASSED")


# ============================================================
# TEST 6 — invalid element ID
# ============================================================

print("")
print("TEST 6")

bad_id_result = ro.get_param(
    999999999,
    "Fire Rating"
)

print(
    "Result for nonexistent element:",
    bad_id_result
)

assert bad_id_result is None

print("TEST 6 PASSED")


print("")
print("========================================")
print("ALL RevitRO TESTS COMPLETED")
print("========================================")