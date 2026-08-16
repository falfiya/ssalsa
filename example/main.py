import ssalsa
import random

s = ssalsa.Runtime[None]()


@s.input
def a():
   return random.randint(1, 9), None


@s.input
def b():
   return random.randint(1, 9), None


@s.tracked
def c():
   return a() + b()


@s.tracked
def times_two():
   return c() * 2


print(times_two.get_memo())
