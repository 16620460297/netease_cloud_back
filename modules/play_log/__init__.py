from flask import Blueprint
from .views import play_log_bp

def init_app(app):
    """初始化播放列表模块"""
    app.register_blueprint(play_log_bp, url_prefix='/api/playlist')
    return app