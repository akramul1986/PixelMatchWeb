from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from comparator import ImageComparator
import os

app = Flask(__name__)
app.secret_key = "portonics_secret_key_2026"

# 1. Define your Team Members here
# Key = Email, Value = Unique Password
USERS = {
    "admin@portonics.com": "PortonicsAdmin!99",
    "akramul.islam@portonics.com": "MySecretPass2026",
    "tester1@portonics.com": "QA_Verify_Safe1",
    "developer1@portonics.com": "Dev_Build_Fix_01"
}


@app.route('/')
def index():
    if 'user_email' in session:
        return render_template('index.html')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')

        # 2. Check if email exists in our dictionary AND password matches
        if email in USERS and USERS[email] == password:
            session['user_email'] = email
            return redirect(url_for('index'))
        else:
            error = "Invalid email or password. Please contact Admin."

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('login'))


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


if __name__ == '__main__':
    app.run(debug=True, port=5000)