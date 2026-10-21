import os
import sqlite3
import hashlib
import json
import datetime
import requests
from werkzeug.utils import secure_filename
from flask import Flask, request, session, redirect, render_template_string, jsonify

app = Flask(__name__)
app.secret_key = "bench_secret_key_2026"

# ── RAILWAY PERSISTENT VOLUME PATHS ──
DATA_DIR = "/app/data" if os.path.exists("/app") else os.getcwd()
DB = os.path.join(DATA_DIR, "shop.db")
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ── TELEGRAM NOTIFICATION CONFIG ──
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8265117304:AAGqricspzxyY4WrCv93nZkkRcktFsU2Huo")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "8371468799")

def send_tg_alert(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            price REAL,
            payments TEXT,
            image TEXT,
            stock INTEGER DEFAULT 0,
            payment_details TEXT,
            payment_type TEXT DEFAULT 'Number'
        );
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            amount REAL,
            method TEXT,
            date TEXT,
            status TEXT DEFAULT 'Pending',
            receipt TEXT,
            contact TEXT,
            emergency_contact TEXT
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            image TEXT,
            date TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            is_admin INTEGER DEFAULT 0,
            text TEXT,
            date TEXT
        );
    """)
    
    # Safe migrations
    try: c.execute("ALTER TABLE feedback ADD COLUMN image TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE products ADD COLUMN payment_type TEXT DEFAULT 'Number'")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE sales ADD COLUMN emergency_contact TEXT")
    except sqlite3.OperationalError: pass
        
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  ("admin", hashlib.sha256(b"admin123").hexdigest(), "admin"))
    except sqlite3.IntegrityError:
        pass
    c.commit()
    c.close()

BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@900&display=swap');
body{background:#0d1117;color:#c9d1d9;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;padding:20px;position:relative;overflow-x:hidden}
body::before {
  content: "AXEL";
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-family: 'Montserrat', sans-serif;
  font-size: 35vw;
  font-weight: 900;
  color: rgba(255, 255, 255, 0.08);
  text-shadow: 0 0 50px rgba(255, 255, 255, 0.2);
  z-index: 0;
  pointer-events: none;
  letter-spacing: -1vw;
}
.container{max-width:900px;margin:auto;position:relative;z-index:1}
.header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #30363d;padding-bottom:15px;margin-bottom:20px}
a{color:#2ea043;text-decoration:none} a.logout{color:#f85149}
h2,h3{margin-top:0}
.brand-title{font-size:24px;font-weight:900;letter-spacing:1px;color:#fff;display:flex;align-items:center;gap:10px}
.brand-title span{color:#ffffff;}
.card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 4px 20px rgba(0,0,0,0.5)}
input,textarea,select{width:100%;padding:10px;margin:8px 0 16px;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;border-radius:6px;box-sizing:border-box;font-family:inherit}
button{background:#2ea043;color:#fff;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-weight:bold;transition:0.2s}
button:hover{background:#3fb950}
button:disabled{background:#30363d;color:#8b949e;cursor:not-allowed}
button.danger{background:#da3633} button.danger:hover{background:#f85149}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:20px}
.p-card{background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;display:flex;flex-direction:column;position:relative;transition:0.3s}
.p-card:hover{transform:translateY(-5px);border-color:#2ea043}
.p-card img{width:100%;height:150px;object-fit:cover;background:#000}
.p-info{padding:15px;flex:1;display:flex;flex-direction:column}
.p-title{font-size:18px;font-weight:bold;margin-bottom:5px;color:#fff}
.p-price{color:#2ea043;font-size:16px;margin-bottom:5px;font-weight:bold}
.p-stock{color:#8b949e;font-size:12px;margin-bottom:10px}
.p-btn{margin-top:auto;display:block;text-align:center}
.oos-badge{position:absolute;top:10px;right:10px;background:#da3633;color:#fff;padding:4px 8px;border-radius:4px;font-size:12px;font-weight:bold}
table{width:100%;border-collapse:collapse;margin-top:10px}
th,td{text-align:left;padding:10px;border-bottom:1px solid #30363d}
.status-pending{color:#f0b429;font-weight:bold}
.status-approved{color:#2ea043;font-weight:bold}

/* Tabs */
.tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
.tab-btn { background: #161b22; color: #8b949e; border: 1px solid #30363d; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; }
.tab-btn.active { background: #2ea043; color: #fff; border-color: #2ea043; }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* Floating Widgets */
.widgets { position: fixed; bottom: 30px; right: 30px; display: flex; flex-direction: column; gap: 15px; z-index: 100; align-items: flex-end; }
.widget-btn { background: #2ea043; color: white; border-radius: 50px; padding: 12px 20px; font-weight: bold; font-size: 15px; border: none; cursor: pointer; box-shadow: 0 4px 15px rgba(46, 160, 67, 0.4); display: flex; align-items: center; gap: 8px; transition: 0.3s; }
.widget-btn:hover { background: #3fb950; transform: translateY(-3px); }
.widget-btn.chat { background: #1f6feb; }
.widget-btn.chat:hover { background: #388bfd; }

/* Chat Window */
.chat-window { display: none; width: 320px; height: 400px; background: #161b22; border: 1px solid #30363d; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom: 15px; flex-direction: column; overflow: hidden; }
.chat-header { background: #1f6feb; color: white; padding: 15px; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
.chat-messages { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.msg-bubble { max-width: 80%; padding: 8px 12px; border-radius: 12px; font-size: 14px; line-height: 1.4; }
.msg-user { align-self: flex-end; background: #1f6feb; color: white; border-bottom-right-radius: 2px; }
.msg-admin { align-self: flex-start; background: #30363d; color: #c9d1d9; border-bottom-left-radius: 2px; }
.chat-input { display: flex; padding: 10px; border-top: 1px solid #30363d; background: #0d1117; }
.chat-input input { margin: 0; border-radius: 20px 0 0 20px; border-right: none; }
.chat-input button { border-radius: 0 20px 20px 0; padding: 10px 15px; }

/* Modal */
.modal { display: none; position: fixed; z-index: 200; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); align-items: center; justify-content: center; }
.modal-content { background: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; width: 90%; max-width: 400px; position: relative; }
.close-btn { position: absolute; top: 15px; right: 20px; color: #8b949e; font-size: 24px; cursor: pointer; font-weight: bold; }

/* Compact Payment Box */
.compact-pay-box { background:#0d1117; border:1px solid #30363d; padding:15px; border-radius:6px; margin-bottom:15px; display:none; font-size:14px; text-align:center; }
.compact-pay-box img { max-width: 100%; max-height: 200px; object-fit: contain; display: block; margin: 0 auto 10px auto; border-radius: 6px; }

/* Login Footer */
.login-footer { display: flex; flex-direction: column; gap: 15px; align-items: center; width: 100%; max-width: 350px; }
.login-footer a { display: flex; align-items: center; gap: 10px; color: #c9d1d9; font-size: 15px; transition: 0.2s; }
.login-footer a:hover { color: #2ea043; }
.login-footer svg { width: 24px; height: 24px; }
</style>
"""

