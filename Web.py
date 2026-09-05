from functools import wraps
from flask import Flask, Response, jsonify, render_template_string, request
import requests

app = Flask(__name__)

# --- CẤU HÌNH KẾT NỐI ---
AI_SERVICE_URL = "http://127.0.0.1:8080"  # Địa chỉ của sv1
API_KEY = "iot_secure_token_2026"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# --- CẤU HÌNH TÀI KHOẢN ĐĂNG NHẬP ADMIN ---
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# Biến toàn cục lưu trữ dữ liệu đồng bộ từ sv1 và môi trường
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


def check_auth(username, password):
  return username == ADMIN_USER and password == ADMIN_PASS


def authenticate():
  return Response(
      "Truy cập bị từ chối. Vui lòng đăng nhập tài khoản Admin!",
      401,
      {"WWW-Authenticate": 'Basic realm="Login Required"'},
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
        .container { max-width: 520px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        h2 { text-align: center; color: #4CAF50; }
        .card { background: #2d2d2d; padding: 15px; margin-bottom: 15px; border-radius: 8px; }
        .card h3 { margin-top: 0; font-size: 1.1em; color: #90caf9; }
        .row { display: flex; justify-content: space-between; align-items: center; margin: 10px 0; }
        input[type="time"] { background: #333; color: #fff; border: 1px solid #555; padding: 8px; border-radius: 5px; font-size: 1em; }
        button { padding: 8px 15px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .btn-primary { background: #4CAF50; color: white; }
        .btn-danger { background: #f44336; color: white; }
        .btn-toggle { background: #ff9800; color: white; }
        .btn-biometric { background: #2196F3; color: white; width: 100%; padding: 12px; font-size: 1em; }
        .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 0.9em; }
        .badge-on { background: #2e7d32; color: #a5d6a7; }
        .badge-off { background: #c62828; color: #ffcdd2; }
    </style>
</head>
<body>
    <div class="container">
        <h2>AI Speaker Dashboard (Admin)</h2>
        
        <!-- Bổ sung Card Đăng nhập / Xác thực Vân tay -->
        <div class="card" style="text-align: center;">
            <h3>🔑 Xác thực Sinh trắc học</h3>
            <button class="btn-biometric" onclick="loginWithFingerprint()">Mở khóa bằng Vân tay / FaceID</button>
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
        // Hàm quét vân tay / sinh trắc học qua WebAuthn API của trình duyệt
        async function loginWithFingerprint() {
            if (!window.PublicKeyCredential) {
                alert("Trình duyệt của Sếp không hỗ trợ xác thực sinh trắc học (WebAuthn)!");
                return;
            }

            try {
                const challenge = new Uint8Array(32);
                window.crypto.getRandomValues(challenge);

                const publicKeyCredentialRequestOptions = {
                    challenge: challenge,
                    timeout: 60000,
                    userVerification: "required",
                };

                const credential = await navigator.credentials.get({
                    publicKey: publicKeyCredentialRequestOptions
                });

                if (credential) {
                    fetch('/api/biometric-login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({id: credential.id})
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === "success") {
                            alert("Xác thực vân tay thành công!");
                        } else {
                            alert("Xác thực thất bại!");
                        }
                    });
                }
            } catch (err) {
                console.error(err);
                alert("Đã hủy hoặc lỗi quét vân tay: " + err.message);
            }
        }

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
    for key in data:
      sv1_live_data[key] = data[key]
    print(f"[sv2] Nhận sync thành công từ sv1: {data}")
    return jsonify({"status": "success"}), 200
  return jsonify({"status": "error"}), 400


# --- ENDPOINT XỬ LÝ ĐĂNG NHẬP SINH TRẮC HỌC (VÂN TAY) ---
@app.route("/api/biometric-login", methods=["POST"])
@requires_auth
def biometric_login():
  data = request.get_json() or {}
  credential_id = data.get("id")
  if credential_id:
    print(f"[sv2 Security] Đăng nhập vân tay thành công! ID: {credential_id[:15]}...")
    return jsonify({"status": "success", "message": "Xác thực thành công"})
  return jsonify({"status": "error", "message": "Xác thực thất bại"}), 400


@app.route("/api/status", methods=["GET"])
@requires_auth
def api_status():
  """Lấy dữ liệu trạng thái kết hợp gọi thời tiết JSON trực tiếp từ wttr.in"""
  try:
    location = sv1_live_data.get("location", "HaNam")
    wttr_res = requests.get(f"https://wttr.in/{location}?format=j1", timeout=2)
    if wttr_res.status_code == 200:
      wttr_json = wttr_res.json()
      sv1_live_data["weather_temp"] = wttr_json["current_condition"][0]["temp_C"]
      sv1_live_data["weather_hum"] = wttr_json["current_condition"][0]["humidity"]
      sv1_live_data["weather_desc"] = wttr_json["current_condition"][0][
          "weatherDesc"
      ][0]["value"]
  except Exception as e:
    print(f"[sv2] Lỗi fetch wttr.in: {e}")

  return jsonify(sv1_live_data)


@app.route("/api/set-alarm", methods=["POST"])
@requires_auth
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
@requires_auth
def api_stop_alarm():
  try:
    requests.post(f"{AI_SERVICE_URL}/api/stop-alarm", headers=HEADERS, timeout=2)
    sv1_live_data["alarm_is_active"] = False
    sv1_live_data["alarm_state"] = "OFF"
  except Exception as e:
    print(f"[sv2 -> sv1] Lỗi stop alarm: {e}")
  return jsonify({"status": "success"})


@app.route("/api/toggle-mode5", methods=["POST"])
@requires_auth
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
