"""CI-only exact passive seam removal. No historical hash is replaced."""
import ast
import copy

TRADE=(
 'from guardian_hedge.host import install as install_hedge_readonly, after_cycle as hedge_readonly_after_cycle, intercept_ambiguous, shutdown as shutdown_hedge_readonly\n',
 '        install_hedge_readonly(guardian)\n',
 '            try:\n                hedge_readonly_after_cycle(guardian)\n            except Exception:\n                pass\n',
 '        shutdown_hedge_readonly()\n',
 '        if intercept_ambiguous(self, key, notice):\n            return  # Read-only evidence; never unblocks the protection client.\n')
OLD_READ='    def read(self):\n        with self._lock:\n            return copy.deepcopy(self._value)\n'
NEW_READ="    def read(self):\n        with self._lock:\n            value = copy.deepcopy(self._value)\n            if self._readonly_value is not None:\n                value = value or {}\n                value['hedge_readonly'] = copy.deepcopy(self._readonly_value)\n            return value\n"
INIT='        self._readonly_value = None\n'
PUBLISH='    def publish_readonly(self, value):\n        with self._lock:\n            self._readonly_value = copy.deepcopy(value)\n\n'
RENDER="    if 'hedge_readonly' in snapshot:\n        if command in ('/position', '/risk'):\n            from guardian_hedge.render import render_view\n            return render_view(command, snapshot['hedge_readonly'], now)\n        if 'timestamp' not in snapshot:\n            return NO_DATA\n"

def normalize_readonly(path,source):
    if path=='trade_guardian.py' and TRADE[0] in source:
        for fragment in TRADE:
            if source.count(fragment)!=1:raise AssertionError('Read-only hook outside exact passive seam')
            source=source.replace(fragment,'',1)
    if path=='guardian_commands.py' and '    def publish_readonly(self, value):' in source:
        for fragment in (INIT,PUBLISH,RENDER):
            if source.count(fragment)!=1:raise AssertionError('Read-only command hook differs')
            source=source.replace(fragment,'',1)
        if source.count(NEW_READ)!=1:raise AssertionError('Read-only cache modified')
        source=source.replace(NEW_READ,OLD_READ,1)
    return source

def strip_readonly(tree):
    tree=copy.deepcopy(tree)
    classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SnapshotCache']
    if not classes:return tree
    cls=classes[0]
    if not any(isinstance(n,ast.FunctionDef) and n.name=='publish_readonly' for n in cls.body):return tree
    fp=lambda n:ast.dump(n,include_attributes=False)
    def parsed(text):return ast.parse('class C:\n'+text).body[0].body[0]
    publish=parsed(PUBLISH);new=parsed(NEW_READ);old=parsed(OLD_READ)
    matches=[n for n in cls.body if fp(n)==fp(publish)]
    if len(matches)!=1:raise AssertionError('Read-only publish AST differs')
    cls.body.remove(matches[0]);matches=[i for i,n in enumerate(cls.body) if fp(n)==fp(new)]
    if len(matches)!=1:raise AssertionError('Read-only read AST differs')
    cls.body[matches[0]]=old
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    expected=ast.parse(INIT.strip()).body[0];matches=[n for n in init.body if fp(n)==fp(expected)]
    if len(matches)!=1:raise AssertionError('Read-only init AST differs')
    init.body.remove(matches[0])
    render=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_command')
    expected=ast.parse('def f():\n'+RENDER).body[0].body[0];matches=[n for n in render.body if fp(n)==fp(expected)]
    if len(matches)!=1:raise AssertionError('Read-only renderer AST differs')
    render.body.remove(matches[0]);return tree
