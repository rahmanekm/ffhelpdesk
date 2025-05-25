# Forefront IT Helpdesk

A comprehensive internal IT helpdesk ticketing application built with Flask and MySQL.

## Features

- User authentication and authorization
- Ticket submission with file attachments
- Ticket management and tracking
- Internal notes and comments
- Email notifications
- Role-based access control
- Responsive web interface

## Requirements

- Python 3.8+
- MySQL 5.7+
- pip (Python package manager)
- Gunicorn (for production)
- Nginx (recommended for production)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/rahmanekm/helpdesk.git
cd helpdesk
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
. .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

### Development Mode
For development purposes, you can use Flask's built-in development server:
```bash
flask run
```
The application will be available at `http://localhost:5000`

### Production Mode
For production deployment, it's recommended to use Gunicorn with Nginx:

1. Install Gunicorn:
```bash
pip install gunicorn
```

2. Run with Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

3. Configure Nginx as a reverse proxy (recommended for production):
```nginx
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Restarting the Application

How you restart the application depends on how it's being run:

*   **Development Mode (`flask run`):**
    1.  Stop the running Flask development server by pressing `Ctrl+C` in the terminal where it's running.
    2.  Restart it by running the command again:
        ```bash
        flask run
        ```

*   **Production Mode (Direct Gunicorn):**
    If you started Gunicorn directly using the command `gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app`:
    1.  Find the Gunicorn process ID (PID). You can use commands like `pgrep gunicorn` or `ps aux | grep gunicorn`.
    2.  Stop the process using its PID. A graceful stop is preferred: `kill -HUP <PID>` (sends SIGHUP to reload workers) or `kill <PID>` (sends SIGTERM).
    3.  Restart Gunicorn using the same command:
        ```bash
        gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
        ```

*   **Production Mode (Process Manager like systemd/supervisor):**
    If you have configured Gunicorn to run as a service using `systemd`, `supervisor`, or a similar tool (which is the recommended approach for robust production deployments), use the service manager's commands to restart. For example, with `systemd`:
100|     ```bash
101|     sudo systemctl restart your_gunicorn_service_name
102|     ```
103|     Replace `your_gunicorn_service_name` with the actual name of the service you configured.
104|
105| *   **Nginx:**
106|     Restarting Gunicorn (the application server) is usually sufficient for application code changes. You typically only need to restart Nginx (`sudo systemctl restart nginx`) if you change the Nginx configuration itself.

## Environment Variables
Create a `.env` file in the root directory with the following variables:
```
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=your-secret-key
DATABASE_URL=mysql://username:password@localhost/helpdesk
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_email_password
```

## MySQL 5.7 Installation (Ubuntu)

These steps guide you through installing MySQL Server 5.7 on an Ubuntu server (tested on Ubuntu 18.04/20.04).

1.  **Update Package List:**
    Ensure your package list is up-to-date.
    ```bash
    sudo apt update
    ```

2.  **Install MySQL Server 5.7:**
    Install the `mysql-server-5.7` package.
    ```bash
    sudo apt install mysql-server-5.7 -y
    ```
    The server should start automatically after installation.

3.  **Check MySQL Service Status:**
    Verify that the MySQL service is running.
    ```bash
    sudo systemctl status mysql
    ```
    You should see output indicating the service is active (running). Press `q` to exit the status view.

4.  **Secure MySQL Installation:**
    Run the security script that comes with MySQL. This script helps you secure your installation by setting the root password, removing anonymous users, disallowing remote root login, and removing the test database.
    ```bash
    sudo mysql_secure_installation
    ```
    *   You will be asked if you want to use the **VALIDATE PASSWORD PLUGIN**. It's generally recommended for production environments (choose 'Y' or 'y'). If enabled, choose a password strength level (0, 1, or 2).
    *   Set a strong password for the MySQL `root` user when prompted. **Remember this password!**
    *   Answer 'Y' or 'y' to the subsequent security questions (remove anonymous users, disallow remote root login, remove test database, reload privilege tables).

5.  **Test MySQL Login:**
    Log in to the MySQL console as the root user.
    ```bash
    sudo mysql -u root -p
    ```
    Enter the root password you set during the `mysql_secure_installation` step. If you successfully log in and see the `mysql>` prompt, the installation is complete and secure. Type `exit;` to quit.

6.  **(Optional) Allow Remote Connections:**
    By default, MySQL 5.7 on Ubuntu might only listen on `127.0.0.1` (localhost). If your application server is different from your database server, you need to configure MySQL to accept remote connections.
    *   Edit the MySQL configuration file. The location might vary slightly, but it's often `/etc/mysql/mysql.conf.d/mysqld.cnf` or `/etc/mysql/my.cnf`.
        ```bash
        sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf
        ```
    *   Find the line `bind-address = 127.0.0.1`.
    *   Comment it out by adding a `#` at the beginning (`#bind-address = 127.0.0.1`) or change `127.0.0.1` to `0.0.0.0` to listen on all available network interfaces. **Be aware of the security implications of listening on all interfaces.** Consider binding to a specific private IP address if possible.
    *   Save the file (Ctrl+O in nano, then Enter) and exit (Ctrl+X).
    *   Restart the MySQL service:
        ```bash
        sudo systemctl restart mysql
        ```
    *   You will also need to grant privileges to your application user to connect from the specific remote host or from any host (`%`). Example:
        ```sql
        -- Log in to MySQL first: sudo mysql -u root -p
        GRANT ALL PRIVILEGES ON your_database_name.* TO 'your_app_user'@'your_app_server_ip' IDENTIFIED BY 'your_app_user_password';
        FLUSH PRIVILEGES;
        EXIT;
        ```
        Replace `your_database_name`, `your_app_user`, `your_app_server_ip`, and `your_app_user_password` with your actual values. Use `'%'` instead of `'your_app_server_ip'` to allow connections from any host (less secure).

