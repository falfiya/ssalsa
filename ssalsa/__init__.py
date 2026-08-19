import abc
import typing as t
from dataclasses import dataclass

type Revision = int
"""
Valid revisions will always be non-negative
"""


class Eq(t.Protocol):
   def __eq__(self, other: t.Self, /) -> bool: ...


class Hashable(t.Protocol):
   def __hash__(self) -> int: ...


type ExtraOp[Ex] = t.Callable[[Ex, Ex], Ex]
"""
Function must be commutative and associative.
"""


class Arguments:
   """
   Holds args and kwargs.
   """

   # If performance is unsatisfactory, this would be my first idea of where to optimize.
   # But optimize responsibly, use a profiler.

   args: tuple
   kwargs: t.Mapping[str, Hashable]
   __kwargs: tuple
   __hash: int
   """
   For internal hashing usage
   """

   def __init__(self, args, kwargs: t.Mapping[str, Hashable]):
      assert len(args) == 0 or not isinstance(args[0], Arguments)
      self.args = args
      self.kwargs = kwargs
      self.__kwargs = tuple(sorted(kwargs.items()))
      self.__hash = hash((args, self.__kwargs))

   def __hash__(self):
      return self.__hash

   def __eq__(self, other):
      if not isinstance(other, Arguments):
         raise NotImplementedError
      return (self.args, self.__kwargs) == (self.args, self.__kwargs)


class Queryable[**Ps, V: Eq, Ex](abc.ABC):
   _rt: Runtime[Ex]

   def __call__(self, *args: Ps.args, **kwargs: Ps.kwargs) -> V:
      m = self.query(*args, **kwargs)
      self._rt._ctx_depends_on(
         Dependency(self, Arguments(args, kwargs)),
         m,
      )
      return m.value

   @abc.abstractmethod
   def query(self, *args: Ps.args, **kwargs: Ps.kwargs) -> Memo[V, Ex]: ...


@dataclass(frozen=True)
class Dependency[**Ps, V, Ex]:
   queryable: Queryable[Ps, V, Ex]

   # Due to the stupidity of ParamSpec, you cannot unpack them into separate,
   # typesafe objects and store them for later. Brilliant, right!
   # You cannot convert Ps.args to tuple[...]
   a_args: Arguments

   def __post_init__(self): ...

   def __eq__(self, other: object) -> bool:
      if not isinstance(other, Dependency):
         raise NotImplementedError
      return self.queryable is other.queryable and self.a_args == other.a_args

   def __hash__(self) -> int:
      return hash((self.queryable, self.a_args))


@dataclass(frozen=True)
class Memo[V: Eq, Ex]:
   changed_at: Revision
   value: V
   ex: Ex | None
   direct_dependencies: frozenset[Dependency]


class Input[V: Eq, Ex](Queryable[[], V, Ex]):
   __present = False
   __changed_at: Revision
   __value: V
   __ex: Ex | None

   def __init__(self, rt: Runtime[Ex]):
      self._rt = rt

   def set(self, value: V, ex: Ex | None = None):
      self.__present = True
      self.__changed_at = self._rt.new_revision()
      self.__value = value
      self.__ex = ex

   def query(self) -> Memo[V, Ex]:
      assert self.__present, "Input was not initialized!"
      return Memo(
         changed_at=self.__changed_at,
         value=self.__value,
         ex=self.__ex,
         direct_dependencies=frozenset(),
      )


class _MutableMemo[V, Ex]:
   """
   Zero Is Initialization
   """

   verified_at: Revision
   changed_at: Revision
   value: V
   ex: Ex | None
   direct_dependencies: frozenset[Dependency]

   def to_memo(self) -> Memo[V, Ex]:
      return Memo(self.changed_at, self.value, self.ex, self.direct_dependencies)


