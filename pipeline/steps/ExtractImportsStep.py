from steps.BaseStep import BaseStep
from context import Context
from tree_sitter import Query, QueryCursor
from tree_sitter_languages import get_language

IMPORT_RULES = {
    "bash": {
        "import": "(source_command) @import"
    },

    "python": {
        "import": """
        [
          (import_statement)
          (import_from_statement)
        ] @import
        """
    },

    "javascript": {
        "import": """
        [
          (import_statement)

          (call_expression
            function: (identifier) @fn
            arguments: (arguments)
            (#eq? @fn "require")
          )

          (call_expression
            function: (identifier) @fn
            arguments: (arguments)
            (#eq? @fn "import")
          )
        ] @import
        """
    },

    "typescript": {
        "import": """
        [
          (import_statement)

          (call_expression
            function: (identifier) @fn
            arguments: (arguments)
            (#eq? @fn "require")
          )

          (call_expression
            function: (identifier) @fn
            arguments: (arguments)
            (#eq? @fn "import")
          )
        ] @import
        """
    },

    "tsx": {
        "import": """
        [
          (import_statement)

          (call_expression
            function: (identifier) @fn
            arguments: (arguments)
            (#eq? @fn "require")
          )

          (call_expression
            function: (identifier) @fn
            arguments: (arguments)
            (#eq? @fn "import")
          )
        ] @import
        """
    },

    "go": {
        "import": "(import_declaration) @import"
    },

    "java": {
        "import": "(import_declaration) @import"
    },

    "c": {
        "import": "(preproc_include) @import"
    },

    "cpp": {
        "import": "(preproc_include) @import"
    },

    "rust": {
        "import": "(use_declaration) @import"
    },
}

class ExtractImportsStep(BaseStep):
    def __init__(self):
        self._query_cache = {}
        
    def run(self, ctx: Context) -> None:
        for path, (language, tree) in ctx.syntax_trees.items():
            if language not in IMPORT_RULES:
                continue
            
            language_obj = get_language(language)
            query_text = IMPORT_RULES[language]["import"]
            if not query_text:
                continue

            cache_key = language
            if cache_key not in self._query_cache:
                self._query_cache[cache_key] = Query(language_obj, query_text)

            query = self._query_cache[cache_key]
            cursor = QueryCursor()

            ctx.imports_by_path[path] = []
            for node, cap in cursor.captures(query, tree.root_node):
                ctx.imports_by_path[path].append({
                    "file": path,
                    "language": language,
                    "byte_range": (node.start_byte, node.end_byte),
                    "raw": node.text.decode("utf-8", errors="replace"),
                })