WIDGETS_HTML = """
<div class="widgets">
  <div class="chat-window" id="chatWindow">
    <div class="chat-header">
      <span>AXEL Seller Support</span>
      <span style="cursor:pointer;" onclick="toggleChat()">✖</span>
    </div>
    <div class="chat-messages" id="chatMessages"></div>
    <div class="chat-input">
      <input type="text" id="chatInput" placeholder="Type..." onkeypress="handleEnter(event)">
      <button onclick="sendMessage()">Send</button>
    </div>
  </div>
  
  {% if role == 'user' %}
  <button class="widget-btn chat" onclick="toggleChat()">💬 Chat Seller</button>
  {% endif %}
  
  <button class="widget-btn" onclick="document.getElementById('feedbackModal').style.display='flex'">💬 Customer Service</button>
</div>

<div id="feedbackModal" class="modal">
  <div class="modal-content">
    <span class="close-btn" onclick="document.getElementById('feedbackModal').style.display='none'">&times;</span>
    <h3 style="margin-top:0;color:#2ea043;">Customer Service</h3>
    <form method="POST" action="/submit_feedback" enctype="multipart/form-data">
      <label>Message</label>
      <textarea name="message" rows="3" required></textarea>
      <label>Upload Picture (Optional)</label>
      <input type="file" name="image" accept="image/*" style="padding:8px">
      <button type="submit" style="width:100%">Send Feedback</button>
    </form>
  </div>
</div>

<script>
  let chatOpen = false;
  const chatWindow = document.getElementById('chatWindow');
  const chatMessages = document.getElementById('chatMessages');
  const chatInput = document.getElementById('chatInput');

  function toggleChat() {
    chatOpen = !chatOpen;
    chatWindow.style.display = chatOpen ? 'flex' : 'none';
    if (chatOpen) { fetchMessages(); chatInput.focus(); }
  }
  function handleEnter(e) { if (e.key === 'Enter') sendMessage(); }
  function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = '';
    appendMessage({ is_admin: 0, text: text, date: 'Sending...' });
    fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text }) }).then(() => fetchMessages());
  }
  function appendMessage(msg) {
    const div = document.createElement('div');
    div.className = 'msg-bubble ' + (msg.is_admin ? 'msg-admin' : 'msg-user');
    div.innerHTML = `<div>${msg.text}</div><div style="font-size:10px;opacity:0.7;margin-top:4px;">${msg.date || ''}</div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
  function fetchMessages() {
    fetch('/api/chat').then(r => r.json()).then(data => {
      chatMessages.innerHTML = '';
      data.forEach(appendMessage);
    });
  }
  setInterval(() => { if (chatOpen) fetchMessages(); }, 5000);
</script>
"""

HEADER_HTML = """
<div class="header">
  <div class="brand-title">AXEL<span>MARKETPLACE</span></div>
  <div>
    {% if user %}
      {% if role == 'user' %}<a href="/profile" style="margin-right:15px">My Profile</a>{% endif %}
      <a href="/logout" class="logout">Logout</a>
    {% endif %}
  </div>
</div>
"""

