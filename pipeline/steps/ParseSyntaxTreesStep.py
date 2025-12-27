from steps.BaseStep import BaseStep
from context import Context
from tree_sitter_languages import get_parser
from concurrent.futures import ThreadPoolExecutor
from threading import local
import os

EXT_TO_LANGUAGE = {
    ".sh": "bash",

    ".c": "c",
    ".h": "c",

    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",

    ".css": "css",

    ".html": "html",
    ".htm": "html",

    ".go": "go",
    ".java": "java",
    ".rs": "rust",

    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",

    ".ts": "typescript",
    ".tsx": "tsx",

    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",

    ".md": "markdown",
    ".markdown": "markdown",
    ".mdx": "markdown",

    ".py": "python",
}

class ParseSyntaxTreesStep(BaseStep):
    def run(self, ctx: Context) -> None:
        parser_cache = local()
        
        def parse_content(item: tuple) -> None:
            path, content = item
            if content:
                ext = ctx.entry_by_path[path]["ext"]

                if ext not in EXT_TO_LANGUAGE:
                    ctx.syntax_trees[path] = content.decode("utf-8", errors="replace")
                    return

                language = EXT_TO_LANGUAGE[ext]

                if language not in parser_cache:
                    parser_cache[language] = get_parser(language)

                parser = parser_cache[language]
                tree = parser.parse(content)
                ctx.syntax_trees[path] = (language, tree)
        
        max_workers = min(os.cpu_count(), 8)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            pool.map(parse_content, ctx.file_contents.items())