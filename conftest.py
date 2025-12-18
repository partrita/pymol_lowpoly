import sys
from unittest.mock import MagicMock

# Mock PyMOL modules globally so tests can run without PyMOL installed
# ALWAYS mock pymol for these unit tests to avoid needing a GUI/license/compiled modules
cgo_mock = MagicMock()
cgo_mock.BEGIN = 2.0
cgo_mock.END = 3.0
cgo_mock.TRIANGLES = 4.0
cgo_mock.VERTEX = 14.0
cgo_mock.NORMAL = 13.0
cgo_mock.COLOR = 6.0
sys.modules['pymol.cgo'] = cgo_mock

pymol_mock = MagicMock()
pymol_mock.cgo = cgo_mock # IMPORTANT: Link the module attribute
sys.modules['pymol'] = pymol_mock

# We must ensure pymol.cmd is also a mock
cmd_mock = MagicMock()
sys.modules['pymol.cmd'] = cmd_mock
pymol_mock.cmd = cmd_mock

sys.modules['pymol.Qt'] = MagicMock()
