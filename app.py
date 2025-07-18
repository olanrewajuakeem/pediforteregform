from flask import Flask, request, jsonify, session, send_file
from flask_restful import Api, Resource, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flasgger import Swagger
from werkzeug.utils import secure_filename
from models import (
    db, StudentInformation, CourseInformation, PaymentInformation, Admin,
    StudentRules, StudentAgreement,
    get_gender_statistics, get_age_group_statistics
)
from datetime import datetime, date
import os
import csv
import io
import json
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app and API
app = Flask(__name__)
api = Api(app)

# Swagger configuration
swagger_config = {
    "openapi": "3.0.0",
    "info": {
        "title": "Pediforte Student Management API",
        "description": "API for managing student registrations, rules, and admin operations",
        "version": "1.0.0"
    },
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "blueprint_name": "pediforte_flasgger"
}

swagger = Swagger(app, template_file='swagger.yml', config=swagger_config)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['UPLOAD_FOLDER'] = 'Uploads/passports'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file size

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db.init_app(app)
migrate = Migrate(app, db)

# Enable CORS for API routes
CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:4200", "http://127.0.0.1:5000", "http://localhost:5000"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "X-Session-ID"]
}}, supports_credentials=True)

# Allowed file extensions for passport upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            abort(401, message="Admin authentication required")
        return f(*args, **kwargs)
    return decorated_function

# Admin Authentication Resources
class AdminLogin(Resource):
    def post(self):
        data = request.get_json()
        if not data or not all(k in data for k in ['username', 'password']):
            abort(400, message="Username and password required")
        
        admin = Admin.query.filter_by(username=data['username']).first()
        if admin and admin.check_password(data['password']):
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            return {
                'message': 'Login successful',
                'admin': {
                    'id': admin.id,
                    'username': admin.username,
                    'email': admin.email
                }
            }, 200
        else:
            abort(401, message="Invalid credentials")

class AdminLogout(Resource):
    def post(self):
        session.pop('admin_id', None)
        session.pop('admin_username', None)
        return {'message': 'Logout successful'}, 200

class AdminRegister(Resource):
    def post(self):
        data = request.get_json()
        if not data or not all(k in data for k in ['username', 'email', 'password']):
            abort(400, message="Username, email and password required")
        
        # Check if admin already exists
        if Admin.query.filter_by(username=data['username']).first():
            abort(400, message="Username already exists")
        if Admin.query.filter_by(email=data['email']).first():
            abort(400, message="Email already exists")
        
        admin = Admin(
            username=data['username'],
            email=data['email']
        )
        admin.set_password(data['password'])
        
        db.session.add(admin)
        db.session.commit()
        
        return {'message': 'Admin registered successfully'}, 201

# Student Rules Management Resources
class StudentRulesResource(Resource):
    def get(self):
        """Get active student rules (public endpoint)"""
        active_rules = StudentRules.get_active_rules()
        if not active_rules:
            return {'rules_content': '', 'version': '1.0'}, 200
        return active_rules.to_dict(), 200

class AdminStudentRulesResource(Resource):
    @admin_required
    def get(self):
        """Get all student rules versions (admin only)"""
        rules = StudentRules.query.order_by(StudentRules.created_at.desc()).all()
        return [rule.to_dict() for rule in rules], 200
    
    @admin_required
    def post(self):
        """Create new student rules version (admin only)"""
        data = request.get_json()
        if not data or 'rules_content' not in data:
            abort(400, message="Rules content is required")
        
        # Deactivate all existing rules
        StudentRules.query.update({'is_active': False})
        
        # Create new version
        version_number = len(StudentRules.query.all()) + 1
        new_rules = StudentRules(
            rules_content=data['rules_content'],
            version=data.get('version', f'v{version_number}.0'),
            is_active=True,
            created_by=session['admin_id']
        )
        
        db.session.add(new_rules)
        db.session.commit()
        
        return new_rules.to_dict(), 201
    
    @admin_required
    def put(self):
        """Update active student rules (admin only)"""
        data = request.get_json()
        if not data or 'rules_content' not in data:
            abort(400, message="Rules content is required")
        
        active_rules = StudentRules.get_active_rules()
        if not active_rules:
            # Create new if none exists
            return self.post()
        
        active_rules.rules_content = data['rules_content']
        active_rules.version = data.get('version', active_rules.version)
        active_rules.updated_at = datetime.utcnow()
        
        db.session.commit()
        return active_rules.to_dict(), 200

