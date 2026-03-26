"""Allow running Kevin as `python -m kevin`."""

from kevin.cli import main
import sys

sys.exit(main())
