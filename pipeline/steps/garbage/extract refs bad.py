from steps.BaseStep import BaseStep
from context import Context
from tree_sitter import Node

class ExtractReferencesStep(BaseStep):
    def __init__(self):
        pass

    def _extract_references_from_cst(self, path: str, root: Node, language: str, ctx: Context, symbol_stack: list[tuple]) -> None:
        symbol_id = (path, root.start_byte, root.end_byte)
        is_symbol = symbol_id in ctx.symbol_table

        if is_symbol:
            symbol_stack.append(symbol_id)

        if root.type == "identifier":
            ctx.reference_list.append({
                "name": root.text.decode("utf-8", errors="replace"),
                "file": path,
                "byte_range": (root.start_byte, root.end_byte),
                "node_type": root.type,
                "parent_type": root.parent.type if root.parent else None,
                "language": language,
                "enclosing_symbol_id": symbol_stack[-1] if symbol_stack else None,
            })

        for child in root.children:
            self._extract_references_from_cst(path, child, language, ctx, symbol_stack)

        if is_symbol:
            symbol_stack.pop()

    def run(self, ctx: Context) -> None:
        for path, (language, cst) in ctx.syntax_trees.items():
            self._extract_references_from_cst(path, cst.root_node, language, ctx, [])
