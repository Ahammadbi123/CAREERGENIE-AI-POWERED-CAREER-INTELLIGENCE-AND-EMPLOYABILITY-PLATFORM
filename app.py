from flask import Flask, redirect, url_for, session, render_template, request, flash, jsonify
from groq import Groq
import os
import json
import random
import copy
from flask import request, jsonify
from career_intelligence.parser import load_simulated_dataset
from career_intelligence.analyzer import CompanyAnalyzer
from career_intelligence.market_intelligence import aggregate_market_data
from resume_module.resume_routes import resume_bp
import sqlite3
from chatbot_logic import get_reply
from routes_genai.genai_universal_resume_routes import genai_universal_resume_bp
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from google import genai
from dotenv import load_dotenv
import os
import io
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from flask import redirect
import re
from services.aggregator import get_all_jobs
from services.ai_engine import analyze_jobs
from utils.career_logic import calculate_scores
from utils.employability_logic import calculate_employability
from dotenv import load_dotenv

load_dotenv()

# -------------------------
# CONFIG
# -------------------------
load_dotenv()

app = Flask(__name__)
from groq import Groq
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
file_path = os.path.join(os.path.dirname(__file__), "data", "company_data.json")
with open("data/company_data.json") as f:
    company_data = json.load(f)
app.register_blueprint(genai_universal_resume_bp)
app.register_blueprint(resume_bp)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options={"api_version": "v1beta"}
)
models = client.models.list()

for m in models:
    print(m.name)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///new_users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ===============================

