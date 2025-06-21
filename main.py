from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask import Flask, render_template, request, redirect, url_for
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

def natural_key(text):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', text)]

submitted_data = []
created_classes = {}

@app.route("/")
def home():
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "teacher" and password == "pass":
            return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")
@app.route("/manage-data")
def manage_data():
    classes = sorted(created_classes.keys(), key=str.casefold)
    return render_template("managedata.html", classes=classes, current_page="manage-data")

@app.route("/manage-data/<classname>")
def class_view(classname):
    if classname not in created_classes:
        return "<h2>Class not found.</h2>", 404

    filtered = [entry for entry in submitted_data if entry["class"] == classname]
    classes = sorted(created_classes.keys(), key=str.casefold)
    return render_template("classdata.html", data=filtered, classname=classname, classes=classes, current_page="manage-data")

@app.route("/create-class", methods=["GET", "POST"])
def create_class():
    error = None

    if request.method == "POST":
        classname = request.form.get("classname").strip()
        password1 = request.form.get("password1")
        password2 = request.form.get("password2")

        if classname in created_classes:
            error = f"Class '{classname}' already exists."
        elif password1 != password2:
            error = "Passwords do not match."
        else:
            created_classes[classname] = password1
            return redirect(url_for("manage_data"))

    return render_template("createclass.html", error=error, current_page="create-class")

@app.route("/settings")
def settings():
    return render_template("settings.html", current_page="settings")

@app.route("/about")
def about():
    return render_template("about.html", current_page="about")

@app.route("/logout")
def logout():
    return redirect(url_for("login"))

@app.route("/submit", methods=["POST"])
def submit():
    try:
        data = request.get_json()
        print("Received data:", data)

        required_fields = {
            "name", "class", "minigame1", "minigame2", "minigame3", "minigame4"
        }
        if not data or not required_fields.issubset(data):
            return jsonify({"error": "Missing or invalid fields"}), 400

        submitted_data.append(data)
        return jsonify({"message": "Data received successfully."}), 200

    except Exception as e:
        print("Error in /submit route:", e)
        return jsonify({"error": "Server error"}), 500

if __name__ == "__main__":
    app.run(debug=True)