class StudentAgreementResource(Resource):
    def post(self, student_id):
        """Record student agreement to rules"""
        data = request.get_json()
        if not data or not data.get('agreed'):
            abort(400, message="Student must agree to terms and conditions")
        
        student = StudentInformation.query.get_or_404(student_id)
        active_rules = StudentRules.get_active_rules()
        
        if not active_rules:
            abort(400, message="No active rules found")
        
        # Check if student already agreed to current rules
        existing_agreement = StudentAgreement.query.filter_by(
            student_id=student_id,
            rules_id=active_rules.id
        ).first()
        
        if existing_agreement:
            return {'message': 'Student has already agreed to current rules'}, 200
        
        # Create new agreement
        agreement = StudentAgreement(
            student_id=student_id,
            rules_id=active_rules.id,
            ip_address=request.environ.get('REMOTE_ADDR'),
            user_agent=request.headers.get('User-Agent', '')[:500]
        )
        
        # Update student record
        student.terms_agreed = True
        student.terms_agreed_at = datetime.utcnow()
        
        db.session.add(agreement)
        db.session.commit()
        
        return {
            'message': 'Terms and conditions accepted successfully',
            'agreement': agreement.to_dict()
        }, 201
    
    @admin_required
    def get(self, student_id):
        """Get student's agreement history (admin only)"""
        agreements = StudentAgreement.query.filter_by(student_id=student_id).all()
        return [agreement.to_dict() for agreement in agreements], 200

class AdminRulesAnalytics(Resource):
    @admin_required
    def get(self):
        """Get rules agreement analytics"""
        total_students = StudentInformation.query.count()
        agreed_students = StudentInformation.query.filter_by(terms_agreed=True).count()
        
        active_rules = StudentRules.get_active_rules()
        current_version_agreements = 0
        if active_rules:
            current_version_agreements = StudentAgreement.query.filter_by(
                rules_id=active_rules.id
            ).count()
        
        return {
            'total_students': total_students,
            'students_agreed': agreed_students,
            'students_not_agreed': total_students - agreed_students,
            'agreement_percentage': (agreed_students / total_students * 100) if total_students > 0 else 0,
            'current_version_agreements': current_version_agreements,
            'active_rules_version': active_rules.version if active_rules else None
        }, 200

# Student Form Resources 
class StudentForm(Resource):
    def get(self, form_id):
        student_info = StudentInformation.query.get_or_404(form_id)
        return student_info.to_dict(include_payment=False), 200

    def put(self, form_id):
        student_info = StudentInformation.query.get_or_404(form_id)
        data = request.get_json()
        
        if not data:
            abort(400, message="No data provided")
        
        # Update student information
        if 'surname' in data:
            student_info.surname = data['surname']
        if 'given_name' in data:
            student_info.given_name = data['given_name']
        if 'other_names' in data:
            student_info.other_names = data['other_names']
        if 'home_address' in data:
            student_info.home_address = data['home_address']
        if 'phone_number' in data:
            student_info.phone_number = data['phone_number']
        if 'email_address' in data:
            student_info.email_address = data['email_address']
        if 'dob' in data and data['dob']:
            student_info.dob = datetime.strptime(data['dob'], '%Y-%m-%d').date()
        if 'gender' in data:
            student_info.gender = data['gender']

        # Update course information
        if 'course_info' in data:
            course_data = data['course_info']
            if 'preferred_course' in course_data:
                student_info.course_info.preferred_course = course_data['preferred_course']
            if 'objectives' in course_data:
                student_info.course_info.objectives = course_data['objectives']
            if 'prior_computer_knowledge' in course_data:
                student_info.course_info.prior_computer_knowledge = course_data['prior_computer_knowledge']
            if 'seek_employment_opportunities' in course_data:
                student_info.course_info.seek_employment_opportunities = course_data['seek_employment_opportunities']
            if 'hear_about_pediforte' in course_data:
                student_info.course_info.hear_about_pediforte = course_data['hear_about_pediforte']
            if 'registration_date' in course_data and course_data['registration_date']:
                student_info.course_info.registration_date = datetime.strptime(course_data['registration_date'], '%Y-%m-%d').date()
            if 'resumption_date' in course_data and course_data['resumption_date']:
                student_info.course_info.resumption_date = datetime.strptime(course_data['resumption_date'], '%Y-%m-%d').date()

        student_info.updated_at = datetime.utcnow()
        db.session.commit()
        
        return student_info.to_dict(include_payment=False), 200