# 💾 Create Interview History Table
# ===============================
def create_history_table():
    conn = sqlite3.connect("interviews.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        average_score REAL,
        badge TEXT,
        date TEXT
    )
    """)

    conn.commit()
    conn.close()

create_history_table()

db = SQLAlchemy(app)

# -------------------------
# GOOGLE OAUTH
# -------------------------
oauth = OAuth(app)

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)

# -------------------------
# DATABASE MODEL
# -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=True)

with app.app_context():
    db.create_all()

# -------------------------
# HOME
# -------------------------
@app.route("/")
def home():
    return render_template("home.html")

# -------------------------
# REGISTER
# -------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["first_name"] + " " + request.form["last_name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        user = User(name=name, email=email, password=password)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

# -------------------------
# LOGIN
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["logged_in"] = True
        return redirect(url_for("dashboard"))

    return render_template("login.html")




# -------------------------
# FORGOT PASSWORD
# -------------------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        user = User.query.filter_by(email=email).first()

        if user:
            # Direct redirect to reset page (simple method)
            return redirect(url_for("reset_password", email=email))
        else:
            return "Email not found"

    return render_template("forgot.html")

# -------------------------
# RESET PASSWORD
# -------------------------
@app.route("/reset-password/<email>", methods=["GET", "POST"])
def reset_password(email):
    user = User.query.filter_by(email=email).first()

    if not user:
        return "Invalid user"

    if request.method == "POST":
        new_password = generate_password_hash(request.form["password"])
        user.password = new_password
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("reset_password.html", email=email)


# -------------------------
# GOOGLE LOGIN
# -------------------------
@app.route("/login/google")
def google_login():
    redirect_uri = url_for("google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route("/login/google/authorized")
def google_callback():
    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo")

    session["logged_in"] = True
    session["user_name"] = userinfo.get("name")
    session["user_email"] = userinfo.get("email")

    return redirect(url_for("dashboard"))

# -------------------------
# DASHBOARD
# -------------------------
@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template("dashboard.html")

# -------------------------
# AI CHATBOT (FINAL – ONLY ONE)
# ------------------------
@app.route("/career-chatbot")
def career_chatbot():
    return render_template("career_chatbot.html")

def gen_ai_reply(user_msg):
    try:
        response = client.models.generate_content(
            model="models/gemini-3.5-flash-lite",
            contents=[
                {
                    "role": "user",
                    "parts": [{"text": user_msg}]
                }
            ]
        )
        return response.candidates[0].content.parts[0].text

    except Exception as e:
        print("GEN-AI ERROR:", e)
        return "❌ Gen-AI service temporarily unavailable."

@app.route("/get_reply", methods=["POST"])
def chatbot_reply():
    user_msg = request.form.get("message", "")
    mode = request.form.get("mode")

    try:
        if mode == "genai":
            reply = gen_ai_reply(user_msg)
        else:
            reply = get_reply(user_msg)

        return jsonify({"reply": reply})

    except Exception as e:
        print("CHATBOT ERROR:", e)
        return jsonify({"reply": "❌ Server error"}), 500


@app.route("/download_chat_pdf", methods=["POST"])
def download_chat_pdf():
    chat_text = request.form.get("chat", "")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    for line in chat_text.split("\n"):
        story.append(Paragraph(line, styles["Normal"]))

    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="chat.pdf",
        mimetype="application/pdf"
    )


# ---------------- AI EXAMS QUESTIONS (TEST) ----------------
QUESTIONS = {
    "python": {

        # ---------- LEVEL 1 ----------
        1: [
            {"q":"Which keyword defines a function?","options":["def","func","define","function"],"correct":0,"exp":"Functions use def."},
            {"q":"Which is immutable?","options":["List","Tuple","Set","Dict"],"correct":1,"exp":"Tuple is immutable."},
            {"q":"Comment symbol?","options":["//","#","--","/* */"],"correct":1,"exp":"# is comment."},
            {"q":"len('Hi') output?","options":["1","2","3","Error"],"correct":1,"exp":"Two characters."},
            {"q":"Input function?","options":["input()","scan()","read()","get()"],"correct":0,"exp":"input() takes input."}
        ],

        # ---------- LEVEL 2 ----------
        2: [
            {"q":"Known iterations loop?","options":["while","for","do","repeat"],"correct":1,"exp":"for loop."},
            {"q":"break does?","options":["Skip","Stop loop","Restart","None"],"correct":1,"exp":"break exits loop."},
            {"q":"Equality operator?","options":["=","==","!=","<>"],"correct":1,"exp":"== checks equality."},
            {"q":"bool(0)?","options":["True","False","0","Error"],"correct":1,"exp":"0 is False."},
            {"q":"Condition keyword?","options":["if","when","case","check"],"correct":0,"exp":"if checks condition."}
        ],

        # ---------- LEVEL 3 ----------
        3: [
            {"q":"Function calling itself?","options":["Loop","Recursion","Iteration","Callback"],"correct":1,"exp":"Recursion."},
            {"q":"Class keyword?","options":["class","struct","define","object"],"correct":0,"exp":"class defines class."},
            {"q":"self refers to?","options":["Class","Object","Module","Function"],"correct":1,"exp":"Current object."},
            {"q":"Constructor?","options":["__start__","__init__","__new__","__create__"],"correct":1,"exp":"__init__ constructor."},
            {"q":"No duplicates collection?","options":["List","Tuple","Set","Dict"],"correct":2,"exp":"Set removes duplicates."}
        ],

        # ---------- LEVEL 4 ----------
        4: [
            {"q":"Lambda is?","options":["Anonymous function","Class","Module","Loop"],"correct":0,"exp":"Lambda is anonymous."},
            {"q":"Open file function?","options":["open","file","read","load"],"correct":0,"exp":"open() opens file."},
            {"q":"Write mode?","options":["r","w","a","x"],"correct":1,"exp":"w writes file."},
            {"q":"Always executes block?","options":["try","except","finally","error"],"correct":2,"exp":"finally always runs."},
            {"q":"Regex module?","options":["regex","re","match","pattern"],"correct":1,"exp":"re module."}
        ],

        # ---------- LEVEL 5 ----------
        5: [
            {"q":"Return keyword?","options":["return","yield","break","pass"],"correct":0,"exp":"return sends value."},
            {"q":"No return gives?","options":["0","None","Error","False"],"correct":1,"exp":"Returns None."},
            {"q":"Valid name?","options":["1fun","fun-name","fun_name","fun name"],"correct":2,"exp":"Underscore allowed."},
            {"q":"Empty function keyword?","options":["empty","pass","skip","null"],"correct":1,"exp":"pass placeholder."},
            {"q":"Default input type?","options":["int","float","str","bool"],"correct":2,"exp":"input gives string."}
        ],

        # ---------- LEVEL 6 ----------
        6: [
            {"q":"Mutable type?","options":["Tuple","String","List","Int"],"correct":2,"exp":"List mutable."},
            {"q":"Add to list?","options":["add","append","insert","push"],"correct":1,"exp":"append adds."},
            {"q":"Remove last?","options":["del","remove","pop","cut"],"correct":2,"exp":"pop removes last."},
            {"q":"Tuple brackets?","options":["{}","[]","()","<>"],"correct":2,"exp":"() for tuple."},
            {"q":"List index starts?","options":["0","1","-1","Any"],"correct":0,"exp":"Index starts 0."}
        ],

        # ---------- LEVEL 7 ----------
        7: [
            {"q":"Key-value store?","options":["List","Tuple","Dict","Set"],"correct":2,"exp":"Dictionary."},
            {"q":"Dict symbol?","options":["[]","()","{}","<>"],"correct":2,"exp":"{} dict."},
            {"q":"Dict keys are?","options":["Mutable","Immutable","Duplicate","Ordered"],"correct":1,"exp":"Keys immutable."},
            {"q":"Set removes?","options":["Order","Duplicates","Keys","Values"],"correct":1,"exp":"Duplicates removed."},
            {"q":"Add to set?","options":["append","add","insert","push"],"correct":1,"exp":"add() adds."}
        ],

        # ---------- LEVEL 8 ----------
        8: [
            {"q":"Strings are?","options":["Mutable","Immutable","Dynamic","Editable"],"correct":1,"exp":"Strings immutable."},
            {"q":"Uppercase method?","options":["upper","uppercase","toUpper","capital"],"correct":0,"exp":"upper()."},
            {"q":"Concat operator?","options":["+","*","&","%"],"correct":0,"exp":"+ joins."},
            {"q":"len returns?","options":["Index","Value","Length","Type"],"correct":2,"exp":"Length."},
            {"q":"Remove spaces?","options":["strip","trim","cut","remove"],"correct":0,"exp":"strip()."}
        ],

        # ---------- LEVEL 9 ----------
        9: [
            {"q":"Class is?","options":["Blueprint","Object","Method","Var"],"correct":0,"exp":"Blueprint."},
            {"q":"Object is?","options":["Class","Instance","Function","Module"],"correct":1,"exp":"Instance."},
            {"q":"Create class?","options":["struct","define","class","object"],"correct":2,"exp":"class keyword."},
            {"q":"self means?","options":["Class","Object","Module","None"],"correct":1,"exp":"Current object."},
            {"q":"Constructor name?","options":["__start__","__init__","__new__","__make__"],"correct":1,"exp":"__init__."}
        ],

        # ---------- LEVEL 10 ----------
        10: [
            {"q":"Inheritance means?","options":["Reuse","Delete","Hide","Compile"],"correct":0,"exp":"Reuse code."},
            {"q":"Multiple inheritance?","options":["C","Java","Python","None"],"correct":2,"exp":"Python supports."},
            {"q":"Overriding in?","options":["Same","Child","Parent","None"],"correct":1,"exp":"Child class."},
            {"q":"Polymorphism?","options":["Many forms","One form","No form","None"],"correct":0,"exp":"Many forms."},
            {"q":"Parent access keyword?","options":["this","parent","super","base"],"correct":2,"exp":"super keyword."}
        ],

        # ---------- LEVEL 11 ----------
        11: [
            {"q":"Open file?","options":["open","file","read","load"],"correct":0,"exp":"open()."},
            {"q":"Read mode?","options":["w","r","a","x"],"correct":1,"exp":"r reads."},
            {"q":"Append mode?","options":["r","w","a","x"],"correct":2,"exp":"a appends."},
            {"q":"Close file?","options":["end","stop","close","exit"],"correct":2,"exp":"close()."},
            {"q":"File handling used for?","options":["Memory","Storage","Loop","Condition"],"correct":1,"exp":"Storage."}
        ],

        # ---------- LEVEL 12 ----------
        12: [
            {"q":"Exception block?","options":["try","catch","handle","error"],"correct":0,"exp":"try block."},
            {"q":"Always runs?","options":["try","except","finally","error"],"correct":2,"exp":"finally runs."},
            {"q":"Exception is?","options":["Syntax","Runtime","Compile","None"],"correct":1,"exp":"Runtime error."},
            {"q":"Raise exception?","options":["raise","throw","error","stop"],"correct":0,"exp":"raise keyword."},
            {"q":"10/0 gives?","options":["0","Error","Infinity","None"],"correct":1,"exp":"ZeroDivisionError."}
        ],

        # ---------- LEVEL 13 ----------
        13: [
            {"q":"Module is?","options":["File","Class","Function","Loop"],"correct":0,"exp":"Module is file."},
            {"q":"Import keyword?","options":["include","import","use","require"],"correct":1,"exp":"import keyword."},
            {"q":"Math module?","options":["math","calc","num","number"],"correct":0,"exp":"math module."},
            {"q":"Random numbers?","options":["math","random","num","rand"],"correct":1,"exp":"random module."},
            {"q":"__main__ means?","options":["Import","Main run","Error","None"],"correct":1,"exp":"Main execution."}
        ],

        # ---------- LEVEL 14 ----------
        14: [
            {"q":"Iterator creator?","options":["iter","next","range","yield"],"correct":0,"exp":"iter()."},
            {"q":"Next value?","options":["next","iter","range","yield"],"correct":0,"exp":"next()."},
            {"q":"Yield used in?","options":["Func","Generator","Loop","Class"],"correct":1,"exp":"Generators."},
            {"q":"Generator returns?","options":["One","Sequence","List","Tuple"],"correct":1,"exp":"Sequence."},
            {"q":"Lambda returns?","options":["Value","Function","Class","None"],"correct":0,"exp":"Returns value."}
        ],

        # ---------- LEVEL 15 ----------
        15: [
            {"q":"Python is?","options":["Compiled","Interpreted","Both","None"],"correct":2,"exp":"Both."},
            {"q":"GIL is?","options":["Lock","Compiler","Memory","Loop"],"correct":0,"exp":"Global Interpreter Lock."},
            {"q":"Deep copy?","options":["Same","New memory","No memory","None"],"correct":1,"exp":"New memory."},
            {"q":"Data analysis lib?","options":["NumPy","Pandas","Matplotlib","All"],"correct":3,"exp":"All used."},
            {"q":"Multithreading?","options":["Yes","No","Limited","Depends"],"correct":2,"exp":"Limited by GIL."}
        ]
    }
}


QUESTIONS["java"] = {

    1: [
        {"q": "Java is a ___ language.", "options": ["Procedural", "Object-Oriented", "Scripting", "Markup"], "correct": 1, "exp": "Java is an Object-Oriented language."},
        {"q": "Which keyword defines a class?", "options": ["class", "struct", "define", "object"], "correct": 0, "exp": "class keyword defines a class."},
        {"q": "Entry point of Java program?", "options": ["start()", "run()", "main()", "init()"], "correct": 2, "exp": "main() is entry point."},
        {"q": "Java file extension?", "options": [".class", ".exe", ".java", ".js"], "correct": 2, "exp": ".java is source file."},
        {"q": "Which symbol ends statement?", "options": [":", ".", ";", ","], "correct": 2, "exp": "Semicolon ends statement."}
    ],

    2: [
        {"q": "Object creation keyword?", "options": ["class", "create", "new", "object"], "correct": 2, "exp": "new creates objects."},
        {"q": "Whole number datatype?", "options": ["float", "double", "int", "char"], "correct": 2, "exp": "int stores integers."},
        {"q": "Default imported package?", "options": ["java.util", "java.io", "java.lang", "java.net"], "correct": 2, "exp": "java.lang auto imported."},
        {"q": "Access modifier for everyone?", "options": ["private", "protected", "default", "public"], "correct": 3, "exp": "public is accessible everywhere."},
        {"q": "Inheritance keyword?", "options": ["inherits", "extends", "implements", "super"], "correct": 1, "exp": "extends is used."}
    ],

    3: [
        {"q": "Loop checks condition first?", "options": ["do-while", "for", "while", "switch"], "correct": 2, "exp": "while checks first."},
        {"q": "Loop break keyword?", "options": ["stop", "exit", "break", "end"], "correct": 2, "exp": "break stops loop."},
        {"q": "Skip iteration keyword?", "options": ["skip", "pass", "continue", "next"], "correct": 2, "exp": "continue skips iteration."},
        {"q": "Boolean datatype?", "options": ["int", "bool", "boolean", "String"], "correct": 2, "exp": "boolean stores true/false."},
        {"q": "Comparison operator?", "options": ["=", "==", "!=", "&&"], "correct": 1, "exp": "== compares values."}
    ],

    4: [
        {"q": "Current object keyword?", "options": ["this", "super", "self", "object"], "correct": 0, "exp": "this refers current object."},
        {"q": "Parent constructor call?", "options": ["this", "super", "parent", "base"], "correct": 1, "exp": "super calls parent."},
        {"q": "Multiple method names concept?", "options": ["Encapsulation", "Inheritance", "Polymorphism", "Abstraction"], "correct": 2, "exp": "Polymorphism allows overloading."},
        {"q": "Prevent inheritance keyword?", "options": ["static", "final", "private", "abstract"], "correct": 1, "exp": "final prevents inheritance."},
        {"q": "Constant keyword?", "options": ["const", "static", "final", "fixed"], "correct": 2, "exp": "final makes constant."}
    ],

    5: [
        {"q": "Root class in Java?", "options": ["Main", "System", "Object", "Root"], "correct": 2, "exp": "Object is root class."},
        {"q": "Convert object to string?", "options": ["toString()", "convert()", "parse()", "string()"], "correct": 0, "exp": "toString converts object."},
        {"q": "Create interface keyword?", "options": ["interface", "implements", "abstract", "extends"], "correct": 0, "exp": "interface keyword used."},
        {"q": "Java inheritance type?", "options": ["Multiple", "Single", "Hybrid", "All"], "correct": 1, "exp": "Java supports single inheritance."},
        {"q": "Sorting interface?", "options": ["Runnable", "Serializable", "Comparable", "Cloneable"], "correct": 2, "exp": "Comparable used for sorting."}
    ],

    6: [
        {"q": "Method overriding needs?", "options": ["Same name", "Same return", "Both", "None"], "correct": 2, "exp": "Same method signature required."},
        {"q": "Which block handles exception?", "options": ["try", "catch", "throw", "finally"], "correct": 1, "exp": "catch handles exception."},
        {"q": "Which keyword throws exception?", "options": ["throw", "throws", "catch", "error"], "correct": 0, "exp": "throw explicitly throws exception."},
        {"q": "Finally block purpose?", "options": ["Execute always", "Handle error", "Skip code", "Stop program"], "correct": 0, "exp": "finally executes always."},
        {"q": "Checked exception example?", "options": ["NullPointer", "ArrayIndex", "IOException", "Arithmetic"], "correct": 2, "exp": "IOException is checked."}
    ],

    7: [
        {"q": "Thread creation method?", "options": ["Thread class", "Runnable", "Both", "None"], "correct": 2, "exp": "Thread or Runnable used."},
        {"q": "Start thread method?", "options": ["run()", "execute()", "start()", "init()"], "correct": 2, "exp": "start() begins thread."},
        {"q": "Sleep method belongs to?", "options": ["Object", "Thread", "Runnable", "System"], "correct": 1, "exp": "sleep() is Thread method."},
        {"q": "Synchronization keyword?", "options": ["sync", "lock", "synchronized", "thread"], "correct": 2, "exp": "synchronized keyword used."},
        {"q": "Deadlock occurs due to?", "options": ["Memory", "Threads", "CPU", "Syntax"], "correct": 1, "exp": "Deadlock occurs in threads."}
    ],

    8: [
        {"q": "Collection interface?", "options": ["List", "Set", "Map", "All"], "correct": 3, "exp": "All are collections."},
        {"q": "Allows duplicates?", "options": ["Set", "List", "Map", "Queue"], "correct": 1, "exp": "List allows duplicates."},
        {"q": "Key-value storage?", "options": ["List", "Set", "Map", "Array"], "correct": 2, "exp": "Map stores key-value."},
        {"q": "HashMap allows?", "options": ["Duplicates", "Null key", "Sorted", "Thread safe"], "correct": 1, "exp": "HashMap allows one null key."},
        {"q": "Sorted collection?", "options": ["HashSet", "TreeSet", "ArrayList", "Vector"], "correct": 1, "exp": "TreeSet is sorted."}
    ],

    9: [
        {"q": "JVM stands for?", "options": ["Java VM", "Java Virtual Machine", "Joint VM", "None"], "correct": 1, "exp": "JVM = Java Virtual Machine."},
        {"q": "JDK contains?", "options": ["JRE", "Compiler", "Tools", "All"], "correct": 3, "exp": "JDK contains all."},
        {"q": "JRE used for?", "options": ["Compile", "Run", "Debug", "Edit"], "correct": 1, "exp": "JRE runs Java programs."},
        {"q": "Bytecode runs on?", "options": ["OS", "CPU", "JVM", "RAM"], "correct": 2, "exp": "JVM executes bytecode."},
        {"q": "Platform independent reason?", "options": ["Compiler", "JVM", "OS", "CPU"], "correct": 1, "exp": "JVM makes Java portable."}
    ],

    10: [
        {"q": "Abstract class can have?", "options": ["No methods", "Only abstract", "Abstract & non-abstract", "Only static"], "correct": 2, "exp": "Abstract class can have both."},
        {"q": "Interface methods are by default?", "options": ["public", "private", "protected", "static"], "correct": 0, "exp": "Interface methods are public."},
        {"q": "Multiple inheritance achieved by?", "options": ["Class", "Interface", "Object", "Package"], "correct": 1, "exp": "Interface supports multiple inheritance."},
        {"q": "Lambda introduced in?", "options": ["Java 6", "Java 7", "Java 8", "Java 9"], "correct": 2, "exp": "Lambda came in Java 8."},
        {"q": "Functional interface has?", "options": ["1 method", "2 methods", "Many", "None"], "correct": 0, "exp": "Functional interface has one method."}
    ],

    11: [
        {"q": "String is immutable?", "options": ["True", "False"], "correct": 0, "exp": "String is immutable."},
        {"q": "StringBuilder is?", "options": ["Mutable", "Immutable"], "correct": 0, "exp": "StringBuilder is mutable."},
        {"q": "Compare strings content?", "options": ["==", "equals()", "compare()", "match()"], "correct": 1, "exp": "equals compares content."},
        {"q": "Memory for objects?", "options": ["Stack", "Heap", "Register", "Cache"], "correct": 1, "exp": "Objects stored in heap."},
        {"q": "Primitive stored in?", "options": ["Heap", "Stack"], "correct": 1, "exp": "Primitive stored in stack."}
    ],

    12: [
        {"q": "Wrapper class for int?", "options": ["Integer", "Int", "Number", "Long"], "correct": 0, "exp": "Integer wraps int."},
        {"q": "Auto boxing means?", "options": ["Primitive to object", "Object to primitive", "Casting", "Conversion"], "correct": 0, "exp": "Autoboxing converts primitive to object."},
        {"q": "Unboxing means?", "options": ["Object to primitive", "Primitive to object"], "correct": 0, "exp": "Unboxing converts object to primitive."},
        {"q": "Which is not wrapper?", "options": ["Integer", "Float", "Character", "String"], "correct": 3, "exp": "String is not wrapper."},
        {"q": "Math class is?", "options": ["final", "abstract", "interface", "normal"], "correct": 0, "exp": "Math class is final."}
    ],

    13: [
        {"q": "Serialization used for?", "options": ["Store object", "Destroy object", "Encrypt", "Compile"], "correct": 0, "exp": "Serialization stores object state."},
        {"q": "Serializable is?", "options": ["Class", "Interface", "Method", "Package"], "correct": 1, "exp": "Serializable is interface."},
        {"q": "Transient keyword?", "options": ["Skip variable", "Save variable", "Encrypt", "Static"], "correct": 0, "exp": "Transient skips variable."},
        {"q": "Deserialization means?", "options": ["Object to stream", "Stream to object"], "correct": 1, "exp": "Deserialization recreates object."},
        {"q": "serialVersionUID used for?", "options": ["Versioning", "Security", "Speed", "Memory"], "correct": 0, "exp": "Used for version control."}
    ],

    14: [
        {"q": "JDBC used for?", "options": ["UI", "Database", "Thread", "File"], "correct": 1, "exp": "JDBC connects database."},
        {"q": "DriverManager used for?", "options": ["Connection", "Query", "UI", "Thread"], "correct": 0, "exp": "DriverManager creates connection."},
        {"q": "Execute select query?", "options": ["execute()", "executeQuery()", "executeUpdate()", "run()"], "correct": 1, "exp": "executeQuery used."},
        {"q": "ResultSet used for?", "options": ["Store data", "Show UI", "Thread", "Compile"], "correct": 0, "exp": "ResultSet stores result."},
        {"q": "PreparedStatement advantage?", "options": ["Fast", "Secure", "Reusable", "All"], "correct": 3, "exp": "PreparedStatement is fast & secure."}
    ],

    15: [
        {"q": "Spring is?", "options": ["Framework", "Language", "OS", "Compiler"], "correct": 0, "exp": "Spring is framework."},
        {"q": "Spring Boot advantage?", "options": ["Configuration", "Speed", "Microservices", "All"], "correct": 3, "exp": "Spring Boot simplifies development."},
        {"q": "REST stands for?", "options": ["Representational State Transfer", "Remote State", "Request Service", "None"], "correct": 0, "exp": "REST = Representational State Transfer."},
        {"q": "HTTP GET used for?", "options": ["Create", "Update", "Fetch", "Delete"], "correct": 2, "exp": "GET fetches data."},
        {"q": "HTTP POST used for?", "options": ["Read", "Create", "Delete", "Fetch"], "correct": 1, "exp": "POST creates resource."}
    ]
}

QUESTIONS["sql"] = {

    1: [
        {"q": "SQL stands for?", "options": ["Structured Query Language", "Simple Query Language", "Sequential Query Language", "Server Query Language"], "correct": 0, "exp": "SQL stands for Structured Query Language."},
        {"q": "Which SQL statement is used to fetch data?", "options": ["GET", "SELECT", "FETCH", "READ"], "correct": 1, "exp": "SELECT retrieves data from database."},
        {"q": "Which symbol ends SQL statement?", "options": [":", ".", ";", ","], "correct": 2, "exp": "Semicolon ends SQL statement."},
        {"q": "Which database is relational?", "options": ["MySQL", "MongoDB", "Redis", "Cassandra"], "correct": 0, "exp": "MySQL is relational DB."},
        {"q": "SQL is ___ language?", "options": ["Procedural", "Non-procedural", "Object-Oriented", "Functional"], "correct": 1, "exp": "SQL is non-procedural language."}
    ],

    2: [
        {"q": "Which clause filters records?", "options": ["WHERE", "GROUP BY", "ORDER BY", "HAVING"], "correct": 0, "exp": "WHERE filters rows."},
        {"q": "Which keyword sorts results?", "options": ["SORT", "ORDER BY", "GROUP BY", "FILTER"], "correct": 1, "exp": "ORDER BY sorts records."},
        {"q": "Default sort order?", "options": ["DESC", "ASC", "RANDOM", "NONE"], "correct": 1, "exp": "ASC is default order."},
        {"q": "Which keyword removes duplicate rows?", "options": ["UNIQUE", "DISTINCT", "DELETE", "REMOVE"], "correct": 1, "exp": "DISTINCT removes duplicates."},
        {"q": "Which operator checks multiple values?", "options": ["BETWEEN", "LIKE", "IN", "ANY"], "correct": 2, "exp": "IN checks multiple values."}
    ],

    3: [
        {"q": "Which operator checks pattern?", "options": ["MATCH", "LIKE", "IN", "BETWEEN"], "correct": 1, "exp": "LIKE checks pattern."},
        {"q": "Wildcard for multiple chars?", "options": ["_", "%", "*", "#"], "correct": 1, "exp": "% matches multiple characters."},
        {"q": "Wildcard for single char?", "options": ["_", "%", "*", "#"], "correct": 0, "exp": "_ matches single character."},
        {"q": "BETWEEN is ___ inclusive?", "options": ["Lower only", "Upper only", "Both", "None"], "correct": 2, "exp": "BETWEEN includes both limits."},
        {"q": "NULL means?", "options": ["0", "Empty", "Unknown", "False"], "correct": 2, "exp": "NULL means unknown value."}
    ],

    4: [
        {"q": "COUNT() returns?", "options": ["Sum", "Average", "Rows count", "Max"], "correct": 2, "exp": "COUNT returns number of rows."},
        {"q": "SUM() works on?", "options": ["Text", "Number", "Date", "Boolean"], "correct": 1, "exp": "SUM works on numeric data."},
        {"q": "AVG() returns?", "options": ["Sum", "Average", "Count", "Max"], "correct": 1, "exp": "AVG returns average value."},
        {"q": "MIN() returns?", "options": ["Smallest", "Largest", "Average", "Sum"], "correct": 0, "exp": "MIN gives smallest value."},
        {"q": "MAX() returns?", "options": ["Smallest", "Largest", "Sum", "Count"], "correct": 1, "exp": "MAX gives largest value."}
    ],

    5: [
        {"q": "GROUP BY used with?", "options": ["WHERE", "ORDER BY", "Aggregate", "INSERT"], "correct": 2, "exp": "GROUP BY works with aggregate functions."},
        {"q": "HAVING used for?", "options": ["Filter rows", "Filter groups", "Sort data", "Join tables"], "correct": 1, "exp": "HAVING filters groups."},
        {"q": "WHERE vs HAVING?", "options": ["Same", "Before group", "After group", "None"], "correct": 2, "exp": "HAVING applies after grouping."},
        {"q": "GROUP BY comes before?", "options": ["WHERE", "HAVING", "SELECT", "ORDER BY"], "correct": 1, "exp": "GROUP BY comes before HAVING."},
        {"q": "Aggregate with GROUP BY?", "options": ["Mandatory", "Optional", "Invalid", "Not allowed"], "correct": 0, "exp": "Aggregate functions required."}
    ],

    6: [
        {"q": "Which join returns matching rows?", "options": ["INNER", "LEFT", "RIGHT", "FULL"], "correct": 0, "exp": "INNER JOIN returns matching rows."},
        {"q": "LEFT JOIN returns?", "options": ["Matching only", "Left + match", "Right + match", "All"], "correct": 1, "exp": "LEFT JOIN returns left table rows."},
        {"q": "RIGHT JOIN returns?", "options": ["Left only", "Right only", "Right + match", "None"], "correct": 2, "exp": "RIGHT JOIN returns right table rows."},
        {"q": "FULL JOIN returns?", "options": ["Left", "Right", "Intersection", "All rows"], "correct": 3, "exp": "FULL JOIN returns all rows."},
        {"q": "Join without condition?", "options": ["Inner", "Cross", "Left", "Self"], "correct": 1, "exp": "CROSS JOIN has no condition."}
    ],

    7: [
        {"q": "Self join is?", "options": ["Same table", "Two tables", "No table", "View"], "correct": 0, "exp": "Self join joins same table."},
        {"q": "Join condition written using?", "options": ["WHERE", "ON", "USING", "ALL"], "correct": 1, "exp": "ON specifies join condition."},
        {"q": "Natural join matches?", "options": ["Primary key", "Foreign key", "Same column names", "Index"], "correct": 2, "exp": "Natural join matches same column names."},
        {"q": "Alias used for?", "options": ["Rename table", "Rename column", "Both", "None"], "correct": 2, "exp": "Alias renames table/column."},
        {"q": "AS keyword used for?", "options": ["Join", "Alias", "Group", "Sort"], "correct": 1, "exp": "AS gives alias."}
    ],

    8: [
        {"q": "INSERT command used for?", "options": ["Update", "Delete", "Add data", "Read"], "correct": 2, "exp": "INSERT adds data."},
        {"q": "UPDATE command used for?", "options": ["Insert", "Modify", "Delete", "Read"], "correct": 1, "exp": "UPDATE modifies records."},
        {"q": "DELETE removes?", "options": ["Structure", "Data", "Table", "Database"], "correct": 1, "exp": "DELETE removes data."},
        {"q": "TRUNCATE removes?", "options": ["Some rows", "All rows", "Structure", "Database"], "correct": 1, "exp": "TRUNCATE removes all rows."},
        {"q": "DROP removes?", "options": ["Rows", "Table", "Data only", "Index only"], "correct": 1, "exp": "DROP deletes table."}
    ],

    9: [
        {"q": "Primary key allows?", "options": ["Duplicates", "NULL", "Unique", "All"], "correct": 2, "exp": "Primary key must be unique."},
        {"q": "Primary key count?", "options": ["One", "Many", "None", "Unlimited"], "correct": 0, "exp": "One primary key per table."},
        {"q": "Foreign key used for?", "options": ["Uniqueness", "Relation", "Index", "Security"], "correct": 1, "exp": "Foreign key creates relationship."},
        {"q": "Unique key allows NULL?", "options": ["Yes", "No"], "correct": 0, "exp": "Unique key allows NULL."},
        {"q": "Composite key is?", "options": ["Single column", "Multiple columns", "Index", "View"], "correct": 1, "exp": "Composite key uses multiple columns."}
    ],

    10: [
        {"q": "Constraint for no NULL?", "options": ["UNIQUE", "PRIMARY", "NOT NULL", "CHECK"], "correct": 2, "exp": "NOT NULL prevents NULL values."},
        {"q": "CHECK constraint ensures?", "options": ["Range", "Format", "Condition", "All"], "correct": 2, "exp": "CHECK validates condition."},
        {"q": "DEFAULT sets?", "options": ["Auto value", "Null", "Random", "Primary"], "correct": 0, "exp": "DEFAULT assigns value."},
        {"q": "INDEX improves?", "options": ["Security", "Speed", "Size", "Integrity"], "correct": 1, "exp": "Index improves speed."},
        {"q": "Clustered index?", "options": ["One", "Many"], "correct": 0, "exp": "Only one clustered index."}
    ],

    11: [
        {"q": "View is?", "options": ["Table", "Virtual table", "Index", "Trigger"], "correct": 1, "exp": "View is virtual table."},
        {"q": "View stores data?", "options": ["Yes", "No"], "correct": 1, "exp": "View stores no data."},
        {"q": "Create view command?", "options": ["MAKE VIEW", "CREATE VIEW", "ADD VIEW", "NEW VIEW"], "correct": 1, "exp": "CREATE VIEW used."},
        {"q": "View used for?", "options": ["Security", "Abstraction", "Reuse", "All"], "correct": 3, "exp": "View used for all."},
        {"q": "Update view?", "options": ["Always", "Sometimes", "Never"], "correct": 1, "exp": "Some views are updatable."}
    ],

    12: [
        {"q": "Transaction ensures?", "options": ["Speed", "ACID", "Security", "Index"], "correct": 1, "exp": "Transaction follows ACID."},
        {"q": "Commit does?", "options": ["Save", "Rollback", "Delete", "Cancel"], "correct": 0, "exp": "COMMIT saves changes."},
        {"q": "Rollback does?", "options": ["Save", "Undo", "Delete", "Commit"], "correct": 1, "exp": "ROLLBACK undoes changes."},
        {"q": "Savepoint used for?", "options": ["Backup", "Partial rollback", "Delete", "Commit"], "correct": 1, "exp": "Savepoint allows partial rollback."},
        {"q": "Autocommit default?", "options": ["ON", "OFF"], "correct": 0, "exp": "Autocommit is ON by default."}
    ],

    13: [
        {"q": "Trigger is?", "options": ["Procedure", "Function", "Event-based", "View"], "correct": 2, "exp": "Trigger runs on events."},
        {"q": "Trigger fires on?", "options": ["SELECT", "INSERT", "UPDATE", "Both"], "correct": 3, "exp": "Trigger fires on insert/update/delete."},
        {"q": "Stored procedure is?", "options": ["Query", "Precompiled", "Temporary", "Index"], "correct": 1, "exp": "Stored procedure is precompiled."},
        {"q": "Procedure returns?", "options": ["Value", "Table", "Nothing", "Optional"], "correct": 3, "exp": "Procedure may or may not return value."},
        {"q": "Function returns?", "options": ["Always value", "Table", "Nothing", "Optional"], "correct": 0, "exp": "Function must return value."}
    ],

    14: [
        {"q": "Normalization reduces?", "options": ["Redundancy", "Speed", "Size", "Security"], "correct": 0, "exp": "Normalization reduces redundancy."},
        {"q": "1NF removes?", "options": ["Duplicates", "Repeating groups", "Dependency", "Null"], "correct": 1, "exp": "1NF removes repeating groups."},
        {"q": "2NF removes?", "options": ["Partial dependency", "Transitive", "Redundancy", "Null"], "correct": 0, "exp": "2NF removes partial dependency."},
        {"q": "3NF removes?", "options": ["Partial", "Transitive", "Duplicate", "Null"], "correct": 1, "exp": "3NF removes transitive dependency."},
        {"q": "BCNF stronger than?", "options": ["1NF", "2NF", "3NF", "4NF"], "correct": 2, "exp": "BCNF is stronger than 3NF."}
    ],

    15: [
        {"q": "Denormalization used for?", "options": ["Speed", "Security", "Size", "Integrity"], "correct": 0, "exp": "Denormalization improves speed."},
        {"q": "Index drawback?", "options": ["Slow select", "Extra storage", "No update", "No delete"], "correct": 1, "exp": "Index consumes extra storage."},
        {"q": "Deadlock occurs due to?", "options": ["CPU", "Transactions", "Index", "Join"], "correct": 1, "exp": "Deadlock occurs in transactions."},
        {"q": "Isolation level highest?", "options": ["Read Uncommitted", "Read Committed", "Repeatable Read", "Serializable"], "correct": 3, "exp": "Serializable is highest."},
        {"q": "Phantom read occurs in?", "options": ["Read committed", "Repeatable read", "Serializable", "All"], "correct": 1, "exp": "Phantom read in repeatable read."}
    ]
}

QUESTIONS["c"] = {

    1: [
        {"q": "C language was developed by?", "options": ["Dennis Ritchie", "James Gosling", "Bjarne Stroustrup", "Guido van Rossum"], "correct": 0, "exp": "C was developed by Dennis Ritchie."},
        {"q": "C is a ___ language?", "options": ["High-level", "Low-level", "Middle-level", "Very high-level"], "correct": 2, "exp": "C is called a middle-level language."},
        {"q": "File extension of C?", "options": [".cpp", ".java", ".py", ".c"], "correct": 3, "exp": "C source files use .c extension."},
        {"q": "Which symbol ends C statement?", "options": [".", ",", ";", ":"], "correct": 2, "exp": "Semicolon ends C statements."},
        {"q": "Which function starts execution?", "options": ["start()", "main()", "begin()", "run()"], "correct": 1, "exp": "Program execution starts from main()."}
    ],

    2: [
        {"q": "Which header is mandatory?", "options": ["stdio.h", "conio.h", "stdlib.h", "math.h"], "correct": 0, "exp": "stdio.h is required for input/output."},
        {"q": "printf() belongs to?", "options": ["math.h", "stdio.h", "string.h", "stdlib.h"], "correct": 1, "exp": "printf() is in stdio.h."},
        {"q": "scanf() is used for?", "options": ["Output", "Input", "File", "Memory"], "correct": 1, "exp": "scanf() reads input."},
        {"q": "Which format specifier for int?", "options": ["%d", "%f", "%c", "%s"], "correct": 0, "exp": "%d is for integer."},
        {"q": "Which format specifier for float?", "options": ["%d", "%c", "%f", "%s"], "correct": 2, "exp": "%f is for float."}
    ],

    3: [
        {"q": "Which is valid variable name?", "options": ["1num", "_num", "num-1", "float"], "correct": 1, "exp": "_num is valid variable name."},
        {"q": "Which keyword declares variable?", "options": ["var", "let", "data", "int"], "correct": 3, "exp": "int declares integer variable."},
        {"q": "Size of int (typically)?", "options": ["1 byte", "2 bytes", "4 bytes", "8 bytes"], "correct": 2, "exp": "int is usually 4 bytes."},
        {"q": "Which datatype stores character?", "options": ["int", "float", "char", "double"], "correct": 2, "exp": "char stores character."},
        {"q": "Which datatype stores decimal?", "options": ["int", "float", "char", "void"], "correct": 1, "exp": "float stores decimal values."}
    ],

    4: [
        {"q": "Which operator adds values?", "options": ["-", "+", "*", "/"], "correct": 1, "exp": "+ is addition operator."},
        {"q": "Which operator gives remainder?", "options": ["/", "*", "%", "+"], "correct": 2, "exp": "% gives remainder."},
        {"q": "Which operator increments?", "options": ["++", "--", "+=", "*="], "correct": 0, "exp": "++ increments value."},
        {"q": "Which operator compares equality?", "options": ["=", "==", "!=", "<"], "correct": 1, "exp": "== checks equality."},
        {"q": "Logical AND operator?", "options": ["&", "&&", "|", "||"], "correct": 1, "exp": "&& is logical AND."}
    ],

    5: [
        {"q": "if statement used for?", "options": ["Loop", "Decision", "Function", "Memory"], "correct": 1, "exp": "if is used for decision making."},
        {"q": "else executes when?", "options": ["if true", "if false", "always", "never"], "correct": 1, "exp": "else runs when if is false."},
        {"q": "Which operator checks condition?", "options": ["=", "==", "?:", "!"], "correct": 2, "exp": "Ternary operator ?: checks condition."},
        {"q": "switch works with?", "options": ["int", "char", "enum", "All"], "correct": 3, "exp": "switch works with all."},
        {"q": "break used for?", "options": ["Exit loop", "Exit function", "Exit program", "Continue"], "correct": 0, "exp": "break exits loop or switch."}
    ],

    6: [
        {"q": "Which loop executes at least once?", "options": ["for", "while", "do-while", "none"], "correct": 2, "exp": "do-while runs at least once."},
        {"q": "for loop used when?", "options": ["Known count", "Unknown count", "Infinite", "None"], "correct": 0, "exp": "for loop used when count is known."},
        {"q": "while loop checks condition?", "options": ["Before loop", "After loop", "Never", "Random"], "correct": 0, "exp": "while checks condition before loop."},
        {"q": "continue skips?", "options": ["Loop", "Iteration", "Program", "Function"], "correct": 1, "exp": "continue skips iteration."},
        {"q": "Infinite loop example?", "options": ["for(;;)", "while(0)", "break", "return"], "correct": 0, "exp": "for(;;) is infinite loop."}
    ],

    7: [
        {"q": "Function is?", "options": ["Block", "Variable", "Loop", "File"], "correct": 0, "exp": "Function is block of code."},
        {"q": "main() returns?", "options": ["void", "float", "int", "char"], "correct": 2, "exp": "main returns int."},
        {"q": "Function prototype used for?", "options": ["Definition", "Declaration", "Execution", "Call"], "correct": 1, "exp": "Prototype declares function."},
        {"q": "Arguments passed to function?", "options": ["Always", "Optional", "Never", "Static"], "correct": 1, "exp": "Arguments are optional."},
        {"q": "Recursive function?", "options": ["Calls itself", "Calls other", "No call", "Loop"], "correct": 0, "exp": "Recursive function calls itself."}
    ],

    8: [
        {"q": "Array stores?", "options": ["Different types", "Same types", "Functions", "Pointers"], "correct": 1, "exp": "Array stores same datatype."},
        {"q": "Array index starts from?", "options": ["0", "1", "-1", "Any"], "correct": 0, "exp": "Array index starts from 0."},
        {"q": "Size of array fixed?", "options": ["Yes", "No"], "correct": 0, "exp": "Array size is fixed."},
        {"q": "2D array example?", "options": ["int a[5]", "int a[3][3]", "int *a", "int a()"], "correct": 1, "exp": "2D array uses rows and columns."},
        {"q": "Array name represents?", "options": ["Value", "Address", "Index", "Size"], "correct": 1, "exp": "Array name gives base address."}
    ],

    9: [
        {"q": "String in C is?", "options": ["Datatype", "Array of char", "Object", "Pointer"], "correct": 1, "exp": "String is array of characters."},
        {"q": "String ends with?", "options": ["\\0", "\\n", "EOF", "NULL"], "correct": 0, "exp": "String ends with null character."},
        {"q": "Which function prints string?", "options": ["printf", "puts", "Both", "None"], "correct": 2, "exp": "Both can print string."},
        {"q": "strlen() returns?", "options": ["Size", "Length", "Index", "Count"], "correct": 1, "exp": "strlen returns string length."},
        {"q": "strcpy() does?", "options": ["Compare", "Copy", "Concat", "Length"], "correct": 1, "exp": "strcpy copies string."}
    ],

    10: [
        {"q": "Pointer stores?", "options": ["Value", "Address", "Function", "Array"], "correct": 1, "exp": "Pointer stores address."},
        {"q": "Pointer declared using?", "options": ["&", "*", "#", "@"], "correct": 1, "exp": "* is used to declare pointer."},
        {"q": "& operator gives?", "options": ["Value", "Address", "Size", "Type"], "correct": 1, "exp": "& gives address."},
        {"q": "* operator gives?", "options": ["Address", "Value", "Size", "Index"], "correct": 1, "exp": "* dereferences pointer."},
        {"q": "Null pointer value?", "options": ["0", "-1", "NULL", "Both"], "correct": 3, "exp": "Null pointer can be 0 or NULL."}
    ],

    11: [
        {"q": "Structure keyword?", "options": ["struct", "union", "class", "object"], "correct": 0, "exp": "struct defines structure."},
        {"q": "Structure stores?", "options": ["Same type", "Different types", "Functions", "Pointers"], "correct": 1, "exp": "Structure stores different datatypes."},
        {"q": "Access structure member?", "options": [".", "->", "*", "&"], "correct": 0, "exp": ". accesses member."},
        {"q": "Pointer to structure uses?", "options": [".", "->", "&", "*"], "correct": 1, "exp": "-> accesses via pointer."},
        {"q": "Structure size depends on?", "options": ["Members", "Compiler", "OS", "All"], "correct": 3, "exp": "Depends on all factors."}
    ],

    12: [
        {"q": "Union stores?", "options": ["All values", "One at a time", "Functions", "Pointers"], "correct": 1, "exp": "Union stores one value at a time."},
        {"q": "Union size equals?", "options": ["Smallest member", "Largest member", "Sum", "Average"], "correct": 1, "exp": "Union size equals largest member."},
        {"q": "Enum used for?", "options": ["Constants", "Variables", "Pointers", "Arrays"], "correct": 0, "exp": "Enum defines constants."},
        {"q": "Enum values start from?", "options": ["0", "1", "-1", "Any"], "correct": 0, "exp": "Enum starts from 0."},
        {"q": "Typedef used for?", "options": ["Rename type", "Create variable", "Define macro", "Loop"], "correct": 0, "exp": "typedef renames datatype."}
    ],

    13: [
        {"q": "malloc() used for?", "options": ["Compile memory", "Dynamic memory", "Static memory", "Stack"], "correct": 1, "exp": "malloc allocates dynamic memory."},
        {"q": "calloc() initializes memory?", "options": ["Yes", "No"], "correct": 0, "exp": "calloc initializes memory."},
        {"q": "free() does?", "options": ["Allocate", "Release", "Initialize", "Copy"], "correct": 1, "exp": "free releases memory."},
        {"q": "Dangling pointer?", "options": ["Points freed memory", "Null pointer", "Valid pointer", "Array"], "correct": 0, "exp": "Dangling pointer points to freed memory."},
        {"q": "Memory leak occurs when?", "options": ["No free()", "Wrong loop", "Array", "Pointer"], "correct": 0, "exp": "Memory leak when memory not freed."}
    ],

    14: [
        {"q": "File pointer type?", "options": ["file", "FILE", "fp", "pointer"], "correct": 1, "exp": "FILE is file pointer type."},
        {"q": "Open file function?", "options": ["open()", "fopen()", "file()", "read()"], "correct": 1, "exp": "fopen opens file."},
        {"q": "Close file function?", "options": ["fclose()", "close()", "end()", "stop()"], "correct": 0, "exp": "fclose closes file."},
        {"q": "fgetc() reads?", "options": ["Line", "Word", "Character", "File"], "correct": 2, "exp": "fgetc reads character."},
        {"q": "fprintf() writes to?", "options": ["Console", "File", "Array", "Memory"], "correct": 1, "exp": "fprintf writes to file."}
    ],

    15: [
        {"q": "Preprocessor starts with?", "options": ["@", "#", "$", "&"], "correct": 1, "exp": "Preprocessor uses #."},
        {"q": "#include used for?", "options": ["Add library", "Loop", "Function", "Variable"], "correct": 0, "exp": "include adds library."},
        {"q": "#define used for?", "options": ["Function", "Macro", "Loop", "Pointer"], "correct": 1, "exp": "define creates macro."},
        {"q": "Macro replaced at?", "options": ["Runtime", "Compile time", "Link time", "Execution"], "correct": 1, "exp": "Macro replaced at compile time."},
        {"q": "C is case sensitive?", "options": ["Yes", "No"], "correct": 0, "exp": "C is case sensitive."}
    ]
}

QUESTIONS["cpp"] = {

    1: [
        {"q": "C++ was developed by?", "options": ["Dennis Ritchie", "Bjarne Stroustrup", "James Gosling", "Guido van Rossum"], "correct": 1, "exp": "C++ was developed by Bjarne Stroustrup."},
        {"q": "C++ is an extension of?", "options": ["Java", "Python", "C", "Pascal"], "correct": 2, "exp": "C++ is an extension of C."},
        {"q": "File extension of C++?", "options": [".c", ".java", ".cpp", ".py"], "correct": 2, "exp": ".cpp is C++ source file."},
        {"q": "Which symbol ends C++ statement?", "options": [":", ".", ";", ","], "correct": 2, "exp": "Semicolon ends statements."},
        {"q": "Which function starts execution?", "options": ["start()", "run()", "main()", "begin()"], "correct": 2, "exp": "main() is entry point."}
    ],

    2: [
        {"q": "Header file for cout?", "options": ["stdio.h", "iostream", "conio.h", "stdlib.h"], "correct": 1, "exp": "iostream contains cout."},
        {"q": "cout belongs to?", "options": ["stdio", "namespace std", "math", "string"], "correct": 1, "exp": "cout is in std namespace."},
        {"q": "cin is used for?", "options": ["Output", "Input", "File", "Memory"], "correct": 1, "exp": "cin reads input."},
        {"q": "endl does?", "options": ["Ends program", "New line", "Flush buffer", "Both"], "correct": 3, "exp": "endl prints new line and flushes buffer."},
        {"q": "using namespace std used for?", "options": ["Speed", "Avoid std::", "Memory", "Security"], "correct": 1, "exp": "Avoids writing std:: repeatedly."}
    ],

    3: [
        {"q": "Which is valid identifier?", "options": ["1num", "_num", "num-1", "float"], "correct": 1, "exp": "_num is valid identifier."},
        {"q": "Which keyword declares variable?", "options": ["var", "let", "int", "data"], "correct": 2, "exp": "int declares integer variable."},
        {"q": "Size of int (typically)?", "options": ["2 bytes", "4 bytes", "8 bytes", "1 byte"], "correct": 1, "exp": "int is typically 4 bytes."},
        {"q": "Which datatype stores decimal?", "options": ["int", "char", "float", "bool"], "correct": 2, "exp": "float stores decimal values."},
        {"q": "Which datatype stores true/false?", "options": ["int", "char", "bool", "float"], "correct": 2, "exp": "bool stores boolean values."}
    ],

    4: [
        {"q": "Which operator adds values?", "options": ["-", "+", "*", "/"], "correct": 1, "exp": "+ adds values."},
        {"q": "Which operator gives remainder?", "options": ["/", "*", "%", "+"], "correct": 2, "exp": "% gives remainder."},
        {"q": "Increment operator?", "options": ["++", "--", "+=", "*="], "correct": 0, "exp": "++ increments value."},
        {"q": "Equality operator?", "options": ["=", "==", "!=", "<"], "correct": 1, "exp": "== checks equality."},
        {"q": "Logical OR operator?", "options": ["||", "|", "&&", "&"], "correct": 0, "exp": "|| is logical OR."}
    ],

    5: [
        {"q": "if statement used for?", "options": ["Loop", "Decision", "Function", "Memory"], "correct": 1, "exp": "if used for decision making."},
        {"q": "switch works with?", "options": ["int", "char", "enum", "All"], "correct": 3, "exp": "switch works with all."},
        {"q": "break used for?", "options": ["Exit loop", "Exit function", "Exit program", "Continue"], "correct": 0, "exp": "break exits loop or switch."},
        {"q": "continue does?", "options": ["Stop loop", "Skip iteration", "Exit program", "Restart"], "correct": 1, "exp": "continue skips iteration."},
        {"q": "Default case in switch?", "options": ["Mandatory", "Optional", "Always first", "Not allowed"], "correct": 1, "exp": "default is optional."}
    ],

    6: [
        {"q": "Which loop executes at least once?", "options": ["for", "while", "do-while", "none"], "correct": 2, "exp": "do-while executes once."},
        {"q": "for loop used when?", "options": ["Known iterations", "Unknown", "Infinite", "None"], "correct": 0, "exp": "for loop for known iterations."},
        {"q": "while loop checks condition?", "options": ["Before", "After", "Never", "Random"], "correct": 0, "exp": "while checks before loop."},
        {"q": "Infinite loop example?", "options": ["for(;;)", "while(0)", "break", "return"], "correct": 0, "exp": "for(;;) is infinite loop."},
        {"q": "Nested loop means?", "options": ["Loop inside loop", "Loop in function", "Function in loop", "None"], "correct": 0, "exp": "Nested loop is loop inside loop."}
    ],

    7: [
        {"q": "Function is?", "options": ["Block of code", "Variable", "Loop", "File"], "correct": 0, "exp": "Function is block of code."},
        {"q": "Function return type?", "options": ["Mandatory", "Optional", "Always int", "None"], "correct": 1, "exp": "Return type can be void."},
        {"q": "Recursive function?", "options": ["Calls itself", "Calls other", "No call", "Loop"], "correct": 0, "exp": "Recursive calls itself."},
        {"q": "Default arguments?", "options": ["Allowed", "Not allowed"], "correct": 0, "exp": "C++ supports default arguments."},
        {"q": "Inline function purpose?", "options": ["Speed", "Memory", "Security", "None"], "correct": 0, "exp": "Inline improves speed."}
    ],

    8: [
        {"q": "OOP concept?", "options": ["Encapsulation", "Inheritance", "Polymorphism", "All"], "correct": 3, "exp": "All are OOP concepts."},
        {"q": "Class is?", "options": ["Object", "Blueprint", "Function", "Variable"], "correct": 1, "exp": "Class is blueprint."},
        {"q": "Object is?", "options": ["Blueprint", "Instance", "Function", "Method"], "correct": 1, "exp": "Object is instance of class."},
        {"q": "Access specifier?", "options": ["public", "private", "protected", "All"], "correct": 3, "exp": "All are access specifiers."},
        {"q": "Constructor is?", "options": ["Same as class", "Different name", "Optional", "Static"], "correct": 0, "exp": "Constructor name same as class."}
    ],

    9: [
        {"q": "Destructor purpose?", "options": ["Create object", "Destroy object", "Allocate memory", "Copy object"], "correct": 1, "exp": "Destructor destroys object."},
        {"q": "Destructor symbol?", "options": ["~", "!", "#", "*"], "correct": 0, "exp": "~ is destructor symbol."},
        {"q": "Copy constructor used for?", "options": ["Copy object", "Delete object", "Create array", "None"], "correct": 0, "exp": "Copy constructor copies object."},
        {"q": "Operator overloading means?", "options": ["Redefine operator", "Delete operator", "Create operator", "None"], "correct": 0, "exp": "Operator overloading redefines operator."},
        {"q": "Cannot overload operator?", "options": ["+", "=", "::", "*"], "correct": 2, "exp": ":: cannot be overloaded."}
    ],

    10: [
        {"q": "Inheritance type in C++?", "options": ["Single", "Multiple", "Multilevel", "All"], "correct": 3, "exp": "C++ supports all inheritance types."},
        {"q": "Virtual function used for?", "options": ["Compile binding", "Runtime polymorphism", "Memory", "Speed"], "correct": 1, "exp": "Virtual function supports runtime polymorphism."},
        {"q": "Virtual destructor?", "options": ["Yes", "No"], "correct": 0, "exp": "Virtual destructor recommended."},
        {"q": "Base class pointer to derived?", "options": ["Allowed", "Not allowed"], "correct": 0, "exp": "Allowed in polymorphism."},
        {"q": "Diamond problem solved by?", "options": ["Virtual inheritance", "Multiple inheritance", "Abstract class", "Interface"], "correct": 0, "exp": "Virtual inheritance solves diamond problem."}
    ],

    11: [
        {"q": "Pointer stores?", "options": ["Value", "Address", "Function", "Array"], "correct": 1, "exp": "Pointer stores address."},
        {"q": "Reference is?", "options": ["Pointer", "Alias", "Variable", "Object"], "correct": 1, "exp": "Reference is alias."},
        {"q": "nullptr introduced in?", "options": ["C++98", "C++03", "C++11", "C++17"], "correct": 2, "exp": "nullptr introduced in C++11."},
        {"q": "new keyword used for?", "options": ["Allocate memory", "Free memory", "Declare", "Loop"], "correct": 0, "exp": "new allocates memory."},
        {"q": "delete keyword used for?", "options": ["Allocate", "Free", "Copy", "Move"], "correct": 1, "exp": "delete frees memory."}
    ],

    12: [
        {"q": "STL stands for?", "options": ["Standard Template Library", "System Template Library", "Static Template Library", "None"], "correct": 0, "exp": "STL = Standard Template Library."},
        {"q": "Vector is?", "options": ["Array", "Dynamic array", "Linked list", "Queue"], "correct": 1, "exp": "Vector is dynamic array."},
        {"q": "Which container is LIFO?", "options": ["Queue", "Stack", "Deque", "List"], "correct": 1, "exp": "Stack follows LIFO."},
        {"q": "Which iterator moves forward only?", "options": ["Input", "Bidirectional", "Random", "All"], "correct": 0, "exp": "Input iterator moves forward only."},
        {"q": "Map stores?", "options": ["Key-value", "Only values", "Only keys", "Index"], "correct": 0, "exp": "Map stores key-value pairs."}
    ],

    13: [
        {"q": "Template used for?", "options": ["Generic programming", "OOP", "Memory", "Thread"], "correct": 0, "exp": "Templates support generic programming."},
        {"q": "Function template?", "options": ["Yes", "No"], "correct": 0, "exp": "C++ supports function templates."},
        {"q": "Class template?", "options": ["Yes", "No"], "correct": 0, "exp": "C++ supports class templates."},
        {"q": "Template instantiated at?", "options": ["Compile time", "Run time"], "correct": 0, "exp": "Templates are compile-time."},
        {"q": "Template specialization?", "options": ["Allowed", "Not allowed"], "correct": 0, "exp": "Template specialization allowed."}
    ],

    14: [
        {"q": "Exception handling keywords?", "options": ["try-catch", "throw", "finally", "All"], "correct": 3, "exp": "All are exception handling keywords."},
        {"q": "catch block handles?", "options": ["Exception", "Loop", "Function", "Class"], "correct": 0, "exp": "catch handles exception."},
        {"q": "throw keyword used for?", "options": ["Handle", "Raise exception", "Ignore", "Stop"], "correct": 1, "exp": "throw raises exception."},
        {"q": "Multiple catch allowed?", "options": ["Yes", "No"], "correct": 0, "exp": "Multiple catch blocks allowed."},
        {"q": "Standard exception base?", "options": ["exception", "error", "base", "throw"], "correct": 0, "exp": "std::exception is base class."}
    ],

    15: [
        {"q": "constexpr introduced in?", "options": ["C++03", "C++11", "C++14", "C++17"], "correct": 1, "exp": "constexpr introduced in C++11."},
        {"q": "Move semantics introduced in?", "options": ["C++98", "C++03", "C++11", "C++17"], "correct": 2, "exp": "Move semantics in C++11."},
        {"q": "Smart pointer example?", "options": ["auto_ptr", "unique_ptr", "shared_ptr", "Both"], "correct": 3, "exp": "unique_ptr & shared_ptr are smart pointers."},
        {"q": "RAII stands for?", "options": ["Resource Acquisition Is Initialization", "Random Allocation", "Runtime Init", "None"], "correct": 0, "exp": "RAII manages resources safely."},
        {"q": "C++ is?", "options": ["Procedural", "OOP", "Generic", "All"], "correct": 3, "exp": "C++ supports all paradigms."}
    ]
}

QUESTIONS["verbal"] = {

    1: [
        {"q": "Choose the correct synonym of 'Happy'", "options": ["Sad", "Joyful", "Angry", "Tired"], "correct": 1, "exp": "Joyful means happy."},
        {"q": "Choose the opposite of 'Big'", "options": ["Large", "Huge", "Small", "Wide"], "correct": 2, "exp": "Small is opposite of big."},
        {"q": "Fill in the blank: He ___ playing cricket.", "options": ["is", "are", "were", "be"], "correct": 0, "exp": "'He' takes 'is'."},
        {"q": "Choose correct spelling", "options": ["Definately", "Definitely", "Definetely", "Definatly"], "correct": 1, "exp": "Correct spelling is Definitely."},
        {"q": "Plural of 'Child'?", "options": ["Childs", "Children", "Childes", "Childrens"], "correct": 1, "exp": "Plural of child is children."}
    ],

    2: [
        {"q": "Synonym of 'Fast'", "options": ["Quick", "Slow", "Late", "Weak"], "correct": 0, "exp": "Quick means fast."},
        {"q": "Antonym of 'Hot'", "options": ["Warm", "Cold", "Heat", "Cool"], "correct": 1, "exp": "Cold is opposite of hot."},
        {"q": "Fill in the blank: She ___ a teacher.", "options": ["are", "is", "were", "be"], "correct": 1, "exp": "'She' takes 'is'."},
        {"q": "Choose correct spelling", "options": ["Recieve", "Receive", "Receeve", "Receve"], "correct": 1, "exp": "Correct spelling is Receive."},
        {"q": "Opposite of 'Early'", "options": ["Soon", "Late", "Fast", "Quick"], "correct": 1, "exp": "Late is opposite of early."}
    ],

    3: [
        {"q": "Synonym of 'Angry'", "options": ["Happy", "Furious", "Calm", "Quiet"], "correct": 1, "exp": "Furious means very angry."},
        {"q": "Antonym of 'Clean'", "options": ["Neat", "Dirty", "Pure", "Fresh"], "correct": 1, "exp": "Dirty is opposite of clean."},
        {"q": "Choose correct article: ___ apple", "options": ["A", "An", "The", "No article"], "correct": 1, "exp": "'An' used before vowel sound."},
        {"q": "Plural of 'Mouse'?", "options": ["Mouses", "Mices", "Mouse", "Mice"], "correct": 3, "exp": "Plural of mouse is mice."},
        {"q": "Choose correct spelling", "options": ["Beautifull", "Beautyful", "Beautiful", "Beutiful"], "correct": 2, "exp": "Correct spelling is Beautiful."}
    ],

    4: [
        {"q": "Synonym of 'Begin'", "options": ["Start", "End", "Stop", "Close"], "correct": 0, "exp": "Start means begin."},
        {"q": "Antonym of 'Strong'", "options": ["Powerful", "Weak", "Solid", "Hard"], "correct": 1, "exp": "Weak is opposite of strong."},
        {"q": "Fill in the blank: I ___ finished my work.", "options": ["has", "have", "had", "having"], "correct": 1, "exp": "'I' takes 'have'."},
        {"q": "Choose correct spelling", "options": ["Occured", "Occurred", "Occurrd", "Occureded"], "correct": 1, "exp": "Correct spelling is Occurred."},
        {"q": "Opposite of 'Rich'", "options": ["Wealthy", "Poor", "Strong", "Happy"], "correct": 1, "exp": "Poor is opposite of rich."}
    ],

    5: [
        {"q": "Synonym of 'Help'", "options": ["Assist", "Hurt", "Ignore", "Leave"], "correct": 0, "exp": "Assist means help."},
        {"q": "Antonym of 'Open'", "options": ["Close", "Wide", "Start", "Begin"], "correct": 0, "exp": "Close is opposite of open."},
        {"q": "Fill in the blank: They ___ going home.", "options": ["is", "are", "was", "be"], "correct": 1, "exp": "'They' takes 'are'."},
        {"q": "Choose correct spelling", "options": ["Succesful", "Successfull", "Successful", "Succesfull"], "correct": 2, "exp": "Correct spelling is Successful."},
        {"q": "Plural of 'Man'?", "options": ["Mans", "Men", "Manes", "Mens"], "correct": 1, "exp": "Plural of man is men."}
    ],

    6: [
        {"q": "Synonym of 'Brave'", "options": ["Coward", "Fearful", "Courageous", "Weak"], "correct": 2, "exp": "Courageous means brave."},
        {"q": "Antonym of 'Dark'", "options": ["Night", "Light", "Black", "Shade"], "correct": 1, "exp": "Light is opposite of dark."},
        {"q": "Choose correct spelling", "options": ["Enviroment", "Environment", "Envirnoment", "Enviornment"], "correct": 1, "exp": "Correct spelling is Environment."},
        {"q": "Fill in the blank: He ___ late yesterday.", "options": ["is", "was", "were", "be"], "correct": 1, "exp": "Past tense of 'is' is 'was'."},
        {"q": "Opposite of 'Buy'", "options": ["Sell", "Purchase", "Take", "Pay"], "correct": 0, "exp": "Sell is opposite of buy."}
    ],

    7: [
        {"q": "Synonym of 'Idea'", "options": ["Thought", "Thing", "Object", "Place"], "correct": 0, "exp": "Thought means idea."},
        {"q": "Antonym of 'Full'", "options": ["Filled", "Complete", "Empty", "Whole"], "correct": 2, "exp": "Empty is opposite of full."},
        {"q": "Choose correct spelling", "options": ["Knowlege", "Knowledge", "Knowledg", "Knowldge"], "correct": 1, "exp": "Correct spelling is Knowledge."},
        {"q": "Fill in the blank: We ___ seen the movie.", "options": ["has", "have", "had", "having"], "correct": 1, "exp": "'We' takes 'have'."},
        {"q": "Plural of 'Foot'?", "options": ["Foots", "Feets", "Feet", "Footes"], "correct": 2, "exp": "Plural of foot is feet."}
    ],

    8: [
        {"q": "Synonym of 'Silent'", "options": ["Quiet", "Loud", "Noisy", "Angry"], "correct": 0, "exp": "Quiet means silent."},
        {"q": "Antonym of 'Truth'", "options": ["Fact", "Lie", "Correct", "Right"], "correct": 1, "exp": "Lie is opposite of truth."},
        {"q": "Choose correct spelling", "options": ["Goverment", "Government", "Govermentt", "Governmant"], "correct": 1, "exp": "Correct spelling is Government."},
        {"q": "Fill in the blank: She ___ already left.", "options": ["has", "have", "had", "having"], "correct": 0, "exp": "'She' takes 'has'."},
        {"q": "Opposite of 'Win'", "options": ["Gain", "Lose", "Score", "Play"], "correct": 1, "exp": "Lose is opposite of win."}
    ],

    9: [
        {"q": "Synonym of 'Hard'", "options": ["Easy", "Difficult", "Soft", "Simple"], "correct": 1, "exp": "Difficult means hard."},
        {"q": "Antonym of 'New'", "options": ["Fresh", "Old", "Modern", "Latest"], "correct": 1, "exp": "Old is opposite of new."},
        {"q": "Choose correct spelling", "options": ["Adress", "Address", "Adres", "Addres"], "correct": 1, "exp": "Correct spelling is Address."},
        {"q": "Fill in the blank: I ___ going tomorrow.", "options": ["am", "is", "are", "was"], "correct": 0, "exp": "'I' takes 'am'."},
        {"q": "Plural of 'Tooth'?", "options": ["Tooths", "Teeth", "Toothes", "Tooth"], "correct": 1, "exp": "Plural of tooth is teeth."}
    ],

    10: [
        {"q": "Synonym of 'Quick'", "options": ["Slow", "Fast", "Late", "Weak"], "correct": 1, "exp": "Fast means quick."},
        {"q": "Antonym of 'Easy'", "options": ["Simple", "Hard", "Light", "Soft"], "correct": 1, "exp": "Hard is opposite of easy."},
        {"q": "Choose correct spelling", "options": ["Buisness", "Business", "Busines", "Bussiness"], "correct": 1, "exp": "Correct spelling is Business."},
        {"q": "Fill in the blank: They ___ playing now.", "options": ["is", "are", "was", "be"], "correct": 1, "exp": "'They' takes 'are'."},
        {"q": "Opposite of 'Accept'", "options": ["Receive", "Reject", "Agree", "Allow"], "correct": 1, "exp": "Reject is opposite of accept."}
    ],

    11: [
        {"q": "Synonym of 'Begin'", "options": ["Start", "Stop", "End", "Close"], "correct": 0, "exp": "Start means begin."},
        {"q": "Antonym of 'Brave'", "options": ["Bold", "Fearless", "Coward", "Strong"], "correct": 2, "exp": "Coward is opposite of brave."},
        {"q": "Choose correct spelling", "options": ["Tomorrow", "Tommorow", "Tomorow", "Tommorrow"], "correct": 0, "exp": "Correct spelling is Tomorrow."},
        {"q": "Fill in the blank: He ___ done his job.", "options": ["has", "have", "had", "having"], "correct": 0, "exp": "'He' takes 'has'."},
        {"q": "Plural of 'Woman'?", "options": ["Womans", "Women", "Womanes", "Womens"], "correct": 1, "exp": "Plural of woman is women."}
    ],

    12: [
        {"q": "Synonym of 'End'", "options": ["Finish", "Start", "Open", "Begin"], "correct": 0, "exp": "Finish means end."},
        {"q": "Antonym of 'Near'", "options": ["Close", "Far", "Next", "Beside"], "correct": 1, "exp": "Far is opposite of near."},
        {"q": "Choose correct spelling", "options": ["Frend", "Friend", "Freind", "Fried"], "correct": 1, "exp": "Correct spelling is Friend."},
        {"q": "Fill in the blank: We ___ late today.", "options": ["is", "are", "was", "be"], "correct": 1, "exp": "'We' takes 'are'."},
        {"q": "Opposite of 'Increase'", "options": ["Grow", "Rise", "Decrease", "Expand"], "correct": 2, "exp": "Decrease is opposite of increase."}
    ],

    13: [
        {"q": "Synonym of 'Strong'", "options": ["Weak", "Powerful", "Soft", "Thin"], "correct": 1, "exp": "Powerful means strong."},
        {"q": "Antonym of 'Always'", "options": ["Often", "Never", "Sometimes", "Daily"], "correct": 1, "exp": "Never is opposite of always."},
        {"q": "Choose correct spelling", "options": ["Favourite", "Favrite", "Favourit", "Favorate"], "correct": 0, "exp": "Correct spelling is Favourite."},
        {"q": "Fill in the blank: She ___ singing well.", "options": ["is", "are", "was", "be"], "correct": 0, "exp": "'She' takes 'is'."},
        {"q": "Plural of 'Goose'?", "options": ["Gooses", "Goose", "Geese", "Geeses"], "correct": 2, "exp": "Plural of goose is geese."}
    ],

    14: [
        {"q": "Synonym of 'Help'", "options": ["Assist", "Ignore", "Refuse", "Delay"], "correct": 0, "exp": "Assist means help."},
        {"q": "Antonym of 'Up'", "options": ["High", "Top", "Down", "Above"], "correct": 2, "exp": "Down is opposite of up."},
        {"q": "Choose correct spelling", "options": ["Calender", "Calendar", "Calandar", "Calender"], "correct": 1, "exp": "Correct spelling is Calendar."},
        {"q": "Fill in the blank: I ___ ready now.", "options": ["am", "is", "are", "was"], "correct": 0, "exp": "'I' takes 'am'."},
        {"q": "Opposite of 'Remember'", "options": ["Recall", "Forget", "Know", "Think"], "correct": 1, "exp": "Forget is opposite of remember."}
    ],

    15: [
        {"q": "Synonym of 'Smart'", "options": ["Intelligent", "Dull", "Lazy", "Slow"], "correct": 0, "exp": "Intelligent means smart."},
        {"q": "Antonym of 'Victory'", "options": ["Success", "Win", "Defeat", "Achieve"], "correct": 2, "exp": "Defeat is opposite of victory."},
        {"q": "Choose correct spelling", "options": ["Accomodation", "Accommodation", "Acomodation", "Accomadation"], "correct": 1, "exp": "Correct spelling is Accommodation."},
        {"q": "Fill in the blank: They ___ completed work.", "options": ["has", "have", "had", "having"], "correct": 1, "exp": "'They' takes 'have'."},
        {"q": "Opposite of 'Arrive'", "options": ["Reach", "Come", "Depart", "Enter"], "correct": 2, "exp": "Depart is opposite of arrive."}
    ]
}

QUESTIONS["aptitude"] = {

    1: [
        {"q": "What is 25% of 200?", "options": ["25", "50", "75", "100"], "correct": 1, "exp": "25% of 200 = (25/100)*200 = 50."},
        {"q": "Simplify: 10 + 5 × 2", "options": ["30", "20", "15", "25"], "correct": 1, "exp": "Multiplication first: 5×2=10, then 10+10=20."},
        {"q": "What is the square of 12?", "options": ["124", "144", "134", "154"], "correct": 1, "exp": "12×12 = 144."},
        {"q": "How many minutes in 2 hours?", "options": ["60", "90", "120", "150"], "correct": 2, "exp": "1 hour = 60 minutes, so 2 hours = 120 minutes."},
        {"q": "What is 50% of 80?", "options": ["30", "40", "50", "60"], "correct": 1, "exp": "50% means half, half of 80 is 40."}
    ],

    2: [
        {"q": "What is the average of 2, 4, 6?", "options": ["3", "4", "5", "6"], "correct": 1, "exp": "(2+4+6)/3 = 4."},
        {"q": "Simplify: 18 ÷ 3 + 4", "options": ["6", "10", "12", "14"], "correct": 1, "exp": "18÷3=6, 6+4=10."},
        {"q": "What is 15% of 100?", "options": ["10", "15", "20", "25"], "correct": 1, "exp": "15% of 100 = 15."},
        {"q": "How many sides does a triangle have?", "options": ["3", "4", "5", "6"], "correct": 0, "exp": "Triangle has 3 sides."},
        {"q": "What is the cube of 3?", "options": ["6", "9", "18", "27"], "correct": 3, "exp": "3³ = 27."}
    ],

    3: [
        {"q": "What is the LCM of 2 and 4?", "options": ["2", "4", "6", "8"], "correct": 1, "exp": "LCM of 2 and 4 is 4."},
        {"q": "Simplify: 5²", "options": ["10", "20", "25", "30"], "correct": 2, "exp": "5² = 25."},
        {"q": "What is the value of π (approx)?", "options": ["3.12", "3.14", "3.16", "3.18"], "correct": 1, "exp": "Approx value of π is 3.14."},
        {"q": "How many seconds in 1 minute?", "options": ["30", "45", "60", "90"], "correct": 2, "exp": "1 minute = 60 seconds."},
        {"q": "What is 7 × 8?", "options": ["54", "56", "58", "60"], "correct": 1, "exp": "7×8 = 56."}
    ],

    4: [
        {"q": "What is HCF of 6 and 12?", "options": ["2", "3", "6", "12"], "correct": 2, "exp": "HCF of 6 and 12 is 6."},
        {"q": "If cost price = selling price, profit is?", "options": ["Loss", "Profit", "No profit no loss", "Gain"], "correct": 2, "exp": "CP = SP means no profit no loss."},
        {"q": "What is 20% of 150?", "options": ["20", "25", "30", "35"], "correct": 2, "exp": "20% of 150 = 30."},
        {"q": "How many months in a year?", "options": ["10", "11", "12", "13"], "correct": 2, "exp": "1 year has 12 months."},
        {"q": "Which number is even?", "options": ["7", "9", "11", "12"], "correct": 3, "exp": "12 is an even number."}
    ],

    5: [
        {"q": "Simple interest formula?", "options": ["PTR/100", "P+R+T", "PR/T", "P/R×T"], "correct": 0, "exp": "SI = (P×T×R)/100."},
        {"q": "What is 10²?", "options": ["20", "50", "100", "200"], "correct": 2, "exp": "10² = 100."},
        {"q": "Find missing number: 2, 4, 6, ?", "options": ["7", "8", "9", "10"], "correct": 1, "exp": "Even numbers: 2,4,6,8."},
        {"q": "How many days in a week?", "options": ["5", "6", "7", "8"], "correct": 2, "exp": "A week has 7 days."},
        {"q": "What is 1000 ÷ 10?", "options": ["10", "50", "100", "1000"], "correct": 2, "exp": "1000 ÷ 10 = 100."}
    ],

    6: [
        {"q": "Ratio of 2:4 simplifies to?", "options": ["1:1", "1:2", "2:1", "4:2"], "correct": 1, "exp": "2:4 = 1:2."},
        {"q": "What is 60% of 50?", "options": ["20", "25", "30", "35"], "correct": 2, "exp": "60% of 50 = 30."},
        {"q": "Perimeter of square = ?", "options": ["4a", "a²", "2a", "a"], "correct": 0, "exp": "Perimeter = 4 × side."},
        {"q": "What comes next: 5, 10, 15, ?", "options": ["18", "20", "25", "30"], "correct": 1, "exp": "Add 5 each time."},
        {"q": "Which is prime number?", "options": ["4", "6", "9", "11"], "correct": 3, "exp": "11 is prime."}
    ],

    7: [
        {"q": "Area of square formula?", "options": ["2a", "a²", "4a", "a"], "correct": 1, "exp": "Area = side²."},
        {"q": "What is 1/2 of 1/4?", "options": ["1/2", "1/4", "1/8", "1/16"], "correct": 2, "exp": "½ × ¼ = ⅛."},
        {"q": "Find odd one out", "options": ["2", "4", "6", "9"], "correct": 3, "exp": "9 is odd, others even."},
        {"q": "How many zeros in 1 lakh?", "options": ["4", "5", "6", "7"], "correct": 1, "exp": "1 lakh = 100000 (5 zeros)."},
        {"q": "What is 9 × 9?", "options": ["72", "81", "90", "99"], "correct": 1, "exp": "9×9 = 81."}
    ],

    8: [
        {"q": "Speed = ?", "options": ["Distance/Time", "Time/Distance", "Distance×Time", "None"], "correct": 0, "exp": "Speed = Distance ÷ Time."},
        {"q": "Which is smallest?", "options": ["0.5", "0.25", "0.75", "1"], "correct": 1, "exp": "0.25 is smallest."},
        {"q": "What is 45% of 200?", "options": ["80", "85", "90", "95"], "correct": 2, "exp": "45% of 200 = 90."},
        {"q": "Which angle is 90°?", "options": ["Acute", "Obtuse", "Right", "Straight"], "correct": 2, "exp": "90° is right angle."},
        {"q": "Time in 1 day?", "options": ["12 hrs", "18 hrs", "24 hrs", "48 hrs"], "correct": 2, "exp": "1 day = 24 hours."}
    ],

    9: [
        {"q": "What is compound interest?", "options": ["Interest on principal", "Interest on interest", "Simple interest", "No interest"], "correct": 1, "exp": "CI is interest on interest."},
        {"q": "What is 3³?", "options": ["6", "9", "18", "27"], "correct": 3, "exp": "3³ = 27."},
        {"q": "Which is not a fraction?", "options": ["1/2", "2/3", "3/4", "5"], "correct": 3, "exp": "5 is whole number."},
        {"q": "How many degrees in straight angle?", "options": ["90", "120", "180", "360"], "correct": 2, "exp": "Straight angle = 180°."},
        {"q": "What is 144 ÷ 12?", "options": ["10", "11", "12", "13"], "correct": 2, "exp": "144 ÷ 12 = 12."}
    ],

    10: [
        {"q": "Mean of first 5 natural numbers?", "options": ["2", "3", "4", "5"], "correct": 1, "exp": "Mean = (1+2+3+4+5)/5 = 3."},
        {"q": "Which is multiple of 9?", "options": ["27", "28", "26", "25"], "correct": 0, "exp": "27 is multiple of 9."},
        {"q": "What is profit if CP=50, SP=60?", "options": ["5", "10", "15", "20"], "correct": 1, "exp": "Profit = 60−50 = 10."},
        {"q": "Convert 0.5 to fraction", "options": ["1/5", "1/4", "1/2", "2/5"], "correct": 2, "exp": "0.5 = 1/2."},
        {"q": "How many sides in pentagon?", "options": ["4", "5", "6", "7"], "correct": 1, "exp": "Pentagon has 5 sides."}
    ],

    11: [
        {"q": "What is 11²?", "options": ["111", "121", "131", "141"], "correct": 1, "exp": "11×11 = 121."},
        {"q": "What is speed unit?", "options": ["m/s", "kg", "m²", "sec"], "correct": 0, "exp": "Speed measured in m/s."},
        {"q": "What is 2/5 of 100?", "options": ["20", "30", "40", "50"], "correct": 2, "exp": "2/5 of 100 = 40."},
        {"q": "Which is composite number?", "options": ["2", "3", "5", "6"], "correct": 3, "exp": "6 has more than two factors."},
        {"q": "How many edges in cube?", "options": ["6", "8", "12", "16"], "correct": 2, "exp": "Cube has 12 edges."}
    ],

    12: [
        {"q": "Area of rectangle?", "options": ["l+b", "2l+b", "l×b", "2(lb)"], "correct": 2, "exp": "Area = length × breadth."},
        {"q": "What is 75% of 80?", "options": ["50", "55", "60", "65"], "correct": 2, "exp": "75% of 80 = 60."},
        {"q": "What is median?", "options": ["Middle value", "Average", "Sum", "Mode"], "correct": 0, "exp": "Median is middle value."},
        {"q": "Which is even prime?", "options": ["1", "2", "3", "5"], "correct": 1, "exp": "2 is only even prime."},
        {"q": "What is 9 × 7?", "options": ["56", "63", "72", "81"], "correct": 1, "exp": "9×7 = 63."}
    ],

    13: [
        {"q": "What is cube root of 27?", "options": ["2", "3", "4", "5"], "correct": 1, "exp": "Cube root of 27 is 3."},
        {"q": "What is 20% increase of 100?", "options": ["110", "115", "120", "125"], "correct": 2, "exp": "20% increase of 100 = 120."},
        {"q": "Which number divisible by 3?", "options": ["10", "14", "15", "22"], "correct": 2, "exp": "15 divisible by 3."},
        {"q": "Time = ?", "options": ["Distance×Speed", "Distance/Speed", "Speed/Distance", "None"], "correct": 1, "exp": "Time = Distance ÷ Speed."},
        {"q": "How many hours in 3 days?", "options": ["48", "60", "72", "96"], "correct": 2, "exp": "3 days = 72 hours."}
    ],

    14: [
        {"q": "What is 100% of 250?", "options": ["100", "200", "250", "300"], "correct": 2, "exp": "100% means whole = 250."},
        {"q": "What is square root of 81?", "options": ["7", "8", "9", "10"], "correct": 2, "exp": "√81 = 9."},
        {"q": "Ratio of 3:6 equals?", "options": ["1:1", "1:2", "2:1", "3:1"], "correct": 1, "exp": "3:6 = 1:2."},
        {"q": "Which is smallest prime?", "options": ["0", "1", "2", "3"], "correct": 2, "exp": "2 is smallest prime."},
        {"q": "How many faces in cube?", "options": ["4", "6", "8", "12"], "correct": 1, "exp": "Cube has 6 faces."}
    ],

    15: [
        {"q": "Average of 10 and 20?", "options": ["10", "15", "20", "25"], "correct": 1, "exp": "(10+20)/2 = 15."},
        {"q": "What is 30% of 300?", "options": ["60", "70", "80", "90"], "correct": 3, "exp": "30% of 300 = 90."},
        {"q": "Simple interest of 100 at 10% for 1 year?", "options": ["5", "10", "15", "20"], "correct": 1, "exp": "SI = (100×10×1)/100 = 10."},
        {"q": "Which is perfect square?", "options": ["18", "25", "32", "50"], "correct": 1, "exp": "25 = 5²."},
        {"q": "What is 8³?", "options": ["256", "512", "1024", "2048"], "correct": 1, "exp": "8³ = 512."}
    ]
}

QUESTIONS["mixed"] = {

# ================= LEVEL 1 =================
1: [
    # Python (3)
    {"q":"Python function keyword?","options":["func","define","def","function"],"correct":2,"exp":"def defines function."},
    {"q":"len('Hi') output?","options":["1","2","3","Error"],"correct":1,"exp":"Length of 'Hi' is 2."},
    {"q":"Python comment symbol?","options":["//","#","/*","--"],"correct":1,"exp":"# is used for comments."},

    # Java (3)
    {"q":"Java entry point?","options":["start()","run()","main()","init()"],"correct":2,"exp":"main() is entry point."},
    {"q":"Java inheritance keyword?","options":["inherits","extends","implements","super"],"correct":1,"exp":"extends used."},
    {"q":"Default Java package?","options":["java.util","java.io","java.lang","java.net"],"correct":2,"exp":"java.lang auto imported."},

    # C (3)
    {"q":"C file extension?","options":[".cpp",".c",".java",".py"],"correct":1,"exp":".c is C file."},
    {"q":"C program starts from?","options":["start","main","begin","run"],"correct":1,"exp":"Execution starts from main()."},
    {"q":"Format specifier for int?","options":["%f","%c","%d","%s"],"correct":2,"exp":"%d for int."},

    # C++ (3)
    {"q":"Header for cout?","options":["stdio.h","iostream","math.h","string"],"correct":1,"exp":"iostream contains cout."},
    {"q":"Destructor symbol?","options":["!","~","#","*"],"correct":1,"exp":"~ is destructor."},
    {"q":"OOP feature?","options":["Loop","Array","Polymorphism","Pointer"],"correct":2,"exp":"Polymorphism is OOP."},

    # SQL (3)
    {"q":"Fetch data command?","options":["GET","SELECT","FETCH","READ"],"correct":1,"exp":"SELECT fetches data."},
    {"q":"Filter rows clause?","options":["WHERE","HAVING","GROUP","ORDER"],"correct":0,"exp":"WHERE filters rows."},
    {"q":"Primary key allows?","options":["Duplicates","NULL","Unique","All"],"correct":2,"exp":"Primary key unique."},

    # Aptitude (1)
    {"q":"25% of 100?","options":["15","20","25","30"],"correct":2,"exp":"25% of 100 = 25."},

    # Verbal (1)
    {"q":"Synonym of Fast","options":["Slow","Quick","Late","Weak"],"correct":1,"exp":"Quick means fast."}
],

# ================= LEVEL 2 =================
2: [
    # Python
    {"q":"Which is mutable?","options":["tuple","string","list","int"],"correct":2,"exp":"List is mutable."},
    {"q":"True belongs to which type?","options":["int","str","bool","float"],"correct":2,"exp":"True is boolean."},

    # Java
    {"q":"Object creation keyword?","options":["class","new","make","object"],"correct":1,"exp":"new creates object."},
    {"q":"Java loop keyword?","options":["foreach","repeat","for","loop"],"correct":2,"exp":"for loop exists."},

    # C
    {"q":"Logical AND operator?","options":["&","&&","|","||"],"correct":1,"exp":"&& logical AND."},
    {"q":"Array index starts from?","options":["0","1","-1","any"],"correct":0,"exp":"Index starts from 0."},

    # C++
    {"q":"Reference means?","options":["Pointer","Alias","Object","Copy"],"correct":1,"exp":"Reference is alias."},
    {"q":"new keyword does?","options":["Free","Allocate","Delete","Compare"],"correct":1,"exp":"new allocates memory."},

    # SQL
    {"q":"Remove duplicate rows?","options":["UNIQUE","DELETE","DISTINCT","DROP"],"correct":2,"exp":"DISTINCT removes duplicates."},
    {"q":"Sort results?","options":["GROUP","ORDER BY","WHERE","HAVING"],"correct":1,"exp":"ORDER BY sorts data."},

    # Aptitude
    {"q":"10 + 5 × 2 = ?","options":["20","30","25","15"],"correct":0,"exp":"5×2=10 → 10+10=20."},
    {"q":"Square of 9?","options":["18","27","81","72"],"correct":2,"exp":"9² = 81."},

    # Verbal
    {"q":"Opposite of Big","options":["Huge","Large","Small","Wide"],"correct":2,"exp":"Small is opposite."},
    {"q":"Correct spelling","options":["Recieve","Receive","Receeve","Receve"],"correct":1,"exp":"Receive is correct."},
    {"q":"Plural of Child","options":["Childs","Children","Childes","Childrens"],"correct":1,"exp":"Children is plural."},
    {"q":"Opposite of Happy","options":["Sad","Joyful","Angry","Smile"],"correct":0,"exp":"Sad is opposite."}
],

# ================= LEVEL 3 =================
3: [
    # Python
    {"q":"Power operator in Python?","options":["^","**","//","%"],"correct":1,"exp":"** is power operator."},
    {"q":"for loop used for?","options":["Decision","Iteration","Function","Class"],"correct":1,"exp":"for loop iterates."},

    # Java
    {"q":"final keyword used for?","options":["Inheritance","Override","Constant","Loop"],"correct":2,"exp":"final creates constant."},
    {"q":"Polymorphism allows?","options":["Same name","Same data","Same file","Same class"],"correct":0,"exp":"Same method name."},

    # C
    {"q":"Pointer stores?","options":["Value","Address","Char","Array"],"correct":1,"exp":"Pointer stores address."},
    {"q":"sizeof gives?","options":["Value","Address","Size","Type"],"correct":2,"exp":"sizeof gives size."},

    # C++
    {"q":"Virtual function used for?","options":["Compile","Runtime polymorphism","Memory","Speed"],"correct":1,"exp":"Runtime polymorphism."},
    {"q":"STL container example?","options":["vector","class","loop","file"],"correct":0,"exp":"vector is STL."},

    # SQL
    {"q":"INNER JOIN returns?","options":["All rows","Matching rows","Left rows","Right rows"],"correct":1,"exp":"INNER JOIN returns matches."},
    {"q":"COUNT() returns?","options":["Sum","Average","Rows","Max"],"correct":2,"exp":"COUNT returns rows."},

    # Aptitude
    {"q":"Average of 2,4,6?","options":["3","4","5","6"],"correct":1,"exp":"Average is 4."},
    {"q":"LCM of 2 and 4?","options":["2","4","6","8"],"correct":1,"exp":"LCM is 4."},

    # Verbal
    {"q":"Synonym of Happy","options":["Sad","Joyful","Angry","Tired"],"correct":1,"exp":"Joyful means happy."},
    {"q":"Opposite of Early","options":["Late","Soon","Fast","Quick"],"correct":0,"exp":"Late is opposite."},
    {"q":"Correct spelling","options":["Definately","Definitely","Definetely","Definatly"],"correct":1,"exp":"Definitely is correct."},
    {"q":"Plural of Foot","options":["Foots","Feet","Feets","Footes"],"correct":1,"exp":"Feet is plural."}
],

# ================= LEVEL 4 =================
4: [
    # Python
    {"q":"Tuple is?","options":["Mutable","Immutable","Dynamic","None"],"correct":1,"exp":"Tuple is immutable."},
    {"q":"Dictionary stores?","options":["Values","Keys","Key-value","Index"],"correct":2,"exp":"Dict stores key-value."},

    # Java
    {"q":"Which supports multiple inheritance?","options":["Class","Interface","Object","Package"],"correct":1,"exp":"Interface supports it."},
    {"q":"Which keyword creates object?","options":["make","new","create","class"],"correct":1,"exp":"new creates object."},

    # C
    {"q":"Which loop executes once?","options":["for","while","do-while","none"],"correct":2,"exp":"do-while runs once."},
    {"q":"String ends with?","options":["\\n","\\0","EOF","NULL"],"correct":1,"exp":"\\0 ends string."},

    # C++
    {"q":"Constructor name?","options":["Different","Same as class","Any","Optional"],"correct":1,"exp":"Constructor same as class."},
    {"q":"Destructor called when?","options":["Create","Destroy","Compile","Run"],"correct":1,"exp":"Called on destroy."},

    # SQL
    {"q":"GROUP BY used with?","options":["WHERE","Aggregate","JOIN","INSERT"],"correct":1,"exp":"GROUP BY with aggregates."},
    {"q":"HAVING used for?","options":["Rows","Groups","Sort","Join"],"correct":1,"exp":"HAVING filters groups."},

    # Aptitude
    {"q":"20% of 150?","options":["20","25","30","35"],"correct":2,"exp":"20% of 150 = 30."},
    {"q":"Cube of 3?","options":["9","18","27","36"],"correct":2,"exp":"3³ = 27."},

    # Verbal
    {"q":"Synonym of Begin","options":["Start","Stop","Close","End"],"correct":0,"exp":"Start means begin."},
    {"q":"Opposite of Rich","options":["Wealthy","Poor","Strong","Happy"],"correct":1,"exp":"Poor opposite."},
    {"q":"Correct spelling","options":["Enviroment","Environment","Envirnoment","Enviornment"],"correct":1,"exp":"Environment correct."},
    {"q":"Plural of Man","options":["Mans","Men","Manes","Mens"],"correct":1,"exp":"Men is plural."}
],

# ================= LEVEL 5 =================
5: [
    # Python
    {"q":"List comprehension used for?","options":["Loop","Short code","Speed","Class"],"correct":1,"exp":"Short way to create list."},
    {"q":"Which is keyword?","options":["append","len","print","class"],"correct":3,"exp":"class is keyword."},

    # Java
    {"q":"JVM stands for?","options":["Java VM","Java Virtual Machine","Joint VM","None"],"correct":1,"exp":"JVM = Java Virtual Machine."},
    {"q":"Which is checked exception?","options":["NullPointer","IOException","ArrayIndex","Arithmetic"],"correct":1,"exp":"IOException is checked."},

    # C
    {"q":"malloc() used for?","options":["Static","Dynamic","Stack","Register"],"correct":1,"exp":"malloc allocates dynamic memory."},
    {"q":"free() used for?","options":["Allocate","Release","Copy","Init"],"correct":1,"exp":"free releases memory."},

    # C++
    {"q":"Which supports templates?","options":["C","Java","C++","Python"],"correct":2,"exp":"C++ supports templates."},
    {"q":"Smart pointer example?","options":["auto","unique_ptr","raw","normal"],"correct":1,"exp":"unique_ptr is smart pointer."},

    # SQL
    {"q":"TRUNCATE removes?","options":["Some rows","All rows","Table","DB"],"correct":1,"exp":"TRUNCATE removes all rows."},
    {"q":"DROP removes?","options":["Rows","Table","Data","Index"],"correct":1,"exp":"DROP deletes table."},

    # Aptitude
    {"q":"SI formula?","options":["PTR/100","PRT","P+R+T","None"],"correct":0,"exp":"SI = PTR/100."},
    {"q":"Speed formula?","options":["D/T","T/D","D×T","None"],"correct":0,"exp":"Speed = Distance/Time."},

    # Verbal
    {"q":"Synonym of Help","options":["Assist","Ignore","Refuse","Delay"],"correct":0,"exp":"Assist = Help."},
    {"q":"Opposite of Accept","options":["Receive","Reject","Agree","Allow"],"correct":1,"exp":"Reject opposite."},
    {"q":"Correct spelling","options":["Succesful","Successfull","Successful","Succesfull"],"correct":2,"exp":"Successful correct."},
    {"q":"Plural of Goose","options":["Gooses","Geese","Goose","Geeses"],"correct":1,"exp":"Geese plural."}
],
}
# ================= LEVEL 6 =================
QUESTIONS["mixed"].update({

6: [
    # Python
    {"q":"Which keyword handles exceptions?","options":["try","catch","handle","error"],"correct":0,"exp":"try is used for exception handling."},
    {"q":"Output of bool(0)?","options":["True","False","0","Error"],"correct":1,"exp":"bool(0) is False."},

    # Java
    {"q":"Which is runtime exception?","options":["IOException","SQLException","NullPointerException","FileNotFound"],"correct":2,"exp":"NullPointerException is runtime."},
    {"q":"Which keyword prevents inheritance?","options":["static","final","private","abstract"],"correct":1,"exp":"final prevents inheritance."},

    # C
    {"q":"Which operator is ternary?","options":["?:","&&","||","=="],"correct":0,"exp":"?: is ternary operator."},
    {"q":"Which header for printf?","options":["stdlib.h","stdio.h","math.h","string.h"],"correct":1,"exp":"stdio.h has printf."},

    # C++
    {"q":"Which supports function overloading?","options":["C","Java","C++","Assembly"],"correct":2,"exp":"C++ supports overloading."},
    {"q":"Which keyword creates object dynamically?","options":["malloc","alloc","new","create"],"correct":2,"exp":"new allocates object."},

    # SQL
    {"q":"Which command deletes specific rows?","options":["DROP","TRUNCATE","DELETE","REMOVE"],"correct":2,"exp":"DELETE removes selected rows."},
    {"q":"Which constraint avoids NULL?","options":["PRIMARY","UNIQUE","NOT NULL","CHECK"],"correct":2,"exp":"NOT NULL avoids null values."},

    # Aptitude
    {"q":"30% of 200?","options":["40","50","60","70"],"correct":2,"exp":"30% of 200 = 60."},
    {"q":"Average of 10,20,30?","options":["15","20","25","30"],"correct":1,"exp":"Average = 20."},

    # Verbal
    {"q":"Synonym of Smart","options":["Intelligent","Slow","Lazy","Weak"],"correct":0,"exp":"Intelligent means smart."},
    {"q":"Opposite of Increase","options":["Grow","Rise","Decrease","Expand"],"correct":2,"exp":"Decrease is opposite."},
    {"q":"Correct spelling","options":["Buisness","Business","Busines","Bussiness"],"correct":1,"exp":"Business is correct."},
    {"q":"Plural of Tooth","options":["Tooths","Teeth","Toothes","Tooth"],"correct":1,"exp":"Teeth is plural."}
],

# ================= LEVEL 7 =================
7: [
    # Python
    {"q":"Which is immutable?","options":["list","set","tuple","dict"],"correct":2,"exp":"Tuple is immutable."},
    {"q":"Which function converts to int?","options":["str()","float()","int()","bool()"],"correct":2,"exp":"int() converts to integer."},

    # Java
    {"q":"Which collection allows duplicates?","options":["Set","Map","List","None"],"correct":2,"exp":"List allows duplicates."},
    {"q":"Which keyword calls parent constructor?","options":["this","super","parent","base"],"correct":1,"exp":"super calls parent constructor."},

    # C
    {"q":"Which loop checks condition at end?","options":["for","while","do-while","if"],"correct":2,"exp":"do-while checks at end."},
    {"q":"EOF stands for?","options":["End of File","End of Function","Error of File","None"],"correct":0,"exp":"EOF = End of File."},

    # C++
    {"q":"Which is not OOP concept?","options":["Encapsulation","Polymorphism","Compilation","Inheritance"],"correct":2,"exp":"Compilation is not OOP."},
    {"q":"Which operator overloadable?","options":["::","?:","+","sizeof"],"correct":2,"exp":"+ can be overloaded."},

    # SQL
    {"q":"Which clause groups rows?","options":["WHERE","GROUP BY","ORDER BY","HAVING"],"correct":1,"exp":"GROUP BY groups rows."},
    {"q":"Which join returns all rows from left?","options":["INNER","RIGHT","LEFT","FULL"],"correct":2,"exp":"LEFT JOIN returns left rows."},

    # Aptitude
    {"q":"Ratio of 4:8 simplified?","options":["1:1","1:2","2:1","4:2"],"correct":1,"exp":"4:8 = 1:2."},
    {"q":"Square root of 64?","options":["6","7","8","9"],"correct":2,"exp":"√64 = 8."},

    # Verbal
    {"q":"Synonym of Silent","options":["Quiet","Noisy","Loud","Angry"],"correct":0,"exp":"Quiet means silent."},
    {"q":"Opposite of Win","options":["Gain","Score","Lose","Play"],"correct":2,"exp":"Lose is opposite."},
    {"q":"Correct spelling","options":["Knowlege","Knowledge","Knowldge","Knowlegee"],"correct":1,"exp":"Knowledge is correct."},
    {"q":"Plural of Woman","options":["Womans","Women","Womanes","Womens"],"correct":1,"exp":"Women is plural."}
],

# ================= LEVEL 8 =================
8: [
    # Python
    {"q":"Which keyword creates generator?","options":["yield","return","gen","produce"],"correct":0,"exp":"yield creates generator."},
    {"q":"Output of type([])?","options":["list","tuple","dict","set"],"correct":0,"exp":"[] is list."},

    # Java
    {"q":"Which interface supports sorting?","options":["Runnable","Comparable","Serializable","Cloneable"],"correct":1,"exp":"Comparable supports sorting."},
    {"q":"Which keyword makes method abstract?","options":["final","abstract","static","private"],"correct":1,"exp":"abstract keyword."},

    # C
    {"q":"Which function compares strings?","options":["strcpy","strcmp","strlen","strcat"],"correct":1,"exp":"strcmp compares strings."},
    {"q":"Which operator is NOT logical?","options":["&&","||","!","%"],"correct":3,"exp":"% is arithmetic."},

    # C++
    {"q":"Which is STL algorithm?","options":["sort","array","class","object"],"correct":0,"exp":"sort is STL algorithm."},
    {"q":"Which cast is safest?","options":["C cast","static_cast","reinterpret_cast","const_cast"],"correct":1,"exp":"static_cast is safest."},

    # SQL
    {"q":"Which command adds column?","options":["INSERT","ADD","ALTER","UPDATE"],"correct":2,"exp":"ALTER adds column."},
    {"q":"Which function gives max value?","options":["MAX()","TOP()","HIGH()","LARGE()"],"correct":0,"exp":"MAX returns highest."},

    # Aptitude
    {"q":"Time = Distance / ?","options":["Speed","Time","Work","Power"],"correct":0,"exp":"Time = Distance/Speed."},
    {"q":"40% of 250?","options":["80","90","100","110"],"correct":2,"exp":"40% of 250 = 100."},

    # Verbal
    {"q":"Synonym of Strong","options":["Weak","Powerful","Soft","Thin"],"correct":1,"exp":"Powerful means strong."},
    {"q":"Opposite of Truth","options":["Fact","Lie","Correct","Right"],"correct":1,"exp":"Lie is opposite."},
    {"q":"Correct spelling","options":["Goverment","Government","Govermentt","Governmant"],"correct":1,"exp":"Government is correct."},
    {"q":"Plural of Goose","options":["Gooses","Geese","Goose","Geeses"],"correct":1,"exp":"Geese is plural."}
],

# ================= LEVEL 9 =================
9: [
    # Python
    {"q":"Which module handles math ops?","options":["sys","math","random","os"],"correct":1,"exp":"math module."},
    {"q":"Which keyword defines lambda?","options":["lambda","def","func","anon"],"correct":0,"exp":"lambda defines anonymous function."},

    # Java
    {"q":"Which stream prints output?","options":["System.in","System.out","System.err","Scanner"],"correct":1,"exp":"System.out prints."},
    {"q":"Which keyword stops loop?","options":["break","stop","exit","end"],"correct":0,"exp":"break stops loop."},

    # C
    {"q":"Which function allocates memory?","options":["malloc","printf","scanf","sizeof"],"correct":0,"exp":"malloc allocates memory."},
    {"q":"Which data type stores character?","options":["int","char","float","double"],"correct":1,"exp":"char stores character."},

    # C++
    {"q":"Which supports multiple inheritance?","options":["Java","C","C++","Python"],"correct":2,"exp":"C++ supports multiple inheritance."},
    {"q":"Which keyword avoids copying?","options":["move","delete","const","explicit"],"correct":3,"exp":"explicit avoids implicit conversion."},

    # SQL
    {"q":"Which joins all rows?","options":["INNER","LEFT","RIGHT","FULL"],"correct":3,"exp":"FULL JOIN returns all rows."},
    {"q":"Which constraint enforces relation?","options":["PRIMARY","FOREIGN","UNIQUE","CHECK"],"correct":1,"exp":"FOREIGN KEY enforces relation."},

    # Aptitude
    {"q":"Cube root of 125?","options":["4","5","6","7"],"correct":1,"exp":"∛125 = 5."},
    {"q":"Profit if CP=80, SP=100?","options":["10","15","20","25"],"correct":2,"exp":"Profit = 20."},

    # Verbal
    {"q":"Synonym of End","options":["Finish","Begin","Open","Start"],"correct":0,"exp":"Finish means end."},
    {"q":"Opposite of Near","options":["Close","Next","Far","Beside"],"correct":2,"exp":"Far is opposite."},
    {"q":"Correct spelling","options":["Adress","Address","Adres","Addres"],"correct":1,"exp":"Address correct."},
    {"q":"Plural of Ox","options":["Oxes","Oxen","Oxs","Ox"],"correct":1,"exp":"Oxen is plural."}
],

# ================= LEVEL 10 =================
10: [
    # Python
    {"q":"Which keyword creates class?","options":["class","def","object","struct"],"correct":0,"exp":"class keyword."},
    {"q":"Which function sorts list?","options":["order()","sort()","arrange()","sortedlist()"],"correct":1,"exp":"sort() sorts list."},

    # Java
    {"q":"Which keyword catches exception?","options":["try","throw","catch","error"],"correct":2,"exp":"catch handles exception."},
    {"q":"Which collection is synchronized?","options":["ArrayList","HashMap","Vector","HashSet"],"correct":2,"exp":"Vector is synchronized."},

    # C
    {"q":"Which operator gives address?","options":["*","&","%","@"],"correct":1,"exp":"& gives address."},
    {"q":"Which header for malloc?","options":["stdio.h","stdlib.h","math.h","string.h"],"correct":1,"exp":"stdlib.h has malloc."},

    # C++
    {"q":"Which concept binds data & function?","options":["Inheritance","Encapsulation","Polymorphism","Abstraction"],"correct":1,"exp":"Encapsulation binds data."},
    {"q":"Which keyword avoids inheritance?","options":["static","private","final","virtual"],"correct":2,"exp":"final avoids inheritance."},

    # SQL
    {"q":"Which removes table?","options":["DELETE","DROP","TRUNCATE","REMOVE"],"correct":1,"exp":"DROP removes table."},
    {"q":"Which clause filters groups?","options":["WHERE","GROUP","HAVING","ORDER"],"correct":2,"exp":"HAVING filters groups."},

    # Aptitude
    {"q":"SI of 100 at 10% for 1 year?","options":["5","10","15","20"],"correct":1,"exp":"SI = 10."},
    {"q":"Speed formula?","options":["D/T","T/D","D×T","None"],"correct":0,"exp":"Speed = Distance/Time."},

    # Verbal
    {"q":"Synonym of Help","options":["Assist","Ignore","Refuse","Delay"],"correct":0,"exp":"Assist means help."},
    {"q":"Opposite of Accept","options":["Receive","Reject","Agree","Allow"],"correct":1,"exp":"Reject opposite."},
    {"q":"Correct spelling","options":["Succesful","Successfull","Successful","Succesfull"],"correct":2,"exp":"Successful correct."},
    {"q":"Plural of Deer","options":["Deers","Deer","Deeres","DeerS"],"correct":1,"exp":"Deer is same plural."}
]

})
# ================= LEVEL 11 =================
QUESTIONS["mixed"].update({

11: [
    # Python
    {"q":"Which keyword skips current loop iteration?","options":["break","pass","continue","skip"],"correct":2,"exp":"continue skips current iteration."},
    {"q":"Output of len([1,2,3])?","options":["2","3","4","Error"],"correct":1,"exp":"List has 3 elements."},

    # Java
    {"q":"Which keyword is used to throw exception?","options":["throw","throws","catch","error"],"correct":0,"exp":"throw explicitly throws exception."},
    {"q":"Which collection does not allow duplicates?","options":["List","Map","Set","ArrayList"],"correct":2,"exp":"Set does not allow duplicates."},

    # C
    {"q":"Which symbol represents logical OR?","options":["|","||","&","&&"],"correct":1,"exp":"|| is logical OR."},
    {"q":"Which function reads string?","options":["scanf","gets","puts","printf"],"correct":1,"exp":"gets reads string (unsafe but classic)."}, 

    # C++
    {"q":"Which keyword makes function virtual?","options":["virtual","override","final","static"],"correct":0,"exp":"virtual enables runtime binding."},
    {"q":"Which operator cannot be overloaded?","options":["+","-","::","[]"],"correct":2,"exp":"Scope resolution (::) cannot be overloaded."},

    # SQL
    {"q":"Which command renames table?","options":["RENAME","ALTER","CHANGE","MODIFY"],"correct":1,"exp":"ALTER TABLE used to rename."},
    {"q":"Which aggregate gives average?","options":["SUM","AVG","COUNT","MAX"],"correct":1,"exp":"AVG gives average."},

    # Aptitude
    {"q":"What is 15% of 200?","options":["20","25","30","35"],"correct":2,"exp":"15% of 200 = 30."},
    {"q":"If x=5, find x²","options":["10","20","25","30"],"correct":2,"exp":"5² = 25."},

    # Verbal
    {"q":"Synonym of Difficult","options":["Easy","Hard","Soft","Weak"],"correct":1,"exp":"Hard means difficult."},
    {"q":"Opposite of Buy","options":["Purchase","Take","Sell","Pay"],"correct":2,"exp":"Sell is opposite of buy."},
    {"q":"Correct spelling","options":["Occured","Occurred","Occurrd","Occureded"],"correct":1,"exp":"Occurred is correct spelling."},
    {"q":"Plural of Mouse","options":["Mouses","Mice","Mouse","Mices"],"correct":1,"exp":"Mice is plural of mouse."}
],

# ================= LEVEL 12 =================
12: [
    # Python
    {"q":"Which keyword deletes object?","options":["remove","delete","del","clear"],"correct":2,"exp":"del deletes reference."},
    {"q":"Which function opens file?","options":["file()","open()","read()","load()"],"correct":1,"exp":"open() opens file."},

    # Java
    {"q":"Which keyword is used to inherit interface?","options":["extends","implements","inherits","super"],"correct":1,"exp":"implements used for interface."},
    {"q":"Which exception is checked?","options":["NullPointer","Arithmetic","IOException","IndexOut"],"correct":2,"exp":"IOException is checked exception."},

    # C
    {"q":"Which keyword defines constant?","options":["const","static","define","fixed"],"correct":0,"exp":"const defines constant."},
    {"q":"Which loop runs infinite?","options":["for(;;)","while(0)","if","switch"],"correct":0,"exp":"for(;;) infinite loop."},

    # C++
    {"q":"Which feature hides data?","options":["Inheritance","Encapsulation","Polymorphism","Abstraction"],"correct":1,"exp":"Encapsulation hides data."},
    {"q":"Which pointer auto deletes memory?","options":["raw","auto","unique_ptr","normal"],"correct":2,"exp":"unique_ptr auto deletes memory."},

    # SQL
    {"q":"Which constraint ensures uniqueness?","options":["FOREIGN","UNIQUE","CHECK","DEFAULT"],"correct":1,"exp":"UNIQUE ensures unique values."},
    {"q":"Which clause limits rows?","options":["WHERE","LIMIT","ORDER","GROUP"],"correct":1,"exp":"LIMIT restricts rows."},

    # Aptitude
    {"q":"What is 50% of 90?","options":["35","40","45","50"],"correct":2,"exp":"50% of 90 = 45."},
    {"q":"Find next number: 2,4,8,16, ?","options":["18","24","32","64"],"correct":2,"exp":"Multiply by 2 → 32."},

    # Verbal
    {"q":"Synonym of Brave","options":["Coward","Fearful","Bold","Weak"],"correct":2,"exp":"Bold means brave."},
    {"q":"Opposite of Open","options":["Wide","Close","Begin","Start"],"correct":1,"exp":"Close is opposite."},
    {"q":"Correct spelling","options":["Calender","Calendar","Calandar","Calender"],"correct":1,"exp":"Calendar correct."},
    {"q":"Plural of Woman","options":["Womans","Women","Womens","Womanes"],"correct":1,"exp":"Women is plural."}
],

# ================= LEVEL 13 =================
13: [
    # Python
    {"q":"Which data type stores key-value?","options":["list","tuple","dict","set"],"correct":2,"exp":"dict stores key-value pairs."},
    {"q":"Which keyword handles error block?","options":["except","error","catch","handle"],"correct":0,"exp":"except handles errors."},

    # Java
    {"q":"Which method converts object to string?","options":["convert()","toString()","string()","parse()"],"correct":1,"exp":"toString converts object."},
    {"q":"Which keyword refers parent class?","options":["this","super","parent","base"],"correct":1,"exp":"super refers parent."},

    # C
    {"q":"Which function compares strings?","options":["strcmp","strcpy","strlen","strcat"],"correct":0,"exp":"strcmp compares strings."},
    {"q":"Which header has malloc()?","options":["stdio.h","stdlib.h","string.h","math.h"],"correct":1,"exp":"stdlib.h has malloc."},

    # C++
    {"q":"Which keyword stops inheritance?","options":["virtual","final","private","static"],"correct":1,"exp":"final stops inheritance."},
    {"q":"Which cast converts safely?","options":["reinterpret","static_cast","const","C cast"],"correct":1,"exp":"static_cast is safe."},

    # SQL
    {"q":"Which command removes all rows fast?","options":["DELETE","DROP","TRUNCATE","REMOVE"],"correct":2,"exp":"TRUNCATE removes all rows quickly."},
    {"q":"Which join returns matching rows only?","options":["LEFT","RIGHT","INNER","FULL"],"correct":2,"exp":"INNER JOIN returns matches."},

    # Aptitude
    {"q":"Average of 10,20,40?","options":["20","23","25","30"],"correct":2,"exp":"(10+20+40)/3 = 23.33 approx 25 not exact; nearest is 23."},
    {"q":"Square root of 121?","options":["9","10","11","12"],"correct":2,"exp":"√121 = 11."},

    # Verbal
    {"q":"Synonym of Small","options":["Tiny","Big","Large","Huge"],"correct":0,"exp":"Tiny means small."},
    {"q":"Opposite of Always","options":["Often","Never","Sometimes","Daily"],"correct":1,"exp":"Never opposite of always."},
    {"q":"Correct spelling","options":["Adress","Address","Adres","Addres"],"correct":1,"exp":"Address correct."},
    {"q":"Plural of Sheep","options":["Sheeps","Sheep","Sheepe","Sheepes"],"correct":1,"exp":"Sheep is same plural."}
],

# ================= LEVEL 14 =================
14: [
    # Python
    {"q":"Which keyword creates empty function?","options":["pass","skip","empty","none"],"correct":0,"exp":"pass is empty statement."},
    {"q":"Which function returns absolute value?","options":["abs()","fabs()","absolute()","mod()"],"correct":0,"exp":"abs() gives absolute value."},

    # Java
    {"q":"Which keyword stops method override?","options":["static","final","private","abstract"],"correct":1,"exp":"final prevents override."},
    {"q":"Which stream reads input?","options":["System.out","System.in","System.err","Scanner"],"correct":1,"exp":"System.in reads input."},

    # C
    {"q":"Which symbol ends statement?","options":[":",";","?","."],"correct":1,"exp":"; ends statement."},
    {"q":"Which function prints output?","options":["scanf","gets","printf","puts"],"correct":2,"exp":"printf prints output."},

    # C++
    {"q":"Which supports generic programming?","options":["C","Java","C++","Python"],"correct":2,"exp":"Templates support generics."},
    {"q":"Which operator dereferences pointer?","options":["&","*","->","::"],"correct":1,"exp":"* dereferences pointer."},

    # SQL
    {"q":"Which command changes column type?","options":["ALTER","UPDATE","MODIFY","CHANGE"],"correct":0,"exp":"ALTER changes column type."},
    {"q":"Which constraint checks condition?","options":["CHECK","UNIQUE","FOREIGN","DEFAULT"],"correct":0,"exp":"CHECK validates condition."},

    # Aptitude
    {"q":"What is 12×12?","options":["124","144","154","164"],"correct":1,"exp":"12×12 = 144."},
    {"q":"If CP=70, SP=50 then?","options":["Profit","Loss","No loss","Gain"],"correct":1,"exp":"Loss because SP < CP."},

    # Verbal
    {"q":"Synonym of Begin","options":["Start","End","Stop","Close"],"correct":0,"exp":"Start means begin."},
    {"q":"Opposite of Heavy","options":["Big","Light","Huge","Strong"],"correct":1,"exp":"Light is opposite."},
    {"q":"Correct spelling","options":["Freind","Friend","Frend","Fried"],"correct":1,"exp":"Friend correct."},
    {"q":"Plural of Fish","options":["Fishs","Fishes","Fish","Fishies"],"correct":2,"exp":"Fish is same plural."}
],

# ================= LEVEL 15 =================
15: [
    # Python
    {"q":"Which keyword creates iterator?","options":["iter","next","iterator","loop"],"correct":0,"exp":"iter() creates iterator."},
    {"q":"Which function checks type?","options":["typeof","type()","check()","isinstance()"],"correct":1,"exp":"type() returns type."},

    # Java
    {"q":"Which concept binds data and methods?","options":["Inheritance","Encapsulation","Polymorphism","Abstraction"],"correct":1,"exp":"Encapsulation binds data and methods."},
    {"q":"Which keyword makes class abstract?","options":["abstract","virtual","final","static"],"correct":0,"exp":"abstract keyword."},

    # C
    {"q":"Which operator increments value?","options":["--","++","+=","=="],"correct":1,"exp":"++ increments value."},
    {"q":"Which function finds string length?","options":["strlen","strcpy","strcmp","strcat"],"correct":0,"exp":"strlen gives length."},

    # C++
    {"q":"Which supports polymorphism?","options":["Inline","Virtual","Static","Friend"],"correct":1,"exp":"Virtual supports polymorphism."},
    {"q":"Which keyword avoids copying object?","options":["delete","explicit","mutable","register"],"correct":1,"exp":"explicit avoids implicit conversion."},

    # SQL
    {"q":"Which index speeds search?","options":["PRIMARY","UNIQUE","INDEX","FOREIGN"],"correct":2,"exp":"INDEX improves search speed."},
    {"q":"Which command saves changes?","options":["SAVE","COMMIT","END","APPLY"],"correct":1,"exp":"COMMIT saves changes."},

    # Aptitude
    {"q":"What is cube of 6?","options":["126","216","256","196"],"correct":1,"exp":"6³ = 216."},
    {"q":"Time = 60km/hr, distance 120km, time?","options":["1hr","2hr","3hr","4hr"],"correct":1,"exp":"120/60 = 2hr."},

    # Verbal
    {"q":"Synonym of Smart","options":["Intelligent","Lazy","Slow","Weak"],"correct":0,"exp":"Intelligent means smart."},
    {"q":"Opposite of Arrive","options":["Reach","Enter","Depart","Come"],"correct":2,"exp":"Depart is opposite."},
    {"q":"Correct spelling","options":["Accomodation","Accommodation","Acomodation","Accomadation"],"correct":1,"exp":"Accommodation correct."},
    {"q":"Plural of Person","options":["Persons","People","Persones","Peoples"],"correct":1,"exp":"People is plural."}
]

})

# ---------------- AI EXAMS ROUTES ----------------

@app.route("/ai-exams")
def ai_exams():
    return render_template("exam_dashboard.html")

@app.route("/stages/<subject>")
def exam_stages(subject):
    unlocked_level = session.get(f"{subject}_level", 1)
    return render_template(
        "exam_stages.html",
        subject=subject,
        unlocked_level=unlocked_level
    )

@app.route("/exam/<subject>/<int:level>")
def exam(subject, level):
    level_questions = QUESTIONS.get(subject, {}).get(level, [])

    return render_template(
        "exam.html",
        subject=subject,
        level=level,
        questions=level_questions
    )

@app.route("/submit/<subject>/<int:level>", methods=["POST"])
def submit_exam(subject, level):
    questions = QUESTIONS.get(subject, {}).get(level, [])

    score = 0
    result = []

    for i, q in enumerate(questions):
        user_ans = request.form.get(str(i))

        if user_ans is not None and int(user_ans) == q["correct"]:
            score += 1
            status = "Correct"
        else:
            status = "Wrong"

        result.append({
            "question": q["q"],
            "user": q["options"][int(user_ans)] if user_ans else "Not Answered",
            "correct": q["options"][q["correct"]],
            "status": status,
            "exp": q["exp"]
        })

    total = len(questions)
    percentage = int((score / total) * 100) if total > 0 else 0
    passed = percentage >= 50

    # unlock next level
    if passed:
        key = f"{subject}_level"
        current = session.get(key, 1)
        if level >= current:
            session[key] = level + 1

    return render_template(
        "result.html",
        score=score,
        total=total,
        percentage=percentage,
        passed=passed,
        result=result,
        subject=subject,
        level=level
    )

# ==============================
# ==============================
# 🎯 Interview Room Page
# ==============================
@app.route("/mock-interview")
def mock_interview():

    # 🔥 RESET INTERVIEW SESSION
    session["question_count"] = 0
    session["total_score"] = 0

    # 🔥 Reset question system
    session.pop("questions", None)
    session.pop("question_index", None)
    session.pop("round_type", None)

    conn = sqlite3.connect("interviews.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT average_score, badge, date
        FROM interview_history
        ORDER BY id ASC
    """)

    history_records = cursor.fetchall()

    conn.close()

    # 🔥 Extract scores for graph
    scores = [row[0] for row in history_records]

    # 🔥 Create labels dynamically
    
    labels = [f"Attempt {i+1}" for i in range(len(scores))]

    return render_template("interview_room.html")



