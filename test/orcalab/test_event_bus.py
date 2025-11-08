from orcalab.event_bus import create_event_bus
import unittest
import asyncio


class Foo:
    def a(self):
        pass

    async def b(self):
        pass


FooBus = create_event_bus(Foo)

foo = FooBus()


class Handler(Foo):
    def __init__(self):
        super().__init__()
        FooBus.connect(self)

    def destroy(self):
        FooBus.disconnect(self)

    def a(self, l):
        l.append("a")

    async def b(self, l):
        l.append("b")


class TestEventBus(unittest.TestCase):
    def test_no_handler(self):
        l = []
        FooBus().a(l)
        self.assertEqual(len(l), 0)

    def test_one_handler(self):
        h = Handler()
        l = []
        FooBus().a(l)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0], "a")
        h.destroy()

    def test_two_handlers(self):
        h1 = Handler()
        h2 = Handler()
        l = []
        FooBus().a(l)
        self.assertEqual(len(l), 2)
        self.assertEqual(l[0], "a")
        self.assertEqual(l[1], "a")
        h1.destroy()
        h2.destroy()

    def test_async_no_handler(self):
        async def run():
            l = []
            await FooBus().b(l)
            self.assertEqual(len(l), 0)

        asyncio.run(run())

    def test_async_one_handler(self):
        h = Handler()

        async def run():
            l = []
            await FooBus().b(l)
            self.assertEqual(len(l), 1)
            self.assertEqual(l[0], "b")

        asyncio.run(run())
        h.destroy()

    def test_async_two_handlers(self):
        h1 = Handler()
        h2 = Handler()

        async def run():
            l = []
            await FooBus().b(l)
            self.assertEqual(len(l), 2)
            self.assertEqual(l[0], "b")
            self.assertEqual(l[1], "b")

        asyncio.run(run())
        h1.destroy()
        h2.destroy()


if __name__ == "__main__":
    unittest.main()
