#!/bin/bash

# Get the process IDs of the worker and API processes
worker_pid=$(pgrep -f "src/worker.py")
api_pid=$(pgrep -f "api.py")

# Terminate the worker process
if [[ -n $worker_pid ]]; then
    kill $worker_pid
fi

# Terminate the API process
if [[ -n $api_pid ]]; then
    kill $api_pid
fi

# Stop the RabbitMQ server
brew services stop rabbitmq
