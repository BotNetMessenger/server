import asyncio
import logging
import concurrent

from grpclib.server import Server
from network_pb2 import *
from network_grpc import BotNodeBase

import arrow
import syncdb as db


logger = logging.getLogger('server')
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(
    logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
)

logger.addHandler(ch)


class BotNode(BotNodeBase):
    def __init__(self):
        self.chat = {}
        self.online = {}

    async def GetInfo(self, stream):
        await stream.send_message(ServerInfo(description="Dinora"))

    async def Register(self, stream):
        request = await stream.recv_message()
        name = request.name
        user = db.User(name=name)
        try:
            user.save()
            await stream.send_message(
                Status(value=True))
        except db.IntegrityError:
            await stream.send_message(
                Status(value=False))

    async def SendMessage(self, stream):
        request = await stream.recv_message()

        receiver = db.User.get(db.User.name == request.receiver)
        sender = db.User.get(db.User.name == request.sender)

        msg_datetime = arrow.utcnow().datetime
        msg = db.Message(
            receiver=receiver,
            sender=sender,
            text=request.text,
            datetime=msg_datetime
        )
        msg.save()
        logger.debug('Save message in db'
                     f'\n\treceiver: {msg.receiver}'
                     f'\n\tsender: {msg.sender}'
                     f'\n\ttext: {msg.text}'
                     f'\n\tdatetime: {msg.datetime}')

        if request.receiver in self.online:
            self.online[request.receiver].set()
            self.chat[request.receiver] = request.sender, request.text
            logger.debug(f'Send message to {request.receiver}')

    async def GetMessages(self, stream):
        request = await stream.recv_message()
        user = db.User.get(db.User.name == request.name)

        for msg in db.Message.select().where(
            db.Message.receiver == user,
            db.Message.datetime > arrow.get(request.lastlogin).datetime  # ISO 8601
        ):
            logger.debug(f'Send archived message: \n\t{msg.text}\nto {user.name}')
            await stream.send_message(
                Message(
                    sender=msg.sender.name,
                    text=msg.text
                )
            )

        self.online[user.name] = asyncio.Event()
        try:
            while True:
                logger.debug(f'<{user.name}> is now online, '
                             f'lastlogin: {request.lastlogin}, '
                             f'wait new messenges')
                await self.online[user.name].wait()
                logger.debug(f'<{user.name}> triggered')
                self.online[user.name].clear()

                sender, text = self.chat[user.name]
                logger.debug(f'<{user.name}> Get message')
                await stream.send_message(
                    Message(
                        sender=sender,
                        text=text
                    )
                )
        except concurrent.futures._base.CancelledError:
            logger.debug(f'User <{user.name}> out')
            del self.online[user.name]
            if user.name in self.chat:
                del self.chat[user.name]

    async def IsOnline(self, stream):
        pass


class BotServer:
    def __init__(self):
        self.botnode = BotNode()

    def run(self):
        loop = asyncio.get_event_loop()
        server = Server([BotNode()], loop=loop)

        host, port = '0.0.0.0', 50051
        loop.run_until_complete(server.start(host, port))
        logger.debug(f'Serving on {host}:{port}')
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()


if __name__ == '__main__':
    BotServer().run()
