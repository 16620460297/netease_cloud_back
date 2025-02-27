from flask import jsonify, request
from utils.auth import get_qrcode_unikey, generate_qrcode_image, check_login_status_once, get_user_profile
from .models import User
import json
import requests
from utils.db import db
def get_qrcode():
    try:
        unikey = get_qrcode_unikey()
        qr_code_base64 = generate_qrcode_image(unikey)
        return jsonify({"code": 200, "data": {"unikey": unikey, "qrCodeBase64": qr_code_base64}})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})

def check_login():
    from app import db  # 在函数内部导入 db
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

def logout():
    cookies = request.cookies
    url = "https://music.163.com/api/logout"
    resp = requests.get(url, headers=get_headers(), cookies=cookies)
    if resp.status_code == 200:
        return jsonify({"code": 200, "msg": "注销成功"})
    return jsonify({"code": 500, "msg": "注销失败"})
