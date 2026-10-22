# -*- coding: utf-8 -*-

"""
sandbox_exec.py

Static AST validation + restricted execution for
LLM-generated read-only fallback code.

Only run_snippet() is intended to be exposed
to the tool-dispatch layer.
"""

import ast


class SandboxRejected(Exception):
    """Raised when a snippet fails static validation."""

    pass


# ============================================================
# ALLOWED AST NODES
# ============================================================

ALLOWED_NODES = {
    ast.Module,
    ast.Expr,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Assign,
    ast.For,
    ast.If,
    ast.Compare,
    ast.BinOp,
    ast.BoolOp,
    ast.List,
    ast.Dict,
    ast.Tuple,
    ast.Subscript,
    ast.Attribute,
    ast.Return,
    ast.FunctionDef,
    ast.Gt,
    ast.Lt,
    ast.GtE,
    ast.LtE,
    ast.Eq,
    ast.NotEq,
    ast.And,
    ast.Or,
    ast.comprehension,
    ast.ListComp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.USub,
    ast.UAdd,
    ast.Not,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
    ast.IfExp,
    ast.Break,
    ast.Continue,
    ast.Pass,
    ast.UnaryOp,   # G3 C4: -x and not x (Invert ~ stays blocked)
    ast.keyword,   # G3 C4: keyword arguments, e.g. f(a, name=b)
    ast.AugAssign, # G5 C12: += and -= only (checked in validate_snippet)
    ast.GeneratorExp,   # C16: like list comprehensions (range cap and timeout still apply)
}


# Python-version-specific AST nodes
for _node_name in (
    "Constant",
    "Num",
    "Str",
    "NameConstant",
    "Index",
    "arguments",
    "arg",
):
    _node_type = getattr(ast, _node_name, None)

    if _node_type is not None:
        ALLOWED_NODES.add(_node_type)
# ============================================================
# FORBIDDEN NAMES
# ============================================================

FORBIDDEN_NAMES = {
    "__import__",
    "eval",
    "exec",
    "open",
    "compile",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "__builtins__",
    "input",
    "help",
    "dir",
    "type",
}


# ============================================================
# VALIDATOR
# ============================================================

# G5 C12: say what to do instead, so the agent can correct its snippet in one try
_HINTS = {
    'Param': ' (functions with parameters are not allowed: write the code inline, without def)',
    'Pow': ' (** is not allowed: use x * x)',
    'While': ' (while is not allowed: use a for loop over a list or range)',
    'TryExcept': ' (try/except is not allowed: check values with == None or if instead)',
    'Try': ' (try/except is not allowed: check values with == None or if instead)',
    'Lambda': ' (lambda is not allowed: write the code inline)',
    'Starred': ' (*args is not allowed)',
    'Invert': ' (~ is not allowed)',
}


def _syntax_message(code, e):   # G5 C14: say WHERE the syntax error is
    ln = getattr(e, 'lineno', None)
    txt = ''
    try:
        if ln:
            txt = code.splitlines()[ln - 1].strip()
    except Exception:
        pass
    msg = 'Syntax error at line %s: %s' % (ln, getattr(e, 'msg', e))
    if txt:
        msg += ' | the line is: ' + txt[:160]
    return msg


def validate_snippet(code):
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise SandboxRejected(
            _syntax_message(code, e)
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.AugAssign) and not isinstance(node.op, (ast.Add, ast.Sub)):   # G5 C12
            raise SandboxRejected('Only += and -= are allowed; write x = x * y instead of x *= y')
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            for side in (node.left, node.right):
                if isinstance(side, (ast.List, ast.ListComp, ast.Tuple)) or isinstance(_const(side), _STRS):
                    raise SandboxRejected('Repeating a list or text with * is not allowed')
        v = _const(node)
        if v is not _NOVAL and not isinstance(v, _STRS) and v is not None and not isinstance(v, bool):
            try:
                if abs(v) > MAX_INT_LITERAL:
                    raise SandboxRejected('Number literal too large')
            except TypeError:
                pass

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise SandboxRejected(
                "Imports are not allowed"
            )

        if type(node) not in ALLOWED_NODES:
            raise SandboxRejected(
                "Disallowed construct: {}".format(
                    type(node).__name__ + _HINTS.get(type(node).__name__, '')   # G5 C12
                )
            )

        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                raise SandboxRejected(
                    "Disallowed name: {}".format(
                        node.id
                    )
                )

        if isinstance(node, ast.Attribute):
            if node.attr.startswith(BLOCKED_ATTR_PREFIXES) or node.attr in BLOCKED_ATTRS:
                raise SandboxRejected(
                    "Attribute access not allowed: {}".format(node.attr)
                )

    return tree


# ============================================================
# SAFE BUILTINS
# ============================================================

SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "sum": sum,
    "min": min,
    "max": max,
    "sorted": sorted,
    "abs": abs,
    "round": round,
    "any": any,
    "all": all,
    "True": True,
    "False": False,
    "None": None,
}

# ============================================================
# TIMEOUT SUPPORT
# ============================================================

import time


