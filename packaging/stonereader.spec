from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata


datas = copy_metadata("stonereader")
datas += collect_data_files("hearthstone_data")

accessible_datas, accessible_binaries, accessible_hiddenimports = collect_all(
    "accessible_output2"
)
unitypy_datas, unitypy_binaries, unitypy_hiddenimports = collect_all("UnityPy")

datas += accessible_datas + unitypy_datas
binaries = accessible_binaries + unitypy_binaries
hiddenimports = ["fsb5", *accessible_hiddenimports, *unitypy_hiddenimports]

a = Analysis(
    ["launch.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StoneReader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="StoneReader",
)