class StudentFormList(Resource):
    def get(self):
        students = StudentInformation.query.all()
        return [student.to_dict(include_payment=False) for student in students], 200

    def post(self):
        data = request.get_json()
        if not data or not all(k in data for k in ['surname', 'given_name', 'email_address', 'course_info']):
            abort(400, message="Required fields missing")

        # Validate course selection
        course_data = data['course_info']
        if course_data['preferred_course'] not in CourseInformation.COURSE_OPTIONS:
            abort(400, message="Invalid course selection")

        # Check terms agreement
        if not data.get('terms_agreed'):
            abort(400, message="You must agree to the terms and conditions to register")

        try:
            # Create course information
            course_info = CourseInformation(
                preferred_course=course_data['preferred_course'],
                objectives=course_data.get('objectives', {}),
                prior_computer_knowledge=course_data.get('prior_computer_knowledge'),
                seek_employment_opportunities=course_data.get('seek_employment_opportunities', False),
                hear_about_pediforte=course_data.get('hear_about_pediforte'),
                registration_date=datetime.strptime(course_data['registration_date'], '%Y-%m-%d').date() if course_data.get('registration_date') else None,
                resumption_date=datetime.strptime(course_data['resumption_date'], '%Y-%m-%d').date() if course_data.get('resumption_date') else None
            )
            db.session.add(course_info)
            db.session.flush()  

            # Create payment information with default values
            payment_info = PaymentInformation(
                course_price=data.get('course_price', 0.0),
                payment_method='cash',  # Default
                payment_status='pending'
            )
            db.session.add(payment_info)
            db.session.flush()  

            # Create student information
            new_student = StudentInformation(
                surname=data['surname'],
                given_name=data['given_name'],
                other_names=data.get('other_names'),
                home_address=data.get('home_address'),
                phone_number=data.get('phone_number'),
                email_address=data['email_address'],
                dob=datetime.strptime(data['dob'], '%Y-%m-%d').date() if data.get('dob') else None,
                gender=data.get('gender'),
                course_info_id=course_info.id,
                payment_info_id=payment_info.id,
                terms_agreed=True,
                terms_agreed_at=datetime.utcnow()
            )
            db.session.add(new_student)
            db.session.flush()  

            # Record terms agreement
            active_rules = StudentRules.get_active_rules()
            if active_rules:
                agreement = StudentAgreement(
                    student_id=new_student.id,
                    rules_id=active_rules.id,
                    ip_address=request.environ.get('REMOTE_ADDR'),
                    user_agent=request.headers.get('User-Agent', '')[:500]
                )
                db.session.add(agreement)

            db.session.commit()
            return new_student.to_dict(include_payment=False), 201

        except Exception as e:
            db.session.rollback()
            abort(500, message=f"Error creating student: {str(e)}")

