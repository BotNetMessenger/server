from os import environ
from peewee import *

db = PostgresqlDatabase(
    database=environ.get('database'),
    user=environ.get('user'),
    password=environ.get('password'),
    host=environ.get('host')
)


class User(Model):
    name = CharField(unique=True)

    class Meta:
        database = db


class Message(Model):
    receiver = ForeignKeyField(User)
    sender = ForeignKeyField(User)
    text = TextField()
    datetime = DateTimeField()

    class Meta:
        database = db


db.connect()
db.create_tables([User, Message])


if __name__ == '__main__':
    pass
