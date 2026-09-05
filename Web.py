from functools import wraps
from flask import Flask, jsonify, render_template_string, request, Response
import requests

app = Flask(__name__)

# --- CẤU HÌNH KẾT NỐI ---
AI_SERVICE_URL = "http://127.0.0.1:8080"  # Địa chỉ của sv1
API_KEY = "iot_secure_token_2026"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# --- CẤU HÌNH TÀI KHOẢN ĐĂNG NHẬP ADMIN ---
ADMIN_USER = "admin"
ADMIN_PASS = "123"

# Biến toàn cục lưu trữ dữ liệu thời tiết và trạng thái nhận chủ động từ sv1
sv1_live_data = {
    "temp": "--",
    "hum": "--",
    "weather_desc": "--",
    "location": "HaNam",
    "alarm_is_active": False,
    "alarm_hour": 6,
    "alarm_minute": 0,
    "mode_5_active": False
}

def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASS

def authenticate():
    return Response(
        'Truy cập bị từ chối. Vui lòng đăng nhập tài khoản Admin!', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Speaker Dashboard (Secure Admin)</title>
    <style>
        body { font-family: Arial, sans-serif; background: #121212; color: #e0e0e0; margin: 0; padding: 20px; }
        .container { max-width: 500px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        h2 { text-align: center; color: #4CAF50; }
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
        <h2>AI Speaker Dashboard (Admin)</h2>
        
        <div class="card">
            <h3>1. Môi trường & Thời tiết từ SV1</h3>
            <div class="row">
                <span>Nhiệt độ: <strong id="temp-val">--</strong>°C</span>
                <span>Độ ẩm: <strong id="hum-val">--</strong>%</span>
            </div>
            <div class="row">
                <span>Trạng thái: <strong id="weather-desc">--</strong></span>
                <span>Khu vực: <strong id="weather-loc">--</strong></span>
            </div>
        </div>

        <div class="card">
            <h3>2. Cài đặt Báo thức</h3>
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
            <h3>3. Tính năng ẩn (Mode 5)</h3>
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
                        alert("Phiên đăng nhập hết hạn hoặc chưa xác thực!");
                        location.reload();
                        return;
                    }
                    return res.json();
                })
                .then(data => {
                    if (!data) return;
                    document.getElementById('temp-val').innerText = data.temp;
                    document.getElementById('hum-val').innerText = data.hum;
                    document.getElementById('weather-desc').innerText = data.weather_desc;
                    document.getElementById('weather-loc').innerText = data.location;
                    
                    let statusText = document.getElementById('alarm-status-text');
                    if (data.alarm_is_active) {
                        statusText.innerText = "ĐANG BẬT (" + data.alarm_hour + ":" + String(data.alarm_minute).padStart(2, '0') + ")";
                        statusText.className = "status-badge badge-on";
                    } else {
                        statusText.innerText = "ĐANG TẮT";
                        statusText.className = "status-badge badge-off";
                    }

                    let m5Text = document.getElementById('m5-status-text');
                    let m5Btn = document.getElementById('btn-m5');
                    if (data.mode_5_active) {
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

@app.route("/")
@requires_auth
def dashboard():
    return render_template_string(HTML_TEMPLATE)


# --- ENDPOINT NHẬN DATA BẮN TỪ SV1 SANG SV2 ---
@app.route("/api/sync", methods=["POST"])
def sync_from_sv1():
    global sv1_live_data
    if request.is_json:
        data = request.get_json()
        # Cập nhật các trường dữ liệu được đẩy từ sv1 sang
        for key in data:
            sv1_live_data[key] = data[key]
        print(f"[sv2] Nhận sync thành công từ sv1: {data}")
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400


@app.route("/api/status", methods=["GET"])
@requires_auth
def api_status():
    """Lấy dữ liệu trạng thái kết hợp gọi thời tiết JSON trực tiếp từ wttr.in (nếu cần) hoặc trả về cache từ sv1"""
    try:
        # Chủ động gọi bóc tách JSON thời tiết từ wttr.in để hiển thị trực tiếp lên Dashboard sv2
        location = sv1_live_data.get("location", "HaNam")
        wttr_res = requests.get(f"https://wttr.in/{location}?format=j1", timeout=2)
        if wttr_res.status_code == 200:
            wttr_json = wttr_res.json()
            sv1_live_data["temp"] = wttr_json["current_condition"][0]["temp_C"]
            sv1_live_data["hum"] = wttr_json["current_condition"][0]["humidity"]
            sv1_live_data["weather_desc"] = wttr_json["current_condition"][0]["weatherDesc"][0]["value"]
    except Exception as e:
        print(f"[sv2] Lỗi fetch wttr.in: {e}")

    return jsonify(sv1_live_data)

@app.route("/api/set-alarm", methods=["POST"])
@requires_auth
def api_set_alarm():
    data = request.get_json()
    try:
        # Bắn lệnh cấu hình báo thức từ sv2 sang sv1
        requests.post(f"{AI_SERVICE_URL}/api/set-alarm", json=data, headers=HEADERS, timeout=2)
        sv1_live_data["alarm_hour"] = data.get("hour")
        sv1_live_data["alarm_minute"] = data.get("minute")
        sv1_live_data["alarm_is_active"] = True
    except Exception as e:
        print(f"[sv2 -> sv1] Lỗi set alarm: {e}")
    return jsonify({"status": "success"})

@app.route("/api/stop-alarm", methods=["POST"])
@requires_auth
def api_stop_alarm():
    try:
        # Bắn lệnh tắt chuông từ sv2 sang sv1
        requests.post(f"{AI_SERVICE_URL}/api/stop-alarm", headers=HEADERS, timeout=2)
        sv1_live_data["alarm_is_active"] = False
    except Exception as e:
        print(f"[sv2 -> sv1] Lỗi stop alarm: {e}")
    return jsonify({"status": "success"})

@app.route("/api/toggle-mode5", methods=["POST"])
@requires_auth
def api_toggle_mode5():
    try:
        # Bắn lệnh chuyển mode 5 từ sv2 sang sv1 và nhận trạng thái phản hồi
        res = requests.post(f"{AI_SERVICE_URL}/api/toggle-mode5", headers=HEADERS, timeout=2)
        res_data = res.json()
        sv1_live_data["mode_5_active"] = res_data.get("mode_5_active", False)
        return jsonify(res_data)
    except Exception as e:
        print(f"[sv2 -> sv1] Lỗi toggle mode 5: {e}")
        return jsonify({"status": "error", "mode_5_active": False})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9090, debug=False)
