from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db
from models import Student, TeacherAssignment, Activity, Grade, Attendance, Subject, AcademicTerm, ActivityPercentageConfig, SchoolLevel
from decorators import login_required
from datetime import datetime

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def get_active_term():
    term_id = session.get('active_term_id')
    if not term_id:
        assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
        if assignment:
            student = Student.query.filter_by(grade=assignment.grade, group=assignment.group).first()
            if student:
                term = AcademicTerm.query.filter_by(school_level_id=student.school_level_id, is_active=True).first()
                if term:
                    session['active_term_id'] = term.id
                    return term
    return AcademicTerm.query.get(term_id) if term_id else None

@teacher_bp.context_processor
def inject_terms():
    active_term = get_active_term()
    assignment = TeacherAssignment.query.filter_by(teacher_id=session.get('user_id')).first()
    all_terms = []
    if assignment:
        student = Student.query.filter_by(grade=assignment.grade, group=assignment.group).first()
        if student:
            all_terms = AcademicTerm.query.filter_by(school_level_id=student.school_level_id, is_active=True).all()
    return dict(active_term=active_term, all_terms=all_terms)

@teacher_bp.route('/set-term', methods=['POST'])
@login_required(permission='VIEW_TEACHER_DASHBOARD')
def set_term():
    term_id = request.form.get('term_id')
    if term_id:
        session['active_term_id'] = int(term_id)
        flash(f"Trimestre cambiado.", "info")
        return redirect(request.referrer or url_for('teacher.teacher_dashboard'))
    return redirect(url_for('teacher.teacher_dashboard'))

@teacher_bp.route('/dashboard')
@login_required(permission='VIEW_TEACHER_DASHBOARD')
def teacher_dashboard():
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado. Contacta al administrador.", "error")
        return render_template('teacher/dashboard.html', assignment=None)
    
    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group, is_active=True).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)
    
    return render_template('teacher/dashboard.html', assignment=assignment, students=students)

