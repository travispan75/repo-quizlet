class Context:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

        self.repo_entries = []
        self.adjacency_list = {}
        
        self.entry_by_path = {}
        self.files_by_category = {}
        
        self.repo_tree = {}
        
        self.file_contents = {}
        
        self.syntax_trees = {}
        
        self.symbol_table = {}
        
        self.refer
        
    def _dfs_repo_tree(self, root: str, indent: int = 0):
        print("  " * indent + root)
        for child in self.adjacency_list.get(root, []):
            self._dfs_repo_tree(child, indent + 1)
    
    def _debug_print(self, debug_repo_path: bool = False, debug_counts: bool = False, debug_keys: bool = False, debug_repo_tree: bool = False):
        if debug_repo_path:
            print(f"[Context] repo_path = {self.repo_path}")

        if debug_counts:
            print(
                "[Context counts]",
                f"entries={len(self.repo_entries)}, "
                f"adjacency={len(self.adjacency_list)}, "
                f"files={len(self.file_contents)}, "
                f"syntax_trees={len(self.syntax_trees)}",
            )

        if debug_keys:
            print(
                "[Context keys]",
                f"files_by_category={list(self.files_by_category.keys())}, "
                f"entry_by_path={list(self.entry_by_path.keys())[:5]}",
            )
            
        if debug_repo_tree:
            print("[Context repo tree]")
            self._dfs_repo_tree(".")