# ==============================
# 🤖 Generate Question (Company Mode Added)
# ==============================
@app.route("/generate_question")
def generate_question():

    round_type = request.args.get("round", "hr")
    company = request.args.get("company", "General")

    session["round_type"] = round_type

    # First time only generate 5 questions
    if "questions" not in session:

        if round_type == "technical":

            prompt = f"""
Generate 5 UNIQUE Technical interview questions commonly asked in {company} interviews.

Rules:
1. Include 2 coding problems.
2. Questions must increase in difficulty.
3. No repetition.
4. No numbering.
5. Each question in new line.
"""

        else:

            prompt = f"""
Generate 5 UNIQUE HR interview questions commonly asked in {company} interviews.

Rules:
1. Behavioral and personality based.
2. No technical questions.
3. No repetition.
4. No numbering.
5. Each question in new line.
"""

        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt
            )

            session["questions"] = response.text.strip().split("\n")
            session["question_index"] = 0

        except Exception as e:
            print("Gemini Error:", e)
            return jsonify({"question": "Tell me about yourself."})

    index = session.get("question_index", 0)

    if index < 5:
        question = session["questions"][index]
        session["question_index"] = index + 1
        return jsonify({"question": question})
    else:
        return jsonify({"completed": True})



# ==============================
# 📥 Receive Answer & Evaluate
# ==============================
@app.route("/receive_answer", methods=["POST"])
def receive_answer():

    data = request.json
    question = data.get("question")
    answer = data.get("answer")

    prompt = f"""
You are a professional AI Interview Evaluator.

Return EXACTLY in this structured format:

## Overall Score: X/10

## 1. Clarity
(2-3 lines explanation)

## 2. Content Quality
(2-3 lines explanation)

## 3. Communication
(2-3 lines explanation)

## 4. STAR Analysis
Situation: (Present / Missing)
Task: (Present / Missing)
Action: (Present / Missing)
Result: (Present / Missing)

## 5. Confidence Level
(Low / Medium / High)

## 6. Improvements
1.
2.
3.

Question: {question}
Candidate Answer: {answer}

Do not add extra text outside this format.
"""

    try:
        response = groq_client.chat.completions.create(
            model="gemini-flash-latest",
            contents=prompt
        )

        feedback = response.text.strip()

    except Exception as e:
        print("Gemini Error:", e)
        feedback = "⚠️ AI service temporarily unavailable."

    # 🔥 Extract score safely
    import re
    match = re.search(r'(\d+)/10', feedback)
    score = int(match.group(1)) if match else 5

    # 🔥 Ensure session keys exist
    if "question_count" not in session:
        session["question_count"] = 0

    if "total_score" not in session:
        session["total_score"] = 0

    # ✅ Increment question count ONLY here
    session["question_count"] += 1

    # ✅ Add score
    session["total_score"] += score

    return jsonify({
        "feedback": feedback,
        "question_count": session["question_count"]
    })


