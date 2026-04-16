import os
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from authlib.integrations.flask_client import OAuth
from comparator import ImageComparator  # Keeping your existing comparator

app = Flask(__name__)

# --- 1. SECURITY & CONFIG ---
# Use your existing secret key
app.secret_key = "portonics_secret_key_2026"

# REQUIRED for IP-based OAuth testing (allows http instead of https)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# 32MB Upload limit for high-res images
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024


# --- 2. SESSION IDLE TIMEOUT ---
@app.before_request
def manage_session():
    session.permanent = True
    # If the user is idle for 30 minutes, they are logged out
    app.permanent_session_lifetime = timedelta(minutes=30)


# --- 3. GOOGLE OAUTH SETUP ---
# NOTE: Replace the strings below with your real IDs from Google Console
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)


# --- 4. NAVIGATION & AUTH ROUTES ---

@app.route('/')
def index():
    if 'user_email' in session:
        return render_template('index.html', user_email=session['user_email'])
    return redirect(url_for('login'))


@app.route('/login')
def login():
    if 'user_email' in session:
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/auth/google')
def google_auth():
    # Force the logic to be precise
    host = request.host

    if "localhost" in host or "127.0.0.1" in host:
        # For Local MacBook testing
        redirect_uri = url_for('auth_callback', _external=True)
    else:
        # For Server testing (matching your nip.io setup)
        redirect_uri = "http://103.70.231.111.nip.io:8088/auth/callback"

    print(f"DEBUG: Sending Redirect URI to Google -> {redirect_uri}")
    return google.authorize_redirect(redirect_uri)


@app.route('/auth/callback')
def auth_callback():
    try:
        token = google.authorize_access_token()
        # Use OpenID Connect userinfo endpoint
        user_info = google.get('https://openidconnect.googleapis.com/v1/userinfo').json()

        # Security check: Ensure the email is from portonics.com
        if not user_info.get('email', '').endswith('@portonics.com'):
            session.clear()
            return "<h1>Access Denied</h1><p>Please use your Portonics email.</p>", 403

        session['user_email'] = user_info['email']
        session['user_name'] = user_info.get('name', 'Tester')

        return redirect(url_for('index'))
    except Exception as e:
        print(f"Auth Error: {e}")
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()  # Clears all session data including email and timeout
    return redirect(url_for('login'))


# --- 5. CORE FUNCTIONAL ROUTES ---

@app.route('/verify', methods=['POST'])
def verify():
    # Verification check to ensure user is logged in
    if 'user_email' not in session:
        return jsonify({"error": "Unauthorized. Please login."}), 401

    try:
        figma_file = request.files['figma']
        app_file = request.files['app']
        # Keeping your existing ImageComparator logic
        result = ImageComparator.compare(figma_file, app_file)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/guide')
def show_guide():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('guide.html')


if __name__ == '__main__':
    # host='0.0.0.0' allows external access on your server IP
    app.run(host='0.0.0.0', port=8088, debug=False)