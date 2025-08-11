from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import json

db = SQLAlchemy()

class StudentInformation(db.Model):
    __tablename__ = 'student_information'
    id = db.Column(db.Integer, primary_key=True)
    surname = db.Column(db.String(100), nullable=False)
    given_name = db.Column(db.String(100), nullable=False)
    other_names = db.Column(db.String(100))
    home_address = db.Column(db.String(200))
    phone_number = db.Column(db.String(20))
    email_address = db.Column(db.String(120), nullable=False, unique=True)
    dob = db.Column(db.Date)
    gender = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    terms_agreed = db.Column(db.Boolean, default=False, nullable=False)
    terms_agreed_at = db.Column(db.DateTime)
    
    course_info_id = db.Column(db.Integer, db.ForeignKey('course_information.id'), nullable=False)
    payment_info_id = db.Column(db.Integer, db.ForeignKey('payment_information.id'), nullable=False)
    course_info = db.relationship('CourseInformation', backref='student', uselist=False, single_parent=True, cascade='all, delete')
    payment_info = db.relationship('PaymentInformation', backref='student', uselist=False, single_parent=True, cascade='all, delete')

    def to_dict(self):
        return {
            'id': self.id,
            'surname': self.surname,
            'given_name': self.given_name,
            'other_names': self.other_names,
            'home_address': self.home_address,
            'phone_number': self.phone_number,
            'email_address': self.email_address,
            'dob': self.dob.isoformat() if self.dob else None,
            'gender': self.gender,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'terms_agreed': self.terms_agreed,
            'terms_agreed_at': self.terms_agreed_at.isoformat() if self.terms_agreed_at else None,
            'course_info': self.course_info.to_dict() if self.course_info else None,
            'payment_info': self.payment_info.to_dict() if self.payment_info else None
        }

class CourseInformation(db.Model):
    __tablename__ = 'course_information'
    id = db.Column(db.Integer, primary_key=True)
    preferred_course = db.Column(db.String(100), nullable=False)
    objectives = db.Column(db.JSON, nullable=False)
    prior_computer_knowledge = db.Column(db.String(200))
    seek_employment_opportunities = db.Column(db.Boolean, default=False)
    hear_about_pediforte = db.Column(db.String(200))
    registration_date = db.Column(db.Date)
    resumption_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    COURSE_OPTIONS = [
        'Fullstack Development',
        'Frontend Development',
        'Cybersecurity',
        'Data Science',
        'Mobile App Development',
        'UI/UX Design'
    ]
    
    OBJECTIVE_OPTIONS = [
        'Expand My Knowledge',
        'Get a Job',
        'Competitive Edge',
        'Looking for Opportunities'
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

class PaymentInformation(db.Model):
    __tablename__ = 'payment_information'
    id = db.Column(db.Integer, primary_key=True)
    course_price = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, default=0.0)
    payment_method = db.Column(db.String(50), nullable=False)
    receipt_no = db.Column(db.String(50))
    payment_status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    PAYMENT_METHODS = ['cash', 'bank_transfer']
    PAYMENT_STATUS = ['pending', 'partial', 'completed']

    def to_dict(self):
        return {
            'id': self.id,
            'course_price': self.course_price,
            'amount_paid': self.amount_paid,
            'balance': self.course_price - self.amount_paid if self.course_price and self.amount_paid else self.course_price or 0,
            'payment_method': self.payment_method,
            'receipt_no': self.receipt_no,
            'payment_status': self.payment_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class StudentRules(db.Model):
    __tablename__ = 'student_rules'
    id = db.Column(db.Integer, primary_key=True)
    rules_content = db.Column(db.Text, nullable=False)
    version = db.Column(db.String(20), default='1.0')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'rules_content': self.rules_content,
            'version': self.version,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class StudentAgreement(db.Model):
    __tablename__ = 'student_agreement'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_information.id'), nullable=False)
    rules_id = db.Column(db.Integer, db.ForeignKey('student_rules.id'), nullable=False)
    agreed_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))

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