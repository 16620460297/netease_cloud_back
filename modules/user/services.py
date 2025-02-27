from flask import jsonify, request, current_app
from utils.auth import get_qrcode_unikey, generate_qrcode_image, check_login_status_once, get_user_profile, get_headers
from .models import User
import json
import requests
from utils.db import db

def get_qrcode():
    try:
        current_app.logger.info("[get_qrcode] 开始生成二维码")
        unikey = get_qrcode_unikey()
        qr_code_base64 = generate_qrcode_image(unikey)

        current_app.logger.debug("[get_qrcode] 生成的 unikey: %s", unikey)

        return jsonify({"code": 200, "data": {"unikey": unikey, "qrCodeBase64": qr_code_base64}})
    except Exception as e:
        current_app.logger.error("[get_qrcode] 发生异常: %s", str(e))
        return jsonify({"code": 500, "msg": str(e)})


def check_login():
    # 在函数内部也可以使用 db，但是注意确保 import 没有循环依赖
    from app import db
    unikey = request.args.get('unikey')

    if not unikey:
        current_app.logger.warning("[check_login] 缺少 unikey 参数")
        return jsonify({"code": 400, "msg": "缺少 unikey 参数"})

    # 可以在这里记录一下调用参数和方法开始的信息
    current_app.logger.info("[check_login] 开始检查登录状态, unikey=%s", unikey)

    try:
        result = check_login_status_once(unikey)

        # 当 result.get("code") == 803 时，代表需要写入数据库
        if result.get("code") == 803:
            cookies = result.get("cookies")
            profile = result.get("profile", {}).get("profile", {})
            user_id = profile.get("userId")

            current_app.logger.debug(
                "[check_login] 登录成功, user_id=%s, nickname=%s",
                user_id, profile.get("nickname")
            )

            if not user_id:
                current_app.logger.error("[check_login] 未能获取用户ID")
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
        else:
            current_app.logger.debug("[check_login] code != 803, result=%s", result)

        return jsonify(result)

    except Exception as e:
        current_app.logger.error("[check_login] 发生异常: %s", str(e))
        return jsonify({"code": 500, "msg": str(e)})


def logout():
    current_app.logger.info("[logout] 开始执行注销")
    cookies = request.cookies
    url = "https://music.163.com/api/logout"

    # 根据实际需求，可选择性地在日志里输出部分 Cookie 内容(注意隐私/敏感信息)
    # current_app.logger.debug("[logout] cookies: %s", cookies)

    resp = requests.get(url, headers=get_headers(), cookies=cookies)
    if resp.status_code == 200:
        current_app.logger.info("[logout] 注销成功")
        return jsonify({"code": 200, "msg": "注销成功"})
    else:
        current_app.logger.error("[logout] 注销失败, status_code=%s, resp=%s",
                                resp.status_code, resp.text)
        return jsonify({"code": 500, "msg": "注销失败"})

