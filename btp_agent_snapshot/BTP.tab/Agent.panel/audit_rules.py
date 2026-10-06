# ============================================================
# Audit Rules
# ============================================================

AUDIT_RULES = {

    "missing_fire_rating": {
        "description": "Find doors without a fire rating",
        "category": ["Doors"],
        "filter": {
            "param": "Fire Rating",
            "op": "is_null"
        }
    },

    "missing_room_number": {
        "description": "Find rooms without room numbers",
        "category": ["Rooms"],
        "filter": {
            "param": "Number",
            "op": "is_null"
        }
    },

    "missing_column_type_mark": {
        "description": "Find columns without type marks",
        "category": ["Columns"],
        "filter": {
            "param": "Type Mark",
            "op": "is_null"
        }
    },

       "missing_wall_mark": {
        "description": "Find walls without a Mark",
        "category": ["Walls"],
        "filter": {
            "param": "Mark",
            "op": "is_null"
        }
    },

    "missing_room_name": {
        "description": "Find rooms without a Name",
        "category": ["Rooms"],
        "filter": {
            "param": "Name",
            "op": "is_null"
        }
    }
        }
    


def run_audit(doc, rule_name):

    from Autodesk.Revit.DB import (
        FilteredElementCollector,
        BuiltInCategory,
        StorageType
    )

    if rule_name not in AUDIT_RULES:
        raise ValueError(
            "Unknown audit rule: " + rule_name
        )

    rule = AUDIT_RULES[rule_name]

    category_map = {
        "Doors": BuiltInCategory.OST_Doors,
        "Rooms": BuiltInCategory.OST_Rooms,
        "Walls": BuiltInCategory.OST_Walls,
        "Columns": BuiltInCategory.OST_StructuralColumns
    }

    category = rule["category"][0]
    parameter_name = rule["filter"]["param"]

    if category not in category_map:
        raise ValueError(
            "Unsupported audit category: " + category
        )

    elements = (
        FilteredElementCollector(doc)
        .OfCategory(category_map[category])
        .WhereElementIsNotElementType()
        .ToElements()
    )

    results = []

    for element in elements:

        parameter = element.LookupParameter(parameter_name)

        if parameter is None and parameter_name == "Type Mark":
         parameter = element.LookupParameter("Type Mark")


      
         

        # Check type parameter if instance parameter is not found
        if parameter is None:

            type_id = element.GetTypeId()

            if type_id and type_id.Value != -1:

                type_element = doc.GetElement(type_id)

                if type_element:
                    parameter = type_element.LookupParameter(
                        parameter_name
                    )

        if parameter is None:
            continue

        missing = False

        if not parameter.HasValue:
            missing = True

        elif parameter.StorageType == StorageType.String:

            value = parameter.AsString()

            if value is None or value == "":
                missing = True

        if missing:

            results.append({
                "_id": element.Id.Value
            })

    return {
        "rule_name": rule_name,
        "description": rule["description"],
        "count": len(results),
        "results": results
    }
def list_audit_rules():
    return [
        {
            "rule_name": rule_name,
            "description": rule["description"]
        }
        for rule_name, rule in AUDIT_RULES.items()
    ]