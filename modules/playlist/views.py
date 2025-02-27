from flask import Blueprint, jsonify, request
from .services import show_playlist, get_playlist_detail,get_single_song_detail

playlist_bp = Blueprint('playlist', __name__, url_prefix='/api/playlist')


@playlist_bp.route('/show', methods=['GET'])
# 显示个人歌单，如果获取失败就使用数据库库存歌单
def save():
    return show_playlist()


@playlist_bp.route('/detail', methods=['GET'])
# 获取歌单详情
def detail():
    return get_playlist_detail()

@playlist_bp.route('/single_detail', methods=['GET'])
def single_detail():
    return get_single_song_detail()