import os
import random
import string
import bcrypt
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'defaultsecretkey123')

# Configuration for file uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Limit upload size to 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# Configuration for Flask-Mail
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
mail = Mail(app)

# Function to get Database Connection
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            user=os.environ.get('DB_USER', 'root'),
            password=os.environ.get('DB_PASSWORD', 'root'),
            database=os.environ.get('DB_NAME', 'digilocker_clone_db')
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

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
            
        conn = get_db_connection()
        if not conn:
            flash("Database connection failed. Please check your setup.", "danger")
            return redirect(url_for('signup'))
            
        cursor = conn.cursor(dictionary=True)
        
        # Check if user already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
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
            # Write to a file for debugging
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'otp.txt'), 'w') as f:
                f.write(veri_code)
            
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
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    "INSERT INTO users (email, password, is_verified) VALUES (%s, %s, TRUE)",
                    (temp_signup['email'], temp_signup['password'])
                )
                conn.commit()
                # Get the new user ID
                cursor.execute("SELECT id FROM users WHERE email = %s", (temp_signup['email'],))
                user = cursor.fetchone()
                
                # Log them in
                session['user_id'] = user['id']
                session['email'] = temp_signup['email']
                
                # Clear temp session
                session.pop('temp_signup', None)
                flash("Email verified successfully! Welcome to your Locker.", "success")
                return redirect(url_for('dashboard'))
            except Exception as e:
                flash("Database error during user creation.", "danger")
                print(e)
            finally:
                cursor.close()
                conn.close()
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
        print(f"New real email sent securely to {email}")
        flash("A new verification code has been sent to your email.", "success")
    except Exception as e:
        print(f"Error sending email: {e}")
        flash("Failed to send new email. Ensure your Gmail is configured.", "danger")
        
    return redirect(url_for('verify'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            if not user['is_verified']:
                flash("Please verify your email before logging in.", "warning")
                return redirect(url_for('verify', email=email))
                
            if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                session['user_id'] = user['id']
                session['email'] = user['email']
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
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Handle File Upload
    if request.method == 'POST':
        if 'document' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['document']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file:
            filename = secure_filename(file.filename)
            custom_name = request.form.get('custom_filename')
            
            if custom_name and custom_name.strip() != '':
                ext = os.path.splitext(filename)[1]
                secure_custom = secure_filename(custom_name.strip())
                if secure_custom: # Ensure it doesn't become empty after stripping illegal chars
                    filename = secure_custom + ext
                    
            # Create a user-specific folder securely
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
            os.makedirs(user_folder, exist_ok=True)
            
            filepath = os.path.join(user_folder, filename)
            file.save(filepath)
            
            # Save file info to database
            relative_path = f"{str(user_id)}/{filename}"
            cursor.execute(
                "INSERT INTO documents (user_id, filename, filepath) VALUES (%s, %s, %s)",
                (user_id, filename, relative_path)
            )
            conn.commit()
            flash("Document uploaded successfully!", "success")
            
    # Fetch all documents for this user
    cursor.execute("SELECT * FROM documents WHERE user_id = %s ORDER BY upload_date DESC", (user_id,))
    documents = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('dashboard.html', documents=documents, email=session['email'])

@app.route('/download/<int:doc_id>')
def download_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Only allow downloading if the document belongs to the logged in user
    cursor.execute("SELECT * FROM documents WHERE id = %s AND user_id = %s", (doc_id, user_id))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if doc:
        return send_from_directory(app.config['UPLOAD_FOLDER'], doc['filepath'], download_name=doc['filename'], as_attachment=True)
    else:
        flash("Document not found or unauthorized.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/view/<int:doc_id>')
def view_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Only allow viewing if the document belongs to the logged in user
    cursor.execute("SELECT * FROM documents WHERE id = %s AND user_id = %s", (doc_id, user_id))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if doc:
        return send_from_directory(app.config['UPLOAD_FOLDER'], doc['filepath'])
    else:
        flash("Document not found or unauthorized.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/delete_document/<int:doc_id>', methods=['POST'])
def delete_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM documents WHERE id = %s AND user_id = %s", (doc_id, user_id))
    doc = cursor.fetchone()
    
    if doc:
        # Delete the actual file from storage
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], doc['filepath'])
        print(f"Attempting to delete file: {full_path}")
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                print(f"File deleted: {full_path}")
            except Exception as e:
                print(f"Error deleting file: {e}")
            
        # Delete from Database
        cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        conn.commit()
        flash("Document deleted securely.", "success")
        print(f"Database record deleted for id: {doc_id}")
    else:
        flash("Document not found.", "danger")
        print(f"Document not found for id: {doc_id} and user_id: {user_id}")
        
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/edit_document/<int:doc_id>', methods=['POST'])
def edit_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    new_name = request.form.get('new_filename')
    if not new_name or new_name.strip() == '':
        flash("The new filename cannot be empty.", "warning")
        return redirect(url_for('dashboard'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM documents WHERE id = %s AND user_id = %s", (doc_id, user_id))
    doc = cursor.fetchone()
    
    if doc:
        # Prevent losing the original extension
        ext = os.path.splitext(doc['filename'])[1]
        secure_custom = secure_filename(new_name.strip())
        
        if secure_custom:
            final_name = secure_custom + ext
            
            # Update File on Disk
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], doc['filepath'])
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
            new_relative_path = f"{str(user_id)}/{final_name}"
            new_path = os.path.join(app.config['UPLOAD_FOLDER'], new_relative_path)
            
            print(f"Renaming file from {old_path} to {new_path}")
            
            if os.path.exists(old_path):
                try:
                    os.rename(old_path, new_path)
                    print("File renamed on disk.")
                except Exception as e:
                    print(f"Error renaming file on disk: {e}")
            
            # Update Database
            cursor.execute("UPDATE documents SET filename = %s, filepath = %s WHERE id = %s", (final_name, new_relative_path, doc_id))
            conn.commit()
            flash("Document renamed successfully.", "success")
            print(f"Database record updated for id: {doc_id}")
        else:
            flash("Invalid characters in filename.", "warning")
    else:
        flash("Document not found.", "danger")
        print(f"Document not found for id: {doc_id} and user_id: {user_id}")
        
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    print("Starting Alpha Loker Server on http://127.0.0.1:5000")
    app.run(debug=True)
