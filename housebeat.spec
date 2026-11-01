# PyInstaller spec: python -m PyInstaller housebeat.spec  ->  dist/HouseBeat.exe
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [("web", "web")] + collect_data_files("soundcard")
hiddenimports = collect_submodules("zeroconf") + collect_submodules("pychromecast") + ["pystray._win32"]

a = Analysis(
    ["housebeat.py"],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="HouseBeat",
    icon="web/icon.ico",
    console=False,
    upx=False,
)
