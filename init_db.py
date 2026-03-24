import mysql.connector
from mysql.connector import Error

def init_db():
    try:
        # Connect to MySQL server (without specifying a database yet)
        print("Connecting to MySQL... Make sure your MySQL server is running!")
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root" # Change this if your MySQL root has a password (e.g., "root")
        )
        
        if conn.is_connected():
            cursor = conn.cursor()
            
            # Create the database
            cursor.execute("CREATE DATABASE IF NOT EXISTS digilocker_clone_db")
            print("Database 'digilocker_clone_db' created or already exists.")
            
            # Switch to the new database
            cursor.execute("USE digilocker_clone_db")
            
            # Create users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                verification_code VARCHAR(10)
            )
            """)
            print("Table 'users' created or already exists.")
            
            # Create documents table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                filename VARCHAR(255) NOT NULL,
                filepath VARCHAR(255) NOT NULL,
                upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """)
            print("Table 'documents' created or already exists.")
            
            conn.commit()
            print("Database initialization successful!")
            
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        print("\nPlease make sure MySQL is installed, running, and the credentials (user='root', password='') are correct in init_db.py.")
        
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            print("MySQL connection closed.")

if __name__ == "__main__":
    init_db()
