"""Message Broker"""
import enum
from typing import Dict, List, Any, Tuple
import socket
import json
import selectors
from src.protocolo import MBProto

class Serializer(enum.Enum):
    """Possible message serializers."""

    JSON = 0
    XML = 1
    PICKLE = 2


class Broker:
    """Implementation of a PubSub Message Broker."""

    def __init__(self):
        """Initialize broker."""
        
        self.DictionaryTopics = set()
        self.DictionaryTopicsMessages = {} 
        self.DictionarySubtopics = {}  
        self.DictionaryUserSerializer = {}      
         

        self.canceled = False
        self._host = "localhost"
        self._port = 5000

        self.socketBroker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socketBroker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.selectorBroker = selectors.DefaultSelector()
        
        self.socketBroker.bind((self._host, self._port))
        self.socketBroker.listen()
        self.selectorBroker.register(self.socketBroker, selectors.EVENT_READ, self.accept)

        

    def accept(self, socketBroker, mask):
        conn, addr = socketBroker.accept()
        print(f'New Connection {addr}')

        conn.setblocking(False)

        data = conn.recv(int.from_bytes(conn.recv(2), "big") ).decode('UTF-8')

        if data:
            if json.loads(data)["Serializer"] == 'XMLQueue':
                self.DictionaryUserSerializer[conn] = Serializer.XML
           
            elif json.loads(data)["Serializer"] == 'JSONQueue':
                self.DictionaryUserSerializer[conn] = Serializer.JSON
            
            elif json.loads(data)["Serializer"] == 'PickleQueue':
                self.DictionaryUserSerializer[conn] = Serializer.PICKLE

        self.selectorBroker.register(conn, selectors.EVENT_READ, self.process)
    

    def process(self, conn, mask):

        try:
            
            if conn in self.DictionaryUserSerializer.keys():
                
                if self.DictionaryUserSerializer[conn] == Serializer.JSON:
                    messageReceive = MBProto.recv_msg(conn, type="JSONQueue")
                elif self.DictionaryUserSerializer[conn] == Serializer.XML:
                    messageReceive = MBProto.recv_msg(conn, type="XMLQueue")
                    
                elif self.DictionaryUserSerializer[conn] == Serializer.PICKLE:
                    messageReceive = MBProto.recv_msg(conn, type="PICKLEQueue")
                
                if messageReceive:
                    if messageReceive["command"] == 'SUBSCRIBE':
                        self.subscribe(messageReceive["topic"], conn, self.DictionaryUserSerializer[conn])
                    
                    elif messageReceive["command"] == 'PUBLISH':
                        self.put_topic(messageReceive["topic"], messageReceive["message"])
                        for topic in self.DictionarySubtopics.keys():
                            if (messageReceive["topic"]).startswith(topic):
                                for topic2 in self.DictionarySubtopics[topic]:
                                    MBProto.send_msg(topic2[0], messageReceive["command"], self.DictionaryUserSerializer[conn], messageReceive["topic"], messageReceive["message"])
                    
                    elif messageReceive["command"] == 'LIST':
                        MBProto.send_msg(conn, messageReceive["command"], self.DictionaryUserSerializer[conn], messageReceive["topic"], self.list_topics())       
                    elif messageReceive["command"] == 'CANCEL':
                        self.unsubscribe(messageReceive["topic"], conn)
                
                else:
                    pass

        except ConnectionError:
            print('closing', conn)
            self.unsubscribe("", conn)
            self.selectorBroker.unregister(conn)
            conn.close()
    

    def list_topics(self) -> List[str]:
        """Returns a list of strings containing all topics containing values."""
        DictionaryTopicsMessages2 = list(self.DictionaryTopicsMessages.keys())
        return DictionaryTopicsMessages2

    def get_topic(self, topic):
        """Returns the currently stored value in topic."""

        for topic2 in self.DictionaryTopics:
            if topic == topic2: 
                return self.DictionaryTopicsMessages[topic]
    
        return None

    def put_topic(self, topic, value):
        """Store in topic the value."""

        if topic in self.DictionaryTopicsMessages:
            self.DictionaryTopicsMessages.update({topic: value})
        else:
            self.DictionaryTopicsMessages[topic] = value

        self.DictionaryTopics.add(topic)
        print(f'\n{topic} has a new message: {value}')

    def list_subscriptions(self, topic: str) -> List[Tuple[socket.socket, Serializer]]:
        """Provide list of subscribers to a given topic."""
        for topic2 in self.DictionarySubtopics.keys():
            if topic == topic2:
                return self.DictionarySubtopics[topic]
            
        return None

    def subscribe(self, topic: str, address: socket.socket, _format: Serializer = None):
        """Subscribe to topic by client in address."""

        self.DictionaryTopics.add(topic)

        if address in self.DictionaryUserSerializer:
            self.DictionaryUserSerializer.update({address: _format})
        else:
            self.DictionaryUserSerializer[address] = _format

        if topic in self.DictionarySubtopics:
            self.DictionarySubtopics[topic].append((address, _format))
        else: 
            self.DictionarySubtopics[topic] = [(address, _format)] 

        for prev_topic in self.DictionaryTopics:
            if prev_topic in topic and prev_topic != topic and prev_topic in self.DictionarySubtopics:
                    [self.DictionarySubtopics[topic].append(sub_topic) for sub_topic in self.DictionarySubtopics[prev_topic]]
            if topic in prev_topic and prev_topic != topic:
                self.DictionarySubtopics[prev_topic].append((address, _format))
            print(f'{address} subscribed the topic {topic}')
            
        if topic in self.DictionaryTopicsMessages:
        
            last_msg = self.DictionaryTopicsMessages[topic]

            if last_msg:
                MBProto.send_msg(address, "PUBLISH", self.DictionaryUserSerializer[address],topic, last_msg)

    def unsubscribe(self, topic, address):
        """Unsubscribe to topic by client in address."""

        if topic in self.DictionarySubtopics:
            Serializer = self.DictionaryUserSerializer[address]
            self.DictionarySubtopics[topic].remove((address, Serializer))

        print(f'{address} unsubscribed the topic {topic}')

    def run(self):
        """Run until canceled."""

        while not self.canceled:
            events = self.selectorBroker.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)