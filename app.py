import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from sqlalchemy import UniqueConstraint
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_school_control_123')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost/school_system')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name_paternal = db.Column(db.String(50), nullable=False)
    last_name_maternal = db.Column(db.String(50))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name_paternal} {self.last_name_maternal or ''}".strip()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    curp = db.Column(db.String(18), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name_paternal = db.Column(db.String(50), nullable=False)
    last_name_maternal = db.Column(db.String(50))
    tutor_data = db.Column(db.Text)
    grade = db.Column(db.Integer, nullable=False)
    group = db.Column(db.String(1), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name_paternal} {self.last_name_maternal or ''}".strip()

class TeacherAssignment(db.Model):
    __tablename__ = 'teacher_assignments'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    group = db.Column(db.String(1), nullable=False)
    
    teacher = db.relationship('User', backref=db.backref('assignment', uselist=False))

    __table_args__ = (UniqueConstraint('grade', 'group', name='_grade_group_uc'),)

class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    formative_field = db.Column(db.String(100), nullable=False)

class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    percentage_value = db.Column(db.Float, nullable=False)

    subject = db.relationship('Subject', backref='activities')

class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)

    __table_args__ = (UniqueConstraint('student_id', 'activity_id', name='_student_activity_uc'),)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(10), nullable=False)

