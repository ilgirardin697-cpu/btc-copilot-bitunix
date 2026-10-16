"""Exact AST normalization of only the authorized /bitman command additions."""
import ast
from pathlib import Path
import subprocess

PRODUCTION_BASE = '5e6c63926015dd31217948de2b2e6e9a5fa5cee4'
HELP_LINE = '/bitman\n→ contexto direccional BTC, manual y SHADOW ONLY\n\n'


def fingerprint(tree):
    return ast.dump(tree, include_attributes=False)


def remove(body, source):
    wanted = fingerprint(ast.parse(source).body[0])
    matches = [node for node in body if fingerprint(node) == wanted]
    assert len(matches) == 1, 'Unexpected BITMAN command integration'
    body.remove(matches[0])


def strip_commands(tree):
    remove(tree.body, 'from bitman_manual.render import unavailable as bitman_unavailable')
    commands = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == 'COMMANDS')
    assert commands.value.elts[-1].value == '/bitman'
    commands.value.elts.pop()
    help_node = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == 'HELP')
    assert help_node.value.value.count(HELP_LINE) == 1
    help_node.value.value = help_node.value.value.replace(HELP_LINE, '')
    renderer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'render_command')
    remove(renderer.body, """if command == '/bitman':
    return bitman_unavailable()""")
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TelegramCommands')
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
    remove(init.body, 'self._bitman = None')
    remove(cls.body, """def _request_bitman(self):
    try:
        if self._bitman is None:
            from bitman_manual.host import BitmanHost
            self._bitman = BitmanHost()
        return self._bitman.request(self._reply)
    except Exception:
        return bool(self._reply(bitman_unavailable()))""")
    process = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'process')
    block = next(n for n in process.body if isinstance(n, ast.Try))
    remove(block.body, """if command == '/bitman':
    return self._request_bitman()""")
    stop = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'stop')
    remove(stop.body, """if self._bitman is not None:
    try:
        self._bitman.stop()
    except Exception:
        pass""")
    return tree


def verify_command_extension():
    current = strip_commands(ast.parse(Path('guardian_commands.py').read_text('utf-8')))
    original = subprocess.check_output(['git', 'show', PRODUCTION_BASE + ':guardian_commands.py']).decode('utf-8')
    assert fingerprint(current) == fingerprint(ast.parse(original)), 'Existing command policy/logic changed'
    return True