FOOTER_HTML = """
<div class="card login-footer">
  <a href="https://t.me/MercyNot1" target="_blank">
    <svg viewBox="0 0 24 24" fill="#2AABEE"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
    Telegram: @MercyNot1
  </a>
  <a href="https://www.facebook.com/profile.php?id=61590616438438" target="_blank">
    <svg viewBox="0 0 24 24" fill="#1877F2"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.469h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.469h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
    Facebook: Axel Pinakapogingbmseller
  </a>
</div>
"""

LOGIN_HTML = BASE_CSS + """
<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;min-height:80vh;position:relative;z-index:1;gap:20px">
  <div class="card" style="width:350px;text-align:center">
    <div class="brand-title" style="justify-content:center;margin-bottom:20px">AXEL<span>MARKETPLACE</span></div>
    {% if error %}<p style="color:#f85149">{{ error }}</p>{% endif %}
    <form method="POST">
      <input type="text" name="user" placeholder="Username" required>
      <input type="password" name="pass" placeholder="Password" required>
      <button type="submit" style="width:100%">Sign In</button>
    </form>
    <p style="margin-top:15px"><a href="/register">Create an account</a></p>
  </div>
  """ + FOOTER_HTML + """
</div>
"""

REGISTER_HTML = BASE_CSS + """
<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;min-height:80vh;position:relative;z-index:1;gap:20px">
  <div class="card" style="width:350px;text-align:center">
    <div class="brand-title" style="justify-content:center;margin-bottom:20px">AXEL<span>MARKETPLACE</span></div>
    <h3>Register</h3>
    {% if error %}<p style="color:#f85149">{{ error }}</p>{% endif %}
    <form method="POST">
      <input type="text" name="user" placeholder="Username" required>
      <input type="password" name="pass" placeholder="Password" required>
      <button type="submit" style="width:100%">Sign Up</button>
    </form>
    <p style="margin-top:15px"><a href="/">Already have an account? Login</a></p>
  </div>
  """ + FOOTER_HTML + """
</div>
"""

USER_STORE = BASE_CSS + WIDGETS_HTML + """
<div class="container">
  """ + HEADER_HTML + """
  <div class="grid">
    {% for p in products %}
    <div class="p-card">
      {% if p['stock'] <= 0 %}
      <div class="oos-badge">OUT OF STOCK</div>
      {% endif %}
      <img src="{{ p['image'] or 'https://via.placeholder.com/300x150?text=No+Image' }}">
      <div class="p-info">
        <div class="p-title">{{ p['title'] }}</div>
        <div class="p-price">₱{{ "%.2f"|format(p['price']) }}</div>
        <div class="p-stock">{{ p['stock'] }} in stock</div>
        {% if p['stock'] > 0 %}
        <a href="/product/{{ p['id'] }}" class="p-btn" style="color:#fff;background:#2ea043;padding:10px;border-radius:6px;text-decoration:none">View Details</a>
        {% else %}
        <button disabled style="width:100%">Out of Stock</button>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  </div>
</div>
"""

USER_PRODUCT = BASE_CSS + WIDGETS_HTML + """
<div class="container">
  """ + HEADER_HTML + """
  <div class="card" style="display:flex;gap:20px;flex-wrap:wrap">
    <img src="{{ p['image'] or 'https://via.placeholder.com/300x300?text=No+Image' }}" style="flex:1;min-width:250px;max-width:400px;object-fit:cover;border-radius:8px">
    <div style="flex:1;min-width:250px">
      <h1 style="margin-top:0">{{ p['title'] }}</h1>
      <h2 style="color:#2ea043;margin-bottom:5px">₱{{ "%.2f"|format(p['price']) }}</h2>
      <div style="color:#8b949e;margin-bottom:20px">{{ p['stock'] }} in stock</div>
      <p style="color:#c9d1d9;line-height:1.6">{{ p['description'] }}</p>
      <hr style="border-color:#30363d;margin:20px 0">
      {% if p['stock'] > 0 %}
      <form method="GET" action="/checkout/{{ p['id'] }}">
        <button type="submit" style="width:100%;margin-top:10px">Buy Now</button>
      </form>
      {% else %}
      <button disabled style="width:100%">Out of Stock</button>
      {% endif %}
    </div>
  </div>
</div>
"""

