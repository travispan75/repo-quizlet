from steps.BaseStep import BaseStep
from context import Context
from tree_sitter import Query, QueryCursor
from tree_sitter_languages import get_language

SYMBOL_RULES = {
    "bash": {
        "function_def": "(function_definition) @def",
        "class_def": None,
        "method_def": None,
        "struct_def": None,
        "enum_def": None,
        "type_def": None,
    },
    "c": {
        "function_def": "(function_definition) @def",
        "class_def": None,
        "method_def": None,
        "struct_def": "(struct_specifier) @def",
        "union_def": "(union_specifier) @def",
        "enum_def": "(enum_specifier) @def",
        "type_def": "(type_definition) @def",
    },
    "cpp": {
        "function_def": "(function_definition) @def",
        "method_def": """
        [
          (method_definition)
          (constructor_definition)
          (destructor_definition)
        ] @def
        """,
        "class_def": "(class_specifier) @def",
        "struct_def": "(struct_specifier) @def",
        "enum_def": "(enum_specifier) @def",
        "type_def": "(type_definition) @def",
    },
    "css": {
        "function_def": None,
        "class_def": None,
        "method_def": None,
        "struct_def": None,
        "enum_def": None,
        "type_def": None,
    },
    "html": {
        "function_def": None,
        "class_def": None,
        "method_def": None,
        "struct_def": None,
        "enum_def": None,
        "type_def": None,
    },
    "go": {
        "function_def": "(function_declaration) @def",
        "method_def": "(method_declaration) @def",
        "class_def": None,
        "struct_def": None,
        "enum_def": None,
        "type_def": "(type_spec) @def",
    },
    "java": {
        "function_def": None,
        "method_def": """
        [
          (method_declaration)
          (constructor_declaration)
        ] @def
        """,
        "class_def": """
        [
          (class_declaration)
          (interface_declaration)
          (enum_declaration)
        ] @def
        """,
        "struct_def": None,
        "enum_def": "(enum_declaration) @def",
        "type_def": None,
    },
    "rust": {
        "function_def": "(function_item) @def",
        "method_def": None,
        "class_def": None,
        "struct_def": "(struct_item) @def",
        "enum_def": "(enum_item) @def",
        "trait_def": "(trait_item) @def",
        "type_def": "(type_item) @def",
        "impl_def": "(impl_item) @def",
    },
    "javascript": {
        "function_def": """
        [
          (function_declaration)
          (generator_function_declaration)
        ] @def
        """,
        "method_def": "(method_definition) @def",
        "class_def": "(class_declaration) @def",
        "arrow_def": "(arrow_function) @def",
        "struct_def": None,
        "enum_def": None,
        "type_def": None,
    },
    "typescript": {
        "function_def": "(function_declaration) @def",
        "method_def": "(method_definition) @def",
        "class_def": "(class_declaration) @def",
        "interface_def": "(interface_declaration) @def",
        "type_alias_def": "(type_alias_declaration) @def",
        "enum_def": "(enum_declaration) @def",
        "arrow_def": "(arrow_function) @def",
        "struct_def": None,
        "type_def": None,
    },
    "tsx": {
        "function_def": "(function_declaration) @def",
        "method_def": "(method_definition) @def",
        "class_def": "(class_declaration) @def",
        "interface_def": "(interface_declaration) @def",
        "type_alias_def": "(type_alias_declaration) @def",
        "enum_def": "(enum_declaration) @def",
        "arrow_def": "(arrow_function) @def",
        "struct_def": None,
        "type_def": None,
    },
    "json": {
        "function_def": None,
        "class_def": None,
        "method_def": None,
        "struct_def": None,
        "enum_def": None,
        "type_def": None,
    },
    "yaml": {
        "function_def": None,
        "class_def": None,
        "method_def": None,
        "struct_def": None,
        "enum_def": None,
        "type_def": None,
    },
    "markdown": {
        "function_def": None,
        "class_def": None,
        "method_def": None,
        "struct_def": None,
        "enum_def": None,
        "type_def": None,
    },
    "python": {
        "function_def": "(function_definition) @def",
        "method_def": "(function_definition) @def",
        "class_def": "(class_definition) @def",
        "struct_def": None,
        "enum_def": None,
        "type_def": None,
    },
}

class ExtractSymbolsStep(BaseStep):
    def __init__(self):
        self._query_cache = {}
        
    def run(self, ctx: Context) -> None:
        for path, (language, tree) in ctx.syntax_trees.items():
            if language not in SYMBOL_RULES:
                continue
            language_obj = get_language(language)
            rules = SYMBOL_RULES[language]
            for symbol_kind, query_text in rules.items():
                if not query_text:
                    continue

                cache_key = (language, symbol_kind)
                if cache_key not in self._query_cache:
                    self._query_cache[cache_key] = Query(language_obj, query_text)

                query = self._query_cache[cache_key]
                cursor = QueryCursor()

                for node, cap in cursor.captures(query, tree.root_node):
                    if cap != "def":
                        continue

                    symbol_id = (path, node.start_byte, node.end_byte)
                    ctx.symbol_table[symbol_id] = {
                        "kind": symbol_kind,
                        "language": language,
                        "file": path,
                        "byte_range": (node.start_byte, node.end_byte),
                    }