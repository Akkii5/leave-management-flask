from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, current_user, logout_user, login_required
from app import db, bcrypt
from app.models import User, LeaveRequest
from datetime import datetime
from werkzeug.security import generate_password_hash
from app.models import User, LeaveRequest

main = Blueprint('main', __name__)


@main.route("/")
def home():
    return render_template("home.html")


@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash('Email already registered.', 'warning')
            return redirect(url_for('main.register'))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(name=name, email=email, password=hashed_pw, role=role, leave_balance=20)
        db.session.add(user)
        db.session.commit()

        flash('Registered successfully! Please login.', 'success')
        return redirect(url_for('main.login'))

    return render_template('register.html')

@main.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Login failed. Check email/password.', 'danger')

    return render_template("login.html")


@main.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)


@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You’ve been logged out.", "info")
    return redirect(url_for('main.login'))


@main.route("/apply-leave", methods=["GET", "POST"])
@login_required
def apply_leave():
    if request.method == "POST":
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        leave_type = request.form["leave_type"]
        reason = request.form["reason"]

        leave = LeaveRequest(
            user_id=current_user.id,
            start_date=datetime.strptime(start_date, "%Y-%m-%d"),
            end_date=datetime.strptime(end_date, "%Y-%m-%d"),
            leave_type=leave_type,
            reason=reason
        )
        db.session.add(leave)
        db.session.commit()
        flash("Leave request submitted successfully!", "success")
        return redirect(url_for("main.view_my_leaves"))

    return render_template("apply_leave.html")


@main.route('/my-leaves', methods=['GET', 'POST'])
@login_required
def view_my_leaves():
    filters = {}
    if request.method == 'POST':
        status = request.form.get('status')
        leave_type = request.form.get('leave_type')

        if status:
            filters['status'] = status
        if leave_type:
            filters['leave_type'] = leave_type

    leaves = LeaveRequest.query.filter_by(user_id=current_user.id, **filters).order_by(LeaveRequest.start_date.desc()).all()
    return render_template('my_leaves.html', leaves=leaves)


@main.route("/admin/leaves")
@login_required
def admin_view_leaves():
    if current_user.role != "admin":
        flash("Access denied!", "danger")
        return redirect(url_for("main.dashboard"))

    leaves = LeaveRequest.query.all()
    return render_template("admin_leaves.html", leaves=leaves)


@main.route('/admin/approve/<int:leave_id>')
@login_required
def approve_leave(leave_id):
    if current_user.role != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('main.dashboard'))

    leave = LeaveRequest.query.get_or_404(leave_id)
    user = User.query.get(leave.user_id)

    # Calculate leave days
    leave_days = (leave.end_date - leave.start_date).days + 1

    if leave.status != 'Pending':
        flash('Leave already processed.', 'info')
    elif user.leave_balance is None:
        flash("User's leave balance is not set. Please update their profile.", "danger")
    elif user.leave_balance < leave_days:
        flash("User doesn't have enough leave balance.", "danger")
    else:
        leave.status = 'Approved'
        user.leave_balance -= leave_days
        db.session.commit()
        flash('Leave approved successfully.', 'success')

    return redirect(url_for('main.admin_view_leaves'))


@main.route("/admin/reject/<int:leave_id>")
@login_required
def reject_leave(leave_id):
    if current_user.role != "admin":
        flash("Access denied!", "danger")
        return redirect(url_for("main.dashboard"))

    leave = LeaveRequest.query.get_or_404(leave_id)
    leave.status = "Rejected"
    db.session.commit()
    flash("Leave rejected!", "warning")
    return redirect(url_for("main.admin_view_leaves"))


@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form['name']
        current_user.email = request.form['email']
        if request.form['password']:
            current_user.password = generate_password_hash(request.form['password'])
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.profile'))

    return render_template('profile.html', user=current_user)


@main.route('/admin/create-user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        leave_balance = int(request.form['leave_balance'])

        hashed_pw = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_pw, role=role, leave_balance=leave_balance)
        db.session.add(new_user)
        db.session.commit()
        flash("New user created!", "success")
        return redirect(url_for('main.create_user'))

    return render_template('create_user.html')
