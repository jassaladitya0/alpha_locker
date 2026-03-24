# Alpha Loker - Beginner Project

Welcome to the Alpha Loker project! This application is built with HTML, CSS, Python (Flask), and MySQL. 

It allows users to register, verifying their account with an email code (simulated in the console), log in securely, and upload/manage their personal documents.

## Prerequisites
1. **Python 3.x** installed on your system.
2. **MySQL Server** installed and running on your system.

## How to Run the App

### Step 1: Install Dependencies
Open a terminal in the project folder (`c:/Users/Aditya Jassal/OneDrive/Desktop/New folder/digilocker_clone`) and run:
```bash
pip install -r requirements.txt
```

### Step 2: Initialize Database
We have provided an initialization script that creates the `digilocker_clone_db` database and its tables automatically.

If your MySQL `root` user has a password other than empty (`""`), please open `init_db.py` and `app.py` and change the `password=""` to `password="your_password"`.

Run the database setup script:
```bash
python init_db.py
```

### Step 3: Start the Flask App
Run the server:
```bash
python app.py
```

### Step 4: Open in Browser
Once the server is running, open your browser and go to:
[http://127.0.0.1:5000](http://127.0.0.1:5000)

## Features Included
- **Beautiful Glassmorphism UI**: High-end styling without complex frameworks.
- **Secure Authentication**: Passwords hashed with `bcrypt`.
- **Email Verification**: User gets a code (printed to terminal) when signing up.
- **Document Uploads**: Users can upload files that are securely stored on the server under an `uploads/` folder and linked in the MySQL database.
- **Download Capability**: View and download uploaded files securely.
