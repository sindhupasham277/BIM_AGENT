import pyrevit
from pyrevit import revit, DB
import sys
print("=== PYTHON ENGINE VERSION ===")
print(sys.version)
print("=============================")

# Access document and selection safely in pyRevit
doc = revit.doc
uidoc = revit.uidoc

def list_categories(doc):
    """Enumerates all non-type elements and groups them by Category Name."""
    collector = DB.FilteredElementCollector(doc).WhereElementIsNotElementType()
    categories = {}
    
    for elem in collector:
        if elem.Category:
            cat_name = elem.Category.Name
            categories[cat_name] = categories.get(cat_name, 0) + 1
            
    return categories

def get_parameters(element):
    """Generically extracts all parameters, types, and values from any element."""
    param_data = []
    
    for param in element.Parameters:
        definition = param.Definition.Name if param.Definition else "Unknown"
        storage_type = str(param.StorageType)
        
        # Read value based on storage type or fallback
        val = param.AsValueString()
        if val is None:
            if param.StorageType == DB.StorageType.String:
                val = param.AsString()
            elif param.StorageType == DB.StorageType.Integer:
                val = param.AsInteger()
            elif param.StorageType == DB.StorageType.Double:
                val = param.AsDouble()
            elif param.StorageType == DB.StorageType.ElementId:
                elem_id = param.AsElementId()
                if elem_id:
                    # Safe check for Revit 2024+ (.Value) vs older versions (.IntegerValue)
                    val = getattr(elem_id, 'Value', getattr(elem_id, 'IntegerValue', None))
                
        param_data.append({
            "name": definition,
            "type": storage_type,
            "value": val
        })
        
    return param_data

# --- TEST EXECUTION ---
print("--- CATEGORY COUNTS ---")
all_cats = list_categories(doc)
for cat, count in list(all_cats.items())[:5]:
    print("{}: {}".format(cat, count))

selection_ids = uidoc.Selection.GetElementIds()
if selection_ids:
    first_elem = doc.GetElement(list(selection_ids)[0])
    print("\n--- PARAMETERS FOR: {} (ID: {}) ---".format(first_elem.Category.Name, first_elem.Id))
    params = get_parameters(first_elem)
    for p in params[:10]:
        print("[{}] {} = {}".format(p["type"], p["name"], p["value"]))
else:
    print("\nSelect an element in Revit (Wall, Door, or Furniture) and click Inspect again.")