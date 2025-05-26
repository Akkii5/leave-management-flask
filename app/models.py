from app import db, login_manager
from flask_login import UserMixin

# User loader for login session
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='employee')  # 'employee' or 'admin'

    # Relationships
    leaves = db.relationship('LeaveRequest', backref='applicant', lazy=True)
    leave_balances = db.relationship('LeaveBalance', backref='user', lazy=True)


# LeaveRequest model
class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)  # 'Casual', 'Sick'
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending')  # 'Pending', 'Approved', 'Rejected'


# LeaveBalance model
class LeaveBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)  # 'Casual', 'Sick'
    total = db.Column(db.Integer, nullable=False)
    used = db.Column(db.Integer, default=0)

    @property
    def remaining(self):
        return self.total - self.used
