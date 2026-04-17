from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import User, Student, TeacherAssignment, Subject, Grade, SchoolLevel, AcademicTerm, Activity, SchoolPeriod
from decorators import login_required
from sqlalchemy.exc import IntegrityError
import re
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/periods', methods=['GET', 'POST'])
@login_required(permission='MANAGE_STUDENTS')
def manage_periods():
    if request.method == 'POST':
        period_id = request.form.get('period_id')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        is_active = 'is_active' in request.form
        
        period = SchoolPeriod.query.get(period_id)
        if period:
            # Basic validation: start before end
            if start_date >= end_date:
                flash(f"Error en {period.name}: La fecha de inicio debe ser anterior a la de fin.", "error")
            else:
                # If activating, deactivate others
                if is_active:
                    SchoolPeriod.query.update({SchoolPeriod.is_active: False})
                
                period.start_date = start_date
                period.end_date = end_date
                period.is_active = is_active
                db.session.commit()
                flash(f"Periodo {period.name} actualizado.", "success")
                
    periods = SchoolPeriod.query.order_by(SchoolPeriod.id).all()
    # Ensure 3 periods exist
    if len(periods) < 3:
        for i in range(len(periods) + 1, 4):
            new_p = SchoolPeriod(
                name=f"Trimestre {i}", 
                start_date=datetime.now().date(), 
                end_date=datetime.now().date()
            )
            db.session.add(new_p)
        db.session.commit()
        periods = SchoolPeriod.query.order_by(SchoolPeriod.id).all()
        
    return render_template('admin/periods.html', periods=periods)

@admin_bp.route('/dashboard')
@login_required(permission='MANAGE_STUDENTS')
def admin_dashboard():
    teacher_count = User.query.filter_by(role='teacher').count()
    student_count = Student.query.filter_by(is_active=True).count()
    return render_template('admin/dashboard.html', teacher_count=teacher_count, student_count=student_count)

@admin_bp.route('/school-levels', methods=['GET', 'POST'])
@login_required(permission='MANAGE_STUDENTS')
def manage_school_levels():
    if request.method == 'POST':
        level_id = request.form.get('level_id')
        trimester_count = int(request.form.get('trimester_count'))
        
        level = SchoolLevel.query.get(level_id)
        if level:
            level.default_trimester_count = trimester_count
            
            # Manage AcademicTerms
            existing_terms = AcademicTerm.query.filter_by(school_level_id=level.id).all()
            existing_numbers = [t.term_number for t in existing_terms]
            
            # Add missing terms
            for i in range(1, trimester_count + 1):
                if i not in existing_numbers:
                    new_term = AcademicTerm(name=f"Trimestre {i}", school_level_id=level.id, term_number=i)
                    db.session.add(new_term)
            
            # Inactivate or re-activate terms based on count
            for term in existing_terms:
                if term.term_number > trimester_count:
                    term.is_active = False
                else:
                    term.is_active = True
                    
            db.session.commit()
            flash(f"Configuración de {level.name} actualizada con éxito.", "success")
            
    levels = SchoolLevel.query.all()
    return render_template('admin/school_levels.html', levels=levels)

@admin_bp.route('/teachers', methods=['GET', 'POST'])
@login_required(permission='MANAGE_TEACHERS')
def manage_teachers():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name_paternal = request.form.get('last_name_paternal')
        last_name_maternal = request.form.get('last_name_maternal')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # REQ-02: Prefix must be > 4 characters (min 5)
        if not re.match(r'^[^@]{5,}@cinsurgentes\.edu\.mx$', email):
            flash("El correo debe tener al menos 5 caracteres antes del dominio @cinsurgentes.edu.mx", "error")
        elif User.query.filter_by(email=email).first():
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

@admin_bp.route('/teachers/toggle/<int:id>')
@login_required(permission='MANAGE_TEACHERS')
def toggle_teacher(id):
    teacher = User.query.get_or_404(id)
    teacher.is_active = not teacher.is_active
    db.session.commit()
    status = "activado" if teacher.is_active else "desactivado"
    flash(f"Profesor {status} con éxito.", "success")
    return redirect(url_for('admin.manage_teachers'))

