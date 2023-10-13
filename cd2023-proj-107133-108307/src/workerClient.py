import logging
import multiprocessing
import os
import sys
import time
import pika
import base64
import json
import ssl
from pkg_resources import cleanup_resources
import torchaudio as ta
from demucs.apply import apply_model
from demucs.pretrained import get_model
from demucs.audio import AudioFile
from multiprocessing import Pool

# Check if the RabbitMQ server port is provided as a command-line argument
if len(sys.argv) < 2:
    print("Please provide the RabbitMQ server port as a command-line argument.")
    sys.exit(1)

rabbitmq_port = int(sys.argv[1])

class MusicPart:
    def __init__(self, data, worker_id, music_id, part_id):
        self.data = data
        self.worker_id = worker_id
        self.music_id = music_id
        self.part_id = part_id

    def to_dict(self):
        return {
            'data': self.data,
            'worker_id': self.worker_id,
            'music_id': self.music_id,
            'part_id': self.part_id
        }
    
# RabbitMQ connection parameters
rabbitmq_host = 'localhost'
exchange_name = 'music_parts'
queue_name = 'instrument_worker'

def process_instrument_worker(ch, method, properties, body):
    music_part_dict = json.loads(body)
    
    music_part = MusicPart(
        part_id=music_part_dict['part_id'],
        data=base64.b64decode(music_part_dict['data']),  # decode the base64 data
        worker_id=music_part_dict['worker_id'],
        music_id=music_part_dict['music_id'],
    )

    temp_file = f'part_{music_part.part_id}.wav'
    with open(temp_file, 'wb') as f:
        f.write(music_part.data)

    # Get the input and output paths from the worker ID
    worker_id = music_part.worker_id
    input_path = f'{temp_file}'
    output_path = f'tracks/{music_part.music_id}/{worker_id}/{music_part.part_id}.wav'

    # Call the processing function with the appropriate arguments
    process_audio(input_path, output_path)

    # Remove the temporary input file
    os.remove(input_path)

    ch.basic_ack(delivery_tag=method.delivery_tag)


def process_audio(input_path, output_path, remove_voice=True, instruments=[]):
    # Get the model
    ssl._create_default_https_context = ssl._create_unverified_context
    model = get_model(name='htdemucs')
    model.cpu()
    model.eval()

    # Load the audio file
    wav = AudioFile(input_path).read(streams=0,
                                     samplerate=model.samplerate, channels=model.audio_channels)
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()

    # Apply the model
    sources = apply_model(model, wav[None], device='cpu', progress=True, num_workers=1)[0]
    sources = sources * ref.std() + ref.mean()

    # Remove voice if specified
    if remove_voice:
        sources[0] = 0.0

    # Remove selected instruments
    for instrument in instruments:
        sources[model.sources.index(instrument)] = 0.0

    # Store the modified audio
    output_directory = os.path.dirname(output_path)
    os.makedirs(output_directory, exist_ok=True)

    for source, name in zip(sources, model.sources):
        stem = os.path.join(output_directory, f'{name}.wav')
        ta.save(stem, source, sample_rate=model.samplerate)

    print(f"Audio saved at: {output_path}")


def connect_to_server(port):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='connect_queue')
    channel.basic_publish(exchange='', routing_key='connect_queue', body=json.dumps(port))

    connection.close()

# Call the connect_to_server function to send a message to the server
connect_to_server(rabbitmq_port)


# Create a connection to the RabbitMQ server
connection_params = pika.ConnectionParameters(host='localhost', port=rabbitmq_port)
connection = pika.BlockingConnection(connection_params)
channel = connection.channel()

# Declare the queue
worker_queue = 'worker_queue1'  # Update with the appropriate worker queue
channel.queue_declare(queue=worker_queue)

# Set up a consumer to receive messages from the queue
channel.basic_consume(queue=worker_queue, on_message_callback=process_instrument_worker)

print('Worker is ready to process music parts.')

# Start consuming messages
channel.start_consuming()