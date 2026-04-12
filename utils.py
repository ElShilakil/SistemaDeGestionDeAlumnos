from extensions import db
from models import User, Subject, Student, TeacherAssignment, Activity, Grade, Attendance
from datetime import datetime

def create_admin():
    if not User.query.filter_by(role='admin').first():
        admin = User(
            first_name="Administrador", 
            last_name_paternal="Escolar",
            last_name_maternal="",
            email="admin1@cinsurgentes.edu.mx", 
            role="admin"
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Admin user created: admin1@cinsurgentes.edu.mx / admin123")

def seed_data():
    if not Subject.query.first():
        s1 = Subject(name="Matemáticas", formative_field="Saberes y pensamiento científico")
        s2 = Subject(name="Español", formative_field="Lenguajes")
        db.session.add_all([s1, s2])
        db.session.commit()
        print("Subjects seeded.")

    if not User.query.filter_by(role='teacher').first():
        teacher = User(first_name="Juan", last_name_paternal="Pérez", last_name_maternal="García", email="profe1@cinsurgentes.edu.mx", role="teacher")
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
        std = Student(
            curp="ABCD123456HDFRRR01", 
            first_name="María", 
            last_name_paternal="López", 
            last_name_maternal="Sosa", 
            grade=1, 
            group="A", 
            nombre_tutor="Ana López", 
            telefono_tutor="555-1234", 
            email_tutor="ana@email.com"
        )
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
