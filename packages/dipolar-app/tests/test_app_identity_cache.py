"""The identity caches of M3 step 4b (dipolar_app.project.ByIdentity): values derived from an
immutable project are computed once while the project is current, and never confused between
projects."""

from __future__ import annotations

from dipolar_app import science
from dipolar_app.project import ByIdentity, load_example, science_hash


def test_a_value_is_computed_once_per_object_and_never_shared_between_objects() -> None:
    cache = ByIdentity(size=2)
    calls: list[str] = []

    def compute(tag: str) -> str:
        calls.append(tag)
        return tag

    a, b, c = object(), object(), object()
    assert cache.get(a, lambda: compute("a")) == "a"
    assert cache.get(a, lambda: compute("again")) == "a"  # cached
    assert cache.get(b, lambda: compute("b")) == "b"
    assert cache.get(c, lambda: compute("c")) == "c"  # evicts a (size 2)
    assert cache.get(a, lambda: compute("a2")) == "a2"
    assert calls == ["a", "b", "c", "a2"]


def test_a_value_depends_on_its_tag_too() -> None:
    """The hashes cover the numerical context as well as the project: a different context is a
    different value for the same object."""
    cache = ByIdentity()
    key = object()
    assert cache.get(key, lambda: 1, tag={"table": "a"}) == 1
    assert cache.get(key, lambda: 2, tag={"table": "a"}) == 1  # an equal tag: cached
    assert cache.get(key, lambda: 3, tag={"table": "b"}) == 3


def test_a_failed_computation_is_not_cached() -> None:
    cache = ByIdentity()
    key = object()

    def fail() -> str:
        raise ValueError("not ready")

    try:
        cache.get(key, fail)
    except ValueError:
        pass
    assert cache.get(key, lambda: "ok") == "ok"


def test_equal_projects_hash_equal_and_copies_are_not_confused() -> None:
    project = load_example("biphenyl-synthetic")
    copy = project.model_copy(update={"name": "another name"})
    assert science_hash(project) == science_hash(project)
    assert science_hash(copy) != science_hash(project)  # a different object is hashed itself
    twin = project.model_copy()
    assert twin is not project and science_hash(twin) == science_hash(project)


def test_the_problem_is_built_once_per_project(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    project = load_example("biphenyl-synthetic").model_copy()  # a fresh object, not cached yet
    built: list[object] = []
    original = science._problem_for

    def counting(p: object) -> object:
        built.append(p)
        return original(p)  # type: ignore[arg-type]

    monkeypatch.setattr(science, "_problem_for", counting)
    first = science.problem_for(project)
    assert science.problem_for(project) is first
    assert built == [project]
