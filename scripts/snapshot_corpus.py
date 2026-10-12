"""Copy the committed source into DVC's reproducible corpus snapshot stage."""

import shutil
from pathlib import Path

source = Path("eval/corpus/egyptian-civil-code.pdf")
target = Path("data/corpus/egyptian-civil-code.pdf")
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, target)