from functools import wraps

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Por favor, inicia sesión para acceder.", "error")
                return redirect(url_for('login'))
            if role and session.get('user_role') != role:
                flash("No tienes permiso para acceder a esta sección.", "error")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session.get('user_role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('teacher_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash("Esta cuenta ha sido desactivada.", "error")
                return redirect(url_for('login'))
            
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            session['user_role'] = user.role
            return redirect(url_for('index'))
        
        flash("Correo o contraseña incorrectos.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required(role='admin')
def admin_dashboard():
    teacher_count = User.query.filter_by(role='teacher').count()
    student_count = Student.query.count()
    return render_template('admin/dashboard.html', teacher_count=teacher_count, student_count=student_count)

from sqlalchemy.exc import IntegrityError

@app.route('/admin/teachers', methods=['GET', 'POST'])
@login_required(role='admin')
def manage_teachers():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name_paternal = request.form.get('last_name_paternal')
        last_name_maternal = request.form.get('last_name_maternal')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash("El correo ya está registrado.", "error")
        else:
            try:
                new_teacher = User(
                    first_name=first_name, 
                    last_name_paternal=last_name_paternal, 
                    last_name_maternal=last_name_maternal,
                    email=email, 
                    role='teacher'
                )
                new_teacher.set_password(password)
                db.session.add(new_teacher)
                db.session.commit()
                flash("Profesor registrado con éxito.", "success")
            except Exception:
                db.session.rollback()
                flash("Error al registrar el profesor.", "error")
    
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('admin/teachers.html', teachers=teachers)

@app.route('/admin/teachers/toggle/<int:id>')
@login_required(role='admin')
def toggle_teacher(id):
    teacher = User.query.get_or_404(id)
    teacher.is_active = not teacher.is_active
    db.session.commit()
    status = "activado" if teacher.is_active else "desactivado"
    flash(f"Profesor {status} con éxito.", "success")
    return redirect(url_for('manage_teachers'))

@app.route('/admin/teachers/edit/<int:id>', methods=['GET', 'POST'])
@login_required(role='admin')
def edit_teacher(id):
    teacher = User.query.get_or_404(id)
    if request.method == 'POST':
        email = request.form.get('email')
        if email != teacher.email and User.query.filter_by(email=email).first():
            flash("Ese correo ya está en uso por otro usuario.", "error")
            return redirect(url_for('edit_teacher', id=id))

        try:
            teacher.first_name = request.form.get('first_name')
            teacher.last_name_paternal = request.form.get('last_name_paternal')
            teacher.last_name_maternal = request.form.get('last_name_maternal')
            teacher.email = email
            
            new_password = request.form.get('password')
            if new_password:
                teacher.set_password(new_password)
                
            db.session.commit()
            flash("Datos del profesor actualizados.", "success")
            return redirect(url_for('manage_teachers'))
        except Exception:
            db.session.rollback()
            flash("Error al actualizar datos.", "error")

    return render_template('admin/edit_teacher.html', teacher=teacher)

@app.route('/admin/students', methods=['GET', 'POST'])
@login_required(role='admin')
def manage_students():
    if request.method == 'POST':
        curp = request.form.get('curp')
        first_name = request.form.get('first_name')
        last_name_paternal = request.form.get('last_name_paternal')
        last_name_maternal = request.form.get('last_name_maternal')
        tutor_data = request.form.get('tutor_data')
        grade = request.form.get('grade')
        group = request.form.get('group')
        
        if Student.query.filter_by(curp=curp).first():
            flash("El CURP ya está registrado.", "error")
        else:
            try:
                new_student = Student(
                    curp=curp, 
                    first_name=first_name,
                    last_name_paternal=last_name_paternal,
                    last_name_maternal=last_name_maternal,
                    tutor_data=tutor_data, 
                    grade=grade, 
                    group=group
                )
                db.session.add(new_student)
                db.session.commit()
                flash("Estudiante registrado con éxito.", "success")
            except Exception:
                db.session.rollback()
                flash("Error al registrar el estudiante.", "error")
            
    students = Student.query.order_by(Student.grade, Student.group).all()
    return render_template('admin/students.html', students=students)

@app.route('/admin/students/edit/<int:id>', methods=['GET', 'POST'])
@login_required(role='admin')
def edit_student(id):
    student = Student.query.get_or_404(id)
    if request.method == 'POST':
        curp = request.form.get('curp')
        if curp != student.curp and Student.query.filter_by(curp=curp).first():
            flash("Ese CURP ya pertenece a otro estudiante.", "error")
            return redirect(url_for('edit_student', id=id))

        try:
            student.curp = curp
            student.first_name = request.form.get('first_name')
            student.last_name_paternal = request.form.get('last_name_paternal')
            student.last_name_maternal = request.form.get('last_name_maternal')
            student.tutor_data = request.form.get('tutor_data')
            student.grade = request.form.get('grade')
            student.group = request.form.get('group')
            
            db.session.commit()
            flash("Datos del estudiante actualizados.", "success")
            return redirect(url_for('manage_students'))
        except Exception:
            db.session.rollback()
            flash("Error al actualizar datos.", "error")

    return render_template('admin/edit_student.html', student=student)

@app.route('/admin/assignments', methods=['GET', 'POST'])
@login_required(role='admin')
def manage_assignments():
    if request.method == 'POST':
        teacher_id = request.form.get('teacher_id')
        grade = request.form.get('grade')
        group = request.form.get('group')
        
        existing_group = TeacherAssignment.query.filter_by(grade=grade, group=group).first()
        if existing_group and str(existing_group.teacher_id) != str(teacher_id):
            flash(f"El grupo {grade}°{group} ya tiene un profesor asignado ({existing_group.teacher.full_name}).", "error")
            return redirect(url_for('manage_assignments'))

        existing_teacher = TeacherAssignment.query.filter_by(teacher_id=teacher_id).first()
        
        try:
            if existing_teacher:
                existing_teacher.grade = grade
                existing_teacher.group = group
                flash("Asignación actualizada.", "success")
            else:
                new_assignment = TeacherAssignment(teacher_id=teacher_id, grade=grade, group=group)
                db.session.add(new_assignment)
                flash("Asignación creada con éxito.", "success")
            
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Error de integridad: Esta asignación viola las reglas del sistema.", "error")
        except Exception:
            db.session.rollback()
            flash("Ocurrió un error inesperado al guardar la asignación.", "error")
        
    teachers = User.query.filter_by(role='teacher', is_active=True).all()
    assignments = TeacherAssignment.query.all()
    return render_template('admin/assignments.html', teachers=teachers, assignments=assignments)

@app.route('/admin/subjects', methods=['GET', 'POST'])
@login_required(role='admin')
def manage_subjects():
    formative_fields = [
        "Lenguajes",
        "Saberes y pensamiento científico",
        "Ética, naturaleza y sociedades",
        "De lo humano y lo comunitario"
    ]
    if request.method == 'POST':
        name = request.form.get('name')
        formative_field = request.form.get('formative_field')
        
        new_subject = Subject(name=name, formative_field=formative_field)
        db.session.add(new_subject)
        db.session.commit()
        flash("Materia registrada con éxito.", "success")
            
    subjects = Subject.query.all()
    return render_template('admin/subjects.html', subjects=subjects, fields=formative_fields)

@app.route('/admin/subjects/edit/<int:id>', methods=['GET', 'POST'])
@login_required(role='admin')
def edit_subject(id):
    subject = Subject.query.get_or_404(id)
    formative_fields = [
        "Lenguajes",
        "Saberes y pensamiento científico",
        "Ética, naturaleza y sociedades",
        "De lo humano y lo comunitario"
    ]
    if request.method == 'POST':
        subject.name = request.form.get('name')
        subject.formative_field = request.form.get('formative_field')
        db.session.commit()
        flash("Materia actualizada.", "success")
        return redirect(url_for('manage_subjects'))
    return render_template('admin/edit_subject.html', subject=subject, fields=formative_fields)

@app.route('/teacher/dashboard')
@login_required(role='teacher')
def teacher_dashboard():
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado. Contacta al administrador.", "error")
        return render_template('teacher/dashboard.html', assignment=None)
    
    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)
    
    return render_template('teacher/dashboard.html', assignment=assignment, students=students)

@app.route('/teacher/attendance', methods=['GET', 'POST'])
@login_required(role='teacher')
def manage_attendance():
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado.", "error")
        return redirect(url_for('teacher_dashboard'))

    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)
    today = datetime.now().date()
    
    if request.method == 'POST':
        date_str = request.form.get('date')
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        for student in students:
            status = request.form.get(f'status_{student.id}')
            att = Attendance.query.filter_by(student_id=student.id, date=selected_date).first()
            if att:
                att.status = status
            else:
                new_att = Attendance(student_id=student.id, date=selected_date, status=status)
                db.session.add(new_att)
        
        db.session.commit()
        flash(f"Asistencia del {selected_date} guardada.", "success")
        return redirect(url_for('manage_attendance'))

    current_att = {a.student_id: a.status for a in Attendance.query.filter_by(date=today).all()}
    return render_template('teacher/attendance.html', students=students, today=today, current_att=current_att)

