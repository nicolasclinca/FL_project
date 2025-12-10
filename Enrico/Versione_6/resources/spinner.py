import itertools
import sys
import asyncio


class Spinner:
    """
    Creates a spinning cursor during the wait phases
    """
    def __init__(self, message="Please, wait", delay=0.6):
        self.cursor = itertools.cycle([
            '    ',
            '.   ',
            '..  ',
            '... ',
        ])

        self.message = message
        self.delay = delay
        self.running = False
        self.spinner_task = None

    async def spin(self):
        while self.running:
            char = next(self.cursor)
            sys.stdout.write(f"\r{self.message} {char}")
            sys.stdout.flush()
            await asyncio.sleep(self.delay)

    def set_message(self, message: str):
        self.message = message

    def start(self, message: str = None):
        if message is not None:
            self.set_message(message)

        self.running = True
        self.spinner_task = asyncio.create_task(self.spin())

    async def restart(self, message: str = None):
        await self.stop()
        self.start(message)

    async def stop(self):
        self.running = False
        if self.spinner_task:
            await self.spinner_task

        sys.stdout.write("\r" + " " * (len(self.message) + 3) + "\r")
        sys.stdout.flush()
