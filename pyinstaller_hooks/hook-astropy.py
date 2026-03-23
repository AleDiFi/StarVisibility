"""Local PyInstaller hook for astropy.

The community hook often attempts to collect *all* astropy submodules.
That can fail when optional visualization dependencies are missing because
some astropy visualization modules raise pytest.Skip (not ImportError).

StarVisibility only needs a small subset of astropy (coordinates/time/units/table),
so we explicitly collect those and avoid the visualization stack.
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, get_package_paths

hiddenimports = []

# Collect submodules from the parts of astropy used by this application.
for _pkg in (
	"astropy.coordinates",
	"astropy.time",
	"astropy.units",
	"astropy.constants",
	"astropy.table",
	"astropy.utils",
):
	hiddenimports += collect_submodules(_pkg, on_error="ignore")

# Bundle astropy data files (e.g. built-in data/config).
datas = collect_data_files("astropy")

# PLY parser table files (generic_parsetab.py, lextab.py, etc.) are read as
# plain text by astropy.utils.parsing._patch_ply_module — they won't work if
# stored only inside the ZlibArchive. Add them explicitly as data files so
# they are extracted to disk next to the other astropy files.
_pkg_base, _pkg_dir = get_package_paths("astropy")
for _root, _dirs, _files in os.walk(_pkg_dir):
    for _fname in _files:
        if _fname.endswith("parsetab.py") or _fname.endswith("lextab.py"):
            _src = os.path.join(_root, _fname)
            _dst = os.path.relpath(_root, _pkg_base)
            datas.append((_src, _dst))
