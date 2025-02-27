from utils.db import db
from sqlalchemy.dialects.mysql import LONGTEXT
from datetime import datetime

class Playlist(db.Model):
    __tablename__ = 'playlists'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.user_id'), unique=True)
    playlist_data = db.Column(LONGTEXT)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
