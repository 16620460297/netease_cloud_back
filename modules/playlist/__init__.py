from flask import Blueprint
from .views import playlist_bp

def init_app(app):
    """初始化播放列表模块"""
    app.register_blueprint(bp, url_prefix='/api/playlist')
    return app