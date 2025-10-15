from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import re
import pandas as pd
from werkzeug.utils import secure_filename
import os

# ---------------- FLASK APP ----------------
app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["https://react-admin.gt.tc"])
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------- DATABASE CONNECTION ----------------
def get_db():
    return mysql.connector.connect(
        host="switchback.proxy.rlwy.net",
        port=14091,
        user="root",
        password="fROvVkrMziyiAauJkszNrldrBndCjvvI",
        database="railway"
    )

# ---------------- UTILITIES ----------------
def natural_key(text):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', text)]

submitted_data = []
created_classes = {}
registered_students = {}

# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect(url_for('login'))

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM teachers WHERE username=%s", (username,))
            teacher = cursor.fetchone()

            if teacher and teacher["password"] == password:
                session["teacher_id"] = teacher["id"]
                session["teacher_username"] = teacher["username"]
                session["teacher_name"] = teacher["fullname"]
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid username or password.", "error")

        except Error as e:
            flash(f"Database error: {e}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    return render_template("login.html", hide_sidebar=True)

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "teacher_id" not in session:
        return redirect(url_for("login"))
    return render_template(
        "dashboard.html",
        teacher_name=session.get("teacher_name"),
        current_page="dashboard"
    )

# ---------------- DATA REPORT ----------------
@app.route("/data-report")
def data_report():
    return render_template("datareport.html", current_page="data-report")

# ---------------- VIEW SCORES ----------------
@app.route("/manage-data")
def manage_data():
    if "teacher_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    with conn.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id, name FROM sections ORDER BY name")
        sections = cursor.fetchall()
    conn.close()

    return render_template("managedata.html", classes=sections, current_page="manage-data", classname=None)

# ---------------- VIEW CLASS DATA ----------------
@app.route("/manage-data/section/<int:section_id>")
def class_view(section_id):
    if "teacher_id" not in session:
        return redirect(url_for("login"))

    data = []
    classes = []
    classname = None

    try:
        conn = get_db()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT name FROM sections WHERE id = %s", (section_id,))
            section = cursor.fetchone()
            if section:
                classname = section.get("name")

            # Fetch students and scores
            try:
                cursor.execute("""
                    SELECT st.name AS student_name, s.name AS section_name,
                    sc.minigame1, sc.minigame2, sc.minigame3, sc.minigame4, sc.quiz
                    FROM students st
                    LEFT JOIN student_scores sc ON st.id = sc.student_id
                    JOIN sections s ON st.section_id = s.id
                    WHERE st.section_id = %s
                    ORDER BY st.name
                """, (section_id,))
                data = cursor.fetchall() or []
            except Exception as e:
                print("Error fetching student data:", e)
                data = []

            # Fetch all sections
            try:
                cursor.execute("SELECT id, name FROM sections ORDER BY name")
                classes = cursor.fetchall() or []
            except Exception as e:
                print("Error fetching sections:", e)
                classes = []

    except Exception as e:
        print("Database connection error:", e)

    finally:
        if conn.is_connected():
            conn.close()

    return render_template("classdata.html", data=data, classname=classname, classes=classes, current_page="manage-data")

# ---------------- STUDENTS CRUD ----------------
@app.route("/api/students", methods=["GET","POST"])
def students():
    if request.method == "GET":
        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, name, student_number, section_id FROM students ORDER BY name")
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify(result)
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

    if request.method == "POST":
        data = request.get_json()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO students (name, student_number, section_id, password) VALUES (%s,%s,%s,%s)",
                (data["name"], data["student_number"], data["section_id"], data["password"])
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

