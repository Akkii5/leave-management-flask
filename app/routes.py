from flask import Blueprint, app, render_template, redirect, url_for, flash, request, abort, current_app, g
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import and_
from app import db
from app.models import LeaveBalance, User, LeaveRequest


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
        reporting_manager_id = request.form.get('reporting_manager_id')

        new_user = User(
            name=name,
            email=email,
            password=password,
            role=role,
            reporting_manager_id=reporting_manager_id if reporting_manager_id else None
        )
        db.session.add(new_user)
        db.session.commit()

        # Create initial leave balances
        casual = LeaveBalance(user_id=new_user.id, leave_type='Casual', total=12, used=0)
        sick = LeaveBalance(user_id=new_user.id, leave_type='Sick', total=6, used=0)
        db.session.add_all([casual, sick])
        db.session.commit()

        flash("User registered successfully with leave balances.", "success")
        return redirect(url_for('main.dashboard'))

    managers = User.query.filter_by(role='admin').all()
    return render_template('register.html', managers=managers)




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
    # Clear the notification seen flag when the user visits the dashboard
    # session.pop('notification_seen', None)

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
        leave_type = request.form["leave_type"]
        reason = request.form["reason"]

        # ✅ Only count Mon–Fri as working days
        def calculate_working_days(start, end):
            count = 0
            current = start
            while current <= end:
                if current.weekday() < 5:  # Mon–Fri only
                    count += 1
                current += timedelta(days=1)
            return count

        leave_days = calculate_working_days(start_date, end_date)

        # Fetch leave balance for selected leave_type
        balance = LeaveBalance.query.filter_by(user_id=current_user.id, leave_type=leave_type).first()
        if not balance:
            flash(f"No leave balance found for {leave_type}.", "danger")
            return redirect(url_for("main.apply_leave"))

        remaining = balance.total - balance.used

        # ❌ Case: More than allowed balance
        if leave_days > remaining:
            flash(
                f"You have only {remaining} {leave_type} leave(s) remaining. "
                f"You can apply for up to {remaining} working day(s).",
                "warning"
            )
            return redirect(url_for("main.apply_leave"))

        # ⚠️ Case: Sick leave > 2 working days
        if leave_type == "Sick" and leave_days > 2:
            flash("Note: For Sick Leave more than 2 working days, Medical Certificate is required.", "warning")

        # ✅ Proceed to save leave request
        leave = LeaveRequest(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            leave_type=leave_type,
            reason=reason,
        )
        db.session.add(leave)
        db.session.commit()

        flash(f"Leave request for {leave_days} working day(s) submitted successfully!", "success")
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

    # Calculate effective_days for each leave
    for leave in leaves:
        if leave.start_date and leave.end_date:
            leave.effective_days = (leave.end_date - leave.start_date).days + 1
        else:
            leave.effective_days = 0

    # Flag to check if at least one leave is pending, to decide whether to show Action column
    show_action_column = any(leave.status == 'Pending' for leave in leaves)

    return render_template('my_leaves.html', leaves=leaves, show_action_column=show_action_column)



# @main.route("/admin/leaves")
# @login_required
# def admin_view_leaves():
#     if current_user.role != "admin":
#         flash("Access denied!", "danger")
#         return redirect(url_for("main.dashboard"))

#     # Only fetch leave requests where the applicant's reporting manager is the current user
#     leaves = LeaveRequest.query.join(User).filter(User.reporting_manager_id == current_user.id).order_by(LeaveRequest.start_date.desc()).all()

#     return render_template("admin_leaves.html", leaves=leaves)
@main.route("/admin/leaves")
@login_required
def admin_view_leaves():
    if current_user.role != "admin":
        flash("Access denied!", "danger")
        return redirect(url_for("main.dashboard"))

    # Display newest leave requests first
    leaves = LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all()

    return render_template("admin_leaves.html", leaves=leaves)