@admin_bp.route('/teachers/edit/<int:id>', methods=['GET', 'POST'])
@login_required(permission='MANAGE_TEACHERS')
def edit_teacher(id):
    teacher = User.query.get_or_404(id)
    if request.method == 'POST':
        email = request.form.get('email')
        # REQ-02: Prefix must be > 4 characters (min 5)
        if not re.match(r'^[^@]{5,}@cinsurgentes\.edu\.mx$', email):
            flash("El correo debe tener al menos 5 caracteres antes del dominio @cinsurgentes.edu.mx", "error")
            return redirect(url_for('admin.edit_teacher', id=id))
        
        if email != teacher.email and User.query.filter_by(email=email).first():
            flash("Ese correo ya está en uso por otro usuario.", "error")
            return redirect(url_for('admin.edit_teacher', id=id))

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
            return redirect(url_for('admin.manage_teachers'))
        except Exception:
            db.session.rollback()
            flash("Error al actualizar datos.", "error")

    return render_template('admin/edit_teacher.html', teacher=teacher)

@admin_bp.route('/students', methods=['GET', 'POST'])
@login_required(permission='MANAGE_STUDENTS')
def manage_students():
    if request.method == 'POST':
        curp = request.form.get('curp')
        first_name = request.form.get('first_name')
        last_name_paternal = request.form.get('last_name_paternal')
        last_name_maternal = request.form.get('last_name_maternal')
        nombre_tutor = request.form.get('nombre_tutor')
        telefono_tutor = request.form.get('telefono_tutor')
        email_tutor = request.form.get('email_tutor')
        grade = request.form.get('grade')
        group = request.form.get('group')
        school_level_id = request.form.get('school_level_id')
        
        if Student.query.filter_by(curp=curp).first():
            flash("El CURP ya está registrado.", "error")
        else:
            try:
                new_student = Student(
                    curp=curp, 
                    first_name=first_name,
                    last_name_paternal=last_name_paternal,
                    last_name_maternal=last_name_maternal,
                    nombre_tutor=nombre_tutor,
                    telefono_tutor=telefono_tutor,
                    email_tutor=email_tutor,
                    grade=grade, 
                    group=group,
                    school_level_id=school_level_id
                )
                db.session.add(new_student)
                db.session.commit()
                flash("Estudiante registrado con éxito.", "success")
            except Exception:
                db.session.rollback()
                flash("Error al registrar el estudiante.", "error")
            
    students = Student.query.filter_by(is_active=True).order_by(Student.grade, Student.group).all()
    levels = SchoolLevel.query.all()
    return render_template('admin/students.html', students=students, levels=levels)

@admin_bp.route('/students/edit/<int:id>', methods=['GET', 'POST'])
@login_required(permission='MANAGE_STUDENTS')
def edit_student(id):
    student = Student.query.get_or_404(id)
    if request.method == 'POST':
        curp = request.form.get('curp')
        if curp != student.curp and Student.query.filter_by(curp=curp).first():
            flash("Ese CURP ya pertenece a otro estudiante.", "error")
            return redirect(url_for('admin.edit_student', id=id))

        try:
            student.curp = curp
            student.first_name = request.form.get('first_name')
            student.last_name_paternal = request.form.get('last_name_paternal')
            student.last_name_maternal = request.form.get('last_name_maternal')
            student.nombre_tutor = request.form.get('nombre_tutor')
            student.telefono_tutor = request.form.get('telefono_tutor')
            student.email_tutor = request.form.get('email_tutor')
            student.grade = request.form.get('grade')
            student.group = request.form.get('group')
            student.school_level_id = request.form.get('school_level_id')
            
            db.session.commit()
            flash("Datos del estudiante actualizados.", "success")
            return redirect(url_for('admin.manage_students'))
        except Exception:
            db.session.rollback()
            flash("Error al actualizar datos.", "error")

    levels = SchoolLevel.query.all()
    return render_template('admin/edit_student.html', student=student, levels=levels)