# ==============================
# 🏁 Final Result Page
# ==============================

@app.route("/final-result")
def final_result():

    total = session.get("total_score", 0)
    count = session.get("question_count", 0)

    if count == 0:
        average = 0
    else:
        average = round(total / count, 1)

    # Badge Logic
    if average >= 8:
        badge = "Gold"
    elif average >= 6:
        badge = "Silver"
    else:
        badge = "Bronze"

    # 🔥 SAVE TO DATABASE (VERY IMPORTANT)
    conn = sqlite3.connect("interviews.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO interview_history (average_score, badge, date)
        VALUES (?, ?, datetime('now'))
    """, (average, badge))

    conn.commit()
    conn.close()

    return render_template(
        "final_result.html",
        average=average,
        badge=badge
    )


@app.route("/history")
def history():

    conn = sqlite3.connect("interviews.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT average_score, badge, date
        FROM interview_history
        ORDER BY id DESC
    """)

    records = cursor.fetchall()
    conn.close()

    scores = [row[0] for row in records]
    labels = [f"Attempt {i+1}" for i in range(len(scores))]

    return render_template(
        "history.html",
        records=records,
        scores=scores,
        labels=labels
    )


@app.route("/clear-history", methods=["POST"])
def clear_history():

    conn = sqlite3.connect("interviews.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM interview_history")

    conn.commit()
    conn.close()

    return redirect("/history")
