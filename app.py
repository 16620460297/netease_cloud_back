from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy import text
from datetime import datetime
import json, random, execjs, requests, qrcode, io, base64
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://music.163.com"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
]


def get_headers():
    return {
        "Host": "music.163.com",
        "Referer": BASE_URL,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": random.choice(USER_AGENTS),
    }


def encrypted_request(data):
    """执行参数加密"""
    with open("main.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    ctx = execjs.compile(js_code)
    result = ctx.call("get_param", json.dumps(data, separators=(",", ":")))
    return {"params": result["encText"], "encSecKey": result["encSecKey"]}


def get_qrcode_unikey():
    url = f"{BASE_URL}/weapi/login/qrcode/unikey"
    data = {"type": 1}
    resp = requests.post(url, data=encrypted_request(data), headers=get_headers())
    if resp.status_code == 200 and resp.json().get("code") == 200:
        return resp.json()["unikey"]
    raise Exception("获取 unikey 失败")


def generate_qrcode_image(unikey):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(f"{BASE_URL}/login?codekey={unikey}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def get_user_profile(cookies):
    url = f"{BASE_URL}/weapi/w/nuser/account/get"
    resp = requests.post(url, data=encrypted_request({}), headers=get_headers(), cookies=cookies)
    return resp.json()


def check_login_status_once(unikey):
    url = f"{BASE_URL}/weapi/login/qrcode/client/login"
    data = {"key": unikey, "type": 1, "csrf_token": ""}
    resp = requests.post(url, data=encrypted_request(data), headers=get_headers())
    result = resp.json()
    if result.get("code") == 803:
        cookies = resp.cookies.get_dict()
        result["cookies"] = cookies
        profile = get_user_profile(cookies)
        result["profile"] = profile
    return result


def get_retry_session():
    """重试策略"""
    session = requests.Session()
    retry = Retry(
        total=10,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


app = Flask(__name__)
CORS(app)

# 配置数据库（请根据实际情况修改）
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:MO520MING@localhost/netease_cloud?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.BigInteger, primary_key=True)
    nickname = db.Column(db.String(100))
    avatar_url = db.Column(db.String(255))
    cookies = db.Column(db.Text)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Playlist(db.Model):
    __tablename__ = 'playlists'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.user_id'), unique=True)
    playlist_data = db.Column(LONGTEXT)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlayLog(db.Model):
    __tablename__ = 'play_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.user_id'))
    song_id = db.Column(db.BigInteger)
    song_name = db.Column(db.String(255))
    current_time = db.Column('current_position', db.Float)
    duration = db.Column('song_duration', db.Float)
    played_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()


@app.route('/api/qrcode', methods=['GET'])
def api_qrcode():
    """获取 unikey 并生成二维码"""
    try:
        unikey = get_qrcode_unikey()
        qr_code_base64 = generate_qrcode_image(unikey)
        return jsonify({"code": 200, "data": {"unikey": unikey, "qrCodeBase64": qr_code_base64}})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})


@app.route('/api/check_login', methods=['GET'])
def api_check_login():
    """查询登录状态"""
    unikey = request.args.get('unikey')
    if not unikey:
        return jsonify({"code": 400, "msg": "缺少 unikey 参数"})
    result = check_login_status_once(unikey)
    if result.get("code") == 803:
        cookies = result.get("cookies")
        profile = result.get("profile", {}).get("profile", {})
        user_id = profile.get("userId")
        if not user_id:
            return jsonify({"code": 500, "msg": "未能获取用户ID"})
        user = User.query.get(user_id)
        if not user:
            user = User(
                user_id=user_id,
                nickname=profile.get("nickname"),
                avatar_url=profile.get("avatarUrl"),
                cookies=json.dumps(cookies)
            )
            db.session.add(user)
        else:
            user.nickname = profile.get("nickname")
            user.avatar_url = profile.get("avatarUrl")
            user.cookies = json.dumps(cookies)
        db.session.commit()
    return jsonify(result)


