"""Регресс багханта 2026-11-14: AST-песочница run_python и tar-slip в клонере кода."""

import io
import os
import tarfile

import pytest

import api.index as api


EXPLOITS = [
    "().__class__.__bases__[0].__subclasses__()",
    "getattr((), '__class__')",
    "__builtins__['open']('/etc/passwd')",
    "'{0.__class__}'.format(())",
    "import io\nio.open('/proc/self/stat')",
    "import os",
    "eval('1')",
    "(x for x in []).gi_frame.f_builtins['open']",
    "open('/etc/passwd')",
    "vars(())",
    "import operator\noperator.attrgetter('__class__')(())",
    "import builtins\nbuiltins.open('/etc/passwd')",
    "x = []\nx.__class__.__mro__",
]


@pytest.mark.parametrize("code", EXPLOITS)
def test_sandbox_blocks_escape_chains(code):
    res = api._run_python_sandbox(code, timeout=5)
    assert res["error"].startswith("Blocked"), res


LEGIT = [
    "print(sum(range(10)))",
    "x = [i*i for i in range(5)]\nprint(x)",
    "def f(a):\n    return a+1\nprint(f(2))",
    "import math\nprint(math.sqrt(16))",
    "d = {'a': 1}\nprint(d['a'])",
]


@pytest.mark.parametrize("code", LEGIT)
def test_sandbox_allows_legit_code(code):
    res = api._run_python_sandbox(code, timeout=5)
    assert res["ok"], res
    assert res["stdout"]


def _tarball(members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, kind, linkname, data in members:
            info = tarfile.TarInfo(name)
            if kind == "sym":
                info.type = tarfile.SYMTYPE
                info.linkname = linkname
                tf.addfile(info)
            else:
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class _FakeResponse:
    status_code = 200

    def __init__(self, content):
        self.content = content


def test_clone_repo_drops_escaping_symlink(tmp_path, monkeypatch):
    payload = _tarball(
        [
            ("repo-main/evil", "sym", "../../..", b""),
            ("repo-main/evil/pwned.txt", "file", "", b"pwned"),
            ("repo-main/ok.txt", "file", "", b"ok"),
        ]
    )
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: _FakeResponse(payload))
    dest = tmp_path / "dest"
    dest.mkdir()
    outside = tmp_path / "pwned.txt"
    assert api._code_clone_repo("https://github.com/x/y", str(dest))
    assert not outside.exists()
    assert (dest / "ok.txt").read_bytes() == b"ok"
    # симлинк отброшен, файл лёг внутрь dest как обычный каталог
    assert (dest / "evil" / "pwned.txt").read_bytes() == b"pwned"


def test_clone_repo_contains_absolute_path(tmp_path, monkeypatch):
    payload = _tarball(
        [
            ("repo-main/ok.txt", "file", "", b"ok"),
            ("/tmp/abs_pwned.txt", "file", "", b"pwned"),
        ]
    )
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: _FakeResponse(payload))
    dest = tmp_path / "dest"
    dest.mkdir()
    assert api._code_clone_repo("https://github.com/x/y", str(dest))
    # filter="data" срезает ведущий "/" — файл остаётся внутри dest
    assert not os.path.exists("/tmp/abs_pwned.txt")
    assert (dest / "tmp" / "abs_pwned.txt").read_bytes() == b"pwned"