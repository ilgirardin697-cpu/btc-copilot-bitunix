"""CI-only exact removal of the reviewed passive command extension."""
import ast
import copy
import json
from pathlib import Path

FRAGMENTS = json.loads(Path(__file__).with_name('daily_router_extension.json').read_text('utf-8'))


def normalize_router(source):
    for fragment in FRAGMENTS:
        if source.count(fragment) != 1:
            raise AssertionError('Daily router differs from exact reviewed extension')
        source = source.replace(fragment, '', 1)
    return source


def strip_router(tree):
    """Only remove exact AST nodes from these passive fragments; no hash reset."""
    tree = copy.deepcopy(tree)
    def fingerprint(node):
        return ast.dump(node, include_attributes=False)
    for fragment in reversed(FRAGMENTS):
        expected = ast.parse(fragment if not fragment.startswith(' ') else 'def f():\n' + fragment)
        if fragment.startswith(' '):
            expected_nodes = expected.body[0].body
        else:
            expected_nodes = expected.body
        for target in expected_nodes:
            matches = []
            for node in ast.walk(tree):
                for _, value in ast.iter_fields(node):
                    if isinstance(value, list):
                        for index, child in enumerate(value):
                            if isinstance(child, ast.AST) and fingerprint(child) == fingerprint(target):
                                matches.append((value,index))
            if len(matches) != 1:
                raise AssertionError('Daily extension AST changed')
            values,index=matches[0]
            values.pop(index)
    return tree
