#!/bin/bash

APP_DIR="/root/model_eval_web"        # 你的項目路徑
ENV_PATH="$HOME/miniconda3"           # Miniconda 路徑
ENV_NAME="myenv"                      # conda 環境名稱
APP_MODULE="app:app"                  # WSGI 模組
BIND="0.0.0.0:8080"                   # 綁定地址
WORKERS=4                             # gunicorn worker 數

PID_FILE="$APP_DIR/gunicorn.pid"

start() {
    echo "Starting gunicorn..."
    source "$ENV_PATH/bin/activate"
    conda activate "$ENV_NAME"
    cd "$APP_DIR" || exit 1
    gunicorn --workers "$WORKERS" --bind "$BIND" "$APP_MODULE" \
        --daemon --pid "$PID_FILE"
    echo "Gunicorn started with PID $(cat $PID_FILE)"
}

stop() {
    echo "Stopping gunicorn..."
    if [ -f "$PID_FILE" ]; then
        kill -TERM $(cat "$PID_FILE") && rm -f "$PID_FILE"
        echo "Gunicorn stopped."
    else
        echo "No PID file found. Gunicorn may not be running."
    fi
}

restart() {
    stop
    sleep 2
    start
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "Gunicorn is running (PID: $PID)"
        else
            echo "PID file exists but process not found."
        fi
    else
        echo "Gunicorn is not running."
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    *) echo "Usage: $0 {start|stop|restart|status}" ;;
esac
