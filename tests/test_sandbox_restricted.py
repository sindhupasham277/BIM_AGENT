from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import safe_builtins

# 1. Define dummy Revit stubs matching Step 2 functions
def dummy_list_categories():
    return {"Walls": 12, "Doors": 4, "Furniture": 8}

def dummy_get_parameters(elem_id):
    return [{"name": "Height", "type": "Double", "value": 3000.0}]

# 2. Build the restricted execution scope
restricted_globals = {
    "__builtins__": safe_builtins,
    "list_categories": dummy_list_categories,
    "get_parameters": dummy_get_parameters,
}

def execute_user_code(source_code):
    """Compiles and runs untrusted Python code safely."""
    try:
        # Compile under safe restrictions
        byte_code = compile_restricted(source_code, filename="<user_code>", mode="exec")
        
        # Safe local context to capture variable outputs
        restricted_locals = {}
        
        # Execute code inside the sandbox
        exec(byte_code, restricted_globals, restricted_locals)
        return {"status": "success", "result": restricted_locals}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# --- VERIFICATION TEST ---
if __name__ == "__main__":
    # Test A: Allowed code using exposed stubs
    safe_code = """
cats = list_categories()
params = get_parameters(101)
"""
    print("--- Test Safe Code ---")
    print(execute_user_code(safe_code))

    # Test B: Unauthorized code (attempting file system access)
    unsafe_code = """
import os
files = os.listdir('.')
"""
    print("\n--- Test Unsafe Code (Should Fail) ---")
    print(execute_user_code(unsafe_code))