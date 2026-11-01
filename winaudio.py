"""Changes the Windows default audio output (undocumented IPolicyConfig COM interface).

It runs in a separate process because soundcard and comtypes initialize COM in
incompatible ways: the app re-launches itself with `--set-default <device id>`.
"""
import os
import subprocess
import sys


def set_default_output(device_id):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--set-default", device_id]
    else:
        python = sys.executable.replace("pythonw.exe", "python.exe")
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "housebeat.py")
        cmd = [python, script, "--set-default", device_id]
    subprocess.run(cmd, check=True, timeout=15, creationflags=flags)


def set_default_now(device_id):
    from ctypes import c_int, c_wchar_p
    import comtypes
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

    class IPolicyConfig(IUnknown):
        _iid_ = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")
        # Only the vtable order matters: the first ten methods are never called
        _methods_ = [COMMETHOD([], HRESULT, f"Unused{i}") for i in range(10)] + [
            COMMETHOD([], HRESULT, "SetDefaultEndpoint",
                      (["in"], c_wchar_p, "device_id"), (["in"], c_int, "role")),
        ]

    policy = comtypes.CoCreateInstance(GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}"),
                                       IPolicyConfig, comtypes.CLSCTX_ALL)
    for role in (0, 1, 2):      # console, multimedia, communications
        policy.SetDefaultEndpoint(device_id, role)
