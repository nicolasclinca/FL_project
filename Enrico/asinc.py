import asyncio
import time

delay_1 = 2
delay_2 = 3

async def say_after(delay, what):
    await asyncio.sleep(delay)
    print(what)


async def main_1():
    print(f"started at {time.strftime('%X')}")

    await say_after(delay_1, 'hello')
    await say_after(delay_2, 'world')

    print(f"finished at {time.strftime('%X')}")

async def main_2():
    task1 = asyncio.create_task(
        say_after(delay_1, 'hello'))

    task2 = asyncio.create_task(
        say_after(delay_2, 'world'))

    print(f"started at {time.strftime('%X')}")

    # Wait until both tasks are completed (should take
    # around 2 seconds.)
    await task1
    await task2

    print(f"finished at {time.strftime('%X')}")

async def main_3():
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(
            say_after(delay_1, 'hello'))

        task2 = tg.create_task(
            say_after(delay_2, 'world'))

        print(f"started at {time.strftime('%X')}")

    # The await is implicit when the context manager exits.

    print(f"finished at {time.strftime('%X')}")


asyncio.run(main_3())