CHECKOUT_PAGE = BASE_CSS + WIDGETS_HTML + """
<div class="container">
  """ + HEADER_HTML + """
  <div class="card" style="max-width:500px; margin: 0 auto;">
    <h2 style="font-size:20px;">Checkout: {{ p['title'] }}</h2>
    <h3 style="color:#2ea043;font-size:18px;margin-bottom:15px;">₱{{ "%.2f"|format(p['price']) }}</h3>
    
    <form method="POST" enctype="multipart/form-data">
      <label style="font-size:14px;">Select Payment Method</label>
      <select name="method" id="payMethod" required onchange="updateDetails()" style="padding:8px;font-size:14px;margin-bottom:10px;">
        {% for m in allowed_methods %}
        <option value="{{ m }}">{{ m }}</option>
        {% endfor %}
      </select>
      
      <div id="payDetailsBox" class="compact-pay-box">
        <div id="payDetailsContent"></div>
      </div>
      
      <label style="font-size:14px;">Emergency Contact (Email/Telegram)</label>
      <input type="text" name="emergency_contact" placeholder="Backup contact" required style="padding:8px;font-size:14px;">
      
      <label style="font-size:14px;">Upload Payment Receipt</label>
      <input type="file" name="receipt" accept="image/*" required style="padding:6px;font-size:14px;">
      
      <button type="submit" style="width:100%;margin-top:10px;padding:10px;font-size:14px;">Submit Payment</button>
    </form>
  </div>
</div>
<script>
  const details = {{ pay_details|tojson|safe }};
  const payType = "{{ p['payment_type'] }}";

  function updateDetails() {
    const method = document.getElementById('payMethod').value;
    const box = document.getElementById('payDetailsBox');
    const content = document.getElementById('payDetailsContent');
    
    if (details && details[method]) {
      box.style.display = 'block';
      if (payType === 'QR') {
        content.innerHTML = `
          <img src="${details[method]}">
          <a href="${details[method]}" download="payment_qr.png" style="display:inline-block; background:#30363d; color:#fff; padding:5px 10px; border-radius:4px; font-size:12px; text-decoration:none; margin-top:5px;">💾 Save QR Image</a>
        `;
      } else {
        content.innerHTML = `<div style="color:#c9d1d9;font-weight:bold;text-align:center;white-space:pre-wrap;">${details[method]}</div>`;
      }
    } else {
      box.style.display = 'none';
    }
  }
  updateDetails();
</script>
"""

USER_PROFILE = BASE_CSS + WIDGETS_HTML + """
<div class="container">
  """ + HEADER_HTML + """
  <div class="card">
    <h2>Profile: {{ user }}</h2>
    <div style="display:flex;gap:40px;margin-top:20px">
      <div><div style="color:#8b949e;font-size:14px">Total Orders</div><div style="font-size:24px;font-weight:bold">{{ total_orders }}</div></div>
      <div><div style="color:#8b949e;font-size:14px">Total Spent</div><div style="font-size:24px;font-weight:bold;color:#2ea043">₱{{ "%.2f"|format(total_spent) }}</div></div>
    </div>
  </div>
  <div class="card">
    <h3>Order History</h3>
    {% if orders %}
    <table>
      <tr><th>Date</th><th>Item</th><th>Amount</th><th>Method</th><th>Status</th></tr>
      {% for o in orders %}
      <tr>
        <td style="color:#8b949e">{{ o['date'] }}</td>
        <td>{{ o['title'] }}</td>
        <td style="color:#2ea043">₱{{ "%.2f"|format(o['amount']) }}</td>
        <td>{{ o['method'] }}</td>
        <td class="status-{{ o['status']|lower }}">{{ o['status'] }}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <p style="color:#8b949e">You haven't bought anything yet. <a href="/store" style="color:#2ea043">Go to Store</a></p>
    {% endif %}
  </div>
</div>
"""

