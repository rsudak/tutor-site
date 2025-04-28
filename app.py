from flask import Flask, render_template, request, redirect, session, url_for, jsonify, json, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import os

app = Flask(__name__)
app.secret_key = "очень_секретный_ключ_сюда"  # можешь придумать свой

API_SECRET_TOKEN = "supersecrettoken123"

# Проверка токена в заголовке
def require_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        abort(403)
    token = auth.split(" ")[1]
    if token != API_SECRET_TOKEN:
        abort(403)

# Настройка базы данных (файл будет создан автоматически)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'site.db')
db = SQLAlchemy(app)

# Модель данных для записи
class Signup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    preferred_date = db.Column(db.String(20), nullable=True)
    preferred_time = db.Column(db.String(20), nullable=True)
    message = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Запись {self.name}>"

class CancelledSignup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    preferred_date = db.Column(db.Date, nullable=False)
    preferred_time = db.Column(db.String(10), nullable=False)
    cancelled_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

# Модель отзыва
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Отзыв от {self.name}>"

class BlockedSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(10), nullable=False)

    def __repr__(self):
        return f"{self.date} {self.time}"

from werkzeug.security import generate_password_hash, check_password_hash

# Модель ученика
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/services")
def services():
    return render_template("services.html")

@app.route("/faq")
def faq():
    return render_template("faq.html")

# Регистрация ученика
@app.route("/register", methods=["GET", "POST"])
def register():
    success_message = session.pop("success_message", None)

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        if Student.query.filter_by(email=email).first():
            return render_template("register.html", error="Пользователь с таким email уже существует.", success_message=success_message)

        student = Student(name=name, email=email)
        student.set_password(password)

        db.session.add(student)
        db.session.commit()

        session["success_message"] = "Регистрация прошла успешно! Теперь войдите."
        return redirect("/login_student")

    return render_template("register.html", success_message=success_message)


# Вход ученика
@app.route("/login_student", methods=["GET", "POST"])
def login_student():
    success_message = session.pop("success_message", None)

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        student = Student.query.filter_by(email=email).first()

        if student and student.check_password(password):
            session["student_logged_in"] = True
            session["student_id"] = student.id
            return redirect("/student/profile")
        else:
            return render_template("login_student.html", error="Неверный email или пароль.", success_message=success_message)

    return render_template("login_student.html", success_message=success_message)


