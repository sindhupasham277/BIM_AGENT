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

def validate_snippet(code):
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise SandboxRejected(
            "Syntax error: {}".format(e)
        )

    for node in ast.walk(tree):

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise SandboxRejected(
                "Imports are not allowed"
            )

        if type(node) not in ALLOWED_NODES:
            raise SandboxRejected(
                "Disallowed construct: {}".format(
                    type(node).__name__
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


def _plain(value, depth=0):
    if depth > 20:
        raise ValueError("result is nested too deeply")
    if value is None or isinstance(value, _PLAIN_SCALARS):
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(x, depth + 1) for x in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if not isinstance(k, _PLAIN_SCALARS):
                raise ValueError("result has a non-plain dictionary key")
            out[k] = _plain(v, depth + 1)
        return out
    raise ValueError("result must be plain data (numbers, text, lists, dicts)")


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
        for i in range(*args):
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