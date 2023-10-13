"""Protocol for chat server - Computação Distribuida Assignment 1."""
import pickle, json
import socket
import xml.etree.cElementTree as arvore


class Message:
    """Message Type."""
    def __init__(self, command):
        self.command = command

    def __str__(self):
        return json.dumps({"command": self.command})

    
class Subscribe_Topic(Message):
    """Message to subscribe a topic."""
    def __init__(self, info):
        self.command=info[0]
        self.type=info[1]
        self.topic=info[2]   
    
    def MSGFormat(self):
        return {"command": self.command, "type": self.type.__str__(), "topic": self.topic}
    def __str__(self):   #repr__(self) -> str:
        return json.dumps({"command": self.command, "type": self.type, "topic": self.topic})

            

class Publish_Message(Message):
    """Message to publish a topic."""
    def __init__(self, info):
        self.command=info[0]
        self.type=info[1]
        self.topic=info[2]
        self.message=info[3]
    
    
    def MSGFormat(self):
        return {"command": self.command, "type": self.type.__str__(), "topic": self.topic, "message": self.message}
    def __str__(self):
        return json.dumps({"command": self.command, "type": self.type, "topic": self.topic, "message": self.message})


class Request_List(Message):
    """Message to list a topic."""
    def __init__(self, info):
        self.command=info[0]
        self.type=info[1]
        
    def MSGFormat(self):
        return {"command": self.command, "type": self.type.__str__()}
    def __str__(self):
        return json.dumps({"command": self.command, "type": self.type})
    

class Response_List(Message):
    """Message to list topics"""

    def __init__(self, info):
        self.command = info[0]
        self.list_topic = info[1]

    def Format(self):
        return {"command": self.command, "type": self.type.__str__(), "topic_list" : self.list_topic}
    def __str__(self):
        return json.dumps({"command": self.command, "type": self.type, "topic_list" : self.list_topic})

class Cancel_Message(Message):
    """Message to subscribe a topic."""
    def __init__(self, info):
        self.command=info[0]
        self.type=info[1]
        self.topic=info[2]
    
    def MSGFormat(self):
        return {"command": self.command, "type": self.type.__str__(), "topic": self.topic}
    def __str__(self):
        return json.dumps({"command": self.command, "type": self.type, "topic": self.topic})
    
class MBProto:
    """Computação Distribuida Protocol."""

    @classmethod
    def subscribe(self, type, topic) -> Subscribe_Topic:
        info=()
        info=("SUBSCRIBE", type, topic)
        return Subscribe_Topic(info)

    @classmethod
    def publish(self, type, topic, message) -> Publish_Message:
        info=()
        info=("PUBLISH", type, topic, message)
        return Publish_Message(info)

    @classmethod
    def list(self, type, list_Topic = None) -> Request_List:
        info=()
        if list_Topic:
            info=("LIST", list_Topic)
            return Response_List(info)
        else:
            info=("LIST", type)
        return Request_List(info)

    @classmethod
    def unsubscribe(self, type, topic) -> Cancel_Message:
        info=()
        info=("CANCEL", type, topic)
        return Cancel_Message(info)

    @classmethod
    def send_msg(self, connection: socket, command, _type="", topic="", message= None):
        """"""
        if command == "SUBSCRIBE":
            send_coded = self.subscribe(_type,topic)
        elif command == "PUBLISH":
            send_coded = self.publish(_type, topic, message)
        elif  command == "LIST":
            send_coded = self.list(_type, message) 
        elif  command == "CANCEL":
            send_coded = self.unsubscribe(_type, topic)


        if _type == "JSONQueue" or _type.__str__() == "Serializer.JSON":
            send_coded = json.dumps(send_coded.MSGFormat()).encode("utf-8")

        elif _type == "PickleQueue" or _type.__str__() == "Serializer.PICKLE":
            send_coded = pickle.dumps(send_coded.MSGFormat())

        elif _type == "XMLQueue" or _type.__str__() == "Serializer.XML":
            send_coded = send_coded.MSGFormat()
            for key in send_coded:
                send_coded[key] = str(send_coded[key])
            send_coded = arvore.Element("mssg", send_coded)
            send_coded = arvore.tostring(send_coded)
        
        try:
            header = len(send_coded).to_bytes(2, "big")
            connection.send(header + send_coded)
        except:
            pass


    @classmethod
    def recv_msg(self,connection : socket ,type) :

        sent_size = int.from_bytes(connection.recv(2), 'big') 
        sent = (connection.recv(sent_size))
        try:
            if sent_size != 0:
                try:
                    sent_decode= sent.decode('utf-8')
                    sent_decode= json.loads(sent)  
                except:
                        try:
                            sent_decode = pickle.loads(sent)
                        except:
                            sent_decode = arvore.fromstring(sent.decode("utf-8"))
                            sent_decode = sent_decode.attrib  

                if sent_decode["command"] == "SUBSCRIBE":
                    info=()
                    info= ("SUBSCRIBE",sent_decode["type"],sent_decode["topic"])
                    return Subscribe_Topic(info).MSGFormat()

                elif sent_decode["command"] == "PUBLISH":
                    info=()
                    info= ("PUBLISH",sent_decode["type"],sent_decode["topic"],sent_decode["message"])
                    return Publish_Message(info).MSGFormat()
                    
                elif sent_decode["command"] == "LIST":
                    info=()
                    if sent_decode["topic_list"]:
                        info= ("LIST",sent_decode["topic_list"])
                        return Response_List(info).MSGFormat()
                    else:
                        info= ("LIST",sent_decode["type"])
                        return Request_List(info).MSGFormat()

                elif sent_decode["command"] == "CANCEL":
                    info=()
                    info= ("CANCEL",sent_decode["type"],sent_decode["topic"])
                    return Cancel_Message(info).MSGFormat()
        
        except:
            raise MBProtoBadFormat()


                


class MBProtoBadFormat(Exception):
    """Exception when source message is not CDProto."""

    def __init__(self, original_msg: bytes=None) :
        """Store original message that triggered exception."""
        self._original = original_msg

    @property
    def original_msg(self) -> str:
        """Retrieve original message as a string."""
        return self._original.decode("utf-8")