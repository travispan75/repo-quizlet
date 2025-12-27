from steps.BaseStep import BaseStep
from context import Context
from tree_sitter import Node

LANG_RULES = {
    "bash": {
        "type_defs": set(),
        "callable_defs": {"function_definition"},
    },
    "c": {
        "type_defs": {
            "struct_specifier",
            "union_specifier",
            "enum_specifier",
            "type_definition",
        },
        "callable_defs": {"function_definition"},
    },
    "cpp": {
        "type_defs": {
            "class_specifier",
            "struct_specifier",
            "enum_specifier",
            "type_definition",
        },
        "callable_defs": {
            "function_definition",
            "method_definition",
            "constructor_definition",
            "destructor_definition",
        },
    },
    "css": {
        "type_defs": set(),
        "callable_defs": set(),
    },
    "html": {
        "type_defs": set(),
        "callable_defs": set(),
    },
    "go": {
        "type_defs": {"type_spec"},
        "callable_defs": {
            "function_declaration",
            "method_declaration",
        },
    },
    "java": {
        "type_defs": {
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
        },
        "callable_defs": {
            "method_declaration",
            "constructor_declaration",
        },
    },
    "rust": {
        "type_defs": {
            "struct_item",
            "enum_item",
            "trait_item",
            "type_item",
            "impl_item",
        },
        "callable_defs": {"function_item"},
    },
    "javascript": {
        "type_defs": {"class_declaration"},
        "callable_defs": {
            "function_declaration",
            "method_definition",
            "arrow_function",
            "generator_function_declaration",
        },
    },
    "typescript": {
        "type_defs": {
            "class_declaration",
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
        },
        "callable_defs": {
            "function_declaration",
            "method_definition",
            "arrow_function",
        },
    },
    "tsx": {
        "type_defs": {
            "class_declaration",
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
        },
        "callable_defs": {
            "function_declaration",
            "method_definition",
            "arrow_function",
        },
    },
    "json": {
        "type_defs": set(),
        "callable_defs": set(),
    },
    "yaml": {
        "type_defs": set(),
        "callable_defs": set(),
    },
    "markdown": {
        "type_defs": set(),
        "callable_defs": set(),
    },
    "python": {
        "type_defs": {"class_definition"},
        "callable_defs": {"function_definition"},
    },
}

class ExtractSymbolsStep(BaseStep):
    def __init__(self):
        pass
    
    def _extract_symbols_from_cst(self, path: str, root: Node, language_rule: dict, ctx: Context, classStack: list[tuple]) -> None:
        className = None
        symbol_id = None

        if root.type in language_rule["type_defs"]:
            className = "<class_name>"
            symbol_id = (path, root.start_byte, root.end_byte)
            ctx.symbol_table[symbol_id] = {
                "name": className,
                "kind": "class",
                "file": path,
                "byte_range": (root.start_byte, root.end_byte),
            }

        elif root.type in language_rule["callable_defs"]:
            symbol_id = (path, root.start_byte, root.end_byte)
            if classStack:
                ctx.symbol_table[symbol_id] = {
                    "kind": "method",
                    "container_class": classStack[-1][1],
                    "file": path,
                    "byte_range": (root.start_byte, root.end_byte),
                }
            else:
                ctx.symbol_table[symbol_id] = {
                    "kind": "function",
                    "file": path,
                    "byte_range": (root.start_byte, root.end_byte),
                }

        if className:
            classStack.append((className, symbol_id))

        for child in root.children:
            self._extract_symbols_from_cst(path, child, language_rule, ctx, classStack)

        if className:
            classStack.pop()
        
    def run(self, ctx: Context) -> None:
        for path, (language, cst) in ctx.syntax_trees.items():
            self._extract_symbols_from_cst(path, cst.root_node, LANG_RULES[language], ctx, [])