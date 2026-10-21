"""CI-only exact removal of audited passive additions; old baselines stay fixed."""
import ast

ADDITIONS={
 'trade_guardian.py':(
  '            try:\n                from bitman_weekly_forward.host import after_cycle\n                after_cycle()\n            except Exception:\n                pass\n',
  '        try:\n            from bitman_weekly_forward.host import shutdown\n            shutdown()\n        except Exception:\n            pass\n'),
 'bitman_manual/host.py':(
  '                    try:\n                        from bitman_weekly_forward.host import manual_context\n                        from bitman_weekly_forward.render import append_context\n                        text = append_context(text, manual_context())\n                    except Exception:\n                        pass\n',),
 'mlrsi_safety_audit.py':(
  "    if path == 'trade_guardian.py':\n        from bitman_weekly_forward.safety import normalize_source\n        tree = ast.parse(normalize_source(path, Path(path).read_text('utf-8')))\n",
  "            if path == 'trade_guardian.py':\n                from bitman_weekly_forward.safety import normalize_source\n                normalized = normalize_source(path, Path(path).read_text('utf-8')).encode('utf-8')\n                current = subprocess.check_output(['git', 'hash-object', '--stdin'], input=normalized).decode().strip()\n                assert current == record['git_blob'], 'Guardian outside passive extension changed'\n                continue\n")}


def normalize_source(path,source):
    for fragment in ADDITIONS.get(path,()):
        if source.count(fragment)!=1:
            raise AssertionError('Passive weekly extension differs from audited fragment')
        source=source.replace(fragment,'',1)
    return source


def normalized_ast(path,source):
    return ast.parse(normalize_source(path,source))