# Admin Resources 
class AdminStudentForm(Resource):
    @admin_required
    def get(self, form_id):
        student_info = StudentInformation.query.get_or_404(form_id)
        return student_info.to_dict(include_payment=True), 200

    @admin_required
    def put(self, form_id):
        student_info = StudentInformation.query.get_or_404(form_id)
        data = request.get_json()
        
        if not data:
            abort(400, message="No data provided")
        
        # Update student information (same as student form)
        if 'surname' in data:
            student_info.surname = data['surname']
        if 'given_name' in data:
            student_info.given_name = data['given_name']
        if 'other_names' in data:
            student_info.other_names = data['other_names']
        if 'home_address' in data:
            student_info.home_address = data['home_address']
        if 'phone_number' in data:
            student_info.phone_number = data['phone_number']
        if 'email_address' in data:
            student_info.email_address = data['email_address']
        if 'dob' in data and data['dob']:
            student_info.dob = datetime.strptime(data['dob'], '%Y-%m-%d').date()
        if 'gender' in data:
            student_info.gender = data['gender']

        # Update course information
        if 'course_info' in data:
            course_data = data['course_info']
            if 'preferred_course' in course_data:
                student_info.course_info.preferred_course = course_data['preferred_course']
            if 'objectives' in course_data:
                student_info.course_info.objectives = course_data['objectives']
            if 'prior_computer_knowledge' in course_data:
                student_info.course_info.prior_computer_knowledge = course_data['prior_computer_knowledge']
            if 'seek_employment_opportunities' in course_data:
                student_info.course_info.seek_employment_opportunities = course_data['seek_employment_opportunities']
            if 'hear_about_pediforte' in course_data:
                student_info.course_info.hear_about_pediforte = course_data['hear_about_pediforte']
            if 'registration_date' in course_data and course_data['registration_date']:
                student_info.course_info.registration_date = datetime.strptime(course_data['registration_date'], '%Y-%m-%d').date()
            if 'resumption_date' in course_data and course_data['resumption_date']:
                student_info.course_info.resumption_date = datetime.strptime(course_data['resumption_date'], '%Y-%m-%d').date()

        # Update payment information
        if 'payment_info' in data:
            payment_data = data['payment_info']
            if 'course_price' in payment_data:
                student_info.payment_info.course_price = payment_data['course_price']
            if 'payment_method' in payment_data:
                if payment_data['payment_method'] in PaymentInformation.PAYMENT_METHODS:
                    student_info.payment_info.payment_method = payment_data['payment_method']
            if 'receipt_no' in payment_data:
                student_info.payment_info.receipt_no = payment_data['receipt_no']
            if 'payment_status' in payment_data:
                if payment_data['payment_status'] in PaymentInformation.PAYMENT_STATUS:
                    student_info.payment_info.payment_status = payment_data['payment_status']

        student_info.updated_at = datetime.utcnow()
        db.session.commit()
        
        return student_info.to_dict(include_payment=True), 200

    @admin_required
    def delete(self, form_id):
        student_info = StudentInformation.query.get_or_404(form_id)
        
        # Delete passport file if exists
        if student_info.passport_path and os.path.exists(student_info.passport_path):
            os.remove(student_info.passport_path)
        
        db.session.delete(student_info)
        db.session.commit()
        return {'message': f"Student {form_id} deleted successfully"}, 200

class AdminStudentFormList(Resource):
    @admin_required
    def get(self):
        students = StudentInformation.query.all()
        return [student.to_dict(include_payment=True) for student in students], 200

    @admin_required
    def post(self):
        data = request.get_json()
        if not data or not all(k in data for k in ['surname', 'given_name', 'email_address', 'course_info']):
            abort(400, message="Required fields missing")

        # Validate course selection
        course_data = data['course_info']
        if course_data['preferred_course'] not in CourseInformation.COURSE_OPTIONS:
            abort(400, message="Invalid course selection")

        # Create course information
        course_info = CourseInformation(
            preferred_course=course_data['preferred_course'],
            objectives=course_data.get('objectives', {}),
            prior_computer_knowledge=course_data.get('prior_computer_knowledge'),
            seek_employment_opportunities=course_data.get('seek_employment_opportunities', False),
            hear_about_pediforte=course_data.get('hear_about_pediforte'),
            registration_date=datetime.strptime(course_data['registration_date'], '%Y-%m-%d').date() if course_data.get('registration_date') else None,
            resumption_date=datetime.strptime(course_data['resumption_date'], '%Y-%m-%d').date() if course_data.get('resumption_date') else None
        )
        db.session.add(course_info)
        db.session.flush()

        # Create payment information
        payment_data = data.get('payment_info', {})
        payment_info = PaymentInformation(
            course_price=payment_data.get('course_price', 0.0),
            amount_paid=payment_data.get('amount_paid', 0.0),
            payment_method=payment_data.get('payment_method', 'cash'),
            receipt_no=payment_data.get('receipt_no'),
            payment_status=payment_data.get('payment_status', 'pending')
        )
        db.session.add(payment_info)
        db.session.flush()

        # Create student information
        new_student = StudentInformation(
            surname=data['surname'],
            given_name=data['given_name'],
            other_names=data.get('other_names'),
            home_address=data.get('home_address'),
            phone_number=data.get('phone_number'),
            email_address=data['email_address'],
            dob=datetime.strptime(data['dob'], '%Y-%m-%d').date() if data.get('dob') else None,
            gender=data.get('gender'),
            course_info_id=course_info.id,
            payment_info_id=payment_info.id,
            terms_agreed=data.get('terms_agreed', False),
            terms_agreed_at=datetime.utcnow() if data.get('terms_agreed') else None
        )
        db.session.add(new_student)
        db.session.flush()

        # Record terms agreement if agreed
        if data.get('terms_agreed'):
            active_rules = StudentRules.get_active_rules()
            if active_rules:
                agreement = StudentAgreement(
                    student_id=new_student.id,
                    rules_id=active_rules.id,
                    ip_address=request.environ.get('REMOTE_ADDR'),
                    user_agent=request.headers.get('User-Agent', '')[:500]
                )
                db.session.add(agreement)

        db.session.commit()

        return new_student.to_dict(include_payment=True), 201