MySQL Server 5.7 should now be installed and configured on your Ubuntu server.

## Database Setup

After installing MySQL, you need to create the database and a dedicated user for the helpdesk application.

1.  **Log in to MySQL as root:**
    Use the root password you set during `mysql_secure_installation`.
    ```bash
    sudo mysql -u root -p
    ```

2.  **Create the database:**
    Replace `helpdesk_db` with your desired database name if different.
    ```sql
    CREATE DATABASE helpdesk_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    ```

3.  **Create a dedicated user:**
    Replace `helpdesk_user` and `your_strong_password` with a secure username and password for your application. Using `'localhost'` restricts this user to connecting only from the same machine where MySQL is running. If your application runs on a different server, replace `'localhost'` with the specific IP address of your application server (e.g., `'192.168.1.100'`) or `'%'` to allow connections from any host (less secure).
    ```sql
    CREATE USER 'helpdesk_user'@'localhost' IDENTIFIED BY 'your_strong_password';
    ```

4.  **Grant privileges to the user:**
    Give the newly created user the necessary permissions on the database.
    ```sql
    GRANT ALL PRIVILEGES ON helpdesk_db.* TO 'helpdesk_user'@'localhost';
    ```

5.  **Apply the changes:**
    Reload the grant tables for the changes to take effect.
    ```sql
    FLUSH PRIVILEGES;
    ```

6.  **Exit MySQL:**
    ```sql
    EXIT;
    ```

7.  **Update Environment Variables:**
    Make sure your `.env` file (or environment variables) reflects the database name, username, and password you just created. Specifically, update the `DATABASE_URL`:
    ```
    DATABASE_URL=mysql+pymysql://helpdesk_user:your_strong_password@localhost/helpdesk_db
    ```
    *(Note: `pymysql` is often used as the DBAPI driver with Flask/SQLAlchemy for MySQL. Ensure it's listed in your `requirements.txt` and installed.)*

Your database should now be set up and ready for the application. You might need to run database migrations if the application uses a tool like Flask-Migrate or Alembic. Refer to the application's specific documentation for migration steps.

## Database Migrations (Flask-Migrate)

This application uses Flask-Migrate to manage database schema changes. This is crucial for keeping your database structure in sync with your application's models (like the `User` model).

**Workflow Overview:**

1.  **Development:** When you change a model in your code (e.g., add a new field like `organization` to the `User` model), you generate a new migration script:
    ```bash
    # (In your development environment, after activating the venv)
    flask db migrate -m "Add organization column to users table"
    ```
    This creates a new file in the `migrations/versions/` directory containing the necessary database changes (e.g., `ALTER TABLE users ADD COLUMN organization ...`). You commit this new migration file to your Git repository along with your code changes.

2.  **Production Deployment:** When you deploy updated code (including new migration files) to your production server:
    *   Pull the latest code (`git pull`).
    *   Install/update dependencies (`pip install -r requirements.txt`).
    *   **Apply the migrations to the production database:** This updates the database schema to match the models in the newly deployed code.
        ```bash
        # (On the production server, after activating the venv)
        flask db upgrade
        ```

**Troubleshooting Errors like "Unknown column":**

The error `(1054, "Unknown column 'users.organization' in 'field list'")` means your code expects the `organization` column, but it hasn't been added to the database table yet. This typically occurs if you deployed code changes without running `flask db upgrade` afterwards.

**Solution:**

1.  **Ensure your virtual environment is activated on the production server:**
    ```bash
    # On Linux/macOS:
    source /path/to/your/project/.venv/bin/activate
    # Replace /path/to/your/project/ with the actual path
    ```

2.  **Run the upgrade command:**
    Navigate to your project's root directory on the server and run:
    ```bash
    flask db upgrade
    ```

This command will execute any pending migration scripts found in the `migrations/versions/` directory, including the one that should add the `organization` column, resolving the error. If the error persists after running `upgrade`, it might indicate that the necessary migration script was not generated during development or not included in the deployment.

## Initial Table Creation (Alternative Script)

**Warning:** This method bypasses the Flask-Migrate versioning system and is **not recommended** for managing production databases if you intend to use migrations for updates. It uses SQLAlchemy's `db.create_all()` function, which creates tables based *only* on the current state of your models and **cannot** handle schema updates (like adding columns to existing tables). Use this script **only** for initial setup on a completely empty database or in specific recovery scenarios where the migration history is unusable. The standard `flask db upgrade` command (described in the "Database Migrations" section) is the preferred method for creating and updating your database schema in production.

If you choose to proceed with this alternative script:

1.  **Ensure your `.env` file exists** in the project root and the `DATABASE_URL` is correctly configured for your production database.
2.  **Activate your virtual environment** on the production server:
    ```bash
    # On Linux/macOS:
    source /path/to/your/project/.venv/bin/activate
    # Replace /path/to/your/project/ with the actual path
    ```
3.  **Run the script:**
    Navigate to the project root directory and execute the script using Python:
    ```bash
    python create_tables.py
    ```
4.  **Confirm Execution:** The script will ask for confirmation before proceeding. Type `yes` to continue.

If the script runs successfully, it will create all tables defined in your application's models in the specified database. Remember, any future model changes will require manual database alterations or switching back to using `flask db migrate` and `flask db upgrade`.
