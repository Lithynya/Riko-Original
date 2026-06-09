#!/bin/bash

# Define virtual environment path
VENV_PATH="/home/rayenfeng/riko_project_v1/.venv"
ACTIVATE="$VENV_PATH/bin/activate"

# Define GPT-SoVITS server config paths
CONFIG_1="GPT_SoVITS/configs/tts_infer.yaml"
# CONFIG_2="GPT_SoVITS/configs/tts_infer_alt.yaml"  # <-- make sure this file exists and uses a different speaker/model



# Kill any running GPT-SoVITS servers first
echo "Killing any existing GPT-SoVITS server processes..."
pkill -f "python3 api_v2.py"
pkill -f "server.py"  # Specifically your animation server

echo "Killing existing Vite/NPM servers..."
pkill -f "npx vite"
pkill -f "vite"

echo "waiting for ports to free up for 4 seconds"
sleep 4  # Wait a moment to ensure ports are freed


# Start animation server (server.py)
echo "Starting animation server..."
bash -c "source $ACTIVATE && cd /home/rayenfeng/riko_project_v1/server && python server.py" &


# Start NPM Vite client
echo "Starting Vite client..."
bash -c "cd /home/rayenfeng/riko_project_v1/client && npx vite" &


# Start GPT-SoVITS server 1 (port 9880)

VENV_PATH_SOVITS="/home/rayenfeng/GPT-SoVITS/.venv"
ACTIVATE_SOVITS="$VENV_PATH_SOVITS/bin/activate"


echo "Starting GPT-SoVITS Server on port 9880..."
bash -c "source $ACTIVATE_SOVITS && cd /home/rayenfeng/GPT-SoVITS && python3 api_v2.py -a 127.0.0.1 -p 9880 -c $CONFIG_1" &


echo "✅ All servers are launching in the background."


# # Start GPT-SoVITS server 2 (port 9881)
# echo "🔊 Starting GPT-SoVITS Server 2 on port 9881..."
# bash -c "source $ACTIVATE && cd /home/rayenfeng/GPT-SoVITS && python3 api_v2.py -a 127.0.0.1 -p 9881 -c $CONFIG_2" &