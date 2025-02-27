from flask import Blueprint, jsonify, request
from .services import set_play_log, get_play_logs

play_log_bp = Blueprint('play_log', __name__, url_prefix='/api/play_log')

@play_log_bp.route('/set', methods=['POST'])
def save_log():
    return set_play_log()

@play_log_bp.route('/get', methods=['GET'])
def get_logs():
    return get_play_logs()