try:
    _LAZY_RANGE = xrange  # IronPython 2.7: range() would build the whole list in memory first
except NameError:
    _LAZY_RANGE = range
MAX_RANGE_ITEMS = 1000000
MAX_INT_LITERAL = 10 ** 12
try:
    _STRS = (str, unicode)  # type: ignore
except NameError:
    _STRS = (str,)
_NOVAL = object()


def _const(node):
    name = type(node).__name__
    if name == 'Constant':
        return node.value
    if name == 'Num':
        return node.n
    if name == 'Str':
        return node.s
    return _NOVAL


class SandboxTimeout(Exception):
    """Raised when a snippet exceeds its allotted wall-clock time."""
    pass


# ============================================================
# EXECUTOR
# ============================================================

# ============================================================
# PHASE 5 HARDENING
# The snippet gets a facade with ONLY the read methods, never the RevitRO
# object or its doc. Dangerous attribute names are blocked, and the
# result must be plain data.
# ============================================================

PUBLIC_METHODS = (
    "get_elements",
    "get_param",
    "get_geometry_bbox",
    "get_relationship",
    "get_level_of_element",
    "get_host_id",
    "get_line",   # G5 C11
    "list_levels",   # C15
    "list_wall_types",   # C15
    "list_family_types",   # C15
    "list_sheets",   # family 7
    "get_wall_joins",   # C18
    "list_schedules",   # schedules
    "read_schedule",   # schedules
)

BLOCKED_ATTR_PREFIXES = ("_", "func_", "im_", "gi_", "f_", "co_", "tb_", "cell_")
BLOCKED_ATTRS = ("doc", "mro", "Document")

try:
    _PLAIN_SCALARS = (bool, int, long, float, str, unicode)  # type: ignore
except NameError:
    _PLAIN_SCALARS = (bool, int, float, str)


def _wrap(fn):
    def call(*args, **kwargs):
        return fn(*args, **kwargs)
    return call


class _Facade(object):
    pass


def _make_facade(ro):
    facade = _Facade()
    for name in PUBLIC_METHODS:
        setattr(facade, name, _wrap(getattr(ro, name)))
    return facade


_CLR_INTS = ("Int64", "Int32", "Int16", "UInt64", "UInt32", "UInt16", "Byte", "SByte")
_CLR_FLOATS = ("Double", "Single", "Decimal")


def _scalar(value):
    # A plain Python scalar, or ValueError. ElementId.Value is a .NET Int64 (not a
    # Python int), so CLR numbers are converted; Revit objects never are.
    if value is None or isinstance(value, _PLAIN_SCALARS):
        return value
    tname = type(value).__name__
    if tname in _CLR_INTS:
        return int(str(value))
    if tname in _CLR_FLOATS:
        return float(str(value))
    if getattr(type(value), "__module__", "") == "System":
        s = str(value)
        try:
            return int(s)
        except ValueError:
            return float(s)
    raise ValueError("not a scalar: " + tname)


def _plain(value, depth=0):
    if depth > 20:
        raise ValueError("result is nested too deeply")
    try:
        return _scalar(value)
    except ValueError:
        pass
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(x, depth + 1) for x in value]
    if type(value).__name__ in ("generator", "xrange", "range", "dict_keys", "dict_values", "dict_items", "enumerate"):
        return [_plain(x, depth + 1) for x in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            try:
                key = _scalar(k)
            except ValueError:
                raise ValueError("result has a non-plain dictionary key")
            out[key] = _plain(v, depth + 1)
        return out
    raise ValueError("result must be plain data (numbers, text, lists, dicts); found type: " + type(value).__name__)


def run_snippet(code, revit_ro_instance, timeout_sec=5):
    """
    Validate and execute a generated read-only snippet.

    Execution occurs synchronously because Revit API calls
    must remain on Revit's API thread.

    Returns a plain result dictionary.
    """

    try:
        validate_snippet(code)

    except SandboxRejected as e:
        return {
            "status": "rejected",
            "message": str(e),
        }

    deadline = [time.time() + timeout_sec]

    def safe_range(*args):
        r = _LAZY_RANGE(*args)
        if len(r) > MAX_RANGE_ITEMS:
            raise ValueError('range is too large (max %d items)' % MAX_RANGE_ITEMS)
        for i in r:
            if time.time() > deadline[0]:
                raise SandboxTimeout(
                    "Snippet exceeded {}s timeout".format(timeout_sec)
                )
            yield i

    safe_builtins = dict(SAFE_BUILTINS)
    safe_builtins["range"] = safe_range

    namespace = {
        "__builtins__": safe_builtins,
        "revit_ro": _make_facade(revit_ro_instance),
        "result": None,
    }

    try:
        exec(
            compile(
                code,
                "<generated>",
                "exec"
            ),
            namespace
        )

    except SandboxTimeout as e:
        return {
            "status": "timeout",
            "message": str(e),
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }

    try:
        plain = _plain(namespace.get("result"))
    except ValueError as e:
        return {
            "status": "error",
            "message": str(e),
        }

    return {
        "status": "ok",
        "result": plain,
    }