@admin_bp.route('/students/toggle/<int:id>')
@login_required(permission='MANAGE_STUDENTS')
def toggle_student(id):
    student = Student.query.get_or_404(id)
    student.is_active = not student.is_active
    db.session.commit()
    status = "activado" if student.is_active else "desactivado (borrado lógico)"
    flash(f"Estudiante {status} con éxito.", "success")
    return redirect(url_for('admin.manage_students'))

@admin_bp.route('/assignments', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ASSIGNMENTS')
def manage_assignments():
    if request.method == 'POST':
        teacher_id = request.form.get('teacher_id')
        grade = request.form.get('grade')
        group = request.form.get('group')
        
        existing_group = TeacherAssignment.query.filter_by(grade=grade, group=group).first()
        if existing_group and str(existing_group.teacher_id) != str(teacher_id):
            flash(f"El grupo {grade}°{group} ya tiene un profesor asignado ({existing_group.teacher.full_name}).", "error")
            return redirect(url_for('admin.manage_assignments'))

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

@admin_bp.route('/subjects', methods=['GET', 'POST'])
@login_required(permission='MANAGE_SUBJECTS')
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

@admin_bp.route('/subjects/edit/<int:id>', methods=['GET', 'POST'])
@login_required(permission='MANAGE_SUBJECTS')
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
        return redirect(url_for('admin.manage_subjects'))
    return render_template('admin/edit_subject.html', subject=subject, fields=formative_fields)

@admin_bp.route('/reports')
@login_required(permission='VIEW_REPORTS')
def list_reports():
    students = Student.query.filter_by(is_active=True).order_by(Student.grade, Student.group).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)
    return render_template('admin/reports_list.html', students=students)

@admin_bp.route('/reports/view/<int:student_id>')
@login_required(permission='VIEW_REPORTS')
def view_report_card(student_id):
    student = Student.query.get_or_404(student_id)
    
    # REQ: 3 periods (T1, T2, T3)
    periods = SchoolPeriod.query.order_by(SchoolPeriod.id).limit(3).all()
    
    formative_fields = [
        "Lenguajes",
        "Saberes y pensamiento científico",
        "Ética, naturaleza y sociedades",
        "De lo humano y lo comunitario"
    ]
    
    # Structure: field_name -> { subjects: { name -> { t1, t2, t3 } }, average: { t1, t2, t3 } }
    report_matrix = {}
    for field in formative_fields:
        report_matrix[field] = {'subjects': {}, 'averages': {p.id: 0 for p in periods}}
        
    subjects = Subject.query.all()
    for subj in subjects:
        report_matrix[subj.formative_field]['subjects'][subj.id] = {
            'name': subj.name,
            'scores': {p.id: 0 for p in periods}
        }
        
    for period in periods:
        grades = Grade.query.join(Activity).filter(
            Grade.student_id == student_id,
            Activity.period_id == period.id
        ).all()
        
        # Calculate subject averages for this period
        subj_totals = {} # subj_id -> [scores]
        for g in grades:
            sid = g.activity.subject_id
            if sid not in subj_totals: subj_totals[sid] = []
            subj_totals[sid].append(g.score)
            
        for sid, scores in subj_totals.items():
            avg = sum(scores) / len(scores)
            field = Subject.query.get(sid).formative_field
            report_matrix[field]['subjects'][sid]['scores'][period.id] = avg
            
    # Calculate field averages per period
    for field in formative_fields:
        for period in periods:
            subjs_in_field = [s for s in report_matrix[field]['subjects'].values() if s['scores'][period.id] > 0]
            if subjs_in_field:
                report_matrix[field]['averages'][period.id] = sum(s['scores'][period.id] for s in subjs_in_field) / len(subjs_in_field)

    return render_template('admin/view_report.html', 
                           student=student, 
                           report_matrix=report_matrix, 
                           periods=periods,
                           today=datetime.now())
