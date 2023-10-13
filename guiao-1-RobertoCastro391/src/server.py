"""CD Chat server program."""
import logging
import socket
import selectors

from src.protocol import CDProto, CDProtoBadFormat, TextMessage, JoinMessage, RegisterMessage
logging.basicConfig(filename="server.log", level=logging.DEBUG)

clients = {"mainChannel":[]}

class Server:
    """Chat Server process."""
    
    def __init__(self):
        
        HOST = '127.0.0.1'               
        PORT = 9862
        
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sel = selectors.DefaultSelector()
            self.s.bind((HOST, PORT))
            self.s.listen(100)
            print(f"Server is up and listennig at {HOST}:{PORT}!")

        except OSError as e:
            print("It was not possible to open the server!")
            self.s.close()
            self.s=None
            exit(0)
        

    def accept(self, sock, mask):
        try:
            conn, addr = sock.accept()  # Should be ready
            print(f'New Connection {addr}')
            logging.debug(f'New Connection {addr}')
            data = CDProto.recv_msg(conn)
            clients["mainChannel"].append(conn)
            newConnection = f'{data.user} just joined the chat!'
            print(newConnection)
            logging.debug(f'{newConnection}')
            for channel in clients.keys():
                for client in clients[channel]:
                    CDProto.send_msg(client,TextMessage(newConnection))
                                   
            conn.setblocking(False)
            self.sel.register(conn, selectors.EVENT_READ, self.processMessages)
        
        except OSError as e:
            self.s.close()
            self.s=None
            exit(0)
        

    def processMessages(self, conn, mask):
        try:
            data = CDProto.recv_msg(conn)
            
            logging.debug(f'Message Received: {str(data)}')
            
            if data:
                if data.command == "join":
                    
                    clients.setdefault(data.channel,[])
                    oldChannel = None
                    
                    for channel in clients.keys():
                        if conn in clients[channel]:
                            oldChannel = channel
                            clients[oldChannel].remove(conn)
                        
                    clients[data.channel].append(conn)

                    print(f'{conn.getpeername()} changed from channel {oldChannel} to {data.channel}!')
                    
                    msg = f'{conn.getpeername()} just left this channel!'
                    for client in clients[oldChannel]:
                        CDProto.send_msg(client, TextMessage(msg, oldChannel))
                    
                    msg = f'{conn.getpeername()} just join this channel!'
                    for client in clients[data.channel]:
                        CDProto.send_msg(client, TextMessage(msg, data.channel))

                if data.command == "message":
                    
                    if data.channel is None:
                        data.channel = "mainChannel"

                    for client in clients[data.channel]:
                        if client != conn:
                            CDProto.send_msg(client,data)
                        else:
                            pass
            else: 
                msg = f'{conn.getpeername()} just left the chat'
                print(msg)
                for channel in clients.keys():
                    if conn in clients[channel]:
                        clients[channel].remove(conn)
                    
                for channel in clients.keys():
                    for client in clients[channel]:
                        CDProto.send_msg(client,TextMessage(msg))

                self.sel.unregister(conn)
                conn.close()

        except CDProtoBadFormat:
            print(f"Received bad format message from {conn.getpeername()}.")
            return
        

    def loop(self):
        
        self.sel.register(self.s, selectors.EVENT_READ, self.accept)
    
        while True:
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
