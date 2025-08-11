from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_migrate import Migrate
from flasgger import Swagger, LazyJSONEncoder
from flask_httpauth import HTTPBasicAuth
from datetime import datetime
import os
from dotenv import load_dotenv
from models import db, StudentInformation, CourseInformation, PaymentInformation, StudentRules, StudentAgreement
import io
import csv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table

app = Flask(__name__)
load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')

app.json_encoder = LazyJSONEncoder

app.config['SWAGGER'] = {
    'title': 'Pediforte Student Management API',
    'uiversion': 3,
    'openapi': '3.0.0'
}
swagger = Swagger(app, template_file='swagger.yml')

db.init_app(app)
migrate = Migrate(app, db)
auth = HTTPBasicAuth()

ADMIN_USERS = {
    'admin': 'securepassword123'
}

@auth.verify_password
def verify_password(username, password):
    if username in ADMIN_USERS and ADMIN_USERS[username] == password:
        return username
    return None

CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:4200"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"]
}})

@app.route('/api/student-information', methods=['POST'])
def create_student_information():
    data = request.get_json()
    if not data or not all(k in data for k in ['surname', 'given_name', 'email_address']):
        return jsonify({"message": "Surname, given name, and email address are required"}), 400

    if StudentInformation.query.filter_by(email_address=data['email_address']).first():
        return jsonify({"message": "Email address already exists"}), 400

    try:
        course_info = CourseInformation(
            preferred_course='Placeholder',
            objectives=[]
        )
        payment_info = PaymentInformation(
            course_price=0.0,
            payment_method='cash'
        )
        db.session.add(course_info)
        db.session.add(payment_info)
        db.session.flush()

        dob = datetime.strptime(data['dob'], '%Y-%m-%d').date() if data.get('dob') else None
        student = StudentInformation(
            surname=data['surname'],
            given_name=data['given_name'],
            other_names=data.get('other_names'),
            home_address=data.get('home_address'),
            phone_number=data.get('phone_number'),
            email_address=data['email_address'],
            dob=dob,
            gender=data.get('gender'),
            course_info_id=course_info.id,
            payment_info_id=payment_info.id
        )
        db.session.add(student)
        db.session.commit()
        return jsonify(student.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error creating student: {str(e)}"}), 400

@app.route('/api/course-information/<int:student_id>', methods=['POST'])
def create_course_information(student_id):
    student = StudentInformation.query.get_or_404(student_id)
    data = request.get_json()
    if not data or not all(k in data for k in ['preferred_course', 'objectives']):
        return jsonify({"message": "Preferred course and objectives are required"}), 400

    if data['preferred_course'] not in CourseInformation.COURSE_OPTIONS:
        return jsonify({"message": "Invalid course selection"}), 400

    if not all(obj in CourseInformation.OBJECTIVE_OPTIONS for obj in data['objectives']):
        return jsonify({"message": "Invalid objectives selected"}), 400

    try:
        registration_date = datetime.strptime(data['registration_date'], '%Y-%m-%d').date() if data.get('registration_date') else None
        resumption_date = datetime.strptime(data['resumption_date'], '%Y-%m-%d').date() if data.get('resumption_date') else None
        course_info = CourseInformation(
            preferred_course=data['preferred_course'],
            objectives=data['objectives'],
            prior_computer_knowledge=data.get('prior_computer_knowledge'),
            seek_employment_opportunities=data.get('seek_employment_opportunities', False),
            hear_about_pediforte=data.get('hear_about_pediforte'),
            registration_date=registration_date,
            resumption_date=resumption_date
        )
        db.session.add(course_info)
        db.session.flush()
        student.course_info_id = course_info.id
        db.session.commit()
        return jsonify(course_info.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error creating course information: {str(e)}"}), 400

@app.route('/api/payment-information/<int:student_id>', methods=['POST'])
def create_payment_information(student_id):
    student = StudentInformation.query.get_or_404(student_id)
    data = request.get_json()
    if not data or not all(k in data for k in ['course_price', 'payment_method']):
        return jsonify({"message": "Course price and payment method are required"}), 400

    if data['payment_method'] not in PaymentInformation.PAYMENT_METHODS:
        return jsonify({"message": "Invalid payment method"}), 400

    try:
        amount_paid = data.get('amount_paid', 0.0)
        payment_status = 'pending'
        if amount_paid >= data['course_price']:
            payment_status = 'completed'
        elif amount_paid > 0:
            payment_status = 'partial'

        payment_info = PaymentInformation(
            course_price=data['course_price'],
            amount_paid=amount_paid,
            payment_method=data['payment_method'],
            receipt_no=data.get('receipt_no'),
            payment_status=payment_status
        )
        db.session.add(payment_info)
        db.session.flush()
        student.payment_info_id = payment_info.id
        db.session.commit()
        return jsonify(payment_info.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error creating payment information: {str(e)}"}), 400

@app.route('/api/student-rules', methods=['GET'])
def get_student_rules():
    active_rules = StudentRules.query.filter_by(is_active=True).first()
    return jsonify(active_rules.to_dict() if active_rules else {'rules_content': '', 'version': '1.0'}), 200

@app.route('/api/student-agreement/<int:student_id>', methods=['POST'])
def create_student_agreement(student_id):
    student = StudentInformation.query.get_or_404(student_id)
    data = request.get_json()
    if not data or not data.get('agreed'):
        return jsonify({"message": "You must agree to the terms and conditions"}), 400

    active_rules = StudentRules.query.filter_by(is_active=True).first()
    if not active_rules:
        return jsonify({"message": "No active rules found"}), 400

    existing_agreement = StudentAgreement.query.filter_by(student_id=student_id, rules_id=active_rules.id).first()
    if existing_agreement:
        return jsonify({"message": "Student has already agreed to current rules"}), 200

    try:
        agreement = StudentAgreement(
            student_id=student_id,
            rules_id=active_rules.id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500]
        )
        student.terms_agreed = True
        student.terms_agreed_at = datetime.utcnow()
        db.session.add(agreement)
        db.session.commit()
        return jsonify({
            "message": "Terms and conditions accepted successfully",
            "agreement": agreement.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error recording agreement: {str(e)}"}), 400

@app.route('/api/admin/students', methods=['GET'])
@auth.login_required
def list_students():
    gender = request.args.get('gender')
    preferred_course = request.args.get('preferred_course')
    objectives = request.args.get('objectives')
    payment_status = request.args.get('payment_status')
    terms_agreed = request.args.get('terms_agreed', type=bool)

    query = StudentInformation.query.join(CourseInformation).join(PaymentInformation)

    if gender:
        query = query.filter(StudentInformation.gender == gender)
    if preferred_course:
        query = query.filter(CourseInformation.preferred_course == preferred_course)
    if objectives:
        objectives_list = objectives.split(',')
        query = query.filter(CourseInformation.objectives.contains(objectives_list))
    if payment_status:
        query = query.filter(PaymentInformation.payment_status == payment_status)
    if terms_agreed is not None:
        query = query.filter(StudentInformation.terms_agreed == terms_agreed)

    students = query.all()
    return jsonify([student.to_dict() for student in students]), 200

@app.route('/api/admin/students/<int:student_id>', methods=['GET'])
@auth.login_required
def get_student(student_id):
    student = StudentInformation.query.get_or_404(student_id)
    return jsonify(student.to_dict()), 200

@app.route('/api/admin/students/<int:student_id>', methods=['PUT'])
@auth.login_required
def update_student(student_id):
    student = StudentInformation.query.get_or_404(student_id)
    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400

    try:
        if 'surname' in data:
            student.surname = data['surname']
        if 'given_name' in data:
            student.given_name = data['given_name']
        if 'other_names' in data:
            student.other_names = data['other_names']
        if 'home_address' in data:
            student.home_address = data['home_address']
        if 'phone_number' in data:
            student.phone_number = data['phone_number']
        if 'email_address' in data:
            if StudentInformation.query.filter_by(email_address=data['email_address']).filter(StudentInformation.id != student_id).first():
                return jsonify({"message": "Email address already exists"}), 400
            student.email_address = data['email_address']
        if 'dob' in data:
            student.dob = datetime.strptime(data['dob'], '%Y-%m-%d').date() if data['dob'] else None
        if 'gender' in data:
            student.gender = data['gender']

        if any(k in data for k in ['preferred_course', 'objectives', 'prior_computer_knowledge', 'seek_employment_opportunities', 'hear_about_pediforte', 'registration_date', 'resumption_date']):
            course_info = student.course_info
            if 'preferred_course' in data:
                if data['preferred_course'] not in CourseInformation.COURSE_OPTIONS:
                    return jsonify({"message": "Invalid course selection"}), 400
                course_info.preferred_course = data['preferred_course']
            if 'objectives' in data:
                if not all(obj in CourseInformation.OBJECTIVE_OPTIONS for obj in data['objectives']):
                    return jsonify({"message": "Invalid objectives selected"}), 400
                course_info.objectives = data['objectives']
            if 'prior_computer_knowledge' in data:
                course_info.prior_computer_knowledge = data['prior_computer_knowledge']
            if 'seek_employment_opportunities' in data:
                course_info.seek_employment_opportunities = data['seek_employment_opportunities']
            if 'hear_about_pediforte' in data:
                course_info.hear_about_pediforte = data['hear_about_pediforte']
            if 'registration_date' in data:
                course_info.registration_date = datetime.strptime(data['registration_date'], '%Y-%m-%d').date() if data['registration_date'] else None
            if 'resumption_date' in data:
                course_info.resumption_date = datetime.strptime(data['resumption_date'], '%Y-%m-%d').date() if data['resumption_date'] else None

        if any(k in data for k in ['course_price', 'amount_paid', 'payment_method', 'receipt_no']):
            payment_info = student.payment_info
            if 'course_price' in data:
                payment_info.course_price = data['course_price']
            if 'amount_paid' in data:
                payment_info.amount_paid = data['amount_paid']
                payment_status = 'pending'
                if payment_info.amount_paid >= payment_info.course_price:
                    payment_status = 'completed'
                elif payment_info.amount_paid > 0:
                    payment_status = 'partial'
                payment_info.payment_status = payment_status
            if 'payment_method' in data:
                if data['payment_method'] not in PaymentInformation.PAYMENT_METHODS:
                    return jsonify({"message": "Invalid payment method"}), 400
                payment_info.payment_method = data['payment_method']
            if 'receipt_no' in data:
                payment_info.receipt_no = data['receipt_no']

        db.session.commit()
        return jsonify(student.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error updating student: {str(e)}"}), 400

@app.route('/api/admin/students/<int:student_id>', methods=['DELETE'])
@auth.login_required
def delete_student(student_id):
    student = StudentInformation.query.get_or_404(student_id)
    try:
        db.session.delete(student)
        db.session.commit()
        return jsonify({"message": "Student deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error deleting student: {str(e)}"}), 400

@app.route('/api/admin/students/report/csv', methods=['GET'])
@auth.login_required
def generate_csv_report():
    gender = request.args.get('gender')
    preferred_course = request.args.get('preferred_course')
    objectives = request.args.get('objectives')
    payment_status = request.args.get('payment_status')
    terms_agreed = request.args.get('terms_agreed', type=bool)

    query = StudentInformation.query.join(CourseInformation).join(PaymentInformation)

    if gender:
        query = query.filter(StudentInformation.gender == gender)
    if preferred_course:
        query = query.filter(CourseInformation.preferred_course == preferred_course)
    if objectives:
        objectives_list = objectives.split(',')
        query = query.filter(CourseInformation.objectives.contains(objectives_list))
    if payment_status:
        query = query.filter(PaymentInformation.payment_status == payment_status)
    if terms_agreed is not None:
        query = query.filter(StudentInformation.terms_agreed == terms_agreed)

    students = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Surname', 'Given Name', 'Email', 'Gender', 'DOB', 'Course', 'Objectives',
        'Course Price', 'Amount Paid', 'Payment Status', 'Terms Agreed'
    ])

    for student in students:
        writer.writerow([
            student.id,
            student.surname,
            student.given_name,
            student.email_address,
            student.gender,
            student.dob.isoformat() if student.dob else '',
            student.course_info.preferred_course,
            ', '.join(student.course_info.objectives) if student.course_info.objectives else '',
            student.payment_info.course_price,
            student.payment_info.amount_paid,
            student.payment_info.payment_status,
            student.terms_agreed
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='students_report.csv'
    )

@app.route('/api/admin/students/report/pdf', methods=['GET'])
@auth.login_required
def generate_pdf_report():
    gender = request.args.get('gender')
    preferred_course = request.args.get('preferred_course')
    objectives = request.args.get('objectives')
    payment_status = request.args.get('payment_status')
    terms_agreed = request.args.get('terms_agreed', type=bool)

    query = StudentInformation.query.join(CourseInformation).join(PaymentInformation)

    if gender:
        query = query.filter(StudentInformation.gender == gender)
    if preferred_course:
        query = query.filter(CourseInformation.preferred_course == preferred_course)
    if objectives:
        objectives_list = objectives.split(',')
        query = query.filter(CourseInformation.objectives.contains(objectives_list))
    if payment_status:
        query = query.filter(PaymentInformation.payment_status == payment_status)
    if terms_agreed is not None:
        query = query.filter(StudentInformation.terms_agreed == terms_agreed)

    students = query.all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    data = [[
        'ID', 'Surname', 'Given Name', 'Email', 'Gender', 'DOB', 'Course', 'Objectives',
        'Course Price', 'Amount Paid', 'Payment Status', 'Terms Agreed'
    ]]

    for student in students:
        data.append([
            str(student.id),
            student.surname,
            student.given_name,
            student.email_address,
            student.gender or '',
            student.dob.isoformat() if student.dob else '',
            student.course_info.preferred_course,
            ', '.join(student.course_info.objectives) if student.course_info.objectives else '',
            str(student.payment_info.course_price),
            str(student.payment_info.amount_paid),
            student.payment_info.payment_status,
            str(student.terms_agreed)
        ])

    table = Table(data)
    doc.build([table])
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='students_report.pdf'
    )

with app.app_context():
    db.create_all()
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
        default_rules = StudentRules(
            rules_content=default_rules_content,
            version='1.0',
            is_active=True
        )
        db.session.add(default_rules)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)