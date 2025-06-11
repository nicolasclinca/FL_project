import asyncio


# Define a coroutine that simulates a time-consuming task
async def fetch_data(delay, id):
    print("Fetching data... id:", id)
    await asyncio.sleep(delay)  # Simulate an I/O operation with a sleep
    print("Data fecthed! id:", id)
    return {"data:": "Some data", "id": id}  # Return some data


# Define another coroutine that calls the first coroutine
async def main():
    task1 = fetch_data(2, 1)
    task2 = fetch_data(2, 2)

    result1 = await task1
    print(f"Received result: {result1}")

    result2 = await task2
    print(f"Received result: {result2}")


# Run the main coroutine
asyncio.run(main())
# Che succede in questo caso? definiamo i due task, ricordiamo che i task partono quando
# sono awaited. In questo caso specifico viene eseguito il task 1, che termina e stampa i risultati
# poi viene eseguito il task 2 che stampa i risultati
# Quindi in realtà NON ci sono stati benefit nel fare questo codice, nessun miglioramento di performance,
# non c'è esecuzione concorrente

# Come faccio a eseguire e far lavorare i task contemporaneamente?
# Con il concetto di Tasks (asyncio.create_task())
