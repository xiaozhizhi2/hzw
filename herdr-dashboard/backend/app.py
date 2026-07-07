"""Herdr 牛马 Dashboard - Flask 后端"""
import json
import time
from flask import Flask, jsonify, Response, request
from flask_cors import CORS
import herdr_client

app = Flask(__name__)
CORS(app)


@app.route("/api/agents")
def api_agents():
    """返回所有 agent 状态列表."""
    agents = herdr_client.get_agents()
    return jsonify({
        "agents": agents,
        "herdr_connected": herdr_client.HERDR_CONNECTED,
        "timestamp": int(time.time()),
    })


@app.route("/api/events")
def api_events():
    """SSE 流 - 实时推送 agent 状态."""
    def generate():
        while True:
            agents = herdr_client.get_agents()
            yield f"data: {json.dumps({'agents': agents, 'herdr_connected': herdr_client.HERDR_CONNECTED, 'timestamp': int(time.time())})}\n\n"
            time.sleep(3)

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    port = 5400
    print(f"🐴 牛马 Dashboard 后端启动 → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