ADMIN_DASH = BASE_CSS + """
<div class="container">
  """ + HEADER_HTML + """
  
  <div class="tabs">
    <button class="tab-btn active" onclick="showTab('tab-orders')">Orders</button>
    <button class="tab-btn" onclick="showTab('tab-products')">Products</button>
    <button class="tab-btn" onclick="showTab('tab-chats')">Live Chats</button>
    <button class="tab-btn" onclick="showTab('tab-feedback')">Feedback</button>
  </div>

  <!-- ORDERS TAB -->
  <div id="tab-orders" class="tab-content active">
    <div class="card">
      <h3>Recent Orders</h3>
      <table>
        <tr><th>Date</th><th>User</th><th>Item</th><th>Emergency Contact</th><th>Receipt</th><th>Status</th><th>Action</th></tr>
        {% for s in sales %}
        <tr>
          <td style="color:#8b949e">{{ s['date'] }}</td>
          <td>{{ s['username'] }}</td>
          <td>{{ s['title'] }}</td>
          <td>{{ s['emergency_contact'] }}</td>
          <td>
            {% if s['receipt'] %}<a href="{{ s['receipt'] }}" target="_blank" style="color:#2ea043">View Receipt</a>{% else %}<span style="color:#8b949e">None</span>{% endif %}
          </td>
          <td class="status-{{ s['status']|lower }}">{{ s['status'] }}</td>
          <td>
            {% if s['status'] == 'Pending' %}<a href="/admin/approve/{{ s['id'] }}"><button style="padding:5px 10px;font-size:12px;background:#2ea043">Approve</button></a>{% else %}<span style="color:#8b949e">Done</span>{% endif %}
          </td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </div>

  <!-- PRODUCTS TAB -->
  <div id="tab-products" class="tab-content">
    <div class="card">
      <h3>Add New Product</h3>
      <form method="POST" action="/admin/add" enctype="multipart/form-data">
        <input type="text" name="title" placeholder="Product Title" required>
        <textarea name="desc" rows="3" placeholder="Product Description" required></textarea>
        <input type="number" step="0.01" name="price" placeholder="Price (e.g. 499.00)" required>
        <input type="number" name="stock" placeholder="Stock Quantity (e.g. 10)" required>
        <label>Upload Image (JPG/PNG):</label>
        <input type="file" name="image" accept="image/*" style="padding:8px">
        
        <label>Payment Type</label>
        <select name="payment_type" id="addPaymentType" onchange="togglePaymentInput()">
          <option value="Number">Number / Text</option>
          <option value="QR">QR Code Image</option>
        </select>

        <div id="addDetailsContainer">
          <label>Payment Methods & Details (One per line: Method=Details)</label>
          <textarea name="payment_details_str" id="addDetailsInput" rows="4" placeholder="GCash=09123456789\nPayPal=paypal@email.com" required></textarea>
        </div>
        
        <div id="addQrContainer" style="display:none;">
          <label>Upload QR Code Image:</label>
          <input type="file" name="qr_image" id="addQrInput" accept="image/*" style="padding:8px">
        </div>

        <button type="submit">Create Product</button>
      </form>
    </div>
    <div class="card">
      <h3>Your Products</h3>
      <table>
        <tr><th>Image</th><th>ID</th><th>Title</th><th>Price</th><th>Stock</th><th>Actions</th></tr>
        {% for p in products %}
        <tr>
          <td><img src="{{ p['image'] or 'https://via.placeholder.com/50' }}" style="width:50px;height:50px;object-fit:cover;border-radius:4px"></td>
          <td>{{ p['id'] }}</td>
          <td>{{ p['title'] }}</td>
          <td style="color:#2ea043">₱{{ "%.2f"|format(p['price']) }}</td>
          <td style="color:{% if p['stock'] <= 0 %}#f85149{% else %}#2ea043{% endif %}">{{ p['stock'] }}</td>
          <td>
            <a href="/admin/edit/{{ p['id'] }}"><button style="padding:5px 10px;font-size:12px">Edit</button></a>
            <a href="/admin/delete/{{ p['id'] }}" onclick="return confirm('Delete?')"><button class="danger" style="padding:5px 10px;font-size:12px">Delete</button></a>
          </td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </div>

  <!-- CHATS TAB -->
  <div id="tab-chats" class="tab-content">
    <div class="card">
      <h3>Live Chats</h3>
      <input type="text" id="userSearch" onkeyup="filterUsers()" placeholder="Search username..." style="margin-bottom:15px;">
      <table id="userTable">
        <tr><th>User</th><th>Last Message</th><th>Action</th></tr>
        {% for c in chats %}
        <tr class="user-row">
          <td class="username">{{ c['username'] }}</td>
          <td>{{ c['last_msg'] or 'No messages yet' }}</td>
          <td><button onclick="openAdminChat({{ c['user_id'] }}, '{{ c['username'] }}')" style="padding:5px 10px;font-size:12px">Chat</button></td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </div>

  <!-- FEEDBACK TAB -->
  <div id="tab-feedback" class="tab-content">
    <div class="card">
      <h3>Customer Feedback</h3>
      <table>
        <tr><th>Date</th><th>User</th><th>Message</th><th>Image</th></tr>
        {% for f in feedbacks %}
        <tr>
          <td style="color:#8b949e">{{ f['date'] }}</td>
          <td>{{ f['username'] or 'Guest' }}</td>
          <td>{{ f['message'] }}</td>
          <td>
            {% if f['image'] %}
            <a href="{{ f['image'] }}" target="_blank" style="color:#2ea043">View Image</a>
            {% else %}
            <span style="color:#8b949e">None</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </div>

</div>

<!-- Admin Chat Modal -->
<div id="adminChatModal" class="modal">
  <div class="modal-content">
    <span class="close-btn" onclick="document.getElementById('adminChatModal').style.display='none'">&times;</span>
    <h3 id="chatTitle" style="margin-top:0">Chat</h3>
    <div id="adminChatMessages" style="height: 300px; overflow-y: auto; background:#0d1117; padding:10px; border-radius:6px; border:1px solid #30363d; display:flex; flex-direction:column; gap:10px;"></div>
    <div style="display:flex; margin-top:10px;">
      <input type="text" id="adminChatInput" style="margin:0; border-radius:6px 0 0 6px;" placeholder="Type reply...">
      <button onclick="sendAdminMsg()" style="border-radius:0 6px 6px 0;">Send</button>
    </div>
  </div>
</div>

<script>
  function showTab(id) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    event.target.classList.add('active');
  }

  function togglePaymentInput() {
    const type = document.getElementById('addPaymentType').value;
    if (type === 'QR') {
      document.getElementById('addDetailsContainer').style.display = 'none';
      document.getElementById('addDetailsInput').removeAttribute('required');
      document.getElementById('addQrContainer').style.display = 'block';
      document.getElementById('addQrInput').setAttribute('required', 'required');
    } else {
      document.getElementById('addDetailsContainer').style.display = 'block';
      document.getElementById('addDetailsInput').setAttribute('required', 'required');
      document.getElementById('addQrContainer').style.display = 'none';
      document.getElementById('addQrInput').removeAttribute('required');
    }
  }

  function filterUsers() {
    const input = document.getElementById('userSearch');
    const filter = input.value.toLowerCase();
    const table = document.getElementById('userTable');
    const rows = table.getElementsByClassName('user-row');

    for (let i = 0; i < rows.length; i++) {
      const td = rows[i].getElementsByClassName('username')[0];
      const txtValue = td.textContent || td.innerText;
      if (txtValue.toLowerCase().indexOf(filter) > -1) {
        rows[i].style.display = "";
      } else {
        rows[i].style.display = "none";
      }
    }
  }

  let currentChatUserId = null;
  function openAdminChat(uid, name) {
    currentChatUserId = uid;
    document.getElementById('chatTitle').innerText = 'Chat with ' + name;
    document.getElementById('adminChatModal').style.display = 'flex';
    fetchAdminMsgs();
  }
  function fetchAdminMsgs() {
    if (!currentChatUserId) return;
    fetch('/api/admin/chat/' + currentChatUserId).then(r => r.json()).then(data => {
      const box = document.getElementById('adminChatMessages');
      box.innerHTML = '';
      data.forEach(m => {
        const d = document.createElement('div');
        d.className = 'msg-bubble ' + (m.is_admin ? 'msg-admin' : 'msg-user');
        d.innerHTML = `<div>${m.text}</div><div style="font-size:10px;opacity:0.7;">${m.date}</div>`;
        box.appendChild(d);
      });
      box.scrollTop = box.scrollHeight;
    });
  }
  function sendAdminMsg() {
    const inp = document.getElementById('adminChatInput');
    if (!inp.value.trim() || !currentChatUserId) return;
    fetch('/api/admin/chat/' + currentChatUserId, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: inp.value }) }).then(() => { inp.value = ''; fetchAdminMsgs(); });
  }
  setInterval(() => { if (currentChatUserId && document.getElementById('adminChatModal').style.display === 'flex') fetchAdminMsgs(); }, 5000);
</script>
"""

