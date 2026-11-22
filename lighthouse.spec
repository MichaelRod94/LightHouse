# PyInstaller: pyinstaller lighthouse.spec --noconfirm --clean
import re
from PyInstaller.utils.hooks import collect_dynamic_libs
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo)

# Versión y autor salen de lighthouse/__init__.py (Propiedades → Detalles del exe).
src = open("lighthouse/__init__.py", encoding="utf-8").read()
ver = re.search(r'VERSION\s*=\s*"([^"]+)"', src).group(1)
author = re.search(r'__author__\s*=\s*"([^"]+)"', src).group(1)
nums = tuple(int(n) for n in ver.split(".")) + (0,)
version = VSVersionInfo(
    ffi=FixedFileInfo(filevers=nums, prodvers=nums),
    kids=[
        StringFileInfo([StringTable("080A04B0", [  # es-MX, Unicode
            StringStruct("ProductName", "LightHouse"),
            StringStruct("FileDescription", "LightHouse"),
            StringStruct("FileVersion", ver),
            StringStruct("ProductVersion", ver),
            StringStruct("CompanyName", author),
            StringStruct("LegalCopyright", f"© 2026 {author}"),
            StringStruct("OriginalFilename", "LightHouse.exe"),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x080A, 1200])]),
    ],
)

a = Analysis(
    ["run.py"],
    binaries=collect_dynamic_libs("pyaudiowpatch"),
    datas=[("assets/intro", "assets/intro")],  # animación de entrada (tools/ nunca entra al exe)
    excludes=["scipy", "cv2", "PIL", "matplotlib", "pandas"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LightHouse",
          console=False, upx=False, icon="assets/lighthouse.ico", version=version)
coll = COLLECT(exe, a.binaries, a.datas, name="LightHouse", upx=False,
               )
