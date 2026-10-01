# -*- coding: utf-8 -*-

from pyrevit import routes 
from chat_session import start_session, refresh_session
from Autodesk.Revit.DB import ( 
    FilteredElementCollector, 
    BuiltInCategory, 
    StorageType, 
    UnitUtils, 
    UnitTypeId, 
    SpecTypeId 
) 
 
# ============================================================ 
# 1. CATEGORY MAPPING 
# ============================================================ 
 
CATEGORY_MAP = { 
    "Doors": BuiltInCategory.OST_Doors,
    "Windows": BuiltInCategory.OST_Windows, 
    "Rooms": BuiltInCategory.OST_Rooms, 
    "Walls": BuiltInCategory.OST_Walls, 
    "Columns": BuiltInCategory.OST_StructuralColumns, 
} 
 
 
# ============================================================ 
# 2. VALUE EXTRACTION 
#    Includes Type Parameter fallback 
#    # Converts Revit internal metric values to meters / square meters / cubic meters 
# ============================================================ 
 
def get_param_value(doc, el, param_name): 
 
    p = el.LookupParameter(param_name) 
 
    # Type parameter fallback 
    if p is None: 
        type_id = el.GetTypeId() 
 
        if type_id: 
            type_el = doc.GetElement(type_id) 
 
            if type_el: 
                p = type_el.LookupParameter(param_name) 
 
    if p is None or not p.HasValue: 
        return None 
 
    st = p.StorageType 
 
    if st == StorageType.Double: 
 
        raw = p.AsDouble()


        param_spec = None 


        try:
         param_spec = p.Definition.GetDataType()
        except Exception:
         pass
         
 
        if param_spec == SpecTypeId.Area: 
            return UnitUtils.ConvertFromInternalUnits( 
                raw, 
                UnitTypeId.SquareMeters 
            ) 
 
        if param_spec == SpecTypeId.Length: 
            return UnitUtils.ConvertFromInternalUnits( 
                raw, 
                UnitTypeId.Meters 
            ) 
 
        if param_spec == SpecTypeId.Volume: 
            return UnitUtils.ConvertFromInternalUnits( 
                raw, 
                UnitTypeId.CubicMeters 
            ) 
 
        return raw 
 
    elif st == StorageType.String: 
        return p.AsString() 
 
    elif st == StorageType.Integer: 
        return p.AsInteger() 
 
    elif st == StorageType.ElementId: 
        return p.AsValueString() 
 
    return None 
 
 
# ============================================================ 
# 3. FILTER OPERATOR & EVALUATION ENGINE 
# ============================================================ 
 
def safe_float(val): 
 
    try: 
        return float(val) 
 
    except (TypeError, ValueError): 
        return None 
 
 
OPS = {

    "eq": lambda v, t: v == t,

    "neq": lambda v, t: v != t,

    "is_null": lambda v, t: v is None,

    "is_not_null": lambda v, t: v is not None,

    "gt": lambda v, t:
        safe_float(v) is not None
        and safe_float(t) is not None
        and safe_float(v) > safe_float(t),

    "lt": lambda v, t:
        safe_float(v) is not None
        and safe_float(t) is not None
        and safe_float(v) < safe_float(t),

    "gte": lambda v, t:
        safe_float(v) is not None
        and safe_float(t) is not None
        and safe_float(v) >= safe_float(t),

    "lte": lambda v, t:
        safe_float(v) is not None
        and safe_float(t) is not None
        and safe_float(v) <= safe_float(t),

    "contains": lambda v, t:
        v is not None
        and t is not None
        and str(t).lower() in str(v).lower(),
}
def passes_filters(doc, el, filters):

    for f in filters:

        val = get_param_value(
            doc,
            el,
            f["param"]
        )

        op_key = f["op"]
        target = f.get("value")

        # Safe handling for string equality/inequality
        if isinstance(val, str) and isinstance(target, str):
            if op_key == "eq":
                if val != target:
                    return False
                continue

            if op_key == "neq":
                if val == target:
                    return False
                continue

        if not OPS[op_key](val, target):
            return False

    return True 
 
 

 
 
# ============================================================ 
# 4. SCHEMA INTROSPECTION 
# ============================================================ 
 
