from datetime import datetime
from urwid import (ListBox, SimpleFocusListWalker, Frame, MainLoop, Edit, Text,
                   ExitMainLoop, AsyncioEventLoop)
from threading import Thread
from websockets import connect
from asyncio import run, new_event_loop
from sys import stdout, argv
from os import _exit
from os.path import dirname, realpath
from shutil import get_terminal_size
from time import time
from textwrap import wrap
dir = dirname(realpath(__file__))


TITLE = "chain (beta)"
MAX_LENGTH = 500
RATE_LIMIT = 0.25


columns = get_terminal_size().columns - 1
stdout.write(f"\x1b]2;{TITLE}\x07") # tries to set console title
online_people = set()
offline_people = set()

try:
    with open(dir + "/.chain") as file:
        data = file.read()
    data = data.split("\n")
    def parse(a):
        a = a.split(":")
        a = [a[0], ":".join(a[1:])]
        return list(map(lambda b: b.strip(), a))
    config = dict(list(map(parse, data)))
    assert len(set(config.keys()) - {"chain", "username"}) == 0
    assert config["username"] != ""
except:
    config = {"chain": "wss://chain.laptop-cat.repl.co", "username": ""}

if len(argv) > 1:
    config["username"] = argv[1].strip().lower()

if config["username"] == "":
    config["username"] = input("please input a username\n> ").strip().lower()

if len(config["username"]) < 4 or len(config["username"]) > 12:
    print("username must be 4-12 characters")
    exit(1)

if not all(ch in "qwertyuiopasdfghjklzxcvbnm1234567890" for ch in config["username"]):
    print("username must only contain characters from a-z, 0-9")
    exit(1)

async def wrapping(self, output):
    try:
        async with connect(config["chain"] + "/w?u=" + config["username"]) as ws:
            self.ws = ws
            async for msg in ws:
                parser(msg, output)
    except Exception as e:
        if "401" in str(e):
            print("username taken")
        else:
            print("lost link to chain ({}: {})".format(type(e).__name__, str(e)))
        _exit(1)

class Chatter:
    def __init__(self, output):
        self.ws = None
        self.output = output
    
    def run(self):
        Thread(target=run, args=(wrapping(self, self.output),)).start()
    
    def send_message(self, content):
        if self.ws:
            Thread(target=run, args=(self.ws.send(content), )).start()


def parser(msg, output, historic=False, timestamp=None):
    global online_people, offline_people
    if timestamp == None:
        timestamp = timeformat()
    elif timestamp == "disable":
        timestamp = ""
    else:
        timestamp = timeformat(datetime.fromtimestamp(datetime.now().timestamp() - timestamp))
    for char in msg[:13]:
        if char == ":":
            msg = msg.split(":")
            msg[0] = msg[0] + ": "
            content = ":".join(msg[1:])
            whitespace = abs(columns - len(wrap(msg[0]+content+timestamp, columns+1)[-1])) * " "
            msg = [('gray', msg[0]), content, whitespace, ('gray', timestamp)]
            if historic:
                output.prepend(msg)
            else:
                output.add(msg)
            break
        elif char == "+":
            msg = msg.split("+")
            username = msg[1]
            msg = "+ " + username + " has joined the chain"
            whitespace = abs(columns - len(wrap(msg+timestamp, columns+1)[-1])) * " "
            msg = [('green', msg), whitespace, ('gray', timestamp)]
            if historic:
                output.prepend(msg)
                if username not in offline_people:
                    online_people.add(username)
            else:
                output.add(msg)
                online_people.add(username)
                if username == config["username"]:
                    del offline_people
            break
        elif char == "-":
            msg = msg.split("-")
            username = msg[1]
            msg = "- " + username + " has left the chain"
            whitespace = abs(columns - len(wrap(msg+timestamp, columns+1)[-1])) * " "
            msg = [('red', msg), whitespace, ('gray', timestamp)]
            if historic:
                output.prepend(msg)
                offline_people.add(username)
            else:
                output.add(msg)
                online_people.remove(username)
            break
        elif char == "@":
            msg = msg.split("@")
            parser("@".join(msg[1:]), output, historic=True, timestamp=int(msg[0]))
            break



class ChatMessages(ListBox):
    def __init__(self):
        self.walker = SimpleFocusListWalker([])
        super(ChatMessages, self).__init__(self.walker)

    def add(self, message):
        self.walker.append(Text(message))
        self.set_focus(len(self.walker)-1)
    
    def prepend(self, message):
        self.walker.insert(0, Text(message))
        self.set_focus(0)


class ChatInput(Edit):
    def __init__(self, chatter, output):
        self.ws = chatter
        self.last_sent = time()
        self.output = output
        super(ChatInput, self).__init__(caption=[('input', config["username"]+": ")])

    def keypress(self, size, key):
        message = self.get_edit_text()

        if key == 'enter':
            if message == '':
                return
            if message.strip().lower() == "/online":
                parser(config["username"] + ":" + "/online\nusers in the chain:\n" + ", ".join(online_people), self.output, timestamp="disable")
                self.set_edit_text('')
                return
            elif len(message) > MAX_LENGTH:
                self.set_edit_text(f'too long! ({len(message)}/{MAX_LENGTH})')
                return
            elif (time() - self.last_sent) > RATE_LIMIT:
                self.last_sent = time()
                self.ws.send_message(message)
                self.set_edit_text('')
                return

        super(ChatInput, self).keypress(size, key)


def timeformat(date=None):
    date = date or datetime.now()
    return date.strftime("%X").strip()


palette = [('header', 'white', 'dark gray'), ('gray', 'light gray', ''), ('green', 'dark green', ''), ('red', 'dark red', ''), ('input', 'dark blue', '')]

def main():
    output = ChatMessages()
    chatter = Chatter(output)
    message = ChatInput(chatter, output)
    banner = TITLE.center(columns+1)
    window = Frame(
        header=Text(('header', banner)),
        body=output,
        footer=message,
        focus_part='footer'
    )
    loop = new_event_loop()
    main_loop = MainLoop(window, palette, event_loop=AsyncioEventLoop(loop=loop))
    chatter.run()
    try:
        main_loop.run()
    except:
        _exit(0)

if __name__ == '__main__':
    main()
