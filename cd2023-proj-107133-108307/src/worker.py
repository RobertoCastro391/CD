import logging
import multiprocessing
import os
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
from pydub import AudioSegment
from multiprocessing import Pool

# Configure the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
worker_ID = 0
connections = []

class MusicPart:
    def __init__(self, data, worker_id, music_id, part_id, instrument):
        self.data = data
        self.worker_id = worker_id
        self.music_id = music_id
        self.part_id = part_id
        self.instrument = instrument

    def to_dict(self):
        return {
            'data': self.data,
            'worker_id': self.worker_id,
            'music_id': self.music_id,
            'part_id': self.part_id,
            'instrument': self.instrument
        }
    
class MusicPart2:
    def __init__(self, part_id, music_id, instrument):
        self.part_id = part_id
        self.music_id = music_id
        self.instrument = instrument

    def to_dict(self):
        return {
            'part_id': self.part_id,
            'music_id': self.music_id,
            'instrument': self.instrument
        }

def divide_music(ch, method, properties, body):
    music = json.loads(body)

    music_file = music['music_file_path']
    music_id = music['music_id']
    
    instruments = music['instruments']

    if not os.path.exists('tracks/' + music_file):
        raise ValueError(f"File does not exist: {music_file}")

    audio = AudioSegment.from_file('tracks/' + music_file, format='mp3')
    total_length = len(audio)
    segment_duration = total_length // len(connections)

    music_parts = []  # Array to store music parts
    print(len(connections))
    for i in range(len(connections)):
        start_time = i * segment_duration
        end_time = start_time + segment_duration
        part = audio[start_time:end_time]
        worker_id = f'instrument_worker{i + 1}'
        part_id = i + 1
        music_part = MusicPart(part, worker_id, music_id, part_id, instruments)
        music_parts.append(music_part)  # Store the music part
        

    for i, connection in enumerate(connections):
        music_part = music_parts[i]  # Get the corresponding music part
        music_part_dict = music_part.to_dict()
        music_data_bytes = music_part.data.export().read()
        music_part_dict['data'] = base64.b64encode(music_data_bytes).decode()
        music_part_dict['part_id'] = music_part.part_id

        channel = connection.channel()
        channel.queue_declare(queue='worker_queue1')
        channel.basic_publish(exchange='', routing_key='worker_queue1', body=json.dumps(music_part_dict))
        channel.close()

    music_part_dict = music_part.to_dict()

    music_data_bytes = music_part.data.export().read()
    music_part_dict['data'] = base64.b64encode(music_data_bytes).decode()

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='worker_queue1')

    for conection in connections:
        channel.basic_publish(exchange='', routing_key='worker_queue1', body=json.dumps(music_part_dict))

    connection.close()

def send_to_worker_join(music_Id, instruments):
    # Create a connection to RabbitMQ
    connection = connect_to_rabbitmq()
    channel = connection.channel()

    # Define the queue for the join worker
    queue = 'join_worker'
    
    # Create a list to store the music part dictionaries
    music_parts = []
    for i in range(get_num_workers()):
        print(i)
        m = MusicPart2(part_id=i + 1, music_id=music_Id, instrument=instruments)
        music_parts.append(m.to_dict())

    message_json = json.dumps(music_parts)
    
    # Publish the message to the join worker queue
    channel.basic_publish(exchange='', routing_key=queue, body=message_json)

    # Close the connection
    connection.close()

def get_num_workers():
    return 3

# def process_instrument_worker(ch, method, properties, body):
#     music_part_dict = json.loads(body)
    
#     music_part = MusicPart(
#         part_id=music_part_dict['part_id'],
#         data=base64.b64decode(music_part_dict['data']),  # decode the base64 data
#         worker_id=music_part_dict['worker_id'],
#         music_id=music_part_dict['music_id'],
#     )

#     temp_file = f'part_{music_part.part_id}.wav'
#     with open(temp_file, 'wb') as f:
#         f.write(music_part.data)

#     # Get the input and output paths from the worker ID
#     worker_id = music_part.worker_id
#     input_path = f'{temp_file}'
#     output_path = f'tracks/{music_part.music_id}/{worker_id}/{music_part.part_id}.wav'

#     # Call the processing function with the appropriate arguments
#     process_audio(input_path, output_path)

#     # Remove the temporary input file
#     os.remove(input_path)


#     ch.basic_ack(delivery_tag=method.delivery_tag)


# def process_audio(input_path, output_path, remove_voice=True, instruments=[]):
#     # Get the model
#     ssl._create_default_https_context = ssl._create_unverified_context
#     model = get_model(name='htdemucs')
#     model.cpu()
#     model.eval()

#     # Load the audio file
#     wav = AudioFile(input_path).read(streams=0,
#                                      samplerate=model.samplerate, channels=model.audio_channels)
#     ref = wav.mean(0)
#     wav = (wav - ref.mean()) / ref.std()