@app.route('/teacher/activities', methods=['GET', 'POST'])
@login_required(role='teacher')
def manage_activities():
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        name = request.form.get('name')
        type = request.form.get('type')
        date_str = request.form.get('date')
        percentage = request.form.get('percentage')
        
        new_activity = Activity(
            teacher_id=session['user_id'],
            subject_id=subject_id,
            name=name,
            type=type,
            date=datetime.strptime(date_str, '%Y-%m-%d').date(),
            percentage_value=float(percentage)
        )
        db.session.add(new_activity)
        db.session.commit()
        flash("Actividad creada con éxito.", "success")
    
    subjects = Subject.query.all()
    activities = Activity.query.filter_by(teacher_id=session['user_id']).order_by(Activity.date.desc()).all()
    return render_template('teacher/activities.html', subjects=subjects, activities=activities)

@app.route('/teacher/gradebook', methods=['GET', 'POST'])
@login_required(role='teacher')
def gradebook():
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado.", "error")
        return redirect(url_for('teacher_dashboard'))

    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)

    activities = Activity.query.filter_by(teacher_id=session['user_id']).order_by(Activity.subject_id, Activity.date).all()
    
    if request.method == 'POST':
        for student in students:
            for activity in activities:
                score_key = f'score_{student.id}_{activity.id}'
                score_val = request.form.get(score_key)
                
                if score_val:
                    grade_obj = Grade.query.filter_by(student_id=student.id, activity_id=activity.id).first()
                    if grade_obj:
                        grade_obj.score = float(score_val)
                    else:
                        new_grade = Grade(student_id=student.id, activity_id=activity.id, score=float(score_val))
                        db.session.add(new_grade)
        
        db.session.commit()
        flash("Calificaciones guardadas con éxito.", "success")
        return redirect(url_for('gradebook'))

    existing_grades = {(g.student_id, g.activity_id): g.score for g in Grade.query.all()}
    
    return render_template('teacher/gradebook.html', students=students, activities=activities, existing_grades=existing_grades)

