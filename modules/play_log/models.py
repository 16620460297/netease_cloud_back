from utils.db import db
from datetime import datetime

class PlayLog(db.Model):
    __tablename__ = 'play_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.user_id'))
    song_id = db.Column(db.BigInteger)
    song_name = db.Column(db.String(255))
    current_time = db.Column('current_position', db.Float)
    duration = db.Column('song_duration', db.Float)
    played_at = db.Column(db.DateTime, default=datetime.utcnow)