ADMIN_EDIT = BASE_CSS + """
<div class="container">
  """ + HEADER_HTML + """
  <div class="card">
    <h3>Edit Product: {{ p['title'] }}</h3>
    <form method="POST" enctype="multipart/form-data">
      <input type="text" name="title" value="{{ p['title'] }}" required>
      <textarea name="desc" rows="4" required>{{ p['description'] }}</textarea>
      <input type="number" step="0.01" name="price" value="{{ p['price'] }}" required>
      <input type="number" name="stock" value="{{ p['stock'] }}" required>
      {% if p['image'] %}<img src="{{ p['image'] }}" style="width:100px;border-radius:6px;display:block;margin-bottom:10px">{% endif %}
      <label>Change Image:</label>
      <input type="file" name="image" accept="image/*" style="padding:8px">
      
      <label>Payment Type</label>
      <select name="payment_type" id="editPaymentType" onchange="toggleEditPaymentInput()">
        <option value="Number" {% if p['payment_type'] == 'Number' %}selected{% endif %}>Number / Text</option>
        <option value="QR" {% if p['payment_type'] == 'QR' %}selected{% endif %}>QR Code Image</option>
      </select>

      <div id="editDetailsContainer" style="{% if p['payment_type'] == 'QR' %}display:none;{% endif %}">
        <label>Payment Methods & Details (One per line)</label>
        <textarea name="payment_details_str" id="editDetailsInput" rows="4">{{ payment_details_str }}</textarea>
      </div>
      
      <div id="editQrContainer" style="{% if p['payment_type'] == 'Number' %}display:none;{% endif %}">
        <label>Upload New QR Code (Leave blank to keep current):</label>
        <input type="file" name="qr_image" id="editQrInput" accept="image/*" style="padding:8px">
        {% if p['payment_type'] == 'QR' and p['payment_details'] %}
          <p style="color:#8b949e;font-size:12px;margin-top:5px;">Current QR image is saved.</p>
        {% endif %}
      </div>

      <button type="submit" style="margin-top:20px;">Save Changes</button>
    </form>
  </div>
</div>

<script>
  function toggleEditPaymentInput() {
    const type = document.getElementById('editPaymentType').value;
    if (type === 'QR') {
      document.getElementById('editDetailsContainer').style.display = 'none';
      document.getElementById('editQrContainer').style.display = 'block';
    } else {
      document.getElementById('editDetailsContainer').style.display = 'block';
      document.getElementById('editQrContainer').style.display = 'none';
    }
  }
</script>
"""