class Database[**Ps, V: Eq, Ex](Queryable[Ps, V, Ex]):
   __calc_fn: t.Callable[Ps, V]
   __memos: dict[Arguments, _MutableMemo]

   def __init__(self, rt: Runtime[Ex], calc_fn: t.Callable[Ps, V]):
      self._rt = rt
      self.__calc_fn = calc_fn
      self.__memos = {}

   def query(self, *args: Ps.args, **kwargs: Ps.kwargs) -> Memo[V, Ex]:
      """
      Semi-internal Interface

      I am the only one allowed to update `verified_at`.
      """
      a_args = Arguments(args, kwargs)
      mm: _MutableMemo[V, Ex]
      if self.__should_compute(a_args):
         if a_args in self.__memos:
            mm = self.__memos[a_args]
            old_value = mm.value
            old_changed_at = mm.changed_at
            self.__compute(a_args)
            if mm.value == old_value:
               mm.changed_at = old_changed_at  # backdating
         else:
            mm = _MutableMemo()
            self.__memos[a_args] = mm
            self.__compute(a_args)
      else:
         mm = self.__memos[a_args]
      # This is the only location allowed to update verified_at
      mm.verified_at = self._rt.current_revision()
      return mm.to_memo()

   def __should_compute(self, a_args: Arguments) -> bool:
      """
      If a `__MutableMemo` exists for the Arguments I will update `ex`.
      This part of the logic is a little sad. Even though it seems more like the
      responsibility of `query`, I do loop through all `direct_dependencies`.

      It's just convenient to put it here.
      """
      maybe_mm = self.__memos.get(a_args)
      if maybe_mm is None:
         return True
      if maybe_mm.verified_at == self._rt.current_revision():
         return False
      ex_acc = None
      for d in maybe_mm.direct_dependencies:
         m = d.queryable.query(*d.a_args.args, **d.a_args.kwargs)
         ex_acc = self._rt._ex_op(ex_acc, m.ex)
         if m.changed_at > maybe_mm.verified_at:
            return True
      maybe_mm.ex = ex_acc  # Accumulation of ex will also be done in __compute.
      return False

   def __compute(self, a_args: Arguments):
      """
      I don't know anything about how a __MutableMemo gets created or stored or
      when it's updated.

      I am responsible for updating:
      - `changed_at`
      - `value`
      - `ex`
      - `direct_dependencies`
      """
      mm = self.__memos[a_args]
      self._rt._capture_computation()
      value = self.__calc_fn(*a_args.args, **a_args.kwargs)  # type: ignore
      direct_dependencies, memos = self._rt._release_computation()
      max_changed_at = 0
      ex_acc = None
      for m in memos:
         max_changed_at = max(max_changed_at, m.changed_at)
         ex_acc = self._rt._ex_op(ex_acc, m.ex)
      mm.changed_at = max_changed_at
      mm.value = value
      mm.ex = ex_acc
      mm.direct_dependencies = direct_dependencies


class Runtime[Ex]:
   __revision = 0
   __tracking_dependencies: list[set[Dependency]]
   __tracking_memos: list[list[Memo]]
   __ex_op: ExtraOp[Ex] | None

   def __init__(self, ex_op: ExtraOp[Ex] | None = None):
      self.__tracking_dependencies = []
      self.__tracking_memos = []
      self.__ex_op = ex_op

   def _ex_op(self, a: Ex | None, b: Ex | None) -> Ex | None:
      if a is None:
         return b
      if b is None:
         return a
      if self.__ex_op is None:
         return None
      else:
         return self.__ex_op(a, b)

   def _capture_computation(self):
      self.__tracking_dependencies.append(set())
      self.__tracking_memos.append([])

   def _release_computation(self) -> tuple[frozenset[Dependency], list[Memo]]:
      return frozenset(self.__tracking_dependencies.pop()), self.__tracking_memos.pop()

   def _ctx_depends_on(self, d: Dependency, m: Memo):
      """
      Tell the parent query that I was called
      """
      assert len(self.__tracking_dependencies) == len(self.__tracking_memos), (
         "SANITY: __tracking_dependencies and __tracking_memos "
         "must have the same length!"
      )
      if len(self.__tracking_dependencies) > 0:
         self.__tracking_dependencies[-1].add(d)
         self.__tracking_memos[-1].append(m)

   def create_input[V](self):
      return Input[V, Ex](self)

   def tracked[**Ts, V: Eq](self, fn: t.Callable[Ts, V]) -> Database[Ts, V, Ex]:
      return Database(self, fn)

   def current_revision(self) -> Revision:
      return self.__revision

   def new_revision(self) -> Revision:
      """
      Is this threadsafe?
      I've got no GILdea!
      """
      self.__revision += 1
      return self.__revision


if __name__ == "main":
   raise RuntimeError("Hss! Not a ssscript...")
