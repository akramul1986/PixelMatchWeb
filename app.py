import os
import io
import pandas as pd
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from authlib.integrations.flask_client import OAuth
from comparator import ImageComparator
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# --- 1. DOCKER & REVERSE PROXY CONFIG ---
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# --- 2. SECURITY & CONFIG ---
app.secret_key = "portonics_secret_key_2026"
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

# Fix for session consistency
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# --- 3. SESSION MANAGEMENT ---
@app.before_request
def manage_session():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=30)

    host = request.host
    if "uiverifier-qa" in host:
        app.config['SESSION_COOKIE_DOMAIN'] = 'uiverifier-qa.portonics.com'
    else:
        app.config['SESSION_COOKIE_DOMAIN'] = None


# --- 4. GOOGLE OAUTH SETUP ---
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)


# --- 5. NAVIGATION & AUTH ROUTES ---

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
    host = request.host
    if "localhost" in host or "127.0.0.1" in host:
        redirect_uri = "http://localhost:84/auth/callback" if ":84" in host else "http://localhost:8088/auth/callback"
    else:
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "https://uiverifier-qa.portonics.com/auth/callback")

    return google.authorize_redirect(redirect_uri)


@app.route('/auth/callback')
def auth_callback():
    try:
        token = google.authorize_access_token()
        user_info = google.get('https://openidconnect.googleapis.com/v1/userinfo').json()

        if not user_info.get('email', '').endswith('@portonics.com'):
            session.clear()
            return "<h1>Access Denied</h1><p>Please use your Portonics email.</p>", 403

        # CRITICAL FIX FOR DOUBLE AUTH:
        # Clear existing session, set data, and explicitly save before redirect
        session.clear()
        session.permanent = True
        session['user_email'] = user_info['email']
        session['user_name'] = user_info.get('name', 'Tester')
        session.modified = True

        return redirect(url_for('index'))
    except Exception as e:
        print(f"Auth Error: {e}")
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- 6. CORE LOGIC (UI VERIFIER) ---

@app.route('/verify', methods=['POST'])
def verify():
    if 'user_email' not in session:
        return jsonify({"error": "Unauthorized. Please login."}), 401

    try:
        figma_file = request.files['figma']
        app_file = request.files['app']
        result = ImageComparator.compare(figma_file, app_file)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- 7. TEST CASE REARRANGER LOGIC ---

@app.route('/testcases', methods=['GET', 'POST'])
def testcases_module():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or file.filename == '':
            return "No file selected", 400

        filename = file.filename.lower()
        column_mapping = {
            'Test Case ID': 'Test Case Id',
            'Title': 'Title',
            'Owner': 'Owner',
            'Description': 'Description',
            'Preconditions': 'Preconditions',
            'Steps': 'Steps',
            'Expected Result': 'Expected Result'
        }

        try:
            # Create a buffer from the uploaded file to avoid read errors
            file_stream = io.BytesIO(file.read())
            output = io.BytesIO()

            # --- CASE 1: MULTI-SHEET EXCEL (.xlsx) ---
            if filename.endswith('.xlsx'):
                # Use engine='openpyxl' for reading
                excel_data = pd.read_excel(file_stream, sheet_name=None, engine='openpyxl')

                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    for sheet_name, df in excel_data.items():
                        existing_cols = [col for col in column_mapping.keys() if col in df.columns]

                        if existing_cols:
                            processed_df = df[existing_cols].rename(columns=column_mapping)
                            processed_df.to_excel(writer, sheet_name=sheet_name, index=False)
                        else:
                            # If no columns match, keep the sheet as is or skip
                            df.to_excel(writer, sheet_name=sheet_name, index=False)

                output.seek(0)
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f"Cleaned_{file.filename}"
                )

            # --- CASE 2: SINGLE-SHEET CSV ---
            elif filename.endswith('.csv'):
                file_stream.seek(0)  # Reset stream for CSV read
                df = pd.read_csv(file_stream)
                existing_cols = [col for col in column_mapping.keys() if col in df.columns]
                processed_df = df[existing_cols].rename(columns=column_mapping)

                output_str = io.StringIO()
                processed_df.to_csv(output_str, index=False)

                output_bytes = io.BytesIO(output_str.getvalue().encode('utf-8'))
                return send_file(
                    output_bytes,
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=f"Cleaned_{file.filename}"
                )

            else:
                return "Unsupported file format. Please upload .csv or .xlsx", 400

        except Exception as e:
            return f"Processing Error: {str(e)}", 500

    return render_template('testcases.html')

@app.route('/guide')
def show_guide():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('guide.html')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8088))
    app.run(host='0.0.0.0', port=port, debug=True)