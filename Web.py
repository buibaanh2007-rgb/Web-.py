from functools import wraps
import time
from flask import Flask, Response, jsonify, render_template_string, request, session, redirect, url_for
import requests

app = Flask(__name__)
app.secret_key = "iot_speaker_secret_key_2026"

# --- CẤU HÌNH KẾT NỐI ---
AI_SERVICE_URL = "http://127.0.0.1:8080"  # Địa chỉ của sv1
API_KEY = "iot_secure_token_2026"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# --- CẤU HÌNH TÀI KHOẢN ĐĂNG NHẬP ADMIN ---
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# --- HỆ THỐNG CHỐNG BRUTE-FORCE (QUẢN LÝ THEO IP) ---
ip_attempts = {}       # Đếm tổng số lần sai của từng IP
ip_lockout_until = {}  # Thời gian hết hạn khóa 60s
ip_banned = set()      # Danh sách các IP bị khóa vĩnh viễn

# Biến toàn cục lưu trữ dữ liệu đồng bộ từ sv1 và môi trường (giữ lại giá trị cuối cùng, mặc định ban đầu là -- nếu chưa có)
sv1_live_data = {
    "event": "waiting",
    "spoken_text": "Chưa có tương tác",
    "bot_state": "NGU",
    "bot_mode": "DEFAULT",
    "alarm_state": "OFF",
    "alarm_hour": "--",
    "alarm_minute": "--",
    "alarm_period": "",
    "room_temp": "--",
    "room_hum": "--",
    "weather_temp": "--",
    "weather_hum": "--",
    "weather_desc": "--",
    "location": "HaNam",
    "mode_5_active": False,
}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            if request.path.startswith('/api/'):
                return jsonify({"status": "unauthorized"}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Đăng nhập - AI Speaker Admin</title>
    <style>
        /* Phông nền kết hợp hài hòa giữa màu xanh da trời và trắng/sáng nhẹ */
        body { 
            font-family: Arial, sans-serif; 
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #e0e6ed 100%); 
            color: #333; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            height: 100vh; 
            margin: 0; 
        }
        
        /* Khung Admin Login trong suốt (Hiệu ứng kính mờ Glassmorphism) */
        .login-card { 
            background: rgba(255, 255, 255, 0.15); 
            backdrop-filter: blur(12px); 
            -webkit-backdrop-filter: blur(12px); 
            padding: 30px; 
            border-radius: 16px; 
            border: 1px solid rgba(255, 255, 255, 0.3); 
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3); 
            width: 320px; 
        }
        
        /* Chữ "Admin Login" màu xanh lá */
        h2 { text-align: center; color: #4CAF50; margin-top: 0; text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
        
        .form-group { margin-bottom: 15px; }
        
        /* Chữ "Tài khoản" và "Mật khẩu" màu vàng */
        label { display: block; margin-bottom: 5px; font-size: 0.9em; color: #ffeb3b; font-weight: bold; text-shadow: 0 1px 2px rgba(0,0,0,0.3); }
        
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; background: rgba(255, 255, 255, 0.8); border: 1px solid rgba(255, 255, 255, 0.5); border-radius: 5px; color: #333; box-sizing: border-box; }
        input[type="text"]:focus, input[type="password"]:focus { background: #ffffff; outline: none; border-color: #4CAF50; }
        
        .password-wrapper { position: relative; }
        .password-wrapper input { width: 100%; padding-right: 40px; box-sizing: border-box; }
        .toggle-password { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; color: #555; cursor: pointer; font-size: 1.1em; padding: 0; }
        .toggle-password:hover { color: #000; }
        
        .checkbox-row { display: flex; align-items: center; margin-bottom: 20px; background: rgba(255, 255, 255, 0.2); padding: 10px; border-radius: 5px; border: 1px solid rgba(255, 255, 255, 0.3); }
        .checkbox-row input { width: 18px; height: 18px; margin-right: 10px; cursor: pointer; }
        
        /* Chữ "Tôi không phải là robot" màu đỏ */
        .robot-label { margin-bottom: 0; cursor: pointer; color: #ff5252 !important; font-size: 0.95em; font-weight: bold; text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
        
        /* Nút Đăng Nhập màu xanh lá */
        .btn-submit { width: 100%; padding: 10px; background: #4CAF50; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 1em; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
        .btn-submit:hover { background: #43a047; }
        .btn-submit:disabled { background: rgba(204, 204, 204, 0.5); color: #666; cursor: not-allowed; }
        .error { color: #ff5252; text-align: center; margin-bottom: 15px; font-size: 0.9em; background: rgba(0, 0, 0, 0.3); padding: 8px; border-radius: 4px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>Admin Login</h2>
        {% if error %}
        <div class="error" id="error-msg">{{ error }}</div>
        {% endif %}
        <form method="POST" id="login-form">
            <div class="form-group">
                <label>Tài khoản:</label>
                <input type="text" id="username-field" name="username" placeholder="Nhập admin..." required autocomplete="off" {{ "disabled" if locked else "" }}>
            </div>
            <div class="form-group">
                <label>Mật khẩu:</label>
                <div class="password-wrapper">
                    <input type="password" id="password-field" name="password" placeholder="Nhập mật khẩu..." required {{ "disabled" if locked else "" }}>
                    <button type="button" class="toggle-password" id="toggle-btn" onclick="togglePassword()">👁️</button>
                </div>
            </div>
            <div class="checkbox-row">
                <input type="checkbox" id="robot" name="robot_check" {{ "disabled" if locked else "" }} required>
                <label for="robot" class="robot-label">Tôi không phải là robot</label>
            </div>
            <button type="submit" id="submit-btn" class="btn-submit" {{ "disabled" if locked else "" }}>Đăng Nhập</button>
        </form>
    </div>

    <script>
        function togglePassword() {
            let pwdInput = document.getElementById('password-field');
            let btn = document.getElementById('toggle-btn');
            if (pwdInput.type === 'password') {
                pwdInput.type = 'text';
                btn.innerText = '🙈';
            } else {
                pwdInput.type = 'password';
                btn.innerText = '👁️';
            }
        }

        let remainingSeconds = {{ remaining_seconds|default(0) }};
        if (remainingSeconds > 0) {
            let errorDiv = document.getElementById('error-msg');
            let usernameField = document.getElementById('username-field');
            let passwordField = document.getElementById('password-field');
            let robotCheckbox = document.getElementById('robot');
            let submitBtn = document.getElementById('submit-btn');

            let countdownTimer = setInterval(function() {
                remainingSeconds--;
                if (remainingSeconds > 0) {
                    errorDiv.innerText = "Sai 3 lần! Tài khoản của bạn bị khóa tạm thời trong " + remainingSeconds + " giây.";
                } else {
                    clearInterval(countdownTimer);
                    errorDiv.innerText = "Đã hết thời gian khóa. Vui lòng thử lại!";
                    errorDiv.style.background = "rgba(0, 0, 0, 0.3)";
                    errorDiv.style.color = "#4CAF50";
                    
                    usernameField.disabled = false;
                    passwordField.disabled = false;
                    robotCheckbox.disabled = false;
                    submitBtn.disabled = false;
                }
            }, 1000);
        }
    </script>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Speaker Dashboard (Secure Admin)</title>
    <style>
        body { font-family: Arial, sans-serif; background: #121212; color: #e0e0e0; margin: 0; padding: 20px; }
        .container { max-width: 520px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        h2 { text-align: center; color: #4CAF50; margin: 0; flex-grow: 1; }
        .btn-logout { background: #f44336; color: white; padding: 6px 12px; border: none; border-radius: 5px; cursor: pointer; font-size: 0.85em; font-weight: bold; text-decoration: none; }
        .card { background: #2d2d2d; padding: 15px; margin-bottom: 15px; border-radius: 8px; }
        .card h3 { margin-top: 0; font-size: 1.1em; color: #90caf9; }
        .row { display: flex; justify-content: space-between; align-items: center; margin: 10px 0; }
        input[type="time"] { background: #333; color: #fff; border: 1px solid #555; padding: 8px; border-radius: 5px; font-size: 1em; }
        button { padding: 8px 15px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .btn-primary { background: #4CAF50; color: white; }
        .btn-danger { background: #f44336; color: white; }
        .btn-toggle { background: #ff9800; color: white; }
        .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 0.9em; }
        .badge-on { background: #2e7d32; color: #a5d6a7; }
        .badge-off { background: #c62828; color: #ffcdd2; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-row">
            <h2>AI Speaker Dashboard</h2>
            <a href="/logout" class="btn-logout">Đăng xuất</a>
        </div>
        
        <div class="card">
            <h3>0. Trạng thái hệ thống (SV1)</h3>
            <div class="row">
                <span>Trạng thái Bot: <strong id="bot-state-val">--</strong></span>
                <span>Chế độ: <strong id="bot-mode-val">--</strong></span>
            </div>
            <div class="row">
                <span>Lệnh gần nhất: <strong id="spoken-text-val" style="color: #ffeb3b;">--</strong></span>
            </div>
        </div>

        <div class="card">
            <h3>1. Môi trường phòng (Cảm biến DHT22)</h3>
            <div class="row">
                <span>Nhiệt độ phòng: <strong id="room-temp-val">--</strong>°C</span>
                <span>Độ ẩm phòng: <strong id="room-hum-val">--</strong>%</span>
            </div>
        </div>

        <div class="card">
            <h3>2. Thời tiết ngoài trời</h3>
            <div class="row">
                <span>Nhiệt độ ngoài: <strong id="weather-temp-val">--</strong>°C</span>
                <span>Độ ẩm ngoài: <strong id="weather-hum-val">--</strong>%</span>
            </div>
            <div class="row">
                <span>Trạng thái: <strong id="weather-desc">--</strong></span>
                <span>Khu vực: <strong id="weather-loc">--</strong></span>
            </div>
        </div>

        <div class="card">
            <h3>3. Cài đặt Báo thức</h3>
            <div class="row">
                <label>Thời gian báo thức:</label>
                <input type="time" id="alarm-time-input">
                <button class="btn-primary" onclick="setAlarm()">Lưu</button>
            </div>
            <div class="row">
                <span>Trạng thái: <span id="alarm-status-text" class="status-badge badge-off">ĐANG TẮT</span></span>
                <button class="btn-danger" onclick="stopAlarm()">Tắt chuông</button>
            </div>
        </div>

        <div class="card">
            <h3>4. Tính năng ẩn (Mode 5)</h3>
            <div class="row">
                <span>Trạng thái Mode 5: <span id="m5-status-text" class="status-badge badge-off">TẮT</span></span>
                <button id="btn-m5" class="btn-toggle" onclick="toggleMode5()">Bật Mode 5</button>
            </div>
        </div>
    </div>

    <script>
        function fetchData() {
            fetch('/api/status')
                .then(res => {
                    if (res.status === 401) {
                        alert("Phiên đăng nhập hết hạn!");
                        window.location.href = '/login';
                        return;
                    }
                    return res.json();
                })
                .then(data => {
                    if (!data) return;
                    
                    document.getElementById('bot-state-val').innerText = data.bot_state;
                    document.getElementById('bot-mode-val').innerText = data.bot_mode;
                    document.getElementById('spoken-text-val').innerText = '"' + (data.spoken_text || '') + '"';

                    document.getElementById('room-temp-val').innerText = data.room_temp;
                    document.getElementById('room-hum-val').innerText = data.room_hum;

                    document.getElementById('weather-temp-val').innerText = data.weather_temp;
                    document.getElementById('weather-hum-val').innerText = data.weather_hum;
                    document.getElementById('weather-desc').innerText = data.weather_desc;
                    document.getElementById('weather-loc').innerText = data.location;
                    
                    let statusText = document.getElementById('alarm-status-text');
                    if (data.alarm_state === "ON" || data.alarm_is_active) {
                        let h = data.alarm_hour !== undefined ? data.alarm_hour : '--';
                        let m = data.alarm_minute !== undefined ? String(data.alarm_minute).padStart(2, '0') : '--';
                        statusText.innerText = "ĐANG BẬT (" + h + ":" + m + ")";
                        statusText.className = "status-badge badge-on";
                    } else {
                        statusText.innerText = "ĐANG TẮT";
                        statusText.className = "status-badge badge-off";
                    }

                    let m5Text = document.getElementById('m5-status-text');
                    let m5Btn = document.getElementById('btn-m5');
                    if (data.mode_5_active || data.bot_mode === "SET_MODE_5") {
                        m5Text.innerText = "ĐANG BẬT";
                        m5Text.className = "status-badge badge-on";
                        m5Btn.innerText = "Tắt Mode 5";
                    } else {
                        m5Text.innerText = "TẮT";
                        m5Text.className = "status-badge badge-off";
                        m5Btn.innerText = "Bật Mode 5";
                    }
                });
        }

        function setAlarm() {
            let timeVal = document.getElementById('alarm-time-input').value;
            if (!timeVal) { alert("Vui lòng chọn giờ!"); return; }
            let parts = timeVal.split(":");
            fetch('/api/set-alarm', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({hour: parseInt(parts[0]), minute: parseInt(parts[1])})
            }).then(res => {
                if(res.ok) { alert("Đã cập nhật báo thức!"); fetchData(); }
            });
        }

        function stopAlarm() {
            fetch('/api/stop-alarm', {method: 'POST'}).then(() => { fetchData(); });
        }

        function toggleMode5() {
            fetch('/api/toggle-mode5', {method: 'POST'}).then(() => { fetchData(); });
        }

        setInterval(fetchData, 2000);
        fetchData();
    </script>
</body>
</html>
"""

@app.route("/login", methods=["GET", "POST"])
def login_page():
    error = None
    client_ip = request.remote_addr
    remaining_seconds = 0
    is_locked = False

    if client_ip in ip_banned:
        return render_template_string(LOGIN_TEMPLATE, error="IP của bạn đã bị KHÓA VĨNH VIỄN do nhập sai quá nhiều lần!", locked=True, remaining_seconds=0)

    if client_ip in ip_lockout_until:
        remaining = int(ip_lockout_until[client_ip] - time.time())
        if remaining > 0:
            remaining_seconds = remaining
            is_locked = True
            error = f"Sai 3 lần! Tài khoản của bạn bị khóa tạm thời trong {remaining_seconds} giây."
        else:
            ip_lockout_until.pop(client_ip, None)
            ip_attempts[client_ip] = 0

    if request.method == "POST" and not is_locked:
        username = request.form.get("username")
        password = request.form.get("password")
        robot_check = request.form.get("robot_check")
        
        if not robot_check:
            error = "Vui lòng xác nhận bạn không phải người máy!"
        elif username == ADMIN_USER and password == ADMIN_PASS:
            ip_attempts.pop(client_ip, None)
            ip_lockout_until.pop(client_ip, None)
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            ip_attempts[client_ip] = ip_attempts.get(client_ip, 0) + 1
            fails = ip_attempts[client_ip]

            if fails >= 6:
                ip_banned.add(client_ip)
                is_locked = True
                error = "Bạn đã nhập sai quá nhiều lần. IP này đã bị KHÓA VĨNH VIỄN!"
            elif fails == 3:
                lock_duration = 60
                ip_lockout_until[client_ip] = time.time() + lock_duration
                remaining_seconds = lock_duration
                is_locked = True
                error = f"Sai 3 lần! Tài khoản của bạn bị khóa tạm thời trong {remaining_seconds} giây."
            else:
                remaining_tries = 3 if fails < 3 else (6 - fails)
                error = f"Sai tài khoản hoặc mật khẩu! (Bạn còn {remaining_tries} lần thử trước khi bị khóa)."
            
    return render_template_string(LOGIN_TEMPLATE, error=error, locked=is_locked, remaining_seconds=remaining_seconds)

@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login_page'))

@app.route("/")
@login_required
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/sync", methods=["POST"])
def sync_from_sv1():
    global sv1_live_data
    if request.is_json:
        data = request.get_json()
        for key, value in data.items():
            # Chỉ cập nhật nếu gói tin gửi lên có chứa dữ liệu hợp lệ (không bị None, rỗng hoặc --)
            if key in ["room_temp", "room_hum"]:
                if value is not None and str(value).strip() != "" and str(value).strip() != "--":
                    sv1_live_data[key] = value
            else:
                if value is not None:
                    sv1_live_data[key] = value
                    
        print(f"[sv2] Nhận sync từ sv1 thành công. Lưu trữ hiện tại -> Phòng: {sv1_live_data.get('room_temp')}°C, {sv1_live_data.get('room_hum')}%")
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400

@app.route("/api/status", methods=["GET"])
@login_required
def api_status():
    try:
        location = sv1_live_data.get("location", "HaNam")
        wttr_res = requests.get(f"https://wttr.in/{location}?format=j1", timeout=2)
        if wttr_res.status_code == 200:
            wttr_json = wttr_res.json()
            sv1_live_data["weather_temp"] = wttr_json["current_condition"][0]["temp_C"]
            sv1_live_data["weather_hum"] = wttr_json["current_condition"][0]["humidity"]
            sv1_live_data["weather_desc"] = wttr_json["current_condition"][0]["weatherDesc"][0]["value"]
    except Exception as e:
        print(f"[sv2] Lỗi fetch wttr.in: {e}")
    return jsonify(sv1_live_data)

@app.route("/api/set-alarm", methods=["POST"])
@login_required
def api_set_alarm():
    data = request.get_json()
    try:
        requests.post(
            f"{AI_SERVICE_URL}/api/set-alarm",
            json=data,
            headers=HEADERS,
            timeout=2,
        )
        sv1_live_data["alarm_hour"] = data.get("hour")
        sv1_live_data["alarm_minute"] = data.get("minute")
        sv1_live_data["alarm_is_active"] = True
        sv1_live_data["alarm_state"] = "ON"
    except Exception as e:
        print(f"[sv2 -> sv1] Lỗi set alarm: {e}")
    return jsonify({"status": "success"})

@app.route("/api/stop-alarm", methods=["POST"])
@login_required
def api_stop_alarm():
    try:
        requests.post(f"{AI_SERVICE_URL}/api/stop-alarm", headers=HEADERS, timeout=2)
        sv1_live_data["alarm_is_active"] = False
        sv1_live_data["alarm_state"] = "OFF"
    except Exception as e:
        print(f"[sv2 -> sv1] Lỗi stop alarm: {e}")
    return jsonify({"status": "success"})

@app.route("/api/toggle-mode5", methods=["POST"])
@login_required
def api_toggle_mode5():
    try:
        res = requests.post(
            f"{AI_SERVICE_URL}/api/toggle-mode5", headers=HEADERS, timeout=2
        )
        res_data = res.json()
        sv1_live_data["mode_5_active"] = res_data.get("mode_5_active", False)
        if sv1_live_data["mode_5_active"]:
            sv1_live_data["bot_mode"] = "SET_MODE_5"
        return jsonify(res_data)
    except Exception as e:
        print(f"[sv2 -> sv1] Lỗi toggle mode 5: {e}")
        return jsonify({"status": "error", "mode_5_active": False})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9090, debug=False)
