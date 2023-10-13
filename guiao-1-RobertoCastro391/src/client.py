"""CD Chat client program"""
import logging
import sys
from socket import *
import selectors
from src.protocol import CDProto, CDProtoBadFormat, TextMessage, JoinMessage, RegisterMessage
logging.basicConfig(filename=f"{sys.argv[0]}.log", level=logging.DEBUG)

class Client:
    """Chat Client process."""    
    def __init__(self, name: str = "Foo"):
        
        HOST = '127.0.0.1'               
        PORT = 9862
        self.s = socket(AF_INET, SOCK_STREAM)
        self.sel = selectors.DefaultSelector()
        
        self.HOST = HOST
        self.PORT = PORT
        
        self.name = name
        self.newChannel = None
        
    
    def SendMessages(self, socket, stdin):
        try:
            data = input()
            if data.rstrip() == "exit":
                CDProto.send_msg(self.s, TextMessage(data))
                self.sel.unregister(self.s)
                self.sel.unregister(sys.stdin)
                self.s.close()
                exit()

            elif data.startswith("/join"):
                data = data.replace("/join","").rstrip()
                self.newChannel = data
                CDProto.send_msg(self.s, JoinMessage(self.newChannel))
                logging.debug(f'The channel has been changed to {str(self.newChannel)}')

            else:
                CDProto.send_msg(self.s, TextMessage(data, self.newChannel))
                logging.debug(f'Message Sent: {str(data)}')
        
        except ConnectionError:
            print("Connection lost!!")
            self.sel.unregister(self.s)
            self.sel.unregister(sys.stdin)
            self.s.close()
            exit()
            
    def receiveMessages(self,socket, stdin):
        try:
            data = CDProto.recv_msg(socket)

            if data.command == "message":
                print(f'Message Received: {str(data.message)}')
                logging.debug(f'Message Received: {str(data)}')
            
        except ConnectionError:
            print("Connection lost!!")
            self.sel.unregister(self.s)
            self.sel.unregister(sys.stdin)
            self.s.close()
            exit()
     
    def connect(self):
        """Connect to chat server and setup stdin flags."""
        try:
            self.s.connect((self.HOST,self.PORT))
            print(f'Connected succesfully to {self.HOST}:{self.PORT}')
            register = CDProto.register(self.name)
            logging.debug(f'Connected succesfully to {self.HOST}:{self.PORT}')
            logging.debug(f'Register from {self.name}')
            CDProto.send_msg(self.s, register)
            
        except ConnectionRefusedError as msg:
            print(f'ERROR:{msg}')
            self.s.close()
            exit()
        pass

    def loop(self):
        try:
            self.s.setblocking(False)
            self.sel.register(self.s, selectors.EVENT_READ, self.receiveMessages)
            self.sel.register(sys.stdin, selectors.EVENT_READ, self.SendMessages)
            
            while True:
                events = self.sel.select()
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, sys.stdin)

        except OSError as e:
            print("Closing Connection!")
            self.sel.unregister(self.s)
            self.sel.unregister(sys.stdin)
            self.s.close()
            exit()