def get_schema(doc): 
 
    schema = {} 
 
    for cat_name, bic in CATEGORY_MAP.items(): 
 
        collector = ( 
            FilteredElementCollector(doc) 
            .OfCategory(bic) 
            .WhereElementIsNotElementType() 
        ) 
 
        param_types = {} 
 
        # Instance parameters 
        for el in collector: 
 
            for p in el.Parameters: 
 
                p_name = p.Definition.Name 
 
                if p_name not in param_types: 
 
                    param_types[p_name] = str( 
                        p.StorageType 
                    ) 
 
            # Type parameters 
            type_id = el.GetTypeId() 
 
            if type_id: 
 
                type_el = doc.GetElement(type_id) 
 
                if type_el: 
 
                    for p in type_el.Parameters: 
 
                        p_name = p.Definition.Name 
 
                        if p_name not in param_types: 
 
                            param_types[p_name] = str( 
                                p.StorageType 
                            ) 
 
        schema[cat_name] = param_types 
 
    return { 
        "categories": schema 
    } 
 
 
# ============================================================ 
# 5. QUERY 
# ============================================================ 
 
def query_elements( 
    doc, 
    category, 
    filters, 
    fields 
): 
 
    bic = CATEGORY_MAP[category] 
 
    collector = ( 
        FilteredElementCollector(doc) 
        .OfCategory(bic) 
        .WhereElementIsNotElementType() 
    ) 
 
    results = [] 
    for el in collector: 
     if passes_filters(doc, el, filters): 
 
        row = {} 
 
        for field in fields: 
            row[field] = get_param_value( 
                doc, 
                el, 
                field 
            ) 
 
        # Revit element ID - reserved system field 
        row["_id"] = el.Id.Value 
 
        results.append(row) 
    return results 
 
 
# ============================================================ 
# 6. AGGREGATE 
# ============================================================ 
 
def aggregate_elements( 
    doc, 
    category, 
    filters, 
    group_by, 
    metric, 
    field 
): 
 
    bic = CATEGORY_MAP[category] 
 
    collector = ( 
        FilteredElementCollector(doc) 
        .OfCategory(bic) 
        .WhereElementIsNotElementType() 
    ) 
 
    matched = [ 
        el 
        for el in collector 
        if passes_filters( 
            doc, 
            el, 
            filters 
        ) 
    ] 
 
    def compute(elements): 
 
        if metric == "count": 
            return len(elements) 
 
        if not field: 
            return None 
 
        values = [ 
            get_param_value(doc, e, field) 
            for e in elements 
        ] 
 
        values = [ 
            v 
            for v in values 
            if v is not None 
        ] 
 
        if not values: 
            return None 
 
        if metric == "sum": 
            return sum(values) 
 
        if metric == "avg": 
            return ( 
                sum(values) 
                / float(len(values)) 
            ) 
 
        if metric == "min": 
            return min(values) 
 
        if metric == "max": 
            return max(values) 
 
        return None 
 
    # No grouping 
    if not group_by: 
 
        return { 
            "result": compute(matched) 
        } 
 
    # Grouping 
    groups = {} 
 
    for el in matched: 
 
        key = get_param_value( 
            doc, 
            el, 
            group_by 
        ) 
 
        key_str = ( 
            str(key) 
            if key is not None 
            else "Unassigned" 
        ) 
 
        groups.setdefault( 
            key_str, 
            [] 
        ).append(el) 
 
    return { 
        "groups": { 
            k: compute(v) 
            for k, v in groups.items() 
        } 
    } 
 
 
# ============================================================ 
# 7. ROUTE SERVER 
# ============================================================ 
 
api = routes.API("bim-brain") 
 
 
# ============================================================ 
# 8. ERROR HANDLING 
# ============================================================ 
 
def handle_errors(func): 
 
    def wrapper(doc, request): 
 
        try: 
 
            return func( 
                doc, 
                request 
            ) 
 
        except Exception as e: 
 
            return routes.make_response( 
                data={ 
                    "error": str(e) 
                }, 
                status=500 
            ) 
 
    return wrapper 
 
 
# ============================================================ 
# 9. /schema 
# ============================================================ 
 
@api.route( 
    "/schema", 
    methods=["GET"] 
) 
def route_schema(doc, request): 
 
    try: 
        return get_schema(doc) 
 
    except Exception as e: 
        return routes.make_response( 
            data={ 
                "error": str(e) 
            }, 
            status=500 
        ) 
# ============================================================ 
# Phase 3 - Step 1 
# Model schema introspection 
# ============================================================ 
 
def get_model_schema(doc):
    categories = ["Doors", "Windows", "Rooms", "Walls", "Columns"]

    schema = {}

    for cat in categories:

        bic = CATEGORY_MAP[cat]

        instances = list(
            FilteredElementCollector(doc)
            .OfCategory(bic)
            .WhereElementIsNotElementType()
            .ToElements()
        )

        types = list(
            FilteredElementCollector(doc)
            .OfCategory(bic)
            .WhereElementIsElementType()
            .ToElements()
        )

   

        param_names = set()

        for el in instances[:10] + types[:5]:

            for p in el.Parameters:

                if p.Definition is not None:
                    name = p.Definition.Name

                    if name:
                        param_names.add(name)

        schema[cat] = {
            "count": len(instances),
            "parameters": sorted(param_names)
        }

    return schema 
 
 
 