# Passport Upload Resource
class PassportUpload(Resource):
    def post(self, student_id):
        if 'file' not in request.files:
            abort(400, message="No file provided")
        file = request.files['file']
        if file.filename == '':
            abort(400, message="No file selected")
        if not allowed_file(file.filename):
            abort(400, message="Invalid file type. Allowed: png, jpg, jpeg, gif, pdf")
        student = StudentInformation.query.get_or_404(student_id)
        # Delete old passport file if exists
        if student.passport_path and os.path.exists(student.passport_path):
            try:
                os.remove(student.passport_path)
            except OSError as e:
                abort(500, message=f"Error deleting old file: {str(e)}")
        # Save new file
        filename = secure_filename(f"student_{student_id}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(file_path)
        except Exception as e:
            abort(500, message=f"Error saving file: {str(e)}")
        # Update student record
        student.passport_filename = filename
        student.passport_path = file_path
        student.updated_at = datetime.utcnow()
        db.session.commit()
        return {
            'message': 'File uploaded successfully',
            'filename': filename,
            'student_id': student_id
        }, 200
    
    
# Statistics and Analytics Resources
class AdminDashboard(Resource):
    @admin_required
    def get(self):
        total_students = StudentInformation.query.count()
        course_stats = CourseInformation.get_course_statistics()
        
        # Recent registrations (last 30 days)
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_students = StudentInformation.query.filter(
            StudentInformation.created_at >= thirty_days_ago
        ).count()
        
        return {
            'total_students': total_students,
            'recent_registrations': recent_students,
            'course_statistics': course_stats,
            'course_options': CourseInformation.COURSE_OPTIONS,
            'payment_methods': PaymentInformation.PAYMENT_METHODS
        }, 200

# Data Export Resource
class ExportData(Resource):
    @admin_required
    def get(self):
        export_type = request.args.get('type', 'all')
        format_type = request.args.get('format', 'csv')
        
        if format_type != 'csv':
            abort(400, message="Only CSV format supported currently")
        
        students = StudentInformation.query.all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # headers
        headers = [
            'ID', 'Full Name', 'Surname', 'Given Name', 'Other Names',
            'Email', 'Phone', 'Address', 'DOB', 'Gender',
            'Course', 'Registration Date', 'Resumption Date',
            'Course Price', 'Amount Paid',
            'Payment Method', 'Receipt No', 'Created At', 'Terms Agreed', 'Terms Agreed At'
        ]
        writer.writerow(headers)
        
        #  data
        for student in students:
            row = [
                student.id,
                student.full_name,
                student.surname,
                student.given_name,
                student.other_names or '',
                student.email_address,
                student.phone_number or '',
                student.home_address or '',
                student.dob.isoformat() if student.dob else '',
                student.gender or '',
                student.course_info.preferred_course if student.course_info else '',
                student.course_info.registration_date.isoformat() if student.course_info and student.course_info.registration_date else '',
                student.course_info.resumption_date.isoformat() if student.course_info and student.course_info.resumption_date else '',
                student.payment_info.course_price if student.payment_info else '',
                student.payment_info.amount_paid if student.payment_info else '',
                student.payment_info.payment_method if student.payment_info else '',
                student.payment_info.receipt_no if student.payment_info else '',
                student.created_at.isoformat() if student.created_at else '',
                'Yes' if student.terms_agreed else 'No',
                student.terms_agreed_at.isoformat() if student.terms_agreed_at else ''
            ]
            writer.writerow(row)
        
        #  download
        output.seek(0)
        
        # Create a BytesIO object for the response
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        
        return send_file(
            mem,
            as_attachment=True,
            download_name=f'students_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            mimetype='text/csv'
        )

# Course Options Resource
class CourseOptions(Resource):
    def get(self):
        return {
            'courses': CourseInformation.COURSE_OPTIONS,
            'payment_methods': PaymentInformation.PAYMENT_METHODS
        }, 200

# Student Rules routes
api.add_resource(StudentRulesResource, '/api/student-rules')
api.add_resource(StudentAgreementResource, '/api/students/<int:student_id>/agreement')

# Admin Rules routes
api.add_resource(AdminStudentRulesResource, '/api/admin/student-rules')
api.add_resource(AdminRulesAnalytics, '/api/admin/rules-analytics')

# Register API routes
# Public routes (Student)
api.add_resource(StudentFormList, '/api/students')
api.add_resource(StudentForm, '/api/students/<int:form_id>')
api.add_resource(CourseOptions, '/api/course-options')

# Admin authentication routes
api.add_resource(AdminLogin, '/api/admin/login')
api.add_resource(AdminLogout, '/api/admin/logout')
api.add_resource(AdminRegister, '/api/admin/register')

# Admin routes (Protected)
api.add_resource(AdminStudentFormList, '/api/admin/students')
api.add_resource(AdminStudentForm, '/api/admin/students/<int:form_id>')
api.add_resource(AdminDashboard, '/api/admin/dashboard')
api.add_resource(ExportData, '/api/admin/export')

# File upload routes
api.add_resource(PassportUpload, '/api/students/<int:student_id>/passport')

# Create database tables and admin
with app.app_context():
    db.create_all()
    
    # Create default admin if none exists
    if not Admin.query.first():
        default_admin = Admin(
            username=os.getenv('ADMIN_USERNAME', 'admin'),
            email=os.getenv('ADMIN_EMAIL', 'admin@pediforte.com')
        )
        default_admin.set_password(os.getenv('ADMIN_PASSWORD', 'admin123'))
        db.session.add(default_admin)
        db.session.commit()

    # Create default student rules if none exist
    if not StudentRules.query.first():
        default_rules_content = """Student Rules (Please read carefully)

1. Students will be given timetable after registration all students are required to follow the time specified on the timetable or the instructor, except there is a public holiday, or the instructor notifies a change in the class schedule.

2. Students are to be respectable to the instructors and the school administrators.

3. Students are required to come with their own laptops.

4. In case a student has to resume school or any other personal engagements, the school should be notified in advance if the student is planning to come back to complete their course in the future.

5. Students are required to complete all projects and assignments issued by instructors or administrators.

6. All documents and projects given to the student must be treated as confidential intellectual properties unless stated otherwise by the instructors.

7. Students must not engage in activities that may be regarded as a disturbance to the school or disrupt ongoing classes.

8. Students are expected to complete their courses within 6 months after which another full payment must be made to continue taking the same course.

9. Alcohol, smoking accessories, weapons, or hard drugs are not allowed on the school premises.

10. Business activities between students (legal or illegal) are not allowed in school premises.

11. Students caught engaged in the below activities within school premises will be expelled without a refund:
    a. Fighting
    b. Smoking or taking hard drugs
    c. Cyber crimes and other illegal activities.

12. All payments must be completed before the duration of the course ends.

13. Certificates will only be issued if all payments are completed.

14. No refund will be issued under any circumstances.

15. Pediforte reserves the right to expel any student that breaks any of these rules.

16. Pediforte reserves the right to make changes to these rules anytime.

I, (student name) have read and promise to abide by the student rules outlined above."""

        default_admin = Admin.query.first()
        default_rules = StudentRules(
            rules_content=default_rules_content,
            version='1.0',
            is_active=True,
            created_by=default_admin.id
        )
        db.session.add(default_rules)
        db.session.commit()

# Run the app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
