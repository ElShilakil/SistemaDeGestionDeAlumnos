import os
from flask import Flask
from extensions import db, session_manager
from utils import create_admin

def create_app():
    app = Flask(__name__)

<<<<<<< Updated upstream
    # Configuración
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_school_control_123')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost/colegio_insurgentes')
=======
    # Configuración para el Sistema de Gestión de Control Académico (Colegio Insurgentes)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_colegio_insurgentes_2026')

    # IMPORTANTE: Reemplaza 'TU_NUEVA_CONTRASEÑA' con la clave que acabas de configurar en pgAdmin
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 
        'postgresql://postgres:1995@localhost:5432/colegio_insurgentes'
    )

>>>>>>> Stashed changes
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_TYPE'] = 'filesystem'

    # Inicialización de extensiones
    db.init_app(app)
    session_manager.init_app(app)

    # Registro de Blueprints
    from blueprints.auth import auth_bp
    from blueprints.admin import admin_bp
    from blueprints.teacher import teacher_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)

    return app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            create_admin()
            print("Database setup complete.")
        except Exception as e:
            print(f"Error: {e}")
    
    app.run(debug=True)
