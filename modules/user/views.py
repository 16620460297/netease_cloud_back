from flask import Blueprint, jsonify, request
from .services import get_qrcode, check_login, logout

user_bp = Blueprint('user', __name__, url_prefix='/api/user')

@user_bp.route('/qrcode', methods=['GET'])
def qrcode():
    return get_qrcode()

@user_bp.route('/check_login', methods=['GET'])
def check_login_status():
    return check_login()

@user_bp.route('/logout', methods=['GET'])
def logout_user():
    return logout()
