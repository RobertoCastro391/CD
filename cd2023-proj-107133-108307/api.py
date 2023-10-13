import json
from flask import Flask, request, render_template, jsonify, send_file
from mutagen.easyid3 import EasyID3
import multiprocessing
import uuid
import pika
from src.worker import divide_music, get_num_workers, send_to_worker_join
import os
import shutil

app = Flask(__name__)

# Dicionário para armazenar as músicas submetidas
musicas = {}

# Dicionário para armazenar os jobs submetidos
jobs = {}

# RabbitMQ connection parameters
RABBITMQ_HOST = 'localhost'
RABBITMQ_QUEUE = 'division_queue'

# Establish a connection to RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
channel = connection.channel()
channel.queue_declare(queue=RABBITMQ_QUEUE)

# Rota para servir a página de upload de música
@app.route('/')
def upload_page():
    return render_template('FrontEnd.html')

# Rota para submeter um arquivo de áudio em formato MP3
@app.route('/music', methods=['POST'])
def submit_music():
    # Verifica se um arquivo de áudio foi enviado
    if 'file' not in request.files:
        return jsonify({'error': 'Arquivo de áudio não encontrado'}), 400

    file = request.files['file']

    # Verifica se o arquivo é um MP3
    if file.filename.endswith('.mp3'):
        filename = file.filename
        file_path = os.path.join('tracks', filename)  # Substitua pelo caminho desejado

        # Salvar o arquivo na pasta desejada
        file.save(file_path)

        # Gera um ID único para a música
        music_id = str(uuid.uuid4())

        # Extrai o nome da música e o nome da banda do formulário de upload
        nome_musica = request.form.get('nome_musica')
        nome_banda = request.form.get('nome_banda')

        # Armazena os metadados da música no dicionário
        musicas[music_id] = {'nome_musica': nome_musica, 'nome_banda': nome_banda, 'instrumentos': [], 'file': file}

        # Acessa os metadados do arquivo MP3 usando o Mutagen
        try:
            audio = EasyID3(file_path)
            if 'title' in audio:
                musicas[music_id]['nome_musica'] = audio['title'][0]
            if 'artist' in audio:
                musicas[music_id]['nome_banda'] = audio['artist'][0]

        except Exception as e:
            return jsonify({'error': 'Erro ao acessar metadados do arquivo: {}'.format(str(e))}), 500

        return jsonify({'music_id': music_id}), 201
    else:
        return jsonify({'error': 'Formato de arquivo inválido'}), 400


@app.route('/music', methods=['GET'])
def get_musicas():
    musicas_without_file = {music_id: music_data.copy() for music_id, music_data in musicas.items()}
    for music_data in musicas_without_file.values():
        music_data.pop('file', None)
    return jsonify(musicas_without_file), 200

@app.route('/music/<music_id>', methods=['GET'])
def get_music_by_id(music_id):
    if music_id not in musicas:
        return jsonify({'error': 'Música não encontrada'}), 404

    music = musicas[music_id]
    return jsonify(music), 200


@app.route('/music/<music_id>', methods=['POST'])
def process_music(music_id):
    if music_id not in musicas:
        return jsonify({'error': 'Music not found'}), 404

    data = request.get_json(force=True)
    if 'instrumentos' not in data:
        return jsonify({'error': 'List of instruments not found'}), 400

    instrumentos = data['instrumentos']

    music_data = musicas[music_id]
    music_file = music_data['file']
    music_file_path = music_file.filename

    num_workers = get_num_workers()
    print(f"Number of workers: {num_workers}")

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='division_queue')

    music = {
        'music_id': music_id,
        'music_file_path': music_file_path,
        'instruments': instrumentos
    }

    channel.basic_publish(exchange='', routing_key='division_queue', body=json.dumps(music))



    #divided_parts = divide_music(music_file_path, num_workers, music_id)

    # Create a process pool with the specified number of workers
    # pool = multiprocessing.Pool(processes=num_workers)

    # # Map the divided parts to worker processes for parallel processing
    # for music_part in divided_parts:
    #     pool.apply_async(send_to_worker, args=(music_part.worker_id, music_part))

    # # Close the pool and wait for all processes to complete
    # pool.close()
    # pool.join()

    #send_to_worker_join(music_id, instrumentos)

    # pool.terminate()

    job_id = str(uuid.uuid4())

    jobs[job_id] = {'music_id': music_id, 'instrumentos': instrumentos}

    return jsonify({'job_id': job_id}), 202


@app.route('/job/', methods=['GET'])
def get_jobs():
    return jsonify(jobs), 200


@app.route('/job/<job_id>', methods=['GET'])
def get_job(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job não encontrado'}), 404

    job_info = jobs[job_id]

    music_id = job_info['music_id']
    music = musicas.get(music_id)

    if music is None:
        return jsonify({'error': 'Música não encontrada'}), 404

    instrumentos = job_info['instrumentos']
    tracks = []

    for instrumento in instrumentos:
        track_id = music['instrumentos'].index(instrumento) + 1
        track_url = f"/music/{music_id}/tracks/{track_id}"
        tracks.append({'name': instrumento, 'track_id': track_id, 'track_url': track_url})

    processed = True
    mixed_url = f"/music/{music_id}/mix"

    if processed:
        response = {
            'music_id': music_id,
            'name': music['nome_musica'],
            'band': music['nome_banda'],
            'tracks': tracks,
            'mixed_url': mixed_url
        }
    else:
        response = {
            'music_id': music_id,
            'name': music['nome_musica'],
            'band': music['nome_banda'],
            'tracks': tracks
        }

    return jsonify(response), 200


@app.route('/music/<music_id>/tracks/<track_id>', methods=['GET'])
def download_track(music_id, track_id):
    if music_id not in musicas:
        return jsonify({'error': 'Música não encontrada'}), 404

    music = musicas[music_id]
    track_id = int(track_id)

    if track_id < 1 or track_id > len(music['instrumentos']):
        return jsonify({'error': 'Faixa/instrumento inválido'}), 400

    # Generate the download link for the track
    track_url = f"/music/{music_id}/tracks/{track_id}/download"

    return jsonify({'music_id': music_id, 'name': music['nome_musica'], 'band': music['nome_banda'],
                    'track_id': track_id, 'track_url': track_url}), 200


@app.route('/music/<music_id>/mix', methods=['GET'])
def download_mix(music_id):
    if music_id not in musicas:
        return jsonify({'error': 'Música não encontrada'}), 404

    # Generate the download link for the mixed file
    mixed_url = f"/music/{music_id}/mix/download"

    return jsonify({'music_id': music_id, 'mixed_url': mixed_url}), 200



@app.route('/reset', methods=['POST'])
def reset():
    musicas.clear()
    jobs.clear()

    directory = 'tracks'
    if os.path.exists(directory):
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

    return jsonify({'message': 'Sistema limpo'}), 200


if __name__ == '__main__':
    app.run(port=5100)
