from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class StudentInformation(db.Model):
    __tablename__ = 'student_information'
    id = db.Column(db.Integer, primary_key=True)
    surname = db.Column(db.String(100), nullable=False)
    given_name = db.Column(db.String(100), nullable=False)
    other_names = db.Column(db.String(100))
    home_address = db.Column(db.String(200))
    phone_number = db.Column(db.String(20))
    email_address = db.Column(db.String(120), nullable=False, unique=True)
    dob = db.Column(db.Date)  # Changed to Date type
    gender = db.Column(db.String(20))
    passport_filename = db.Column(db.String(255))  # Store passport file name
    passport_path = db.Column(db.String(500))  # Store full file path
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Add this field to StudentInformation class
    terms_agreed = db.Column(db.Boolean, default=False, nullable=False)
    terms_agreed_at = db.Column(db.DateTime)
    
    # Foreign Keys
    course_info_id = db.Column(db.Integer, db.ForeignKey('course_information.id'), nullable=False)
    payment_info_id = db.Column(db.Integer, db.ForeignKey('payment_information.id'), nullable=False)
    
    # Relationships
    course_info = db.relationship('CourseInformation', backref='student', uselist=False, cascade='all, delete-orphan', single_parent=True)
    payment_info = db.relationship('PaymentInformation', backref='student', uselist=False, cascade='all, delete-orphan', single_parent=True)
    
    @property
    def full_name(self):
        """Get full name"""
        names = [self.surname, self.given_name]
        if self.other_names:
            names.append(self.other_names)
        return ' '.join(names)
    
    def to_dict(self, include_payment=False):
        """Convert to dictionary with optional payment info"""
        data = {
            'id': self.id,
            'surname': self.surname,
            'given_name': self.given_name,
            'other_names': self.other_names,
            'full_name': self.full_name,
            'home_address': self.home_address,
            'phone_number': self.phone_number,
            'email_address': self.email_address,
            'dob': self.dob.isoformat() if self.dob else None,
            'gender': self.gender,
            'passport_filename': self.passport_filename,
            'passport_path': self.passport_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'course_info': self.course_info.to_dict() if self.course_info else None,
            'terms_agreed': self.terms_agreed,
            'terms_agreed_at': self.terms_agreed_at.isoformat() if self.terms_agreed_at else None,
        }
        
        if include_payment and self.payment_info:
            data['payment_info'] = self.payment_info.to_dict()
            
        return data