@app.route('/admin/reports')
@login_required(role='admin')
def list_reports():
    students = Student.query.order_by(Student.grade, Student.group).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)
    return render_template('admin/reports_list.html', students=students)

@app.route('/admin/reports/view/<int:student_id>')
@login_required()
def view_report_card(student_id):
    student = Student.query.get_or_404(student_id)
    
    grades = Grade.query.filter_by(student_id=student_id).all()
    
    subject_data = {}
    
    for g in grades:
        activity = g.activity
        subj = activity.subject
        if subj.id not in subject_data:
            subject_data[subj.id] = {
                'name': subj.name,
                'field': subj.formative_field,
                'scores': []
            }
        subject_data[subj.id]['scores'].append(g.score)
    
    for sid in subject_data:
        scores = subject_data[sid]['scores']
        subject_data[sid]['average'] = sum(scores) / len(scores) if scores else 0
    
    field_data = {}
    formative_fields = [
        "Lenguajes",
        "Saberes y pensamiento científico",
        "Ética, naturaleza y sociedades",
        "De lo humano y lo comunitario"
    ]
    
    for field in formative_fields:
        field_data[field] = {'subjects': [], 'average': 0}
        
    for sid in subject_data:
        data = subject_data[sid]
        field_data[data['field']]['subjects'].append(data)
        
    for field in field_data:
        subjs = field_data[field]['subjects']
        if subjs:
            field_data[field]['average'] = sum(s['average'] for s in subjs) / len(subjs)
        else:
            field_data[field]['average'] = 0
            
    return render_template('admin/view_report.html', student=student, field_data=field_data, today=datetime.now())

def create_admin():
    with app.app_context():
        if not User.query.filter_by(role='admin').first():
            admin = User(
                first_name="Administrador", 
                last_name_paternal="Escolar",
                last_name_maternal="",
                email="admin@escuela.com", 
                role="admin"
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: admin@escuela.com / admin123")


def seed_data():
    with app.app_context():
        if not Subject.query.first():
            s1 = Subject(name="Matemáticas", formative_field="Saberes y pensamiento científico")
            s2 = Subject(name="Español", formative_field="Lenguajes")
            db.session.add_all([s1, s2])
            db.session.commit()
            print("Subjects seeded.")

        if not User.query.filter_by(role='teacher').first():
            teacher = User(first_name="Juan", last_name_paternal="Pérez", last_name_maternal="García", email="maestro@escuela.com", role="teacher")
            teacher.set_password("maestro123")
            db.session.add(teacher)
            db.session.commit()
            print("Teacher seeded.")

            if not TeacherAssignment.query.filter_by(teacher_id=teacher.id).first():
                ass = TeacherAssignment(teacher_id=teacher.id, grade=1, group="A")
                db.session.add(ass)
                db.session.commit()
                print("Assignment seeded.")

        if not Student.query.first():
            std = Student(curp="ABCD123456HDFRRR01", first_name="María", last_name_paternal="López", last_name_maternal="Sosa", grade=1, group="A", tutor_data="Ana López - 555-1234")
            db.session.add(std)
            db.session.commit()
            print("Student seeded.")

        t = User.query.filter_by(role='teacher').first()
        s = Subject.query.first()
        if t and s and not Activity.query.first():
            act = Activity(teacher_id=t.id, subject_id=s.id, name="Examen 1", type="Examen", percentage_value=20.0)
            db.session.add(act)
            db.session.commit()
            print("Activity seeded.")

        st = Student.query.first()
        ac = Activity.query.first()
        if st and ac and not Grade.query.first():
            db.session.add(Grade(student_id=st.id, activity_id=ac.id, score=9.5))
            db.session.add(Attendance(student_id=st.id, status="Present"))
            db.session.commit()
            print("Grades and Attendance seeded.")

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            create_admin()
            seed_data()
            print("Database setup complete.")
        except Exception as e:
            print(f"Error: {e}")
    
    app.run(debug=True)
