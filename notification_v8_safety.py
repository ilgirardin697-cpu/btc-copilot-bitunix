"""Remove only the exact outbound relay wrapper; all V8 decisions stay frozen."""
import ast
import copy

WRAPPER='''def telegram(message):
    from igod_notifications.client import dispatch_v8
    return dispatch_v8(message, _legacy_telegram)
'''


def normalize_relay_tree(tree):
    tree=copy.deepcopy(tree)
    wrapper=ast.parse(WRAPPER).body[0]
    same=[node for node in tree.body if ast.dump(node)==ast.dump(wrapper)]
    if len(same)!=1:raise AssertionError('V8 outbound wrapper differs from reviewed seam')
    tree.body.remove(same[0])
    old=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='_legacy_telegram']
    if len(old)!=1:raise AssertionError('V8 original sender missing')
    old[0].name='telegram'
    return tree