# ============================================================ 
# Phase 3 - Step 1 
# /get_schema 
# ============================================================ 
 
@api.route( 
    "/get_schema", 
    methods=["GET"] 
) 
@handle_errors 
def route_get_schema(doc, request): 
 
    return get_model_schema(doc) 
 
 
# ============================================================
# 10. /query
# ============================================================

@api.route(
    "/query",
    methods=["POST"]
)
def route_query(doc, request):

    try:
        data = request.data

        category = data["category"]

        # Step 2 schema names
        filters = data.get("filters", [])
        return_fields = data.get("return_fields", [])

        # Convert Step 2 filter format to existing Phase 2 format
        converted_filters = []

        converted_filters = []

        for f in filters:
           converted_filters.append({
        "param": f["parameter"],
        "op": {
    "==": "eq",
    "!=": "neq",
    ">": "gt",
    "<": "lt",
    ">=": "gte",
    "<=": "lte",
    "contains": "contains",
    "is_null": "is_null",
    "is_not_null": "is_not_null"
}[f["operator"]],
        "value": f.get("value")
    })

        return {
            "results": query_elements(
                doc,
                category,
                converted_filters,
                return_fields
            )
        }

    except KeyError as e:
        return routes.make_response(
            data={
                "error": "missing required field: " + str(e)
            },
            status=400
        )

    except Exception as e:
        import traceback
        return routes.make_response(
            data={
                "error": traceback.format_exc()
            },
            status=500
        )
 
# ============================================================
# 11. /aggregate
# ============================================================

@api.route(
    "/aggregate",
    methods=["POST"]
)
def route_aggregate(doc, request):

    try:
        data = request.data

        category = data["category"]
        filters = data.get("filters", [])
        group_by = data.get("group_by")
        metric = data["aggregate"]
        field = data.get("aggregate_field")

        # Convert Step 2 filter format to existing Phase 2 format
        converted_filters = []

        for f in filters:
            converted_filters.append({
                "param": f["parameter"],
                "op": {
    "==": "eq",
    "!=": "neq",
    ">": "gt",
    "<": "lt",
    ">=": "gte",
    "<=": "lte",
    "contains": "contains",
    "is_null": "is_null",
    "is_not_null": "is_not_null"
}[f["operator"]],
                "value": f.get("value")
            })

        return aggregate_elements(
            doc,
            category,
            converted_filters,
            group_by,
            metric,
            field
        )

    except KeyError as e:
        return routes.make_response(
            data={
                "error": "missing required field: " + str(e)
            },
            status=400
        )

    except Exception as e:
        return routes.make_response(
            data={
                "error": str(e)
            },
            status=500
        )
    
    #/start_session
@api.route("/start_session", methods=["POST"])
def route_start_session(doc, request):
    data = request.data
    session_id = data["session_id"]

    return {
        "system_prompt": start_session(doc, session_id)
    }

#/refresh_schema
@api.route("/refresh_schema", methods=["POST"])
def route_refresh_schema(doc, request):
    data = request.data
    session_id = data["session_id"]

    return {
        "system_prompt": refresh_session(doc, session_id)
    }


@api.route("/chat", methods=["POST"])
def route_chat(doc, request):
    from chat_loop import handle_user_message

    data = request.data

    return {
        "response": handle_user_message(
            doc,
            data["session_id"],
            data["message"]
        )
    }
# ============================================================
# 12. /audit
# ============================================================

@api.route("/audit", methods=["POST"])
def route_audit(doc, request):

    from audit_rules import run_audit

    data = request.data
    rule_name = data["rule_name"]

    return run_audit(
        doc,
        rule_name
    )

@api.route("/audit_rules", methods=["POST"])
def route_audit_rules(doc, request):
    from audit_rules import list_audit_rules
    return {
        "rules": list_audit_rules()
    }
# ============================================================
# GENERATED SNIPPET
# ============================================================

# ============================================================
# GENERATED SNIPPET
# ============================================================

# ============================================================
# GENERATED SNIPPET
# ============================================================

@api.route(
    "/generated_snippet",
    methods=["POST"]
)
@handle_errors
def route_generated_snippet(doc, request):

    import revit_ro
    import sandbox_exec

    data = request.data
    code = data["code"]

    revit_ro_instance = revit_ro.RevitRO(doc)

    result = sandbox_exec.run_snippet(
        code,
        revit_ro_instance
    )

    return result
