"""Random useful stuff."""


def find_nodes(key: str, tree):
    """Return all subtrees that have a matching key."""
    if isinstance(tree, dict):
        for i in tree:
            if i == key:
                yield tree
            yield from find_nodes(key, tree[i])
    elif isinstance(tree, list):
        for i in tree:
            yield from find_nodes(key, i)
