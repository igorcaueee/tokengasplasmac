#!/bin/bash
nohup /usr/local/bin/ngrok start --all --config /home/raspgas1/.config/ngrok/ngrok.yml > /home/raspgas1/ngrok.log 2>&1 &