@teacher_bp.route('/activity-config', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ACTIVITIES')
def activity_config():
    term = get_active_term()
    if not term:
        flash("Selecciona un trimestre primero.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))
    
    formative_fields = [
        "Lenguajes",
        "Saberes y pensamiento científico",
        "Ética, naturaleza y sociedades",
        "De lo humano y lo comunitario"
    ]
    activity_types = ["Tarea", "Examen", "Proyecto"]
    
    if request.method == 'POST':
        field = request.form.get('formative_field')
        total_percent = 0
        configs = []
        for atype in activity_types:
            val_str = request.form.get(f'percent_{atype}', '0')
            val = float(val_str) if val_str else 0
            total_percent += val
            configs.append((atype, val))
        
        if total_percent > 100:
            flash(f"La suma de porcentajes para {field} no puede exceder 100%. (Total: {total_percent}%)", "error")
        else:
            for atype, val in configs:
                conf = ActivityPercentageConfig.query.filter_by(
                    teacher_id=session['user_id'],
                    term_id=term.id,
                    formative_field=field,
                    activity_type=atype
                ).first()
                if conf:
                    conf.percentage = val
                else:
                    new_conf = ActivityPercentageConfig(
                        teacher_id=session['user_id'],
                        term_id=term.id,
                        formative_field=field,
                        activity_type=atype,
                        percentage=val
                    )
                    db.session.add(new_conf)
            db.session.commit()
            flash(f"Configuración para {field} guardada con éxito.", "success")
            
    existing_configs = ActivityPercentageConfig.query.filter_by(
        teacher_id=session['user_id'], 
        term_id=term.id
    ).all()
    
    config_map = {(c.formative_field, c.activity_type): c.percentage for c in existing_configs}
    
    return render_template('teacher/activity_config.html', fields=formative_fields, types=activity_types, config_map=config_map, term=term)

@teacher_bp.route('/attendance', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ATTENDANCE')
def manage_attendance():
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group, is_active=True).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)

    term = get_active_term()
    if not term:
        flash("Selecciona un trimestre.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))
    
    # Manejar fecha seleccionada por el usuario o usar la de hoy
    selected_date_str = request.form.get('date') if request.method == 'POST' else request.args.get('date')
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    else:
        selected_date = datetime.now().date()
    
    if request.method == 'POST':
        for student in students:
            status = request.form.get(f'status_{student.id}')
            if status:
                att = Attendance.query.filter_by(student_id=student.id, date=selected_date).first()
                if att:
                    att.status = status
                    att.term_id = term.id
                else:
                    new_att = Attendance(student_id=student.id, date=selected_date, status=status, term_id=term.id)
                    db.session.add(new_att)
        
        db.session.commit()
        flash(f"Asistencia del {selected_date} guardada con éxito.", "success")
        return redirect(url_for('teacher.manage_attendance', date=selected_date))

    current_att = {a.student_id: a.status for a in Attendance.query.filter_by(date=selected_date).all()}
    selected_date_is_past = selected_date < datetime.now().date()
    
    # REQ-07: Fetch absences grouped by term for display
    absence_summary = {}
    for student in students:
        # Get all terms for this student's level
        level_terms = AcademicTerm.query.filter_by(school_level_id=student.school_level_id, is_active=True).all()
        absence_summary[student.id] = {}
        for t in level_terms:
            absences = Attendance.query.filter_by(student_id=student.id, term_id=t.id, status='Falta').count()
            absence_summary[student.id][t.id] = absences

    return render_template('teacher/attendance.html', 
                           students=students, 
                           selected_date=selected_date, 
                           current_att=current_att, 
                           selected_date_is_past=selected_date_is_past,
                           term=term,
                           absence_summary=absence_summary)

@teacher_bp.route('/activities', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ACTIVITIES')
def manage_activities():
    term = get_active_term()
    if not term:
        flash("Selecciona un trimestre.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        name = request.form.get('name')
        type = request.form.get('type')
        date_str = request.form.get('date')
        percentage = request.form.get('percentage')
        
        # REQ-05: Validation against configured percentage
        subject = Subject.query.get(subject_id)
        config = ActivityPercentageConfig.query.filter_by(
            teacher_id=session['user_id'],
            term_id=term.id,
            formative_field=subject.formative_field,
            activity_type=type
        ).first()
        
        allowed_max = config.percentage if config else 0
        if allowed_max == 0:
            flash(f"No has configurado un porcentaje para '{type}' en el campo '{subject.formative_field}'.", "error")
        else:
            # Check current total for this type/field/term
            current_activities = Activity.query.filter_by(
                teacher_id=session['user_id'],
                subject_id=subject_id,
                term_id=term.id,
                type=type
            ).all()
            current_total = sum(a.percentage_value for a in current_activities)
            
            if current_total + float(percentage) > allowed_max:
                flash(f"El valor excede el máximo permitido para '{type}' ({allowed_max}%). Ya tienes {current_total}%.", "error")
            else:
                new_activity = Activity(
                    teacher_id=session['user_id'],
                    subject_id=subject_id,
                    term_id=term.id,
                    name=name,
                    type=type,
                    date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                    percentage_value=float(percentage)
                )
                db.session.add(new_activity)
                db.session.commit()
                flash("Actividad creada con éxito.", "success")
    
    subjects = Subject.query.all()
    activities = Activity.query.filter_by(teacher_id=session['user_id'], term_id=term.id).order_by(Activity.date.desc()).all()
    return render_template('teacher/activities.html', subjects=subjects, activities=activities, term=term)

@teacher_bp.route('/gradebook', methods=['GET', 'POST'])
@login_required(permission='MANAGE_GRADES')
def gradebook():
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group, is_active=True).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)

    term = get_active_term()
    if not term:
        flash("Selecciona un trimestre.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    activities = Activity.query.filter_by(teacher_id=session['user_id'], term_id=term.id).order_by(Activity.subject_id, Activity.date).all()
    
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
        return redirect(url_for('teacher.gradebook'))

    existing_grades = {(g.student_id, g.activity_id): g.score for g in Grade.query.all()}
    
    return render_template('teacher/gradebook.html', students=students, activities=activities, existing_grades=existing_grades)