@main.route("/approve/<int:leave_id>")
@login_required
def approve_leave(leave_id):
    if current_user.role != "admin":
        flash("Unauthorized", "danger")
        return redirect(url_for("main.admin_view_leaves"))

    leave = LeaveRequest.query.get_or_404(leave_id)

    # Optional: Restrict to manager-only
    # if leave.applicant.reporting_manager_id != current_user.id:
    #     flash("Not authorized to approve this request.", "danger")
    #     return redirect(url_for("main.admin_view_leaves"))

    leave.status = "Approved"
    db.session.commit()
    flash("Leave approved", "success")
    return redirect(url_for("main.admin_view_leaves"))


@main.route("/reject/<int:leave_id>")
@login_required
def reject_leave(leave_id):
    if current_user.role != "admin":
        flash("Unauthorized", "danger")
        return redirect(url_for("main.admin_view_leaves"))

    leave = LeaveRequest.query.get_or_404(leave_id)
    leave.status = "Rejected"
    db.session.commit()
    flash("Leave rejected", "danger")
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

    # ✅ Get reporting manager name if available
    reporting_manager_name = current_user.manager.name if current_user.manager else "Not Assigned"

    return render_template('profile.html', user=current_user, reporting_manager_name=reporting_manager_name)



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
        reporting_manager_id = request.form.get('reporting_manager_id')

        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'warning')
            return redirect(url_for('main.create_user'))

        hashed_pw = generate_password_hash(password, method='sha256')
        new_user = User(
            name=name,
            email=email,
            password=hashed_pw,
            role=role,
            reporting_manager_id=reporting_manager_id if reporting_manager_id else None
        )
        db.session.add(new_user)
        db.session.commit()

        # Initialize leave balances
        casual = LeaveBalance(user_id=new_user.id, leave_type='Casual', total=12, used=0)
        sick = LeaveBalance(user_id=new_user.id, leave_type='Sick', total=6, used=0)
        db.session.add_all([casual, sick])
        db.session.commit()

        flash("New user created with leave balances!", "success")
        return redirect(url_for('main.create_user'))

    managers = User.query.filter_by(role='admin').all()
    return render_template('create_user.html', managers=managers)

@main.route("/delete-leave/<int:leave_id>", methods=["POST"])
@login_required
def delete_leave(leave_id):
    leave = LeaveRequest.query.get_or_404(leave_id)

    if leave.applicant.id  != current_user.id:
        flash("You are not authorized to delete this leave request.", "danger")
        return redirect(url_for("main.view_my_leaves"))

    if leave.status != "Pending":
        flash("Only pending leave requests can be deleted.", "warning")
        return redirect(url_for("main.view_my_leaves"))

    db.session.delete(leave)
    db.session.commit()
    flash("Leave request deleted successfully.", "success")
    return redirect(url_for("main.view_my_leaves"))


def calculate_effective_days(start_date, end_date):
    total_days = (end_date - start_date).days + 1
    effective_days = 0
    for i in range(total_days):
        day = start_date + timedelta(days=i)
        if day.weekday() not in (5, 6):  # Skip Saturday (5) and Sunday (6)
            effective_days += 1
    return effective_days



@main.before_request
def load_notifications():
    if current_user.is_authenticated:
        if current_user.role == 'employee':
            # Get count of approved leaves for this employee that are new/unread
            g.notification_count = get_unread_approved_leaves_count(current_user.id)
            g.notifications = get_unread_approved_leaves(current_user.id)
        elif current_user.role == 'admin':
            # Get count of pending leave requests employees made
            g.notification_count = get_pending_leave_requests_count()
            g.notifications = get_pending_leave_requests()
    else:
        g.notification_count = 0
        g.notifications = []


from flask import url_for
from flask_login import current_user

