#!/usr/bin/env python3
from __future__ import annotations

import sysconfig
from pathlib import Path


OLD_BLOCK = """    selected_device = (
        os.environ.get("CUDA_VISIBLE_DEVICES", None)
        if os.environ.get("MUJOCO_EGL_DEVICE_ID", None) is None
        else os.environ.get("MUJOCO_EGL_DEVICE_ID", None)
    )
"""

NEW_BLOCK = """    # CUDA_VISIBLE_DEVICES contains physical IDs, while EGL enumerates only
    # the devices visible inside this process. Use an explicit logical EGL index
    # when provided; otherwise let device_id select logical device 0.
    selected_device = os.environ.get("MUJOCO_EGL_DEVICE_ID", None)
"""


def main() -> None:
    site_packages = Path(sysconfig.get_paths()["purelib"])
    candidates = [site_packages / "robosuite/renderers/context/egl_context.py"]
    try:
        import robosuite

        candidates.insert(
            0,
            Path(robosuite.__file__).resolve().parent / "renderers/context/egl_context.py",
        )
    except ImportError:
        pass
    target = next((path for path in candidates if path.is_file()), None)
    if target is None:
        raise FileNotFoundError(
            "Could not find robosuite EGL context. Checked: "
            + ", ".join(str(path) for path in candidates)
        )

    text = target.read_text(encoding="utf-8")
    if NEW_BLOCK in text:
        print(f"robosuite EGL patch already applied: {target}")
        return
    if OLD_BLOCK not in text:
        raise RuntimeError(f"Expected robosuite EGL block was not found in {target}")

    backup = target.with_suffix(".py.orig")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    target.write_text(text.replace(OLD_BLOCK, NEW_BLOCK, 1), encoding="utf-8")
    print(f"patched robosuite EGL logical-device selection: {target}")


if __name__ == "__main__":
    main()