print(app.url_map)



def run_career_intelligence():
    dataset = load_simulated_dataset()
    analyzer = CompanyAnalyzer()

    company_reports = []

    for company in dataset:
        report = analyzer.analyze_company(company)
        company_reports.append(report)

    market_data = aggregate_market_data(company_reports)

    final_output = {
        "companies": company_reports,
        "market_intelligence": market_data
    }

    with open("output/hiring_intelligence.json", "w") as f:
        json.dump(final_output, f, indent=4)

    print("Career Intelligence Report Generated Successfully!")



def run_career_intelligence():

    os.makedirs("output", exist_ok=True)

    dataset = load_simulated_dataset()
    analyzer = CompanyAnalyzer()

    company_reports = []

    for company in dataset:
        report = analyzer.analyze_company(company, len(dataset))
        company_reports.append(report)

    market_data = aggregate_market_data(company_reports)

    final_output = {
        "Company Hiring Intelligence Reports": company_reports,
        "Multi-Company Market Intelligence": market_data,
        "Fresher Readiness Blueprint": {
            "Minimum Stack": [
                "Python or Java",
                "Data Structures & Algorithms",
                "OOPS",
                "SQL",
                "Cloud Basics (AWS/Azure)",
                "Problem Solving",
                "Communication"
            ]
        },
        "Student Skill Gap Analysis Logic": {
            "Fit Score Formula":
                "Fit Score = (Matched Skills / Total Required Skills) * 100"
        }
    }

    with open("output/hiring_intelligence.json", "w") as f:
        json.dump(final_output, f, indent=4)

    print("Advanced AI Career Intelligence Report Generated Successfully!")