@main.app_context_processor
def inject_notifications():
    if not current_user.is_authenticated:
        return dict(notification_count=0, notifications=[])

    if current_user.role == 'employee':
        leaves = LeaveRequest.query.filter(
            LeaveRequest.user_id == current_user.id,
            LeaveRequest.status == 'Approved',
            LeaveRequest.is_read == False
        ).order_by(LeaveRequest.created_at.desc()).all()

        notifications = [
            {
                'message': f"Your leave request #{leave.id} has been approved.",
                'link': url_for('main.view_my_leaves')  # You may link to individual leave if you implement view_leave
            }
            for leave in leaves
        ]
        notification_count = len(notifications)

    elif current_user.role == 'admin':
        leaves = LeaveRequest.query.join(User).filter(
            LeaveRequest.status == 'Pending',
            User.reporting_manager_id == current_user.id
        ).order_by(LeaveRequest.created_at.desc()).all()

        notifications = [
            {
                'message': f"New leave request from {leave.applicant.name}.",
                'link': url_for('main.admin_view_leaves')
            }
            for leave in leaves
        ]
        notification_count = len(notifications)

    else:
        notification_count = 0
        notifications = []

    return dict(notification_count=notification_count, notifications=notifications)


def get_unread_approved_leaves_count(user_id):
    return LeaveRequest.query.filter(
        LeaveRequest.user_id == user_id,
        LeaveRequest.status == 'approved',
        LeaveRequest.is_read == False
    ).count()

def get_unread_approved_leaves(user_id):
    leaves = LeaveRequest.query.filter(
        LeaveRequest.user_id == user_id,
        LeaveRequest.status == 'approved',
        LeaveRequest.is_read == False
    ).order_by(LeaveRequest.created_at.desc()).all()

    notifications = []
    for leave in leaves:
        notifications.append({
            "message": f"Your leave request #{leave.id} has been approved.",
            "link": url_for('main.view_leave', leave_id=leave.id)
        })
    return notifications

def get_pending_leave_requests():
    leaves = LeaveRequest.query.filter_by(status='pending').order_by(LeaveRequest.created_at.desc()).all()
    notifications = []
    for leave in leaves:
        user = leave.applicant
        notifications.append({
            "message": f"New leave request from {user.name}.",
            "link": url_for('main.admin_view_leaves', leave_id=leave.id)
        })
    return notifications

def get_pending_leave_requests_count():
    return LeaveRequest.query.filter_by(status='pending').count()

@main.route('/mark_as_read/<int:leave_id>')
@login_required
def mark_as_read(leave_id):
    leave = LeaveRequest.query.get_or_404(leave_id)
    if leave.applicant.id  == current_user.id:
        leave.is_read = True
        db.session.commit()
    return redirect(url_for('main.view_my_leaves'))


# @main.route('/admin/leaves')
# @login_required
# def view_leaves():
#     if current_user.role != 'admin':
#         flash("Access denied!", "danger")
#         return redirect(url_for('main.dashboard'))
    
#     leaves = LeaveRequest.query.all()
#     return render_template('admin_leaves.html', leaves=leaves)
# @main.route('/notification/click')
# @login_required
# def handle_notification_click():
#     # Clear session-based or context-based notification flag
#     session['notification_seen'] = True

#     if current_user.role == 'admin':
#         return redirect(url_for('main.admin_view_leaves'))
#     else:
#         return redirect(url_for('main.view_my_leaves'))

@main.route('/notifications/clear')
@login_required
def clear_notifications():
    if current_user.role == 'employee':
        unread_leaves = LeaveRequest.query.filter_by(
            user_id=current_user.id,
            status='Approved',
            is_read=False
        ).all()
        for leave in unread_leaves:
            leave.is_read = True
        db.session.commit()
        return redirect(url_for('main.view_my_leaves'))

    elif current_user.role == 'admin':
        # No need to mark anything as read
        return redirect(url_for('main.admin_view_leaves'))

    return redirect(url_for('main.dashboard'))

