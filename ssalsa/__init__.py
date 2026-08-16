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


class Dependencies:
   ids: set[int]
   cells: list[Cell]

   def __init__(self):
      self.ids = set()
      self.cells = []

   def copy(self) -> Dependencies:
      new = Dependencies()
      new.ids = self.ids.copy()
      new.cells = self.cells.copy()
      return new

   def add(self, dep: Cell):
      if id(dep) in self.ids:
         return
      else:
         self.ids.add(id(dep))
         self.cells.append(dep)

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
      return iter(self.cells)

   def __len__(self):
      return len(self.cells)

   def __repr__(self):
      return repr(self.cells)


@dataclass
class Memo[V: Eq, Ex: TotalOrder | None]:
   value: V
   changed_at: Revision
   # verified_at: Revision             this would always be the current revision!
   ex: Ex | None
   dependencies: Dependencies


class Cell[*Ts, V: Eq, Ex: TotalOrder | None](abc.ABC):
   is_input: bool
   _rt: Runtime
   """
   MUST ASSIGN!
   """
   _present: bool = False
   """
   `present = False` tells everyone to recompute me
   """
   _changed_at: Revision

   @abc.abstractmethod
   def get_memo(self, *args: *Ts) -> Memo[V, Ex]: ...

   def __call__(self, *args: *Ts) -> V:
      m = self.get_memo(*args)
      self._rt._i_was_called(self, m)
      return m.value


class Input[*Ts, V: Eq, Ex: TotalOrder | None](Cell[*Ts, V, Ex]):
   is_input = True

   def __init__(self, rt: Runtime, producer_fn: t.Callable[[*Ts], tuple[V, Ex]]):
      self._rt = rt
      self.__producer_fn = producer_fn

   __producer_fn: t.Callable[[*Ts], tuple[V, Ex]]
   __value: V
   __ex: Ex | None

   def get_memo(self, *args: *Ts) -> Memo[V, Ex]:
      if self.__should_fetch():
         v, ex = self.__producer_fn(*args)
         self.__value = v
         self.__ex = ex
         # NOTE(nicola): Somehow I feel like this will cause an issue later.
         # I have no proof of it. Should this be self.__rt.new_revision()?
         # But then it would change revisions mid calc-chain, which is awful.
         self._changed_at = self._rt.current_revision()
      return Memo(
         value=self.__value,
         changed_at=self._changed_at,
         ex=self.__ex,
         dependencies=Dependencies(),
      )

   def __should_fetch(self):
      """
      Only fetches once by default.
      Yes, I will spell out both branches thankyouverymuch.
      """
      if self._present:  # noqa: SIM103
         # This is even stronger than self.verified_at == self.__rt.current_revision()
         return False
      else:
         return True

   def invalidate(self):
      new_rev = self._rt.new_revision()
      self._present = False
      self._changed_at = new_rev
      del self.__value
      self.__ex = None


class Calc[*Ts, V: Eq, Ex: TotalOrder | None](Cell[*Ts, V, Ex]):
   is_input = False

   def __init__(self, rt: Runtime, calc_fn: t.Callable[[*Ts], V]):
      self._rt = rt
      self.__calc_fn = calc_fn

   __calc_fn: t.Callable[[*Ts], V]
   __value: V
   __verified_at: Revision
   __ex: Ex | None = None
   __dependencies: Dependencies
   __all_dependencies: Dependencies

   def get_memo(self, *args: *Ts) -> Memo[V, Ex]:
      if self.__should_recompute():
         self._rt._capture_computation()
         new_value = self.__calc_fn(*args)
         self.__dependencies, memos = self._rt._release_computation()
         max_changed_at = 0
         min_ex = None
         all_dependencies = self.__dependencies
         for memo in memos:
            max_changed_at = max(max_changed_at, memo.changed_at)
            if min_ex is None or memo.ex < min_ex:
               min_ex = memo.ex
            all_dependencies += memo.dependencies
         self.__ex = min_ex
         self.__all_dependencies = all_dependencies
         if self._present and new_value == self.__value:
            # Backdate: No update to changed_at
            pass
         else:
            self.__value = new_value
            self._changed_at = max_changed_at
      self.__verified_at = self._rt.current_revision()
      return Memo(
         value=self.__value,
         changed_at=self._changed_at,
         ex=self.__ex,
         dependencies=self.__all_dependencies,
      )

   def __should_recompute(self) -> bool:
      if self._present:
         assert self.__verified_at is not None
         assert self.__dependencies is not None
      else:
         return True
      if self.__verified_at == self._rt.current_revision():
         return False
      for d in self.__dependencies:
         if not d._present:
            return True
         if d._changed_at > self.__verified_at:
            return True
      return False


class Runtime[Ex: TotalOrder | None]:
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

   def _i_was_called(self, i: Cell, m: Memo):
      """
      Tell the parent cell that I was called
      """
      self.__tracking_dependencies[-1].add(i)
      self.__tracking_memos[-1].append(m)

   def input[*Ts, V](self, fn: t.Callable[[*Ts], tuple[V, Ex]]) -> Input[*Ts, V, Ex]:
      return Input(self, fn)

   def tracked[*Ts, V: Eq](self, fn: t.Callable[[*Ts], V]) -> Calc[*Ts, V, Ex]:
      return Calc(self, fn)

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