@app.route('/api/save_playlist', methods=['GET'])
def api_save_playlist():
    """获取用户歌单并保存"""
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"code": 400, "msg": "缺少 uid 参数"})
    url = f"http://music.163.com/api/user/playlist/?offset=0&limit=100&uid={uid}"
    resp = requests.get(url, headers=get_headers())
    if resp.status_code == 200:
        playlist_data = resp.json()
        playlist = Playlist.query.filter_by(user_id=uid).first()
        if not playlist:
            playlist = Playlist(user_id=uid, playlist_data=json.dumps(playlist_data))
            db.session.add(playlist)
        else:
            playlist.playlist_data = json.dumps(playlist_data)
        db.session.commit()
        return jsonify({"code": 200, "msg": "歌单数据已存储", "data": playlist_data})
    else:
        return jsonify({"code": 500, "msg": "获取歌单失败"})


@app.route('/api/logout', methods=['GET'])
def api_logout():
    """退出登录"""
    cookies = request.cookies
    url = f"{BASE_URL}/api/logout"
    resp = requests.get(url, headers=get_headers(), cookies=cookies)
    if resp.status_code == 200:
        return jsonify({"code": 200, "msg": "注销成功"})
    return jsonify({"code": 500, "msg": "注销失败"})


@app.route('/api/playlist/detail', methods=['GET'])
def get_playlist_detail():
    """获取歌单详情"""
    playlist_id = request.args.get('id')
    if not playlist_id:
        return jsonify({"code": 400, "msg": "缺少歌单ID"})

    required_cookies = {
        'MUSIC_U': request.cookies.get('MUSIC_U'),
        '__csrf': request.cookies.get('__csrf')
    }
    if not all(required_cookies.values()):
        return jsonify({"code": 401, "msg": "认证失败，请确保已登录"})

    try:
        url = f"{BASE_URL}/api/playlist/detail?id={playlist_id}"
        session = get_retry_session()
        resp = session.get(url, headers=get_headers(), cookies=required_cookies)
        if resp.status_code != 200:
            raise Exception(f"接口返回错误状态码: {resp.status_code}")
        data = resp.json()
        if 'result' not in data:
            raise Exception("返回数据缺少 'result' 字段")
        playlist = data['result']
        processed = {
            "playlist_id": playlist.get('id'),
            "name": playlist.get('name', '未知歌单'),
            "tracks": [
                {
                    "sort_id": idx + 1,
                    "picurl": t.get('album', {}).get('picUrl') or t.get('album', {}).get('blurPicUrl', ''),
                    "song_id": t.get('id'),
                    "title": t.get('name', '未知曲目'),
                    "duration": f"{t.get('duration', 0) // 1000 // 60:02d}:{t.get('duration', 0) // 1000 % 60:02d}",
                    "artists": ", ".join(a['name'] for a in t.get('artists', []) if a.get('name')),
                    "album": t.get('album', {}).get('name', '')
                }
                for idx, t in enumerate(playlist.get('tracks', []))
            ]
        }
        return jsonify({"code": 200, "data": processed})
    except Exception as e:
        return jsonify({"code": 500, "msg": "服务器处理异常", "error_detail": str(e)})


@app.route('/api/play_log', methods=['POST'])
def save_play_log():
    """保存播放记录"""
    try:
        data = request.json
        sql = text("""
            INSERT INTO play_logs 
            (user_id, song_id, song_name, current_position, song_duration, played_at)
            VALUES (:user_id, :song_id, :song_name, :current_time, :duration, NOW())
            ON DUPLICATE KEY UPDATE 
              current_position = VALUES(current_position),
              song_duration = VALUES(song_duration),
              played_at = NOW(),
              update_time = NOW()
        """)
        db.session.execute(sql, {
            'user_id': data['user_id'],
            'song_id': data['song_id'],
            'song_name': data.get('song_name', ''),
            'current_time': data['current_time'],
            'duration': data['duration']
        })
        db.session.commit()
        return jsonify({"code": 200, "msg": "播放记录已保存"})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})


@app.route('/api/play_logs', methods=['GET'])
def get_play_logs():
    """获取播放历史记录"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"code": 400, "msg": "缺少 user_id 参数"})
        sql = text("""
            SELECT 
                song_id,
                song_name,
                CASE 
                    WHEN current_position >= song_duration * 0.9 THEN 0
                    ELSE current_position
                END AS adjusted_current_time,
                song_duration,
                played_at
            FROM play_logs
            WHERE user_id = :user_id
            ORDER BY played_at DESC
            LIMIT 100
        """)
        result = db.session.execute(sql, {'user_id': user_id})
        logs = [dict(row._mapping) for row in result]
        return jsonify({"code": 200, "data": logs})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})


if __name__ == '__main__':
    app.run('0.0.0.0', debug=True, port=5000)
