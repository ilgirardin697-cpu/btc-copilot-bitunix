"""Status-only entrypoint. No capture option, scheduler or filesystem writes."""
import json
from pathlib import Path
if __name__=='__main__':
    print(json.dumps(json.loads((Path(__file__).parent/'runtime.json').read_text()),sort_keys=True))
