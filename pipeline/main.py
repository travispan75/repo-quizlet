import sys

from pipeline import Pipeline


def _debug_dependency_graph(ctx):
    print(f"dependency_graph: {len(ctx.dependency_graph)} symbols with dependencies")
    for symbol_id, deps in list(ctx.dependency_graph.items())[:3]:
        print(f"  {symbol_id!r} -> {dict(list(deps.items())[:3])}")


def _debug_call_graph(ctx):
    print(f"call_graph: {len(ctx.call_graph)} callers")
    print(f"called_by_graph: {len(ctx.called_by_graph)} callees")
    for caller, callees in list(ctx.call_graph.items())[:3]:
        print(f"  {caller!r} calls {len(callees)} symbol(s): {list(callees)[:2]}")


def _debug_chunks(ctx):
    print(f"chunks: {len(ctx.chunks)} total")
    for chunk in ctx.chunks[:3]:
        print(f"  [{chunk.file}:{chunk.start_line}-{chunk.end_line}] {chunk.name!r} | calls={len(chunk.calls)} called_by={len(chunk.called_by)}")
        print(f"    code preview: {chunk.code[:80].strip()!r}")


def _debug_embeddings(ctx):
    embedded = [c for c in ctx.chunks if c.embedding is not None]
    print(f"embeddings: {len(embedded)}/{len(ctx.chunks)} chunks embedded")
    if embedded:
        print(f"  embedding dim: {len(embedded[0].embedding)}")
        print(f"  sample (first 5 values): {embedded[0].embedding[:5]}")


def _debug_symbol_table(ctx):
    from collections import Counter
    kinds = Counter(s.kind for s in ctx.symbol_table.values())
    print(f"symbol_table: {len(ctx.symbol_table)} symbols")
    print(f"  kinds: {dict(kinds.most_common())}")

    in_table = sum(1 for sid in ctx.definition_map if sid in ctx.symbol_table)
    missing = sum(1 for sid in ctx.definition_map if sid not in ctx.symbol_table)
    print(f"definition_map: {len(ctx.definition_map)} entries | in symbol_table={in_table} | missing={missing}")

    for sid in list(ctx.definition_map)[:5]:
        sym = ctx.symbol_table.get(sid)
        print(f"  {sid!r} -> kind={sym.kind if sym else 'NOT IN SYMBOL TABLE'}")

    print(f"occurrences with enclosing_symbol_id: {sum(1 for o in ctx.occurrence_table.values() if o.enclosing_symbol_id)}/{len(ctx.occurrence_table)}")


def _debug_indexing(ctx):
    from collections import Counter

    print(f"files indexed: {len(ctx.file_table)}")
    for path, f in list(ctx.file_table.items())[:5]:
        print(f"  {path!r} (lang={f.language})")

    print(f"\nsymbols found: {len(ctx.symbol_table)}")
    kinds = Counter(s.kind for s in ctx.symbol_table.values())
    print(f"  kinds: {dict(kinds.most_common())}")
    for sid, sym in list(ctx.symbol_table.items())[:5]:
        print(f"  {sym.display_name!r} | kind={sym.kind} | id={sid!r}")

    definitions = [o for o in ctx.occurrence_table.values() if o.is_definition]
    references = [o for o in ctx.occurrence_table.values() if not o.is_definition]
    print(f"\noccurrences: {len(ctx.occurrence_table)} total | {len(definitions)} definitions | {len(references)} references")
    for occ in definitions[:3]:
        print(f"  [def] {occ.symbol_id!r} @ {occ.file_path}:{occ.start_line}")
    for occ in references[:3]:
        print(f"  [ref] {occ.symbol_id!r} @ {occ.file_path}:{occ.start_line}")


def main(argv):
    if len(argv) != 3:
        print("Usage: python -m pipeline.main <path-to-repo> <repo-name>")
        sys.exit(1)

    repo_path = argv[1]
    repo_name = argv[2]

    pipeline = Pipeline()
    ctx = pipeline.run(repo_path=repo_path, repo_name=repo_name)

    print("\n--- indexing results ---")
    _debug_indexing(ctx)

    # print("\n--- symbol table ---")
    # _debug_symbol_table(ctx)

    # print("\n--- dependency graph ---")
    # _debug_dependency_graph(ctx)

    # print("\n--- call graph ---")
    # _debug_call_graph(ctx)

    # print("\n--- chunks ---")
    # _debug_chunks(ctx)

    # print("\n--- embeddings ---")
    # _debug_embeddings(ctx)


if __name__ == "__main__":
    main(sys.argv)