class CourseInformation(db.Model):
    __tablename__ = 'course_information'
    id = db.Column(db.Integer, primary_key=True)
    preferred_course = db.Column(db.String(100), nullable=False)
    objectives = db.Column(db.JSON, nullable=False)  # e.g., {"learn_html": True, "learn_python": False}
    prior_computer_knowledge = db.Column(db.String(200))
    seek_employment_opportunities = db.Column(db.Boolean, default=False)
    hear_about_pediforte = db.Column(db.String(200))
    registration_date = db.Column(db.Date)  # Changed to Date type
    resumption_date = db.Column(db.Date)  # Changed to Date type
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Course options as class variable
    COURSE_OPTIONS = [
        'Fullstack Development',
        'Frontend Development', 
        'Cybersecurity',
        'Data Science',
        'Mobile App Development',
        'UI/UX Design'
    ]
    
    def to_dict(self):
        return {
            'id': self.id,
            'preferred_course': self.preferred_course,
            'objectives': self.objectives,
            'prior_computer_knowledge': self.prior_computer_knowledge,
            'seek_employment_opportunities': self.seek_employment_opportunities,
            'hear_about_pediforte': self.hear_about_pediforte,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None,
            'resumption_date': self.resumption_date.isoformat() if self.resumption_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def get_course_statistics():
        """Get statistics for each course"""
        from sqlalchemy import func
        stats = db.session.query(
            CourseInformation.preferred_course,
            func.count(CourseInformation.id).label('student_count')
        ).join(StudentInformation).group_by(CourseInformation.preferred_course).all()
        
        return {course: count for course, count in stats}

class PaymentInformation(db.Model):
    __tablename__ = 'payment_information'
    id = db.Column(db.Integer, primary_key=True)
    course_price = db.Column(db.Float)
    amount_paid = db.Column(db.Float, default=0.0)
    payment_method = db.Column(db.String(50))  # 'cash' or 'bank_transfer'
    payments = db.Column(db.Text)  # JSON string for payment history
    receipt_no = db.Column(db.String(50))
    payment_status = db.Column(db.String(50), default='pending')  # pending, partial, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Payment method options
    PAYMENT_METHODS = ['cash', 'bank_transfer']
    PAYMENT_STATUS = ['pending', 'partial', 'completed']
    
    @property
    def balance(self):
        """Calculate remaining balance"""
        if self.course_price and self.amount_paid:
            return self.course_price - self.amount_paid
        return self.course_price or 0
    
    def add_payment(self, amount, method, receipt_no=None):
        """Add a new payment"""
        self.amount_paid = (self.amount_paid or 0) + amount
        self.payment_method = method
        if receipt_no:
            self.receipt_no = receipt_no
            
        # Update payment status
        if self.amount_paid >= self.course_price:
            self.payment_status = 'completed'
        elif self.amount_paid > 0:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'pending'
            
        # Update payment history
        self.updated_at = datetime.utcnow()
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_price': self.course_price,
            'amount_paid': self.amount_paid,
            'balance': self.balance,
            'payment_method': self.payment_method,
            'payments': json.loads(self.payments) if self.payments else [],
            'receipt_no': self.receipt_no,
            'payment_status': self.payment_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def get_payment_statistics():
        """Get payment method statistics"""
        from sqlalchemy import func
        stats = db.session.query(
            PaymentInformation.payment_method,
            func.count(PaymentInformation.id).label('count'),
            func.sum(PaymentInformation.amount_paid).label('total_amount')
        ).group_by(PaymentInformation.payment_method).all()
        
        return {
            method: {'count': count, 'total_amount': float(total_amount or 0)} 
            for method, count, total_amount in stats
        }

class StudentRules(db.Model):
    __tablename__ = 'student_rules'
    id = db.Column(db.Integer, primary_key=True)
    rules_content = db.Column(db.Text, nullable=False)
    version = db.Column(db.String(20), default='1.0')
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    created_by_admin = db.relationship('Admin', backref='created_rules')
    
    def to_dict(self):
        return {
            'id': self.id,
            'rules_content': self.rules_content,
            'version': self.version,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_by_admin': self.created_by_admin.username if self.created_by_admin else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def get_active_rules():
        """Get the currently active rules"""
        return StudentRules.query.filter_by(is_active=True).first()

class StudentAgreement(db.Model):
    __tablename__ = 'student_agreement'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_information.id'), nullable=False)
    rules_id = db.Column(db.Integer, db.ForeignKey('student_rules.id'), nullable=False)
    agreed_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))  # For audit trail
    user_agent = db.Column(db.String(500))  # For audit trail
    
    # Relationships
    student = db.relationship('StudentInformation', backref='agreements')
    rules = db.relationship('StudentRules', backref='agreements')
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'rules_id': self.rules_id,
            'rules_version': self.rules.version if self.rules else None,
            'agreed_at': self.agreed_at.isoformat() if self.agreed_at else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent
        }

# Utility functions for statistics
def get_gender_statistics():
    """Get gender distribution statistics"""
    from sqlalchemy import func
    stats = db.session.query(
        StudentInformation.gender,
        func.count(StudentInformation.id).label('count')
    ).group_by(StudentInformation.gender).all()
    
    return {gender: count for gender, count in stats}

def get_age_group_statistics():
    """Get age group statistics"""
    students = StudentInformation.query.all()
    adults = sum(1 for s in students if s.dob and (date.today().year - s.dob.year) >= 18)
    minors = sum(1 for s in students if s.dob and (date.today().year - s.dob.year) < 18)
    unknown = sum(1 for s in students if not s.dob)
    
    return {
        'adults': adults,
        'minors': minors,
        'unknown_age': unknown,
        'total': len(students)
    }
