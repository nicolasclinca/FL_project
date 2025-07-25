import itertools
import sys
import asyncio


class Cursor:
    """
    Creates a spinning cursor during the wait phases
    """
    def __init__(self, message="Please, wait", delay=0.1, mode: int = 0):
        if mode == 1:
            self.cursor = itertools.cycle([
                '- ',
                '\\ ',
                '| ',
                '/ '])

        else:  # mode==0
            self.cursor = itertools.cycle([
                '    ',
                '.   ',
                '..  ',
                '... '])

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

    def start(self):
        self.running = True
        self.spinner_task = asyncio.create_task(self.spin())

    async def stop(self):
        self.running = False
        if self.spinner_task:
            await self.spinner_task

        sys.stdout.write("\r" + " " * (len(self.message) + 3) + "\r")
        sys.stdout.flush()
