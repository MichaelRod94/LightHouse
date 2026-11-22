# PyInstaller: pyinstaller lighthouse.spec --noconfirm --clean
from PyInstaller.utils.hooks import collect_dynamic_libs

a = Analysis(
    ["run.py"],
    binaries=collect_dynamic_libs("pyaudiowpatch"),
    excludes=["scipy", "cv2", "PIL", "matplotlib", "pandas"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LightHouse",
          console=False, upx=False, icon="assets/lighthouse.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="LightHouse", upx=False,
               )
