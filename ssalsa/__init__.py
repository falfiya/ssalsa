import abc
import typing as t
from dataclasses import dataclass

type Revision = int
"""
Valid revisions will always be non-negative
"""


class Eq(t.Protocol):
   def __eq__(self, other: t.Self, /) -> bool: ...


class TotalOrder(t.Protocol):
   def __eq__(self, other: object, /) -> bool: ...
   def __le__(self, other: t.Self, /) -> bool: ...


class Hashable(t.Protocol):
   def __hash__(self) -> int: ...

type Extra = TotalOrder | None

class Queryable[*Ts, V: Eq, Ex: Extra](abc.ABC):
   _rt: Runtime

   @abc.abstractmethod
   def query(self, args: tuple[*Ts]) -> Memo[V, Ex]: ...

   def __call__(self, *args: *Ts) -> V:
      m = self.query(args)
      self._rt._ctx_depends_on(
         Dependency(queryable=self, args=args),
         m,
      )
      return m.value

@dataclass(frozen=True)
class Dependency[*Ts, V, Ex: Extra]:
   queryable: Queryable[*Ts, V, Ex]
   args: tuple[*Ts]
   def __eq__(self, other: object) -> bool:
      if not isinstance(other, Dependency):
         raise NotImplementedError
      return self.queryable is other.queryable and self.args == other.args

class Dependencies:
   ids: set[int]
   deps: list[Dependency]
   none: Dependencies

   def __init__(self):
      self.ids = set()
      self.deps = []

   def copy(self) -> Dependencies:
      new = Dependencies()
      new.ids = self.ids.copy()
      new.deps = self.deps.copy()
      return new

   def add(self, dep: Dependency):
      # raise NotImplementedError
      if id(dep) in self.ids:
         return
      else:
         self.ids.add(id(dep))
         self.deps.append(dep)

   def __add__(self, other: object):
      if not isinstance(other, Dependencies):
         return NotImplemented()
      if len(self) > len(other):
         new = self.copy()
         for c in other:
            new.add(c)
      else:
         new = other.copy()
         for c in self:
            new.add(c)
      return new

   def __iter__(self):
      return iter(self.deps)

   def __len__(self):
      return len(self.deps)

   def __repr__(self):
      return repr(self.deps)

   def __contains__(self, dep):
      return id(dep) in self.ids

Dependencies.none = Dependencies()

@dataclass(frozen=True)
class Memo[V: Eq, Ex: Extra]:
   changed_at: Revision
   value: V
   ex: Ex | None
   direct_dependencies: Dependencies

   def all_dependencies(self) -> Dependencies:
      raise NotImplementedError


class Input[V: Eq, Ex: Extra](Queryable[V, Ex]):
   type Setter = t.Callable[[V, Ex], None]
   __present = False

   def __init__(self, rt: Runtime):
      self._rt = rt

   def set(self, value: V, ex: Ex):
      self.__present = True
      self.__changed_at = self._rt.new_revision()
      self.__value = value
      self.__ex = ex

   def query(self, args: tuple) -> Memo[V, Ex]:
      assert self.__present, "Input was not initialized!"
      return Memo(
         changed_at=self.__changed_at,
         value=self.__value,
         ex=self.__ex,
         direct_dependencies=Dependencies.none,
      )


class Database[*Ts, V: Eq, Ex: Extra](Queryable[*Ts, V, Ex]):
   @dataclass(frozen=True)
   class DatabaseMemo(Memo[V, Ex]):
      verified_at: Revision

   def __init__(self, rt: Runtime, calc_fn: t.Callable[[*Ts], V]):
      self._rt = rt
      self.__calc_fn = calc_fn
      self.__memos = {}

   __calc_fn: t.Callable[[*Ts], V]
   __memos: dict[tuple[*Ts], DatabaseMemo[V, Ex]]

   def query(self, args: tuple[*Ts]) -> Memo[V, Ex]:
      if self.__should_compute(args):
         old_memo = self.__memos.get(args)
         new_memo = self.__compute(args)
         if old_memo is not None and old_memo.value == new_memo.value:
            self.__memos[args] = self.DatabaseMemo(
               old_memo.changed_at, # backdating
               new_memo.value,
               new_memo.ex,
               new_memo.direct_dependencies,
               new_memo.verified_at,
            )
         else:
            self.__memos[args] = new_memo
      return self.__memos[args]

   def __should_compute(self, args: tuple[*Ts]) -> bool:
      m = self.__memos.get(args)
      if m is None:
         return True
      if m.verified_at == self._rt.current_revision():
         return False
      for d in m.direct_dependencies:
         m2 = d.queryable.query(d.args)
         if m2.changed_at > m.verified_at:
            return True
      return False

   def __compute(self, args: tuple[*Ts]) -> DatabaseMemo:
      self._rt._capture_computation()
      value = self.__calc_fn(*args)
      direct_dependencies, memos = self._rt._release_computation()
      max_changed_at = 0
      min_ex = None
      for memo in memos:
         max_changed_at = max(max_changed_at, memo.changed_at)
         if min_ex is None or memo.ex < min_ex:
            min_ex = memo.ex
      return self.DatabaseMemo(
         max_changed_at,
         value,
         min_ex,
         direct_dependencies,
         self._rt.current_revision(),
      )


class Runtime[Ex: Extra]:
   __revision = 0

   def __init__(self):
      self.__tracking_dependencies = []
      self.__tracking_memos = []

   __tracking_dependencies: list[Dependencies]
   __tracking_memos: list[list[Memo]]
   """
   The last set[Cell] is active one
   """

   def _capture_computation(self):
      self.__tracking_dependencies.append(Dependencies())
      self.__tracking_memos.append([])

   def _release_computation(self) -> tuple[Dependencies, list[Memo]]:
      return self.__tracking_dependencies.pop(), self.__tracking_memos.pop()

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

   def tracked[*Ts, V: Eq](self, fn: t.Callable[[*Ts], V]) -> Database[*Ts, V, Ex]:
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
