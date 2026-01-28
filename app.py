from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

# Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'attendance.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    employee_id = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    attendance_records = db.relationship('Attendance', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'employee_id': self.employee_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='present')  # present, absent, late, leave

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'check_in': self.check_in.strftime('%Y-%m-%d %H:%M:%S') if self.check_in else None,
            'check_out': self.check_out.strftime('%Y-%m-%d %H:%M:%S') if self.check_out else None,
            'date': self.date.strftime('%Y-%m-%d'),
            'status': self.status
        }


# Routes
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# API Routes - Users
@app.route("/api/users", methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])


@app.route("/api/users", methods=['POST'])
def create_user():
    data = request.get_json()
    
    if not data or not all(k in data for k in ['name', 'email', 'employee_id']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    if User.query.filter_by(employee_id=data['employee_id']).first():
        return jsonify({'error': 'Employee ID already exists'}), 400
    
    user = User(
        name=data['name'],
        email=data['email'],
        employee_id=data['employee_id']
    )
    db.session.add(user)
    db.session.commit()
    
    return jsonify(user.to_dict()), 201


@app.route("/api/users/<int:user_id>", methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())


@app.route("/api/users/<int:user_id>", methods=['PUT'])
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if 'name' in data:
        user.name = data['name']
    if 'email' in data:
        if User.query.filter_by(email=data['email']).first() and user.email != data['email']:
            return jsonify({'error': 'Email already exists'}), 400
        user.email = data['email']
    if 'employee_id' in data:
        if User.query.filter_by(employee_id=data['employee_id']).first() and user.employee_id != data['employee_id']:
            return jsonify({'error': 'Employee ID already exists'}), 400
        user.employee_id = data['employee_id']
    
    db.session.commit()
    return jsonify(user.to_dict())


@app.route("/api/users/<int:user_id>", methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204


# API Routes - Attendance
@app.route("/api/attendance", methods=['GET'])
def get_attendance():
    user_id = request.args.get('user_id', type=int)
    date = request.args.get('date')
    
    query = Attendance.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if date:
        query = query.filter_by(date=datetime.strptime(date, '%Y-%m-%d').date())
    
    attendance = query.all()
    return jsonify([a.to_dict() for a in attendance])


@app.route("/api/attendance/check-in", methods=['POST'])
def check_in():
    data = request.get_json()
    
    if not data or 'user_id' not in data:
        return jsonify({'error': 'Missing user_id'}), 400
    
    user = User.query.get_or_404(data['user_id'])
    today = datetime.utcnow().date()
    
    # Check if already checked in today
    existing = Attendance.query.filter_by(user_id=data['user_id'], date=today).first()
    if existing:
        return jsonify({'error': 'Already checked in today'}), 400
    
    attendance = Attendance(
        user_id=data['user_id'],
        check_in=datetime.utcnow(),
        date=today,
        status='present'
    )
    db.session.add(attendance)
    db.session.commit()
    
    return jsonify({
        'message': f'{user.name} checked in successfully',
        'attendance': attendance.to_dict()
    }), 201


@app.route("/api/attendance/<int:attendance_id>/check-out", methods=['POST'])
def check_out(attendance_id):
    attendance = Attendance.query.get_or_404(attendance_id)
    
    if attendance.check_out:
        return jsonify({'error': 'Already checked out'}), 400
    
    attendance.check_out = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'message': 'Checked out successfully',
        'attendance': attendance.to_dict()
    })


@app.route("/api/attendance/user/<int:user_id>/summary", methods=['GET'])
def get_attendance_summary(user_id):
    user = User.query.get_or_404(user_id)
    records = Attendance.query.filter_by(user_id=user_id).all()
    
    summary = {
        'user': user.to_dict(),
        'total_records': len(records),
        'present': len([r for r in records if r.status == 'present']),
        'absent': len([r for r in records if r.status == 'absent']),
        'late': len([r for r in records if r.status == 'late']),
        'leave': len([r for r in records if r.status == 'leave']),
        'records': [r.to_dict() for r in records]
    }
    
    return jsonify(summary)


# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# Create database tables
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)