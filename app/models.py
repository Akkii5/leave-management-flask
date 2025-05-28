from app import db, login_manager
from flask_login import UserMixin
from sqlalchemy.orm import relationship
from datetime import datetime

# User loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='employee')  # 'employee', 'admin'

    # Reporting Manager (self-referencing)
    reporting_manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    manager = db.relationship(
        'User',
        remote_side=[id],
        backref=db.backref('team_members', lazy='dynamic'),
        lazy='joined'
    )

    # Relationships
    leave_requests = db.relationship('LeaveRequest', backref='applicant', lazy=True)
    leave_balances = db.relationship('LeaveBalance', backref='user', lazy=True)

    def __repr__(self):
        return f"<User {self.name} ({self.email})>"


class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # user = db.relationship('User', backref='leave_requests')  # this is correct

class LeaveBalance(db.Model):
    __tablename__ = 'leave_balance'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)  # e.g., 'Casual', 'Sick'
    total = db.Column(db.Integer, nullable=False)
    used = db.Column(db.Integer, default=0)

    @property
    def remaining(self):
        return self.total - self.used