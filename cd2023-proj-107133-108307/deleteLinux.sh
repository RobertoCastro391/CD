#!/bin/bash

# Comando para terminar o arquivo worker.py
pkill -f src/worker.py

# Comando para terminar o arquivo api.py
pkill -f api.py

# Comando para terminar o servidor RabbitMQ
service rabbitmq-server stop
