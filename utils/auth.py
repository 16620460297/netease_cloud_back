import requests
import qrcode
import io
import base64
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random
import execjs
import json

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
    with open("static/main.js", "r", encoding="utf-8") as f:
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
    session = requests.Session()
    retry = Retry(total=10, backoff_factor=1, status_forcelist=[500, 502, 503, 504], allowed_methods=["GET", "POST"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
