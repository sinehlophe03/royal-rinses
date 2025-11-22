from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'royalrinse-secret')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///royalrinse.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Admin credentials
ADMIN_USER = 'admin'
ADMIN_PASS = '1234'

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(128))

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(140))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    phone = db.Column(db.String(60))
    email = db.Column(db.String(200))
    service = db.Column(db.String(80))
    date = db.Column(db.Date)
    time = db.Column(db.String(20))
    address = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(30), default='pending')  # pending, approved, rejected, completed
    paid = db.Column(db.Boolean, default=False)
    amount = db.Column(db.Float, default=0.0)

DEFAULT_SLOTS = ['08:00','09:00','10:00','11:00','12:00','13:00','14:00','15:00','16:00']

SERVICE_PRICES = {'basic': 15.0, 'deluxe': 30.0, 'royal': 50.0}

def available_slots_for(date_obj):
    bookings = Booking.query.filter_by(date=date_obj, status='approved').all()
    taken = [b.time for b in bookings]
    return [s for s in DEFAULT_SLOTS if s not in taken]

@app.context_processor
def inject_common():
    contact = {'phone': '76716978', 'email': 'royalrinse07@gmail.com', 'location': 'Mbabane, Sdwashini'}
    return {'current_year': datetime.utcnow().year, 'contact': contact}

@app.route('/')
def index():
    services = [
        {'id':'basic','title':'Basic Rinse','price':SERVICE_PRICES['basic'],'desc':'Exterior wash & dry'},
        {'id':'deluxe','title':'Deluxe Rinse','price':SERVICE_PRICES['deluxe'],'desc':'Exterior + interior vacuum'},
        {'id':'royal','title':'Royal Rinse','price':SERVICE_PRICES['royal'],'desc':'Full detail: wax, polish, deep interior clean'}
    ]
    return render_template('index.html', services=services)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        if not (fullname and email and password):
            flash('Please fill all fields', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'warning')
            return redirect(url_for('register'))
        u = User(fullname=fullname, email=email, password=password)
        db.session.add(u); db.session.commit()
        flash('Account created, please login', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        # admin login
        if email == ADMIN_USER and password == ADMIN_PASS:
            session['admin'] = True
            flash('Admin logged in', 'success')
            return redirect(url_for('admin_dashboard'))
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            session['fullname'] = user.fullname
            flash('Logged in', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('index'))

@app.route('/book', methods=['GET','POST'])
def book():
    if 'user_id' not in session:
        flash('Please login to book', 'warning')
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('customer_name') or session.get('fullname')
        phone = request.form.get('phone')
        email = request.form.get('email')
        service = request.form.get('service') or 'basic'
        date_str = request.form.get('date')
        time_slot = request.form.get('time')
        address = request.form.get('address')
        notes = request.form.get('notes')
        if not (name and phone and date_str and time_slot and address):
            flash('Please fill required fields', 'danger')
            return redirect(url_for('book'))
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date', 'danger'); return redirect(url_for('book'))
        if time_slot not in available_slots_for(d):
            flash('Slot not available', 'warning'); return redirect(url_for('book'))
        amount = SERVICE_PRICES.get(service, SERVICE_PRICES['basic'])
        b = Booking(customer_name=name, user_id=session.get('user_id'), phone=phone, email=email, service=service, date=d, time=time_slot, address=address, notes=notes, amount=amount)
        db.session.add(b); db.session.commit()
        session['pending_booking_id'] = b.id
        flash('Booking created. Proceed to payment.', 'info')
        return redirect(url_for('payment'))
    return render_template('book.html')

@app.route('/api/slots')
def api_slots():
    date_str = request.args.get('date')
    if not date_str: return jsonify({'slots': []})
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'slots': []})
    return jsonify({'slots': available_slots_for(d)})

@app.route('/payment', methods=['GET','POST'])
def payment():
    booking_id = session.get('pending_booking_id')
    if not booking_id:
        flash('No booking to pay for', 'warning'); return redirect(url_for('book'))
    b = Booking.query.get(booking_id)
    if not b:
        flash('Booking not found', 'danger'); return redirect(url_for('book'))
    if request.method == 'POST':
        card = request.form.get('card_number','').strip()
        exp = request.form.get('exp','').strip()
        cvv = request.form.get('cvv','').strip()
        if len(card) < 12 or len(cvv) < 3:
            flash('Invalid card (demo only)', 'danger'); return redirect(url_for('payment'))
        b.paid = True; db.session.commit()
        session.pop('pending_booking_id', None)
        flash('Payment successful. Waiting admin approval.', 'success')
        return redirect(url_for('my_bookings'))
    return render_template('payment.html', booking=b)

@app.route('/my_bookings')
def my_bookings():
    if 'user_id' not in session:
        flash('Please login', 'warning'); return redirect(url_for('login'))
    bookings = Booking.query.filter_by(user_id=session['user_id']).order_by(Booking.date.desc(), Booking.time).all()
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/schedule')
def schedule():
    date_str = request.args.get('date')
    if date_str:
        try: selected = datetime.strptime(date_str, '%Y-%m-%d').date()
        except: selected = date.today()
    else: selected = date.today()
    bookings = Booking.query.filter_by(date=selected, status='approved', paid=True).order_by(Booking.time).all()
    return render_template('schedule.html', bookings=bookings, today=selected)

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get('username'); pw = request.form.get('password')
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['admin'] = True; flash('Admin logged in', 'success'); return redirect(url_for('admin_dashboard'))
        flash('Invalid', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None); flash('Logged out', 'info'); return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    bookings = Booking.query.order_by(Booking.status.asc(), Booking.date.desc(), Booking.time).all()
    return render_template('admin.html', bookings=bookings)

@app.route('/admin/action/<int:bid>', methods=['POST'])
def admin_action(bid):
    if not session.get('admin'): flash('Not authorized', 'danger'); return redirect(url_for('admin_login'))
    action = request.form.get('action'); b = Booking.query.get_or_404(bid)
    if action == 'approve': b.status = 'approved'
    elif action == 'reject': b.status = 'rejected'
    elif action == 'complete': b.status = 'completed'
    db.session.commit(); flash('Action applied', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