@app.route("/api/students/<int:student_id>", methods=["PUT","DELETE"])
def student_detail(student_id):
    if request.method == "PUT":
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON body provided"}), 400

        for field in ["name", "student_number", "section_id"]:
            if field not in data:
                return jsonify({"status": "error", "message": f"Missing field: {field}"}), 400

        try:
            conn = get_db()
            cursor = conn.cursor()

            query = "UPDATE students SET name=%s, student_number=%s, section_id=%s"
            params = [data["name"], data["student_number"], data["section_id"]]

            password = data.get("password")
            if password and password.strip():
                query += ", password=%s"
                params.append(password.strip())

            query += " WHERE id=%s"
            params.append(student_id)

            cursor.execute(query, params)
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status": "success"})

        except Error as e:
            return jsonify({"status": "error", "message": f"Database error: {e}"}), 500
        except Exception as e:
            return jsonify({"status": "error", "message": f"Unexpected error: {e}"}), 500

    if request.method == "DELETE":
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status": "success"})
        except Error as e:
            return jsonify({"status": "error", "message": str(e)}), 500

# ---------------- SECTIONS CRUD ----------------
@app.route("/api/sections", methods=["GET","POST"])
def sections():
    if request.method == "GET":
        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, name FROM sections ORDER BY name")
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify(result)
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

    if request.method == "POST":
        data = request.get_json()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sections (name) VALUES (%s)",
                (data["name"],)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