#     # Apply the model
#     sources = apply_model(model, wav[None], device='cpu', progress=True, num_workers=1)[0]
#     sources = sources * ref.std() + ref.mean()

#     # Remove voice if specified
#     if remove_voice:
#         sources[0] = 0.0

#     # Remove selected instruments
#     for instrument in instruments:
#         sources[model.sources.index(instrument)] = 0.0

#     # Store the modified audio
#     output_directory = os.path.dirname(output_path)
#     os.makedirs(output_directory, exist_ok=True)

#     for source, name in zip(sources, model.sources):
#         stem = os.path.join(output_directory, f'{name}.wav')
#         ta.save(stem, source, sample_rate=model.samplerate)

#     print(f"Audio saved at: {output_path}")

def process_join_worker(ch, method, properties, body):
    music_part = json.loads(body)
    print("Join worker received a message")

    music_ID = None

    for music in music_part:
        print(music['part_id'])
        music_ID = music['music_id']

    music_part.sort(key=lambda x: x['part_id'])

    combined_tracks = []
    
    # Concatenate the music parts into a single AudioSegment
    combined_audio_bass = AudioSegment.empty()
    combined_audio_drums = AudioSegment.empty()
    combined_audio_other = AudioSegment.empty()
    combined_audio_vocals = AudioSegment.empty()
    
    for music in music_part:
        a = music['part_id']
        audio_segment_bass = AudioSegment.from_file(f'tracks/{music_ID}/instrument_worker{a}/bass.wav', format='wav')
        audio_segment_drums = AudioSegment.from_file(f'tracks/{music_ID}/instrument_worker{a}/drums.wav', format='wav')
        audio_segment_other = AudioSegment.from_file(f'tracks/{music_ID}/instrument_worker{a}/other.wav', format='wav')
        audio_segment_vocals = AudioSegment.from_file(f'tracks/{music_ID}/instrument_worker{a}/vocals.wav', format='wav')

        combined_audio_bass += audio_segment_bass
        combined_audio_drums += audio_segment_drums
        combined_audio_other += audio_segment_other
        combined_audio_vocals += audio_segment_vocals
    
    # Export the combined audio as an MP3 file
    combined_audio_bass.export(f'tracks/{music_ID}/combined_music_bass.wav', format='wav')
    combined_audio_drums.export(f'tracks/{music_ID}/combined_music_drums.wav', format='wav')
    combined_audio_other.export(f'tracks/{music_ID}/combined_music_other.wav', format='wav')
    combined_audio_vocals.export(f'tracks/{music_ID}/combined_music_vocals.wav', format='wav')

    if len(music_part[0]['instrument']) != 0:
        for music_part in music_part:
            part_id = music_part['part_id']
            for instrument in music_part['instrument']:
                track_path = f'tracks/{music_ID}/combined_music_{instrument}.wav'
                audio_segment = AudioSegment.from_file(track_path, format='wav')

                if audio_segment.channels > 1:
                    audio_segment = audio_segment.set_channels(1)
                audio_segment = audio_segment.normalize()

                combined_tracks.append(audio_segment)

        mixed_audio = AudioSegment.from_mono_audiosegments(*combined_tracks)

        # Export the mixed audio as an MP3 file
        output_path = f'tracks/{music_ID}/combined_musicSELECTED.mp3'
        mixed_audio.export(output_path, format='mp3')
        logging.info(f"Audio saved at: {output_path}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

def connect_to_rabbitmq():
    connection_params = pika.ConnectionParameters(
        host='localhost',
        heartbeat=0,  
        blocked_connection_timeout=500,  
    )
    connection = pika.BlockingConnection(connection_params)
    return connection

def handle_worker_connect(ch, method, properties, body):
    worker_id = body.decode()
    logging.info(f"Worker connected: {worker_id}")
    # Store the connection
    connections.append(ch._connection)

    for connection in connections:
        print(connection) 

def run_worker():
    num_workers = get_num_workers()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"Number of workers: {num_workers}")

# Store worker connections

    while True:
        try:
            connection = connect_to_rabbitmq()
            channel = connection.channel()

            channel.queue_declare(queue='division_queue')
            channel.queue_declare(queue='join_worker')  # Declare the join_queue
            channel.queue_declare(queue='connect_queue')  # Declare the connect_queue

            #channel.basic_qos(prefetch_count=num_workers + 2)  # Set prefetch count to handle all workers and join worker
            channel.basic_consume(queue='division_queue', on_message_callback=divide_music)
            channel.basic_consume(queue='join_worker', on_message_callback=process_join_worker)
            channel.basic_consume(queue='connect_queue', on_message_callback=handle_worker_connect)

            channel.start_consuming()

            connections.append(connection)  # Store the worker connection
            logging.info(f"Worker connection stored: {connection}")

        except pika.exceptions.AMQPConnectionError:
            logging.error("AMQP connection error. Retrying in 5 seconds...")
            time.sleep(5)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            break





if __name__ == '__main__':
    run_worker()