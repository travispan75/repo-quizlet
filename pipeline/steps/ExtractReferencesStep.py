from steps.BaseStep import BaseStep
from context import Context
from tree_sitter import Query, QueryCursor
from tree_sitter_languages import get_language

REFERENCE_RULES = {
    "bash": {
        "identifier_ref": "(word) @ref",
    },

    "c": {
        "identifier_ref": "(identifier) @ref",
    },

    "cpp": {
        "identifier_ref": "(identifier) @ref",
    },

    "go": {
        "identifier_ref": "(identifier) @ref",
    },

    "java": {
        "identifier_ref": "(identifier) @ref",
    },

    "rust": {
        "identifier_ref": "(identifier) @ref",
    },

    "javascript": {
        "identifier_ref": "(identifier) @ref",
    },

    "typescript": {
        "identifier_ref": "(identifier) @ref",
    },

    "tsx": {
        "identifier_ref": "(identifier) @ref",
    },

    "python": {
        "identifier_ref": "(identifier) @ref",
    },
}

class ExtractReferencesStep(BaseStep):
    def __init__(self):
        self._query_cache = {}
        
    def run(self, ctx: Context) -> None:
        for path, (language, tree) in ctx.syntax_trees.items():
            if language not in REFERENCE_RULES:
                continue
            
            language_obj = get_language(language)
            query_text = REFERENCE_RULES[language]["identifier_ref"]
            if not query_text:
                continue

            cache_key = language
            if cache_key not in self._query_cache:
                self._query_cache[cache_key] = Query(language_obj, query_text)

            query = self._query_cache[cache_key]
            cursor = QueryCursor()

            for node, cap in cursor.captures(query, tree.root_node):
                ctx.reference_list.append({
                    "file": path,
                    "name": node.text.decode("utf-8", errors="replace"),
                    "byte_range": (node.start_byte, node.end_byte),
                    "language": language,
                })