@app.route("/api/sections/<int:section_id>", methods=["PUT","DELETE"])
def sections_detail(section_id):
    if request.method == "PUT":
        data = request.get_json()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sections SET name=%s WHERE id=%s",
                (data["name"], section_id)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

    if request.method == "DELETE":
        try:
            conn = get_db()
            cursor = conn.cursor()
            # Delete all students in this section first
            cursor.execute("DELETE FROM students WHERE section_id=%s", (section_id,))
            # Then delete the section
            cursor.execute("DELETE FROM sections WHERE id=%s", (section_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

'''
@app.route("/api/sections/<int:section_id>", methods=["DELETE"])
def section_detail(section_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Delete students first (optional: cascade in DB)
        cursor.execute("DELETE FROM students WHERE section_id=%s", (section_id,))
        cursor.execute("DELETE FROM sections WHERE id=%s", (section_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status":"success"})
    except Error as e:
        return jsonify({"status":"error","message":str(e)}),500
'''

# ---------------- Submit game or quiz score ----------------
@app.route("/submit-score", methods=["POST"])
def submit_score():
    try:
        data = request.get_json()
        student_number = data.get("student_number")
        minigame1 = data.get("minigame1", 0)
        minigame2 = data.get("minigame2", 0)
        minigame3 = data.get("minigame3", 0)
        minigame4 = data.get("minigame4", 0)
        quiz = data.get("quiz", 0)

        if not student_number:
            return jsonify({"status": "error", "message": "Missing student number"}), 400

        conn = get_db()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id, section_id FROM students WHERE student_number=%s", (student_number,))
            student = cursor.fetchone()
            if not student:
                return jsonify({"status": "fail", "message": "Student not found"}), 404

            cursor.execute(
                "SELECT * FROM student_scores WHERE student_id=%s AND section_id=%s",
                (student["id"], student["section_id"])
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE student_scores
                    SET minigame1=%s, minigame2=%s, minigame3=%s, minigame4=%s, quiz=%s
                    WHERE student_id=%s AND section_id=%s
                """, (minigame1, minigame2, minigame3, minigame4, quiz, student["id"], student["section_id"]))
            else:
                cursor.execute("""
                    INSERT INTO student_scores (student_id, section_id, minigame1, minigame2, minigame3, minigame4, quiz)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (student["id"], student["section_id"], minigame1, minigame2, minigame3, minigame4, quiz))

            conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Scores updated."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------------- CREATE CLASS ----------------
@app.route("/create-class", methods=["GET", "POST"])
def create_class():
    error = None
    if request.method == "POST":
        classname = request.form.get("classname").strip()

        if not classname:
            error = "Section name cannot be empty."
            return render_template("createclass.html", error=error, current_page="create-class")

        try:
            conn = get_db()
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO sections (name) VALUES (%s)", (classname,))
                conn.commit()
            conn.close()
            return redirect("/create-class")

        except Exception as e:
            error = f"Database error: {str(e)}"
            return render_template("createclass.html", error=error, current_page="create-class")

    return render_template("createclass.html", error=error, current_page="create-class")

# ---------------- CREATE STUDENT ----------------
@app.route("/create-student", methods=["GET", "POST"])
def create_student():
    error = None
    conn = get_db()
    with conn.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id, name FROM sections ORDER BY name")
        sections = cursor.fetchall()

    if request.method == "POST":
        studname = request.form.get("studname").strip()
        studnum = request.form.get("studnum").strip()
        section_id = request.form.get("section")
        password1 = request.form.get("password1")
        password2 = request.form.get("password2")

        if password1 != password2:
            error = "Passwords do not match."
        else:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO students (name, student_number, section_id, password) VALUES (%s, %s, %s, %s)",
                    (studname, studnum, section_id, password1)
                )
                conn.commit()
            conn.close()
            return redirect(url_for("create_student"))

    conn.close()
    return render_template("createstudent.html", error=error, sections=sections, current_page="create-student")

# ---------------- UPLOAD STUDENTS ----------------
@app.route("/upload-students", methods=["POST"])
def upload_students():
    if "teacher_id" not in session:
        return redirect(url_for("login"))

    file = request.files.get("excel_file")
    if not file:
        flash("No file selected", "error")
        return redirect(url_for("create_student"))

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config.get("UPLOAD_FOLDER", "."), filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    try:
        df = pd.read_excel(filepath)
        headers = [h.lower() for h in df.columns]

        col_map = {}
        for key in ["student_number", "name", "section", "password"]:
            for i, h in enumerate(headers):
                if h == key.lower():
                    col_map[key] = i
                    break
            else:
                flash(f"Missing required column: {key}", "error")
                return redirect(url_for("create_student"))

        conn = get_db()
        with conn.cursor() as cursor:
            added_students = 0
            skipped_students = 0
            for _, row in df.iterrows():
                student_number = str(row[col_map["student_number"]]).strip()
                name = str(row[col_map["name"]]).strip()
                section_name = str(row[col_map["section"]]).strip()
                password = str(row[col_map["password"]]).strip()

                cursor.execute("SELECT id FROM sections WHERE name=%s", (section_name,))
                result = cursor.fetchone()
                if result:
                    section_id = result[0]
                else:
                    cursor.execute("INSERT INTO sections (name) VALUES (%s)", (section_name,))
                    conn.commit()
                    section_id = cursor.lastrowid

                cursor.execute("SELECT id FROM students WHERE student_number=%s", (student_number,))
                if cursor.fetchone():
                    skipped_students += 1
                    continue

                cursor.execute(
                    "INSERT INTO students (name, student_number, section_id, password) VALUES (%s, %s, %s, %s)",
                    (name, student_number, section_id, password)
                )
                added_students += 1

            conn.commit()
        conn.close()
        flash(f"{added_students} students added successfully! {skipped_students} duplicates skipped.", "success")

    except Exception as e:
        flash(f"Error processing Excel file: {e}", "error")

    return redirect(url_for("create_student"))

'''
# ----------------- FOR ADMIN ----------------
@app.route("/api/upload-students", methods=["POST"])
def api_upload_students():
    if "teacher_id" not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    file = request.files.get("excel_file")
    if not file:
        return jsonify({"status": "error", "message": "No file selected"}), 400

    try:
        df = pd.read_excel(file)
        headers = [h.lower() for h in df.columns]

        col_map = {}
        for key in ["student_number", "name", "section", "password"]:
            for i, h in enumerate(headers):
                if h == key.lower():
                    col_map[key] = i
                    break
            else:
                return jsonify({"status": "error", "message": f"Missing required column: {key}"}), 400

        conn = get_db()
        with conn.cursor() as cursor:
            added_students = 0
            skipped_students = 0
            for _, row in df.iterrows():
                student_number = str(row[col_map["student_number"]]).strip()
                name = str(row[col_map["name"]]).strip()
                section_name = str(row[col_map["section"]]).strip()
                password = str(row[col_map["password"]]).strip()

                cursor.execute("SELECT id FROM sections WHERE name=%s", (section_name,))
                result = cursor.fetchone()
                if result:
                    section_id = result[0]
                else:
                    cursor.execute("INSERT INTO sections (name) VALUES (%s)", (section_name,))
                    conn.commit()
                    section_id = cursor.lastrowid

                cursor.execute("SELECT id FROM students WHERE student_number=%s", (student_number,))
                if cursor.fetchone():
                    skipped_students += 1
                    continue

                cursor.execute(
                    "INSERT INTO students (name, student_number, section_id, password) VALUES (%s, %s, %s, %s)",
                    (name, student_number, section_id, password)
                )
                added_students += 1

            conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"{added_students} students added successfully. {skipped_students} duplicates skipped."
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
'''

# ---------------- EXTERNAL UPLOAD (for PHP site) ----------------
@app.route("/api/upload-students", methods=["POST"])
def api_upload_students():
    file = request.files.get("excel_file")
    if not file:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config.get("UPLOAD_FOLDER", "."), filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    try:
        df = pd.read_excel(filepath)
        headers = [h.lower() for h in df.columns]
        required = ["student_number", "name", "section", "password"]
        for key in required:
            if key not in headers:
                return jsonify({"status": "error", "message": f"Missing required column: {key}"}), 400

        conn = get_db()
        with conn.cursor() as cursor:
            added = 0
            skipped = 0
            for _, row in df.iterrows():
                student_number = str(row["student_number"]).strip()
                name = str(row["name"]).strip()
                section_name = str(row["section"]).strip()
                password = str(row["password"]).strip()

                cursor.execute("SELECT id FROM sections WHERE name=%s", (section_name,))
                result = cursor.fetchone()
                if result:
                    section_id = result[0]
                else:
                    cursor.execute("INSERT INTO sections (name) VALUES (%s)", (section_name,))
                    conn.commit()
                    section_id = cursor.lastrowid

                cursor.execute("SELECT id FROM students WHERE student_number=%s", (student_number,))
                if cursor.fetchone():
                    skipped += 1
                    continue

                cursor.execute(
                    "INSERT INTO students (name, student_number, section_id, password) VALUES (%s, %s, %s, %s)",
                    (name, student_number, section_id, password)
                )
                added += 1

            conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"{added} students added, {skipped} skipped."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500

# ---------------- QUIZ ROUTES ----------------
@app.route("/create-quiz", methods=["GET", "POST"])
def create_quiz():
    if request.method == "POST":
        question = request.form["question"]
        A = request.form["A"]
        B = request.form["B"]
        C = request.form["C"]
        D = request.form["D"]
        correct_answer = request.form["correct_answer"]

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO quiz (question, A, B, C, D, correct_answer) 
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (question, A, B, C, D, correct_answer)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Quiz question added successfully!", "success")
        return redirect(url_for("create_quiz"))

    return render_template("create_quiz.html", current_page="create-quiz")

@app.route("/edit-quiz", methods=["GET", "POST"])
def edit_quiz():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        question_id = request.form["id"]
        question = request.form["question"]
        A = request.form["A"]
        B = request.form["B"]
        C = request.form["C"]
        D = request.form["D"]
        correct_answer = request.form["correct_answer"]

        cursor.execute(
            """UPDATE quiz
               SET question=%s, A=%s, B=%s, C=%s, D=%s, correct_answer=%s
               WHERE id=%s""",
            (question, A, B, C, D, correct_answer, question_id)
        )
        conn.commit()
        flash("Quiz question updated successfully!", "success")

    cursor.execute("SELECT * FROM quiz")
    quizzes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("edit_quiz.html", quizzes=quizzes, current_page="edit-quiz")

# ---------------- UPLOAD QUIZ ----------------
@app.route("/upload-quiz", methods=["POST"])
def upload_quiz():
    if "quiz_file" not in request.files:
        flash("No file selected", "error")
        return redirect(url_for("create_quiz"))

    file = request.files["quiz_file"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("create_quiz"))

    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(upload_path)

    try:
        if file_ext in [".xls", ".xlsx"]:
            df = pd.read_excel(upload_path)
        else:
            df = pd.read_csv(upload_path)

        required_cols = ["question", "A", "B", "C", "D", "correct_answer"]
        if not all(col in df.columns for col in required_cols):
            flash("File is missing required columns.", "error")
            return redirect(url_for("create_quiz"))

        conn = get_db()
        cursor = conn.cursor()
        for _, row in df.iterrows():
            cursor.execute(
                """INSERT INTO quiz (question, A, B, C, D, correct_answer)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (row["question"], row["A"], row["B"], row["C"], row["D"], row["correct_answer"])
            )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Quiz uploaded successfully!", "success")
    except Exception as e:
        flash(f"Error uploading quiz: {str(e)}", "error")

    return redirect(url_for("create_quiz"))

@app.route("/export_quiz")
def export_quiz():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT question, A, B, C, D, correct_answer FROM quiz")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    import csv
    from io import StringIO
    si = StringIO()
    writer = csv.DictWriter(si, fieldnames=["question","A","B","C","D","correct_answer"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    return si.getvalue(), 200, {
        "Content-Type": "text/csv",
        "Content-Disposition": 'attachment; filename="quiz.csv"'
    }

@app.route("/quiz/json")
def get_quiz_json():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT question, A, B, C, D, correct_answer FROM quiz")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)

@app.route("/update-quiz/<int:quiz_id>", methods=["POST"])
def update_quiz(quiz_id):
    question = request.form["question"]
    A = request.form.get("A") or request.form.get("choices", "").split(";")[0]
    B = request.form.get("B") or request.form.get("choices", "").split(";")[1]
    C = request.form.get("C") or request.form.get("choices", "").split(";")[2]
    D = request.form.get("D") or request.form.get("choices", "").split(";")[3]
    correct_answer = request.form.get("correct_answer") or request.form.get("answer")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE quiz
           SET question=%s, A=%s, B=%s, C=%s, D=%s, correct_answer=%s
           WHERE id=%s""",
        (question, A, B, C, D, correct_answer, quiz_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Quiz updated successfully!", "success")
    return redirect(url_for("edit_quiz"))

# ---------------- ABOUT ----------------
@app.route("/about")
def about():
    return render_template("about.html", current_page="about")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- SUBMIT DATA ----------------
@app.route("/submit", methods=["POST"])
def submit():
    try:
        data = request.get_json()
        print("Received data:", data)

        required_fields = {"name", "class", "minigame1", "minigame2", "minigame3", "minigame4"}
        if not data or not required_fields.issubset(data):
            return jsonify({"error": "Missing or invalid fields"}), 400

        submitted_data.append(data)
        return jsonify({"message": "Data received successfully."}), 200

    except Exception as e:
        print("Error in /submit route:", e)
        return jsonify({"error": "Server error"}), 500

# ---------------- FLASK API LOGIN FOR RENPY ----------------
@app.route("/api/login", methods=["POST"])
def api_login():
    try:
        data = request.get_json()
        student_number = data.get("student_number")
        password = data.get("password")

        if not student_number or not password:
            return jsonify({"status": "error", "message": "Missing student number or password"}), 400

        conn = get_db()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM students WHERE student_number=%s AND password=%s",
                (student_number, password)
            )
            student = cursor.fetchone()
        conn.close()

        if student:
            return jsonify({"status": "success", "student_name": student["name"], "section_id": student["section_id"]})
        else:
            return jsonify({"status": "fail", "message": "Invalid student number or password"}), 401

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------------- DROPDOWN SECTIONS API ----------------
@app.route("/api/sections-dropdown")
def sections_dropdown():
    try:
        conn = get_db()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id, name FROM sections ORDER BY name")
            sections = cursor.fetchall()
        conn.close()
        return jsonify(sections)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------------- PHP API FOR STUDENT SCORES ----------------
@app.route("/api/student_scores", methods=["POST"])
def student_scores():
    try:
        data = request.get_json()
        student_number = data.get("student_number")
        if not student_number:
            return jsonify({"error": "Missing student_number"}), 400

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT st.name AS student_name, s.name AS section_name,
                   sc.minigame1, sc.minigame2, sc.minigame3, sc.minigame4, sc.quiz
            FROM students st
            LEFT JOIN student_scores sc ON st.id = sc.student_id AND sc.section_id = st.section_id
            JOIN sections s ON st.section_id = s.id
            WHERE st.student_number = %s
        """, (student_number,))
        result = cursor.fetchall()
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- ADMIN LOGIN ----------------
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"status":"error","message":"Missing username or password"}),400

    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin_users WHERE username=%s AND password=%s", (username, password))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        if admin:
            return jsonify({"status":"success","admin_name":admin["username"]})
        else:
            return jsonify({"status":"fail","message":"Invalid credentials"}),401
    except Error as e:
        return jsonify({"status":"error","message":str(e)}),500

# ---------------- TEACHERS CRUD ----------------
@app.route("/api/teachers", methods=["GET","POST"])
def teachers():
    if request.method == "GET":
        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, username, fullname FROM teachers ORDER BY fullname")
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify(result)
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

    if request.method == "POST":
        data = request.get_json()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO teachers (username, password, fullname) VALUES (%s,%s,%s)",
                (data["username"], data["password"], data["fullname"])
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

@app.route("/api/teachers/<int:teacher_id>", methods=["PUT","DELETE"])
def teacher_detail(teacher_id):
    if request.method == "PUT":
        data = request.get_json()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE teachers SET username=%s, password=%s, fullname=%s WHERE id=%s",
                (data["username"], data["password"], data["fullname"], teacher_id)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

    if request.method == "DELETE":
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM teachers WHERE id=%s", (teacher_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

# ---------------- FEEDBACK CRUD ----------------
@app.route("/api/feedback", methods=["GET","POST"])
def feedback():
    if request.method == "GET":
        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""SELECT f.id, f.feedback_text, f.student_id, s.name AS student_name 
                              FROM feedback f JOIN students s ON f.student_id=s.id ORDER BY f.id""")
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify(result)
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

    if request.method == "POST":
        data = request.get_json()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO feedback (student_id, feedback_text) VALUES (%s,%s)",
                (data["student_id"], data["feedback_text"])
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

@app.route("/api/feedback/<int:feedback_id>", methods=["PUT","DELETE"])
def feedback_detail(feedback_id):
    if request.method == "PUT":
        data = request.get_json()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE feedback SET student_id=%s, feedback_text=%s WHERE id=%s",
                (data["student_id"], data["feedback_text"], feedback_id)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

    if request.method == "DELETE":
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feedback WHERE id=%s", (feedback_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status":"success"})
        except Error as e:
            return jsonify({"status":"error","message":str(e)}),500

# ---------------- TEST DB CONNECTION ----------------
@app.route("/test-db")
def test_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students LIMIT 5")
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"students": results}
    except Exception as e:
        return {"error": str(e)}

@app.route('/api/ping', methods=['POST', 'GET'])
def ping():
    return jsonify({"success": True, "message": "Flask API reachable!"})

# ---------------- RUN SERVER ----------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
