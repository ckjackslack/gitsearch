import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from functools import partial

# hacks
json.dumps = partial(json.dumps, default=str)