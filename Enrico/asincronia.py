import asyncio
import time


async def main(duration, wait):

    print(f"Main Start at {time.strftime('%X')}")

    task = asyncio.create_task(operation(duration))  # parte la co-routine, ma il codice non si ferma
    adv = asyncio.create_task(interruption(wait))

    result = await task
    await adv

    print(result)
    print(f"Main end at {time.strftime('%X')}")


async def operation(duration):
    print('Task start')
    for i in range(duration):
        print(duration - i)
        await asyncio.sleep(1)

    return f'Task ended in {duration} seconds'


async def interruption(wait):
    await asyncio.sleep(wait)
    print('Interruption')


asyncio.run(main(5, 2))


