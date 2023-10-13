#!/bin/bash
mkdir tracks
python3 -m venv venv

#
source venv/bin/activate
pip install -r requirements_torch.txt
pip install -r requirements_demucs.txt

pip install pika mutagen flask pydub

# Comando para iniciar o servidor RabbitMQ
service rabbitmq-server start

# Atraso 
sleep 1

# Comando para iniciar o arquivo worker.py
python3 src/worker.py &

# Comando para iniciar o arquivo api.py
python3 api.py