@app.route("/update_company", methods=["POST"])
def update_company():

    company_name = request.json.get("company")

    with open("output/hiring_intelligence.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    companies = data.get("Company Hiring Intelligence Reports", [])

    for company in companies:
        if company.get("Company Name", "").lower() == company_name.lower():

            # 🔥 Save previous version safely
            if "versions" not in company:
                company["versions"] = []

            old_version = copy.deepcopy(company)
            old_version.pop("versions", None)   # remove nested versions

            company["versions"].append(old_version)

            # 🔥 Perform Update
            company["Demand Level"] = random.choice(["HIGH", "MEDIUM", "LOW"])

            if "Required Programming Languages" not in company:
                company["Required Programming Languages"] = []

            if "Rust" not in company["Required Programming Languages"]:
                company["Required Programming Languages"].append("Rust")

            key = "Emerging Skills (<50%)"

            if key not in company:
                company[key] = []

            if "Blockchain" not in company[key]:
                company[key].append("Blockchain")

            break

    with open("output/hiring_intelligence.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    return jsonify({"status": "updated"})

@app.route("/previous_company", methods=["POST"])
def previous_company():

    company_name = request.json.get("company")

    with open("output/hiring_intelligence.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    companies = data.get("Company Hiring Intelligence Reports", [])

    for company in companies:
        if company.get("Company Name", "").lower() == company_name.lower():

            if "versions" in company and len(company["versions"]) > 0:

                last_version = company["versions"].pop()

                # Restore safely
                for key in list(company.keys()):
                    if key != "versions":
                        company.pop(key)

                company.update(last_version)

                with open("output/hiring_intelligence.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

                return jsonify({"status": "previous"})

            break

    return jsonify({"status": "no_previous"})
 
 
 
@app.route("/company-analysis")
def company_list():

    import os
    if not os.path.exists("output/hiring_intelligence.json"):
        run_career_intelligence()

    with open("output/hiring_intelligence.json", "r") as f:
        data = json.load(f)

    companies = data["Company Hiring Intelligence Reports"]

    return render_template("company_list.html", companies=companies)

@app.route("/company/<name>")
def company_detail(name):

    with open("output/hiring_intelligence.json", "r") as f:
        data = json.load(f)

    companies = data["Company Hiring Intelligence Reports"]

    selected_company = None

    for company in companies:
        if company["Company Name"].lower() == name.lower():
            selected_company = company
            break

    # Default version = 1
    current_version = 1

    return render_template(
        "company_detail.html",
        company=selected_company,
        company_name=name,
        current_version=current_version
    )
    
    
# ==============================
# 📊 Programming Skill Demand Analyzer
# ==============================

@app.route("/skill-trend-analyzer")
def skill_trend_analyzer():
    return render_template("skill_trend_analyzer.html")


@app.route("/generate-trending-skills", methods=["GET", "POST"]) 
def generate_trending_skills():

       skills = [
    {"name":"Python + AI/ML","demand":95,"salary":"₹12–20 LPA","category":"AI"},
    {"name":"Machine Learning","demand":93,"salary":"₹11–19 LPA","category":"AI"},
    {"name":"React + TypeScript","demand":92,"salary":"₹10–18 LPA","category":"Frontend"},
    {"name":"Java (Spring Boot)","demand":91,"salary":"₹10–19 LPA","category":"Backend"},
    {"name":"AWS / Cloud","demand":90,"salary":"₹14–25 LPA","category":"Cloud"},
    {"name":"Deep Learning","demand":89,"salary":"₹12–22 LPA","category":"AI"},
    {"name":"SQL & Data Analytics","demand":89,"salary":"₹8–16 LPA","category":"Data"},
    {"name":"Node.js Backend","demand":88,"salary":"₹9–16 LPA","category":"Backend"},
    {"name":"Azure","demand":87,"salary":"₹13–23 LPA","category":"Cloud"},
    {"name":"Django","demand":86,"salary":"₹9–15 LPA","category":"Backend"},
    {"name":"DevOps (Docker, Kubernetes)","demand":85,"salary":"₹13–22 LPA","category":"DevOps"},
    {"name":"Google Cloud","demand":84,"salary":"₹12–21 LPA","category":"Cloud"},
    {"name":"Cybersecurity","demand":83,"salary":"₹11–21 LPA","category":"Security"},
    {"name":"Next.js","demand":82,"salary":"₹9–16 LPA","category":"Frontend"},
    {"name":"CI/CD Pipelines","demand":81,"salary":"₹10–18 LPA","category":"DevOps"},
    {"name":"Power BI / Tableau","demand":80,"salary":"₹7–14 LPA","category":"Data"},
    {"name":"Terraform","demand":79,"salary":"₹12–20 LPA","category":"DevOps"},
    {"name":"Ethical Hacking","demand":78,"salary":"₹9–17 LPA","category":"Security"},
    {"name":"Angular","demand":77,"salary":"₹8–14 LPA","category":"Frontend"},
    {"name":"Blockchain / Web3","demand":75,"salary":"₹10–19 LPA","category":"Emerging"}
]
       return jsonify(skills)

# 2. AI Generated Skills
@app.route("/generate-ai-skills", methods=["POST"])
def generate_ai_skills():
    try:
        data = request.get_json()
        role = data.get("role")
        location = data.get("location")
        experience = data.get("experience")

        prompt = f"""
        Give top 6 skills for Role: {role}, Location: {location}, Exp: {experience}.
        Return ONLY a JSON array. 
        Each object MUST have: "name", "demand" (0-100), "salary", and "category".
        Example: [{{"name":"Python","demand":90,"salary":"10LPA","category":"Backend"}}]
        """
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.choices[0].message.content.strip()
        # Clean JSON markdown
        clean = re.sub(r"```json|```", "", raw).strip()
        
        # Extract only the array part [ ... ]
        start = clean.find("[")
        end = clean.rfind("]") + 1
        skills = json.loads(clean[start:end])

        return jsonify(skills) # Direct list return chestunnam

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500



@app.route("/list-models")
def list_models():
    models = client.models.list()@app.route("/generate-ai-skills", methods=["POST"])
def generate_ai_skills():
    return jsonify({
        "skills": [
            {"name": "Python", "demand": 90, "category": "Backend"},
            {"name": "Machine Learning", "demand": 85, "category": "AI"},
            {"name": "Deep Learning", "demand": 80, "category": "AI"},
            {"name": "TensorFlow", "demand": 78, "category": "AI"}
        ]
    })
    return {
        "models": [m.name for m in models]
    }

@app.route('/optimize-genai-universal', methods=['POST'])
def optimize_genai_universal():
    data = request.get_json()

    resume = data.get("resumeText")
    role = data.get("jobRole")

    return jsonify({
        "optimized_resume": f"<h3>Optimized for {role}</h3><p>{resume}</p>",
        "ats_score": 86,
        "job_match": 96
    })
    
@app.route('/private-software-jobs')
def jobs_page():
    return render_template('jobs.html')

@app.route('/advanced_jobs', methods=['POST'])
def advanced_jobs():
    data = request.json
    role = data['role']
    skills = data['skills']

    jobs = get_all_jobs(role)
    result = analyze_jobs(jobs, skills)

    return jsonify(result)

@app.route('/job-feed-data')
def job_feed_data():

    roles = [
        "software engineer","frontend developer","backend developer",
        "full stack developer","python developer","java developer",
        "data analyst","data scientist","machine learning engineer",
        "ai engineer","cloud engineer","devops engineer",
        "cyber security","tester","qa engineer",
        "mobile developer","android developer","ios developer",
        "ui ux designer","system engineer"
    ]

    all_jobs = []

    for role in roles:
        jobs = get_all_jobs(role)
        all_jobs.extend(jobs)

    # 🔥 remove duplicates
    unique = {}
    for job in all_jobs:
        key = (job['title'] + job['company']).lower().strip()
        unique[key] = job

    jobs = list(unique.values())

    # 🔥 limit 50
    jobs = jobs[:50]

    return jsonify(jobs)

@app.route('/company-prep')
def company_prep():
    return render_template("company_selection.html")

@app.route("/prep/<company>")
def prep(company):

    company = company.lower()

    data = None
    for key in company_data:
        if key.lower() == company:
            data = company_data[key]
            company = key
            break

    if not data:
        return "Company not found"

    return render_template("company.html", name=company, data=data)

@app.route("/career-visibility-score", methods=["GET", "POST"])
def career_score():
    if request.method == "POST":

        skills = request.form.get("skills", "")
        projects = request.form.get("projects")
        coding = request.form.get("coding")
        # empty unte 0 ga set chey
        projects = int(projects) if projects else 0
        coding = int(coding) if coding else 0
        resume = request.form.get("resume", "average")
        communication = request.form.get("communication", "average")

        data = {
            "skills": skills.split(","),
            "projects": projects,
            "coding": coding,
            "resume": resume,
            "communication": communication
        }

        result = calculate_scores(data)

        return render_template("career_result.html", result=result)

    return render_template("career_score.html")

@app.route("/global-employability", methods=["GET", "POST"])
def global_employability():

    if request.method == "POST":

        skills_input = request.form.get("skills", "")
        skills_list = [s.strip() for s in skills_input.split(",") if s.strip()]
        skills_count = len(skills_list)

        projects = int(request.form.get("projects") or 0)
        coding = int(request.form.get("coding") or 0)
        resume = request.form.get("resume")
        communication = request.form.get("communication")

        # INIT
        score = 0
        gaps = []
        suggestions = []

        # SCORE LOGIC
        score += skills_count * 5
        score += projects * 10
        score += coding // 10

        # Resume
        if resume == "good":
            score += 20
        elif resume == "average":
            score += 10
            suggestions.append("Improve resume with strong projects and metrics")
        else:
            gaps.append("Improve resume")
            suggestions.append("Create ATS-friendly resume with achievements")

        # Communication
        if communication == "good":
            score += 20
        elif communication == "average":
            score += 10
            suggestions.append("Practice speaking and mock interviews")
        else:
            gaps.append("Improve communication")
            suggestions.append("Work on English fluency and confidence")

        # LIMIT
        score = min(score, 100)

        # LEVEL
        if score < 40:
            level = "Beginner"
        elif score < 70:
            level = "Intermediate"
        else:
            level = "Advanced"

        # BADGE
        badge = "🚀 Job Ready" if score > 75 else "🔥 Growing"

        # ROLE
        role = "Software Developer" if score > 60 else "Support Engineer"

        # GAPS LOGIC
        if skills_count < 3:
            gaps.append("Improve technical skills")
            suggestions.append("Learn Python, DSA, DBMS basics")

        if projects < 2:
            gaps.append("Build projects")
            suggestions.append("Create real-world projects (AI, Web, Apps)")

        if coding < 100:
            gaps.append("Practice DSA")
            suggestions.append("Solve 100+ coding problems (LeetCode)")

        # COMPANIES
        if score > 80:
            companies = ["Amazon", "Microsoft", "Google"]
        elif score > 60:
            companies = ["Accenture", "Capgemini", "Cognizant"]
        else:
            companies = ["TCS", "Infosys", "Wipro"]

        # FEEDBACK (SMART)
        if level == "Advanced":
            feedback = "Excellent! You are job-ready for top companies."
        elif level == "Intermediate":
            feedback = "Good progress. Improve key areas to reach top level."
        else:
            feedback = "Start with fundamentals and build consistency."

        # ROADMAP (DYNAMIC)
        roadmap = []

        if "Practice DSA" in gaps:
            roadmap.append("Daily DSA (2 problems/day)")
        if "Build projects" in gaps:
            roadmap.append("Complete 2 projects in 1 month")
        if "Improve resume" in gaps:
            roadmap.append("Update resume with strong content")
        if "Improve communication" in gaps:
            roadmap.append("Mock interviews weekly")

        if not roadmap:
            roadmap = ["Apply for jobs", "Attend interviews", "Upskill advanced topics"]

        result = {
            "score": score,
            "level": level,
            "badge": badge,
            "role": role,
            "gaps": gaps,
            "companies": companies,
            "feedback": feedback,
            "roadmap": roadmap,
            "suggestions": suggestions
        }

        return render_template("global_result.html", result=result)

    return render_template("global_employability.html")

profile_data = {}

@app.route("/profile", methods=["GET", "POST"])
def career_profile():

    global profile_data

    if request.method == "POST":

        resume = request.files.get("resume")
        filename = ""

        if resume:
            filename = resume.filename
            resume.save("static/" + filename)

        profile_data = {
            "name": request.form.get("name"),
            "email": request.form.get("email"),
            "qualification": request.form.get("qualification"),
            "skills": request.form.get("skills"),
            "interests": request.form.get("interests"),
            "goal": request.form.get("goal"),
            "strengths": request.form.get("strengths"),
            "weaknesses": request.form.get("weaknesses"),
            "password": request.form.get("password"),
            "resume": filename
        }

        return redirect("/profile")

    return render_template("career_profile.html", profile=profile_data)


# DELETE
@app.route("/delete")
def delete():
    global profile_data
    profile_data.clear()
    return redirect("/profile")


# PERSONALIZATION
@app.route("/personalize")
def personalize():

    if not profile_data:
        return "Create profile first"

    skills = profile_data.get("skills", "")
    interests = profile_data.get("interests", "")

    # 🎯 BASIC AI LOGIC
    score = 0

    if skills:
        score += 40
    if interests:
        score += 30

    # bonus
    score += 20

    # LIMIT
    if score > 100:
        score = 100

    # PATH LOGIC
    if "python" in skills.lower():
        path = "Software Engineer 💻"
        companies = ["Wipro", "Accenture"]
    else:
        path = "General IT Role"
        companies = ["Infosys", "TCS"]

    skill_gap = ["DSA", "Projects", "Communication"]

    return render_template("career_personalization.html",
                           path=path,
                           companies=companies,
                           skills=skill_gap,
                           score=score)

@app.route("/logout")   # 🔥 THIS LINE VERY IMPORTANT
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)
