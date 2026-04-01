import os
import random
import string
import bcrypt
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore, storage

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey123')

# Configuration for Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'coder.hacker.otp@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'esar bsyg xtii hulu')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
mail = Mail(app)

# Limit upload size to 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# Initialize Firebase Admin SDK
firebase_credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'firebase_credentials.json')

try:
    cred = credentials.Certificate(firebase_credentials_path)
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', 'alpha-locker.firebasestorage.app')
    })
    print("Firebase Admin HTTP successfully initialized.")
    
    # Initialize Firestore and Storage Clients
    db = firestore.client()
    bucket = storage.bucket()
except Exception as e:
    print(f"Error initializing Firebase Admin SDK. Please ensure firebase_credentials.json is correct: {e}")
    db = None
    bucket = None

# Generate a 6-digit random code
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for('signup'))
            
        if not db:
            flash("Database connection failed. Please check Firebase credentials.", "danger")
            return redirect(url_for('signup'))
            
        # Check if user already exists
        users_ref = db.collection('users')
        docs = users_ref.where('email', '==', email).limit(1).stream()
        
        user_exists = False
        for _ in docs:
            user_exists = True
            break
            
        if user_exists:
            flash("Email already registered. Please log in.", "warning")
            return redirect(url_for('login'))
            
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        veri_code = generate_verification_code()
        
        # Save temp data in session instead of DB
        session['temp_signup'] = {
            'email': email,
            'password': hashed_password,
            'otp': veri_code
        }
        
        # Send real email using Flask-Mail
        msg = Message('Your Alpha Loker Verification Code', recipients=[email])
        msg.body = f"Welcome to Alpha Loker!\n\nYour 6-digit verification code is: {veri_code}\n\nPlease enter this code on the website to verify your account and access your locker."
        
        try:
            mail.send(msg)
            print(f"Real email sent securely to {email}")
            flash("Check your email for the verification code.", "success")
        except Exception as e:
            print(f"Error sending email: {e}")
            flash("Registered, but failed to send email. Ensure you configured your Gmail and App Password in app.py.", "danger")
            # Fallback for debugging if email fails
            print(f"Fallback. Code is: {veri_code}")
            
        return redirect(url_for('verify'))
        
    return render_template('signup.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    temp_signup = session.get('temp_signup')
    if not temp_signup:
        flash("Please start the signup process first.", "warning")
        return redirect(url_for('signup'))
        
    email = temp_signup['email']
    
    if request.method == 'POST':
        code = request.form.get('code')
        
        if code == temp_signup['otp']:
            # OTP is correct! Now insert them into DB
            try:
                # Add a new document in collection "users"
                new_user_ref = db.collection('users').document()
                new_user_ref.set({
                    'email': temp_signup['email'],
                    'password': temp_signup['password'],
                    'is_verified': True
                })
                
                # Log them in
                session['user_id'] = new_user_ref.id
                session['email'] = temp_signup['email']
                
                # Clear temp session
                session.pop('temp_signup', None)
                flash("Email verified successfully! Welcome to your Locker.", "success")
                return redirect(url_for('dashboard'))
            except Exception as e:
                flash("Database error during user creation.", "danger")
                print(e)
        else:
            flash("Invalid verification code. Please try again.", "danger")
            
    return render_template('verify.html', email=email)

@app.route('/resend', methods=['POST'])
def resend():
    temp_signup = session.get('temp_signup')
    if not temp_signup:
        return redirect(url_for('signup'))
        
    email = temp_signup['email']
    veri_code = generate_verification_code()
    
    # Update temp OTP in session
    temp_signup['otp'] = veri_code
    session['temp_signup'] = temp_signup
    
    # Send new email using Flask-Mail
    msg = Message('Your Alpha Loker Verification Code', recipients=[email])
    msg.body = f"Welcome to Alpha Loker!\n\nYour new 6-digit verification code is: {veri_code}\n\nPlease enter this code on the website to verify your account and access your locker."
    
    try:
        mail.send(msg)
        flash("A new verification code has been sent to your email.", "success")
    except Exception as e:
        print(f"Error sending email: {e}")
        flash("Failed to send new email.", "danger")
        
    return redirect(url_for('verify'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not db:
            flash("Database connection failed. Please check setup.", "danger")
            return render_template('login.html')
            
        users_ref = db.collection('users')
        docs = users_ref.where('email', '==', email).limit(1).stream()
        
        user_data = None
        user_id = None
        for doc in docs:
            user_data = doc.to_dict()
            user_id = doc.id
            
        if user_data:
            if not user_data.get('is_verified', False):
                flash("Please verify your email before logging in.", "warning")
                return redirect(url_for('verify', email=email))
                
            if bcrypt.checkpw(password.encode('utf-8'), user_data['password'].encode('utf-8')):
                session['user_id'] = user_id
                session['email'] = user_data['email']
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid email or password.", "danger")
        else:
            flash("Invalid email or password.", "danger")
            
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access your locker.", "danger")
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    
    # Handle File Upload
    if request.method == 'POST':
        if 'document' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['document']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file and bucket:
            filename = secure_filename(file.filename)
            custom_name = request.form.get('custom_filename')
            
            if custom_name and custom_name.strip() != '':
                ext = os.path.splitext(filename)[1]
                secure_custom = secure_filename(custom_name.strip())
                if secure_custom: 
                    filename = secure_custom + ext
                    
            # Set the Firebase Cloud Storage relative path
            relative_path = f"{str(user_id)}/{filename}"
            blob = bucket.blob(relative_path)
            
            # Upload actual file bytes to Firebase Storage
            blob.upload_from_file(file, content_type=file.content_type)
            
            # Save file info to Firestore database
            db.collection('documents').add({
                'user_id': user_id,
                'filename': filename,
                'filepath': relative_path,
                'upload_date': firestore.SERVER_TIMESTAMP
            })
            flash("Document uploaded successfully to Firebase!", "success")
            
    # Fetch all documents for this user
    docs_ref = db.collection('documents').where('user_id', '==', user_id).order_by('upload_date', direction=firestore.Query.DESCENDING).stream()
    documents = []
    for doc in docs_ref:
        doc_dict = doc.to_dict()
        doc_dict['id'] = doc.id
        documents.append(doc_dict)
    
    return render_template('dashboard.html', documents=documents, email=session['email'])

@app.route('/download/<doc_id>')
def download_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    
    doc_ref = db.collection('documents').document(doc_id)
    doc = doc_ref.get()
    
    if doc.exists and doc.to_dict().get('user_id') == user_id:
        doc_data = doc.to_dict()
        blob = bucket.blob(doc_data['filepath'])
        
        # Generate a Signed URL valid for 1 hour to let the browser download it natively
        url = blob.generate_signed_url(expiration=datetime.timedelta(hours=1), version="v4", 
                                       response_disposition=f"attachment; filename=\"{doc_data['filename']}\"")
        return redirect(url)
    else:
        flash("Document not found or unauthorized.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/view/<doc_id>')
def view_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    
    doc_ref = db.collection('documents').document(doc_id)
    doc = doc_ref.get()
    
    if doc.exists and doc.to_dict().get('user_id') == user_id:
        doc_data = doc.to_dict()
        blob = bucket.blob(doc_data['filepath'])
        
        # Generate a Signed URL valid for 1 hour to let the browser view it
        url = blob.generate_signed_url(expiration=datetime.timedelta(hours=1), version="v4", 
                                       response_disposition="inline")
        return redirect(url)
    else:
        flash("Document not found or unauthorized.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/delete_document/<doc_id>', methods=['POST'])
def delete_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    
    doc_ref = db.collection('documents').document(doc_id)
    doc = doc_ref.get()
    
    if doc.exists and doc.to_dict().get('user_id') == user_id:
        doc_data = doc.to_dict()
        
        # Delete from Firebase Storage
        blob = bucket.blob(doc_data['filepath'])
        if blob.exists():
            try:
                blob.delete()
                print(f"File deleted from storage: {doc_data['filepath']}")
            except Exception as e:
                print(f"Error deleting file from Firebase Storage: {e}")
            
        # Delete from Firestore
        doc_ref.delete()
        flash("Document deleted securely from Firebase.", "success")
    else:
        flash("Document not found or unauthorized.", "danger")
        
    return redirect(url_for('dashboard'))

@app.route('/edit_document/<doc_id>', methods=['POST'])
def edit_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    new_name = request.form.get('new_filename')
    if not new_name or new_name.strip() == '':
        flash("The new filename cannot be empty.", "warning")
        return redirect(url_for('dashboard'))
        
    user_id = session['user_id']
    
    doc_ref = db.collection('documents').document(doc_id)
    doc = doc_ref.get()
    
    if doc.exists and doc.to_dict().get('user_id') == user_id:
        doc_data = doc.to_dict()
        
        # Prevent losing the original extension
        ext = os.path.splitext(doc_data['filename'])[1]
        secure_custom = secure_filename(new_name.strip())
        
        if secure_custom:
            final_name = secure_custom + ext
            new_relative_path = f"{str(user_id)}/{final_name}"
            
            # If the filename actually changed
            if doc_data['filepath'] != new_relative_path:
                source_blob = bucket.blob(doc_data['filepath'])
                
                if source_blob.exists():
                    try:
                        # Rename in Firebase Storage (Copies to new, deletes old)
                        bucket.rename_blob(source_blob, new_relative_path)
                        print("File renamed in Firebase Storage.")
                    except Exception as e:
                        print(f"Error renaming file in Storage: {e}")
                        
            # Update Firestore Database
            doc_ref.update({
                'filename': final_name, 
                'filepath': new_relative_path
            })
            flash("Document renamed successfully.", "success")
        else:
            flash("Invalid characters in filename.", "warning")
    else:
        flash("Document not found.", "danger")
        
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    print("Starting Alpha Loker Server on http://127.0.0.1:5000")
    app.run(debug=True)
