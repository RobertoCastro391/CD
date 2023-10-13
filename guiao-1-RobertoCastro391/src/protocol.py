"""Protocol for chat server - Computação Distribuida Assignment 1."""
import json
from datetime import datetime
from socket import socket


class Message:
    """Message Type."""
    def __init__(self, command) -> None:
        self.command = command
    
    def __str__(self) -> str:
        return json.dumps({"command": self.command})

    
class JoinMessage(Message):
    """Message to join a chat channel."""
    
    def __init__(self, channel) -> None:
        super().__init__("join")
        self.channel = channel
    def __str__(self) -> str:
        return json.dumps({"command": "join", "channel": self.channel})



class RegisterMessage(Message):
    """Message to register username in the server."""
    def __init__(self, user) -> None:
        super().__init__("register")
        self.user = user
    def __str__(self) -> str:
        return json.dumps({"command": "register", "user": self.user})

    
class TextMessage(Message):
    def __init__(self, message, channel = None, ts = None) -> None:
        super().__init__("message")
        self.message = message
        self.channel = channel
        self.ts = ts

    def __str__(self) -> str:
        if self.channel == None:
            return json.dumps({"command": "message", "message": self.message, "ts": self.ts})
        else:
            return json.dumps({"command": "message", "message": self.message, "channel": self.channel ,"ts": self.ts})


class CDProto:
    """Computação Distribuida Protocol."""

    @classmethod
    def register(cls, username: str) -> RegisterMessage:
        """Creates a RegisterMessage object."""
        return RegisterMessage(username)

    @classmethod
    def join(cls, channel: str) -> JoinMessage:
        """Creates a JoinMessage object."""
        return JoinMessage(channel)

    @classmethod
    def message(cls, message: str, channel: str = None, ts = None) -> TextMessage:
        """Creates a TextMessage object."""

        if ts == None:
            return TextMessage(message, channel, int(datetime.now().timestamp()))
        else:
            return TextMessage(message, channel, ts)
        
    
    @classmethod
    def send_msg(cls, connection: socket, msg: Message):
        """Sends through a connection a Message object."""
        
        connection.send(len(str(msg)).to_bytes(2, byteorder='big')  + str(msg).encode('utf-8'))
        

    @classmethod
    def recv_msg(cls, connection: socket) -> Message:
        """Receives through a connection a Message object."""
        msgSize = int.from_bytes(connection.recv(2), byteorder='big')
        
        if msgSize == 0:
            return
        
        try:
            recvMsg = connection.recv(msgSize).decode('utf-8')
            msg = json.loads(recvMsg)
        except json.JSONDecodeError as err:
            raise CDProtoBadFormat(recvMsg)
        
        if msg['command'] == "join":
            channel = msg['channel']
            return CDProto.join(channel)
        
        elif msg['command'] == "register":
            user = msg['user']
            return CDProto.register(user)
        
        elif msg['command'] == "message":

            if "message" not in msg.keys():
                raise CDProtoBadFormat(msg)
            
            message = msg['message']
            
            if "channel" in msg.keys() and "ts" in msg.keys():
                channel = msg["channel"]
                ts = msg["ts"]
                return CDProto.message(message, channel, ts)
            
            elif "channel" in msg.keys() and "ts" not in msg.keys():
                channel = msg["channel"]
                return CDProto.message(message, channel)
            
            elif "channel" not in msg.keys() and "ts" in msg.keys():
                channel = msg["ts"]
                return CDProto.message(message, channel)
            
            else:
                return CDProto.message(message)

        


class CDProtoBadFormat(Exception):
    """Exception when source message is not CDProto."""

    def __init__(self, original_msg: bytes=None) :
        """Store original message that triggered exception."""
        self._original = original_msg

    @property
    def original_msg(self) -> str:
        """Retrieve original message as a string."""
        return self._original.decode("utf-8")