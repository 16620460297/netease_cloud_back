from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json, random, execjs, requests, qrcode, io, base64
from sqlalchemy.dialects.mysql import LONGTEXT
# 基础配置
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
    return {
        "params": result["encText"],
        "encSecKey": result["encSecKey"]
    }

def get_qrcode_unikey():
    """获取登录二维码的 unikey"""
    url = f"{BASE_URL}/weapi/login/qrcode/unikey"
    data = {"type": 1}
    response = requests.post(url, data=encrypted_request(data), headers=get_headers())
    if response.status_code == 200:
        result = response.json()
        if result["code"] == 200:
            return result["unikey"]
    raise Exception("获取 unikey 失败")

def generate_qrcode_image(unikey):
    """生成二维码图片并返回 base64 编码字符串"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    # 二维码中携带登录链接（可以根据实际需求调整）
    qr.add_data(f"{BASE_URL}/login?codekey={unikey}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_str

def get_user_profile(cookies):
    url = f"{BASE_URL}/weapi/w/nuser/account/get"
    response = requests.post(url,
                             data=encrypted_request({}),
                             headers=get_headers(),
                             cookies=cookies)
    return response.json()

def check_login_status_once(unikey):
    """单次查询登录状态"""
    url = f"{BASE_URL}/weapi/login/qrcode/client/login"
    data = {
        "key": unikey,
        "type": 1,
        "csrf_token": ""
    }
    response = requests.post(url, data=encrypted_request(data), headers=get_headers())
    result = response.json()
    if result.get("code") == 803:  # 803 表示登录成功
        cookies = response.cookies.get_dict()
        print("[登录成功] Cookies:", cookies)
        result["cookies"] = cookies
        profile = get_user_profile(cookies)
        print("[用户信息]", profile)
        result["profile"] = profile
    return result

app = Flask(__name__)
CORS(app)

# 配置 MySQL 数据库（请根据实际情况修改用户名、密码、主机和数据库名）
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:MO520MING@localhost/netease_cloud?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 用户模型：使用登录返回的 userId 作为主键
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.BigInteger, primary_key=True)  # 登录后返回的 userId
    nickname = db.Column(db.String(100))
    avatar_url = db.Column(db.String(255))
    cookies = db.Column(db.Text)  # 保存 cookies（以 JSON 字符串形式）
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 歌单模型：存储用户的个人歌单数据（JSON 格式）
class Playlist(db.Model):
    __tablename__ = 'playlists'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.user_id'), unique=True)  # 每个用户一个唯一的歌单记录
    playlist_data = db.Column(LONGTEXT)  # 歌单数据 JSON 字符串
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 播放记录模型：记录用户播放的歌曲和播放时间
class PlayLog(db.Model):
    __tablename__ = 'play_logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.user_id'))
    song_id = db.Column(db.BigInteger)  # 歌曲 ID（可按需扩展）
    song_name = db.Column(db.String(255))
    played_at = db.Column(db.DateTime, default=datetime.utcnow)

# 首次运行时创建数据表
with app.app_context():
    db.create_all()

@app.route('/api/qrcode', methods=['GET'])
def api_qrcode():
    """
    1. 获取 unikey
    2. 生成二维码图片（返回 base64 字符串）
    """
    try:
        unikey = get_qrcode_unikey()
        qr_code_base64 = generate_qrcode_image(unikey)
        return jsonify({
            "code": 200,
            "data": {
                "unikey": unikey,
                "qrCodeBase64": qr_code_base64
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})

@app.route('/api/check_login', methods=['GET'])
def api_check_login():
    unikey = request.args.get('unikey')
    if not unikey:
        return jsonify({"code": 400, "msg": "缺少 unikey 参数"})
    result = check_login_status_once(unikey)
    print(result)
    if result.get("code") == 803:
        cookies = result.get("cookies")
        profile = result.get("profile")
        # 注意：用户 ID 存放在 profile['profile'] 中
        user_profile = profile.get("profile", {})
        user_id = user_profile.get("userId")
        if not user_id:
            return jsonify({"code": 500, "msg": "未能获取用户ID"})
        # 保存到数据库
        user = User.query.get(user_id)
        if not user:
            user = User(
                user_id=user_id,
                nickname=user_profile.get("nickname"),
                avatar_url=user_profile.get("avatarUrl"),
                cookies=json.dumps(cookies)
            )
            db.session.add(user)
        else:
            user.nickname = user_profile.get("nickname")
            user.avatar_url = user_profile.get("avatarUrl")
            user.cookies = json.dumps(cookies)
        db.session.commit()
    return jsonify(result)


@app.route('/api/save_playlist', methods=['GET'])
def api_save_playlist():
    """
    调用网易云音乐的个人歌单接口，将数据存储到数据库中。
    uid 参数为登录后返回的 userId
    接口示例：http://music.163.com/api/user/playlist/?offset=0&limit=100&uid=1677021648
    """
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"code": 400, "msg": "缺少 uid 参数"})
    url = f"http://music.163.com/api/user/playlist/?offset=0&limit=100&uid={uid}"
    res = requests.get(url, headers=get_headers())
    if res.status_code == 200:
        playlist_data = res.json()
        # 将歌单数据以 JSON 格式保存到数据库中
        playlist = Playlist.query.filter_by(user_id=uid).first()
        if not playlist:
            playlist = Playlist(
                user_id=uid,
                playlist_data=json.dumps(playlist_data)
            )
            db.session.add(playlist)
        else:
            playlist.playlist_data = json.dumps(playlist_data)
        db.session.commit()
        return jsonify({"code": 200, "msg": "歌单数据已存储", "data": playlist_data})
    else:
        return jsonify({"code": 500, "msg": "获取歌单失败"})

@app.route('/api/logout', methods=['GET'])
def api_logout():
    """
    退出登录接口
    调用网易云音乐的注销接口并返回结果
    """
    cookies = request.cookies
    url = f"{BASE_URL}/api/logout"
    response = requests.get(url, headers=get_headers(), cookies=cookies)
    if response.status_code == 200:
        return jsonify({"code": 200, "msg": "注销成功"})
    return jsonify({"code": 500, "msg": "注销失败"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
