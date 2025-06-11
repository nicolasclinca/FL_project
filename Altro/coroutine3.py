import asyncio


# Come faccio a eseguire e far lavorare i task contemporaneamente?
# Con il concetto di Tasks (asyncio.create_task())
# 


async def fetch_data(id, sleep_time):
    print(f"Coroutine {id} starting to fecth data")
    await asyncio.sleep(sleep_time)
    return {"id": id, "data": f"Sample data from coroutine{id}"}


async def tasks():
    # Create tasks for running coroutines concurrently
    task1 = asyncio.create_task(fetch_data(1, 2))
    task2 = asyncio.create_task(fetch_data(2, 3))
    task3 = asyncio.create_task(fetch_data(3, 1))
    # Basically it takes 3 seconds only

    result1 = await task1
    result2 = await task2
    result3 = await task3

    print(result1, result2, result3)


async def gather():
    # asyncio.gather ci permette di fare ciò che abbiamo fatto in main a mano, cioè creare i tre task
    # it is not great at error handling and it's not going to automatically cancel other coroutine if one of
    # them were to fail
    results = await asyncio.gather(fetch_data(1, 2), fetch_data(2, 1), fetch_data(3, 3))
    for result in results:
        print(f"Received result: {result}")


# risolve il problema di gather con gli errori e il fatto che non capisce se uno fallisce
async def group():
    tasks = []
    async with asyncio.TaskGroup() as tg:
        for i, sleep_time in enumerate([2, 1, 3], start=1):
            task = tg.create_task(fetch_data(i, sleep_time))
            tasks.append(task)

    # After the Task Group block, all tasks have completed
    results = [tasks.result() for tasks in tasks]

    for result in results:
        print(f"Received result: {result}")

    #asyncio.run(tasks())


#asyncio.run(gather())
asyncio.run(group())
