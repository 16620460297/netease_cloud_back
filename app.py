from flask import Flask
from flask_cors import CORS
from modules.user.views import user_bp
from modules.playlist.views import playlist_bp
from modules.play_log.views import play_log_bp
from flask_sqlalchemy import SQLAlchemy
from utils.db import db
def create_app():
    app = Flask(__name__)
    CORS(app)

    # 加载配置
    app.config.from_pyfile('config.py')

    # 初始化数据库（此时只需要 init_app）
    db.init_app(app)

    # 注册蓝图
    with app.app_context():
        from modules.user.views import user_bp
        from modules.playlist.views import playlist_bp
        from modules.play_log.views import play_log_bp

        app.register_blueprint(user_bp)
        app.register_blueprint(playlist_bp)
        app.register_blueprint(play_log_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run('0.0.0.0', debug=True, port=5000)
