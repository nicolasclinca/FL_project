# FILE DI TEST
"""
File usato per i test specifici, da svolgere in autonomia rispetto agli altri file
"""
from datetime import date


def data_test():
    d0 = date(2000, 7, 27)
    d1 = date(2025, 7, 23)
    delta = d1 - d0
    print(delta.days)


def yield_test():
    def fun(m):
        for i in range(m):
            yield i + 1

            # call the generator function

    for j in fun(5):
        print(j)


yield_test()
