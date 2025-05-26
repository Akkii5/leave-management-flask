from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, current_user, logout_user, login_required
from datetime import datetime
from werkzeug.security import generate_password_hash
from app import db
from app.models import LeaveBalance, User, LeaveRequest
from werkzeug.security import check_password_hash

main = Blueprint('main', __name__)


@main.route("/")
def home():
    return render_template("home.html")


@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'], method='sha256')
        role = request.form['role']

        new_user = User(name=name, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()

        # Create initial leave balances
        casual = LeaveBalance(user_id=new_user.id, leave_type='Casual', total=12, used=0)
        sick = LeaveBalance(user_id=new_user.id, leave_type='Sick', total=6, used=0)
        db.session.add_all([casual, sick])
        db.session.commit()

        flash("User registered successfully with leave balances.", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('register.html')



@main.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Login failed. Check email/password.', 'danger')

    return render_template("login.html")


@main.route("/dashboard")
@login_required
def dashboard():
    balances = LeaveBalance.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', leave_balances=balances, user=current_user)



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
        start_date = datetime.strptime(request.form["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(request.form["end_date"], "%Y-%m-%d")
        leave = LeaveRequest(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            leave_type=request.form["leave_type"],
            reason=request.form["reason"]
        )
        db.session.add(leave)
        db.session.commit()
        flash("Leave request submitted successfully!", "success")
        return redirect(url_for("main.view_my_leaves"))

    return render_template("apply_leave.html")


@main.route('/my-leaves', methods=['GET', 'POST'])
@login_required
def view_my_leaves():
    filters = {'user_id': current_user.id}

    if request.method == 'POST':
        status = request.form.get('status')
        leave_type = request.form.get('leave_type')
        if status:
            filters['status'] = status
        if leave_type:
            filters['leave_type'] = leave_type

    leaves = LeaveRequest.query.filter_by(**filters).order_by(LeaveRequest.start_date.desc()).all()
    return render_template('my_leaves.html', leaves=leaves)


@main.route("/admin/leaves")
@login_required
def admin_view_leaves():
    if current_user.role != "admin":
        flash("Access denied!", "danger")
        return redirect(url_for("main.dashboard"))

    leaves = LeaveRequest.query.order_by(LeaveRequest.start_date.desc()).all()
    return render_template("admin_leaves.html", leaves=leaves)


@main.route('/approve/<int:leave_id>')
@login_required
def approve_leave(leave_id):
    leave = LeaveRequest.query.get_or_404(leave_id)
    user = leave.applicant  # This is the User object
    leave_days = (leave.end_date - leave.start_date).days + 1

    # Get the LeaveBalance record for that user and leave type
    balance = LeaveBalance.query.filter_by(user_id=user.id, leave_type=leave.leave_type).first()

    if not balance:
        flash("Leave balance record not found for this type.", "danger")
        return redirect(url_for('main.admin_view_leaves'))

    if balance.remaining < leave_days:
        flash(f"Insufficient {leave.leave_type} leave balance.", "danger")
        return redirect(url_for('main.admin_view_leaves'))

    # Approve and update used leave
    leave.status = 'Approved'
    balance.used += leave_days
    db.session.commit()

    flash("Leave approved successfully.", "success")
    return redirect(url_for('main.admin_view_leaves'))



@main.route("/admin/reject/<int:leave_id>")
@login_required
def reject_leave(leave_id):
    if current_user.role != "admin":
        flash("Access denied!", "danger")
        return redirect(url_for("main.dashboard"))

    leave = LeaveRequest.query.get_or_404(leave_id)
    if leave.status != 'Pending':
        flash('Leave already processed.', 'info')
    else:
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

        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'warning')
            return redirect(url_for('main.create_user'))

        hashed_pw = generate_password_hash(password, method='sha256')
        new_user = User(name=name, email=email, password=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()  # Commit to get new_user.id

        # Initialize leave balances for new user
        casual = LeaveBalance(user_id=new_user.id, leave_type='Casual', total=12, used=0)
        sick = LeaveBalance(user_id=new_user.id, leave_type='Sick', total=6, used=0)
        db.session.add_all([casual, sick])
        db.session.commit()

        flash("New user created with leave balances!", "success")
        return redirect(url_for('main.create_user'))

    return render_template('create_user.html')
