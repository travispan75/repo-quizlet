from steps.BaseStep import BaseStep
from context import Context
import os

class ScanFilesStep(BaseStep):
    def __init__(self):
        pass

    def run(self, ctx: Context) -> None:
        repo_path = ctx.repo_path

        for root, dirs, files in os.walk(repo_path):
            rel_path = os.path.relpath(root, repo_path)
            ctx.repo_entries.append({
                "rel_path": rel_path,
                "name": os.path.basename(root),
                "ext": "",
                "size": 0,
                "is_binary": False,
                "is_dir": True
            })

            ctx.adjacency_list[rel_path] = []
            for d in dirs:
                full = os.path.join(root, d)
                rel  = os.path.relpath(full, repo_path)
                ctx.adjacency_list[rel_path].append(rel)
                
            for f in files:
                full = os.path.join(root, f)
                rel  = os.path.relpath(full, repo_path)
                ext  = os.path.splitext(f)[1] or None

                ctx.repo_entries.append({
                    "rel_path": rel,
                    "name": f,
                    "ext": ext,
                    "size": os.path.getsize(full),
                    "is_binary": False,
                    "is_dir": False
                })
                ctx.adjacency_list[rel_path].append(rel)

