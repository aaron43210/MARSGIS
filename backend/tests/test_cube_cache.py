"""Downloaded areas stay within the disk budget, oldest first, never the one in use."""

from __future__ import annotations

import os


def _cube(d, name, mb, age):
    img = d / f"{name}.img"
    img.write_bytes(b"\0" * int(mb * 1024 * 1024))
    (d / f"{name}.hdr").write_text("ENVI")
    os.utime(img, (age, age))
    return img


def test_prunes_least_recently_used_but_keeps_current(tmp_path):
    from app.config import Settings
    from app.services.jobs.tasks import prune_cube_cache

    cubes = tmp_path / "cubes"
    cubes.mkdir()
    oldest = _cube(cubes, "a_strip_small", 4, 1000)
    middle = _cube(cubes, "b_strip_small", 4, 2000)
    current = _cube(cubes, "c_strip_small", 4, 500)  # oldest mtime but in use
    partial = cubes / "d_strip_small_partial_x.img"
    partial.write_bytes(b"\0" * 1024)

    s = Settings(storage_root=str(tmp_path), cube_cache_max_gb=9 / 1024)  # 9 MB budget
    prune_cube_cache(s, keep=current)

    assert current.exists() and partial.exists()
    assert not oldest.exists() and not oldest.with_suffix(".hdr").exists()
    assert middle.exists()


def test_zero_means_no_limit(tmp_path):
    from app.config import Settings
    from app.services.jobs.tasks import prune_cube_cache

    cubes = tmp_path / "cubes"
    cubes.mkdir()
    a = _cube(cubes, "a", 2, 1000)
    prune_cube_cache(Settings(storage_root=str(tmp_path), cube_cache_max_gb=0), keep=a)
    assert a.exists()