# Личный кабинет ученика
@app.route("/student/profile", methods=["GET", "POST"])
def student_profile():
    if not session.get("student_logged_in"):
        return redirect("/login_student")

    success_message = session.pop("success_message", None)

    student = Student.query.get(session["student_id"])

    subject_filter = request.args.get("subject", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    applications_query = Signup.query.filter_by(email=student.email)

    if subject_filter:
        applications_query = applications_query.filter(Signup.subject == subject_filter)
    
    if start_date:
        applications_query = applications_query.filter(Signup.preferred_date >= start_date)
    
    if end_date:
        applications_query = applications_query.filter(Signup.preferred_date <= end_date)

    applications = applications_query.order_by(Signup.date_created.desc()).all()

    # Подготовка событий для календаря
    calendar_events = [
        {
            "title": app.subject,
            "start": app.preferred_date,
            "description": app.message
        }
        for app in applications
    ]

    return render_template(
        "student_profile.html",
        student=student,
        applications=applications,
        calendar_events=calendar_events,
        success_message=success_message,
        subject_filter=subject_filter,
        start_date=start_date,
        end_date=end_date
    )


#Редактирование профиля ученика
@app.route("/student/edit", methods=["GET", "POST"])
def edit_student_profile():
    if not session.get("student_logged_in"):
        return redirect("/login_student")

    success_message = session.pop("success_message", None)

    student = Student.query.get(session["student_id"])

    if request.method == "POST":
        new_name = request.form["name"]
        new_email = request.form["email"]
        new_password = request.form.get("password")

        if student.email != new_email:
            if Student.query.filter_by(email=new_email).first():
                return render_template("edit_student_profile.html", student=student, error="Email уже используется другим пользователем.", success_message=success_message)

        student.name = new_name
        student.email = new_email

        if new_password:
            student.set_password(new_password)

        db.session.commit()
        session["success_message"] = "Профиль успешно обновлён!"
        return redirect("/student/profile")

    return render_template("edit_student_profile.html", student=student, success_message=success_message)

#Восстановление пароля
@app.route("/student/forgot_password", methods=["GET", "POST"])
def forgot_password():
    success_message = session.pop("success_message", None)

    if request.method == "POST":
        email = request.form["email"]
        student = Student.query.filter_by(email=email).first()

        if student:
            session["reset_student_id"] = student.id
            return redirect("/student/reset_password")
        else:
            return render_template("forgot_password.html", error="Пользователь с таким email не найден.", success_message=success_message)

    return render_template("forgot_password.html", success_message=success_message)

#Сброс пароля
@app.route("/student/reset_password", methods=["GET", "POST"])
def reset_password():
    if "reset_student_id" not in session:
        return redirect("/student/forgot_password")

    success_message = session.pop("success_message", None)

    student = Student.query.get(session["reset_student_id"])

    if request.method == "POST":
        new_password = request.form["password"]
        student.set_password(new_password)
        db.session.commit()

        session.pop("reset_student_id", None)
        session.pop("student_logged_in", None)
        session.pop("student_id", None)

        session["success_message"] = "Пароль успешно изменён! Пожалуйста, войдите заново."
        return redirect("/login_student")

    return render_template("reset_password.html", success_message=success_message)


# Выход ученика
@app.route("/logout_student")
def logout_student():
    session.pop("student_logged_in", None)
    session.pop("student_id", None)
    session["success_message"] = "Вы успешно вышли из аккаунта."
    return redirect("/")


@app.route("/contacts", methods=["GET", "POST"])
def contacts():
    today = datetime.now(timezone.utc).date()
    available_days = [today + timedelta(days=i) for i in range(7)]
    available_times = ["10:00", "12:00", "14:00", "16:00", "18:00"]

    # Получаем все занятые слоты
    busy_entries = Signup.query.filter(
        Signup.preferred_date >= str(today),
        Signup.preferred_date <= str(today + timedelta(days=7))
    ).all()

    busy_set = set(f"{e.preferred_date}_{e.preferred_time[:5]}" for e in busy_entries)

    # Подключаем закрытые слоты:
    blocked = BlockedSlot.query.all()
    for b in blocked:
        busy_set.add(f"{b.date}_{b.time[:5]}")


    # Формируем список свободных слотов
    free_slots = []
    for day in available_days:
        str_day = day.strftime("%Y-%m-%d")
        for t in available_times:
            key = f"{str_day}_{t}"
            if key not in busy_set:
                free_slots.append({"date": str_day, "time": t})

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        subject = request.form["subject"]
        preferred_date = request.form["preferred_date"]
        preferred_time = request.form["preferred_time"]
        message = request.form["message"]

        formatted_time = preferred_time[:5]  # убираем секунды

        # Проверка занятости слота
        existing = Signup.query.filter(
            Signup.preferred_date == preferred_date,
            Signup.preferred_time.like(f"{formatted_time}%")
        ).first()

        if existing:
            error = "На выбранную дату и время уже есть запись. Пожалуйста, выберите другой слот."
            return render_template("contacts.html", free_slots=free_slots, error=error)

        # Всё ок — сохраняем
        new_entry = Signup(
            name=name,
            email=email,
            subject=subject,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            message=message
        )
        db.session.add(new_entry)
        db.session.commit()
        return redirect("/thanks")

    return render_template("contacts.html", free_slots=free_slots)

@app.route("/reviews", methods=["GET", "POST"])
def reviews():
    if request.method == "POST":
        name = request.form["name"]
        subject = request.form["subject"]
        message = request.form["message"]
        new_review = Review(name=name, subject=subject, message=message)
        db.session.add(new_review)
        db.session.commit()
        return redirect("/reviews")

    all_reviews = Review.query.order_by(Review.id.desc()).all()
    return render_template("reviews.html", reviews=all_reviews)

@app.route("/api/reviews")
def api_reviews():
    reviews = Review.query.all()
    data = [
        {
            "name": r.name,
            "subject": r.subject,
            "message": r.message
        }
        for r in reviews
    ]
    return app.response_class(
        response=json.dumps(data, ensure_ascii=False, indent=2),
        mimetype='application/json'
    )

@app.route("/api/applications", methods=["POST"])
def api_create_application():
    require_token()

    try:
        data = request.get_json()

        name = data.get("name")
        email = data.get("email")
        subject = data.get("subject")
        message = data.get("message")
        preferred_date = data.get("preferred_date")
        preferred_time = data.get("preferred_time")

        if not all([name, email, subject, message]):
            return jsonify({"error": "Заполните все поля"}), 400

        new_entry = Signup(
            name=name,
            email=email,
            subject=subject,
            message=message,
            preferred_date=preferred_date,
            preferred_time=preferred_time
        )
        db.session.add(new_entry)
        db.session.commit()

        return jsonify({"status": "ok", "message": "Заявка добавлена"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/applications", methods=["GET"])
def api_get_applications():
    require_token()

    applications = Signup.query.order_by(Signup.date_created.desc()).all()

    data = []
    for app in applications:
        data.append({
            "id": app.id,
            "name": app.name,
            "email": app.email,
            "subject": app.subject,
            "message": app.message,
            "preferred_date": app.preferred_date,
            "preferred_time": app.preferred_time,
            "created": app.date_created.strftime("%Y-%m-%d %H:%M")
        })

    return jsonify(data)


@app.route("/admin/applications")
def admin_applications():
    if not session.get("logged_in"):
        return redirect("/login")
    records = Signup.query.all()
    return render_template("admin.html", records=records)

@app.route("/admin/applications/edit/<int:entry_id>", methods=["GET", "POST"])
def edit_application(entry_id):
    if not session.get("logged_in"):
        return redirect("/login")

    entry = Signup.query.get_or_404(entry_id)

    if request.method == "POST":
        entry.name = request.form["name"]
        entry.email = request.form["email"]
        entry.subject = request.form["subject"]
        entry.message = request.form["message"]
        entry.preferred_date = request.form["preferred_date"]
        entry.preferred_time = request.form["preferred_time"]
        db.session.commit()
        return redirect("/admin/applications")

    return render_template("edit_application.html", entry=entry)

@app.route("/admin/applications/delete/<int:entry_id>")
def delete_entry(entry_id):
    if not session.get("logged_in"):
        return redirect("/login")
    entry = Signup.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    return redirect("/admin/applications")

@app.route("/admin/reviews")
def admin_reviews():
    if not session.get("logged_in"):
        return redirect("/login")
    all_reviews = Review.query.all()
    return render_template("admin_reviews.html", reviews=all_reviews)

@app.route("/admin/reviews/edit/<int:review_id>", methods=["GET", "POST"])
def edit_review(review_id):
    if not session.get("logged_in"):
        return redirect("/login")

    review = Review.query.get_or_404(review_id)

    if request.method == "POST":
        review.name = request.form["name"]
        review.subject = request.form["subject"]
        review.message = request.form["message"]
        db.session.commit()
        return redirect("/admin/reviews")

    return render_template("edit_review.html", review=review)

@app.route("/admin/reviews/delete/<int:review_id>")
def delete_review(review_id):
    if not session.get("logged_in"):
        return redirect("/login")
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    return redirect("/admin/reviews")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        # Замените на свои данные
        if username == "admin" and password == "1234":
            session["logged_in"] = True
            return redirect("/admin")
        else:
            return render_template("login.html", error="Неверный логин или пароль")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect("/")

@app.route("/thanks")
def thanks():
    return render_template("thanks.html")

@app.route("/api/docs")
def api_docs():
    return render_template("api_docs.html")

@app.route("/admin")
def admin_dashboard():
    if not session.get("logged_in"):
        return redirect("/login")
    return render_template("admin_dashboard.html")

@app.route("/admin/stats")
def admin_stats():
    if not session.get("logged_in"):
        return redirect("/login")
    
    total_signups = Signup.query.count()
    total_reviews = Review.query.count()

    # Подсчёт заявок за последние 7 дней
    today = datetime.utcnow().date()
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    labels = [d.strftime("%d.%m") for d in days]
    counts = []
    for d in days:
        next_day = d + timedelta(days=1)
        count = Signup.query.filter(Signup.date_created >= d, Signup.date_created < next_day).count()
        counts.append(count)

    # Статистика по предметам
    subjects = ["Математика", "Физика", "Информатика"]
    subject_counts = {
        subject: Signup.query.filter(Signup.subject == subject).count()
        for subject in subjects
    }

    # Самые частые временные слоты
    all_slots = db.session.query(Signup.preferred_time).all()
    slot_freq = {}
    for row in all_slots:
        time = row[0]
        if time:
            t = time[:5] if isinstance(time, str) else time.strftime("%H:%M")
            slot_freq[t] = slot_freq.get(t, 0) + 1
    sorted_slots = sorted(slot_freq.items(), key=lambda x: x[1], reverse=True)

    return render_template("admin_stats.html",
        total_signups=total_signups,
        total_reviews=total_reviews,
        labels=labels,
        counts=counts,
        subject_counts=subject_counts,
        sorted_slots=sorted_slots
    )

@app.route("/admin/cancelled")
def admin_cancelled():
    if not session.get("logged_in"):
        return redirect("/login")

    subject_filter = request.args.get("subject")
    name_filter = request.args.get("name")
    date_filter = request.args.get("date")

    query = CancelledSignup.query

    if subject_filter:
        query = query.filter(CancelledSignup.subject == subject_filter)
    if name_filter:
        query = query.filter(CancelledSignup.name.ilike(f"%{name_filter}%"))
    if date_filter:
        query = query.filter(CancelledSignup.preferred_date == date_filter)

    records = query.order_by(CancelledSignup.cancelled_at.desc()).all()

    return render_template(
        "admin_cancelled.html",
        records=records,
        selected_subject=subject_filter,
        selected_name=name_filter,
        selected_date=date_filter
    )

@app.route("/admin/blocked", methods=["GET", "POST"])
def admin_blocked():
    if not session.get("logged_in"):
        return redirect("/login")

    if request.method == "POST":
        mode = request.form.get("mode")

        if mode == "mass":
            start_date = datetime.strptime(request.form["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
            selected_times = request.form.getlist("times")

            current = start_date
            while current <= end_date:
                for t in selected_times:
                    exists = BlockedSlot.query.filter_by(date=current, time=t).first()
                    if not exists:
                        db.session.add(BlockedSlot(date=current, time=t))
                current += timedelta(days=1)

            db.session.commit()

        elif mode == "single":
            d = datetime.strptime(request.form["single_date"], "%Y-%m-%d").date()
            t = request.form["single_time"]
            exists = BlockedSlot.query.filter_by(date=d, time=t).first()
            if not exists:
                db.session.add(BlockedSlot(date=d, time=t))
                db.session.commit()

        return redirect("/admin/blocked")

    blocks = BlockedSlot.query.order_by(BlockedSlot.date, BlockedSlot.time).all()
    return render_template("admin_blocked.html", blocks=blocks)


@app.route("/admin/blocked/delete/<int:block_id>", methods=["POST"])
def delete_blocked(block_id):
    if not session.get("logged_in"):
        return redirect("/login")
    b = BlockedSlot.query.get_or_404(block_id)
    db.session.delete(b)
    db.session.commit()
    return redirect("/admin/blocked")

@app.route("/admin/schedule")
def admin_schedule():
    if not session.get("logged_in"):
        return redirect("/login")

    subject_filter = request.args.get("subject")
    name_filter = request.args.get("name")
    date_filter = request.args.get("date")

    today = datetime.now(timezone.utc).date()
    query = Signup.query.filter(Signup.preferred_date >= str(today))

    if subject_filter:
        query = query.filter(Signup.subject == subject_filter)

    if name_filter:
        query = query.filter(Signup.name.ilike(f"%{name_filter}%"))  # нечёткий поиск по имени

    if date_filter:
        query = query.filter(Signup.preferred_date == date_filter)

    upcoming = query.order_by(Signup.preferred_date, Signup.preferred_time).all()

    return render_template("admin_schedule.html",
                           schedule=upcoming,
                           selected_subject=subject_filter,
                           selected_name=name_filter,
                           selected_date=date_filter)

import pandas as pd
from flask import make_response
from weasyprint import HTML

@app.route("/admin/schedule/export/excel")
def export_schedule_excel():
    if not session.get("logged_in"):
        return redirect("/login")

    subject = request.args.get("subject")
    name = request.args.get("name")
    date = request.args.get("date")

    today = datetime.now(timezone.utc).date()
    query = Signup.query.filter(Signup.preferred_date >= str(today))

    if subject:
        query = query.filter(Signup.subject == subject)
    if name:
        query = query.filter(Signup.name.ilike(f"%{name}%"))
    if date:
        query = query.filter(Signup.preferred_date == date)

    data = query.order_by(Signup.preferred_date, Signup.preferred_time).all()

    # Формируем таблицу
    df = pd.DataFrame([{
        "Дата": entry.preferred_date,
        "Время": entry.preferred_time[:5],
        "Предмет": entry.subject,
        "Имя": entry.name,
        "Email": entry.email,
        "Комментарий": entry.message
    } for entry in data])

    output = pd.ExcelWriter("schedule_export.xlsx", engine="openpyxl")
    df.to_excel(output, index=False, sheet_name="Расписание")
    output.close()

    with open("schedule_export.xlsx", "rb") as f:
        content = f.read()

    response = make_response(content)
    response.headers["Content-Disposition"] = "attachment; filename=schedule.xlsx"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response


@app.route("/admin/schedule/export/pdf")
def export_schedule_pdf():
    if not session.get("logged_in"):
        return redirect("/login")

    subject = request.args.get("subject")
    name = request.args.get("name")
    date = request.args.get("date")

    today = datetime.now(timezone.utc).date()
    query = Signup.query.filter(Signup.preferred_date >= str(today))

    if subject:
        query = query.filter(Signup.subject == subject)
    if name:
        query = query.filter(Signup.name.ilike(f"%{name}%"))
    if date:
        query = query.filter(Signup.preferred_date == date)

    data = query.order_by(Signup.preferred_date, Signup.preferred_time).all()

    rendered = render_template("admin_schedule_pdf.html", schedule=data)
    pdf = HTML(string=rendered).write_pdf()

    response = make_response(pdf)
    response.headers["Content-Disposition"] = "attachment; filename=schedule.pdf"
    response.headers["Content-Type"] = "application/pdf"
    return response

@app.route("/student", methods=["GET", "POST"])
def student_portal():
    records = []
    email = ""
    if request.method == "POST":
        email = request.form.get("email") or request.args.get("email")
        records = Signup.query.filter(Signup.email == email).order_by(
            Signup.preferred_date, Signup.preferred_time
        ).all()
    return render_template("student_portal.html", records=records, email=email)

@app.route("/student/delete/<int:entry_id>", methods=["POST"])
def student_delete_entry(entry_id):
    entry = Signup.query.get_or_404(entry_id)
    email = entry.email

    # ✅ Преобразуем дату к типу date (если она хранится как строка)
    if isinstance(entry.preferred_date, str):
        preferred_date = datetime.strptime(entry.preferred_date, "%Y-%m-%d").date()
    else:
        preferred_date = entry.preferred_date

    # Сохраняем в архив
    cancelled = CancelledSignup(
        name=entry.name,
        email=entry.email,
        subject=entry.subject,
        message=entry.message,
        preferred_date=preferred_date,  # уже точно дата
        preferred_time=entry.preferred_time
    )
    db.session.add(cancelled)

    db.session.delete(entry)
    db.session.commit()

    return redirect(f"/student?email={email}")

from datetime import datetime

@app.context_processor
def inject_now():
    return {'now': datetime.now}

if __name__ == "__main__":
    # Создаём базу данных при первом запуске
    with app.app_context():
        db.create_all()
    app.run(debug=True)