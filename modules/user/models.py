from utils.db import db
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.BigInteger, primary_key=True)
    nickname = db.Column(db.String(100))
    avatar_url = db.Column(db.String(255))
    cookies = db.Column(db.Text)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
