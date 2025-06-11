import asyncio

# utilizzando async, vado a definire una funzione asincrona (una coroutine)
# main() ---> coroutine object, that need to be awaited

# await si può usare solo in una async function o coroutine function


# Define a coroutine that simulates a time-consuming task
async def fetch_data(delay):
    print("Fetching data...")
    await asyncio.sleep(delay)    # Simulate an I/O operation with a sleep
    print("Data fetched!")
    return {"data": "Some data"}    # Return the data


# Define another coroutine that calls the first coroutine
async def main():
    print("Start of the main coroutine")
    task = fetch_data(2)   # ---> we have created the coroutine object, need to be awaited.
    # It starts its execution when it is awaited
    # Await the fetch_data coroutine, pausing execution of main until fetch_data completes
    result = await task   # starts the execution of the coroutine
    print(f"Received result:  {result}")
    print("End of the main coroutine")
    
    
# Run the main coruotine 
asyncio.run(main())
