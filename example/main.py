import ssalsa
import random

s = ssalsa.Runtime[None]()

a = s.create_input()
b = s.create_input()

@s.tracked
def c():
   print(f"c() = {a()} + {b()} = {a() + b()}")
   return a() + b()


@s.tracked
def d(x):
   print(f"d({x}) = {x} // 2 = {x // 2}")
   return x // 2

@s.tracked
def e():
   print(f"e() = d(c()) = d({c()}) = {d(c())}")
   return d(c())

@s.tracked
def print_it():
   print(f"The result was {e()}")

a.set(1, None)
b.set(2, None)
print_it()
# Full Compute
#     c() = 1 + 2 = 3
#     d(3) = 3 // 2 = 1
#     e() = d(c()) = d(3) = 1
#     The result was 1
b.set(1, None)
# Partial compute
#     c() = 1 + 1 = 2
#     d(2) = 2 // 2 = 1
#     e() = d(c()) = d(2) = 1
# Does not print_it!
print_it()