# ─── ROUTES ───

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect("/admin" if session.get("role") == "admin" else "/store")
    err = None
    if request.method == "POST":
        u, p = request.form.get("user"), request.form.get("pass")
        c = db()
        user = c.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        c.close()
        if user and user["password"] == hashlib.sha256(p.encode()).hexdigest():
            session["user"] = user["username"]
            session["role"] = user["role"]
            session["uid"] = user["id"]
            return redirect("/admin" if user["role"] == "admin" else "/store")
        err = "Invalid credentials"
    return render_template_string(LOGIN_HTML, error=err)

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user"):
        return redirect("/store")
    err = None
    if request.method == "POST":
        u, p = request.form.get("user"), request.form.get("pass")
        if not u or not p:
            err = "Fill all fields"
        else:
            c = db()
            try:
                c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                          (u, hashlib.sha256(p.encode()).hexdigest(), "user"))
                c.commit()
                c.close()
                return redirect("/")
            except sqlite3.IntegrityError:
                c.close()
                err = "Username already taken"
    return render_template_string(REGISTER_HTML, error=err)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    message = request.form.get("message")
    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"fb_{int(datetime.datetime.now().timestamp())}_{filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            image_path = f"/static/uploads/{filename}"

    if message:
        c = db()
        c.execute("INSERT INTO feedback (user_id, message, image, date) VALUES (?, ?, ?, ?)",
                  (session.get("uid", 0), message, image_path, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
        c.commit()
        c.close()
        send_tg_alert(f"📩 *New Feedback!*\nFrom: {session.get('user','Guest')}\nMessage: {message}")
    return "<script>alert('Feedback sent!');window.location='/store';</script>"

@app.route("/api/chat", methods=["GET", "POST"])
def chat():
    if not session.get("user"): return jsonify({"error": "unauthorized"}), 401
    uid = session["uid"]
    c = db()
    if request.method == "POST":
        data = request.get_json()
        text = data.get("text", "").strip()
        if text:
            c.execute("INSERT INTO messages (user_id, is_admin, text, date) VALUES (?, 0, ?, ?)",
                      (uid, text, datetime.datetime.now().strftime("%H:%M")))
            c.commit()
            send_tg_alert(f"💬 *New Chat from {session['user']}*\n{text}")
        c.close()
        return jsonify({"ok": True})
    msgs = c.execute("SELECT * FROM messages WHERE user_id=? ORDER BY id ASC", (uid,)).fetchall()
    c.close()
    return jsonify([dict(m) for m in msgs])

@app.route("/api/admin/chat/<int:uid>", methods=["GET", "POST"])
def admin_chat(uid):
    if not session.get("user") or session.get("role") != "admin": return jsonify({"error": "unauthorized"}), 401
    c = db()
    if request.method == "POST":
        data = request.get_json()
        text = data.get("text", "").strip()
        if text:
            c.execute("INSERT INTO messages (user_id, is_admin, text, date) VALUES (?, 1, ?, ?)",
                      (uid, text, datetime.datetime.now().strftime("%H:%M")))
            c.commit()
        c.close()
        return jsonify({"ok": True})
    msgs = c.execute("SELECT * FROM messages WHERE user_id=? ORDER BY id ASC", (uid,)).fetchall()
    c.close()
    return jsonify([dict(m) for m in msgs])

@app.route("/store")
def store():
    if not session.get("user") or session.get("role") != "user": return redirect("/")
    c = db()
    products = c.execute("SELECT * FROM products").fetchall()
    c.close()
    return render_template_string(USER_STORE, user=session["user"], role=session["role"], products=products)

@app.route("/profile")
def profile():
    if not session.get("user") or session.get("role") != "user": return redirect("/")
    c = db()
    orders = c.execute("""
        SELECT s.*, p.title 
        FROM sales s 
        JOIN products p ON s.product_id = p.id 
        WHERE s.user_id = ?
        ORDER BY s.id DESC
    """, (session["uid"],)).fetchall()
    total_spent = sum(o["amount"] for o in orders if o["status"] == "Approved")
    total_orders = len(orders)
    c.close()
    return render_template_string(USER_PROFILE, user=session["user"], role=session["role"], orders=orders, total_spent=total_spent, total_orders=total_orders)

@app.route("/product/<int:pid>")
def product_detail(pid):
    if not session.get("user") or session.get("role") != "user": return redirect("/")
    c = db()
    p = c.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    c.close()
    if not p: return "Product not found", 404
    allowed_methods = json.loads(p["payments"]) if p["payments"] else []
    return render_template_string(USER_PRODUCT, user=session["user"], role=session["role"], p=p, allowed_methods=allowed_methods)

@app.route("/checkout/<int:pid>", methods=["GET", "POST"])
def checkout(pid):
    if not session.get("user") or session.get("role") != "user": return redirect("/")
    c = db()
    p = c.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p or p["stock"] <= 0:
        c.close()
        return redirect("/store")
    if request.method == "POST":
        method = request.form.get("method")
        emergency_contact = request.form.get("emergency_contact")
        receipt_path = None
        if 'receipt' in request.files:
            file = request.files['receipt']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"receipt_{int(datetime.datetime.now().timestamp())}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                receipt_path = f"/static/uploads/{filename}"
        if not receipt_path or not emergency_contact:
            return "All fields are required", 400
        c.execute("UPDATE products SET stock = stock - 1 WHERE id=?", (pid,))
        c.execute("""INSERT INTO sales (user_id, product_id, amount, method, date, status, receipt, emergency_contact) 
                     VALUES (?, ?, ?, ?, ?, 'Pending', ?, ?)""",
                  (session["uid"], pid, p["price"], method, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), receipt_path, emergency_contact))
        c.commit()
        c.close()
        msg = f"💰 *New Payment Uploaded!*\n\nUser: {session['user']}\nItem: {p['title']}\nMethod: {method}\nEmergency: {emergency_contact}\nCheck admin dashboard."
        send_tg_alert(msg)
        return "<script>alert('Order submitted! Please wait for admin approval.');window.location='/profile';</script>"
    allowed_methods = json.loads(p["payments"]) if p["payments"] else []
    pay_details = json.loads(p["payment_details"]) if p["payment_details"] else {}
    c.close()
    return render_template_string(CHECKOUT_PAGE, user=session["user"], role=session["role"], p=p, allowed_methods=allowed_methods, pay_details=pay_details)

@app.route("/admin")
def admin():
    if not session.get("user") or session.get("role") != "admin": return redirect("/")
    c = db()
    products = c.execute("SELECT * FROM products").fetchall()
    sales = c.execute("""
        SELECT s.*, u.username, p.title 
        FROM sales s 
        JOIN users u ON s.user_id = u.id 
        JOIN products p ON s.product_id = p.id
        ORDER BY s.id DESC
    """).fetchall()
    feedbacks = c.execute("""
        SELECT f.*, u.username 
        FROM feedback f 
        LEFT JOIN users u ON f.user_id = u.id 
        ORDER BY f.id DESC
    """).fetchall()
    
    # Get all users for the chat list
    chats = c.execute("""
        SELECT u.id as user_id, u.username, m.text as last_msg 
        FROM users u 
        LEFT JOIN messages m ON m.id = (SELECT MAX(id) FROM messages WHERE user_id = u.id)
        WHERE u.role = 'user'
        ORDER BY m.id DESC
    """).fetchall()
    
    c.close()
    return render_template_string(ADMIN_DASH, user=session["user"], role=session["role"], products=products, sales=sales, feedbacks=feedbacks, chats=chats)

@app.route("/admin/approve/<int:sid>")
def admin_approve(sid):
    if not session.get("user") or session.get("role") != "admin": return redirect("/")
    c = db()
    c.execute("UPDATE sales SET status = 'Approved' WHERE id = ?", (sid,))
    c.commit()
    c.close()
    return redirect("/admin")

@app.route("/admin/add", methods=["POST"])
def admin_add():
    if not session.get("user") or session.get("role") != "admin": return redirect("/")
    title = request.form.get("title")
    desc = request.form.get("desc")
    price = float(request.form.get("price"))
    stock = int(request.form.get("stock", 0))
    payment_details_str = request.form.get("payment_details_str")
    p_type = request.form.get("payment_type", "Number")
    
    details = {}
    if p_type == "QR":
        if 'qr_image' in request.files:
            file = request.files['qr_image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"qr_{int(datetime.datetime.now().timestamp())}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                details = {"QR": f"/static/uploads/{filename}"}
    else:
        for line in payment_details_str.split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                details[k.strip()] = v.strip()
                
    payments = list(details.keys())
    if not payments: payments = ["Credit Card"]
    
    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"{int(datetime.datetime.now().timestamp())}_{filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            image_path = f"/static/uploads/{filename}"
            
    c = db()
    c.execute("INSERT INTO products (title, description, price, payments, image, stock, payment_details, payment_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (title, desc, price, json.dumps(payments), image_path, stock, json.dumps(details), p_type))
    c.commit()
    c.close()
    return redirect("/admin")

@app.route("/admin/edit/<int:pid>", methods=["GET", "POST"])
def admin_edit(pid):
    if not session.get("user") or session.get("role") != "admin": return redirect("/")
    c = db()
    if request.method == "POST":
        title = request.form.get("title")
        desc = request.form.get("desc")
        price = float(request.form.get("price"))
        stock = int(request.form.get("stock", 0))
        payment_details_str = request.form.get("payment_details_str")
        p_type = request.form.get("payment_type", "Number")
        
        current_p = c.execute("SELECT image, payment_details FROM products WHERE id=?", (pid,)).fetchone()
        image_path = current_p["image"]
        old_details = json.loads(current_p["payment_details"]) if current_p["payment_details"] else {}
        
        details = {}
        if p_type == "QR":
            if 'qr_image' in request.files:
                file = request.files['qr_image']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    filename = f"qr_{int(datetime.datetime.now().timestamp())}_{filename}"
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(save_path)
                    details = {"QR": f"/static/uploads/{filename}"}
            if not details and old_details:
                details = old_details
        else:
            for line in payment_details_str.split("\n"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    details[k.strip()] = v.strip()
                    
        payments = list(details.keys())
        if not payments: payments = ["Credit Card"]
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"{int(datetime.datetime.now().timestamp())}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                image_path = f"/static/uploads/{filename}"
                
        c.execute("UPDATE products SET title=?, description=?, price=?, payments=?, image=?, stock=?, payment_details=?, payment_type=? WHERE id=?",
                  (title, desc, price, json.dumps(payments), image_path, stock, json.dumps(details), p_type, pid))
        c.commit()
        c.close()
        return redirect("/admin")
    
    p = c.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    c.close()
    if not p: return "Product not found", 404
    
    payment_details = json.loads(p["payment_details"]) if p["payment_details"] else {}
    payment_details_str = "\n".join(f"{k}={v}" for k, v in payment_details.items())
    
    return render_template_string(ADMIN_EDIT, user=session["user"], role=session["role"], p=p, payment_details_str=payment_details_str)

@app.route("/admin/delete/<int:pid>")
def admin_delete(pid):
    if not session.get("user") or session.get("role") != "admin": return redirect("/")
    c = db()
    c.execute("DELETE FROM products WHERE id=?", (pid,))
    c.commit()
    c.close()
    return redirect("/admin")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
