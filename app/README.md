# Flask Helpdesk Application Deployment to Ubuntu Production Server

This guide provides step-by-step instructions to deploy the Flask helpdesk application to a production Ubuntu server using Gunicorn and Nginx.

## 1. Prerequisites

*   **Ubuntu Server**: A clean Ubuntu server (20.04 LTS or newer recommended).
*   **User with Sudo Privileges**: A non-root user with `sudo` privileges.
*   **Domain Name (Optional but Recommended)**: A domain name pointing to your server's IP address if you want to use SSL.
*   **Git**: Installed on your server (`sudo apt update && sudo apt install git`).
*   **Python 3 and Pip**: Installed on your server.
    ```bash
    sudo apt update
    sudo apt install python3 python3-pip python3-venv -y
    ```
*   **PostgreSQL (Recommended Production Database)**:
    ```bash
    sudo apt install postgresql postgresql-contrib -y
    # Start and enable PostgreSQL
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    ```

## 2. Clone the Repository

Clone your project repository onto the server. Replace `your_username/your_repository.git` with your actual repository URL.

```bash
# Navigate to a suitable directory, e.g., /srv
cd /srv
sudo git clone https://github.com/your_username/your_repository.git helpdesk
cd helpdesk
```
*(If you haven't pushed your code to a repository yet, you'll do this after these setup instructions are complete. For now, you would manually copy your project files to `/srv/helpdesk` on the server).*

## 3. Set Up Python Virtual Environment & Install Dependencies

Create a virtual environment and install the project dependencies.

```bash
# Ensure you are in the project directory (e.g., /srv/helpdesk)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```
*Note: `gunicorn` is included in `requirements.txt`.*

## 4. Configure Production Database (PostgreSQL Example)

1.  **Create a PostgreSQL User and Database**:
    ```bash
    sudo -u postgres psql
    ```
    Inside the PostgreSQL prompt:
    ```sql
    CREATE DATABASE helpdesk_prod;
    CREATE USER helpdesk_user WITH PASSWORD 'your_strong_password';
    ALTER ROLE helpdesk_user SET client_encoding TO 'utf8';
    ALTER ROLE helpdesk_user SET default_transaction_isolation TO 'read committed';
    ALTER ROLE helpdesk_user SET timezone TO 'UTC';
    GRANT ALL PRIVILEGES ON DATABASE helpdesk_prod TO helpdesk_user;
    \q
    ```
    Replace `'your_strong_password'` with a strong, unique password.

2.  Your `config.py`'s `ProductionConfig` already has a placeholder for PostgreSQL:
    ```python
    # In app/config.py
    class ProductionConfig(Config):
        # ...
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'postgresql://username:password@localhost/helpdesk_prod'
        # ...
    ```
    You will set the `DATABASE_URL` environment variable in the next step.

## 5. Set Environment Variables

Your application requires several environment variables for production, as defined in `app/config.py`. These should be set securely on the server. **Do not hardcode them into your application or commit them to version control.**

A common way to manage these is using a `.env` file that Gunicorn can load via the systemd service, or by setting them directly in the systemd service file.

**Required Environment Variables:**

*   `SECRET_KEY`: A long, random, and unique string. Generate one using `python -c 'import secrets; print(secrets.token_hex(32))'`.
*   `DATABASE_URL`: The connection string for your PostgreSQL database.
    Example: `postgresql://helpdesk_user:your_strong_password@localhost/helpdesk_prod`
*   `MAIL_SERVER`: e.g., `smtp.googlemail.com`
*   `MAIL_PORT`: e.g., `587`
*   `MAIL_USE_TLS`: `true` or `false`
*   `MAIL_USERNAME`: Your email username.
*   `MAIL_PASSWORD`: Your email password (or an app-specific password if using Gmail/OAuth).
*   `FLASK_CONFIG`: Set this to `production` to ensure the correct configuration is loaded.

**Method 1: Using an `.env` file (Recommended for Gunicorn/Systemd)**

1.  Create a `.env` file in your project root (`/srv/helpdesk/.env`):
    ```
    SECRET_KEY='your_generated_secret_key'
    DATABASE_URL='postgresql://helpdesk_user:your_strong_password@localhost/helpdesk_prod'
    MAIL_SERVER='smtp.googlemail.com'
    MAIL_PORT='587'
    MAIL_USE_TLS='true'
    MAIL_USERNAME='your_email_username'
    MAIL_PASSWORD='your_email_password'
    FLASK_CONFIG='production'
    # Add any other environment variables your app needs
    ```
2.  **Secure this file**: `sudo chmod 600 /srv/helpdesk/.env` and ensure it's owned by the user running the application.
3.  **Ensure `.env` is in your `.gitignore` file** to prevent committing it.

## 6. Run Database Migrations

With the virtual environment activated and environment variables (especially `DATABASE_URL` and `FLASK_CONFIG`) conceptually set, apply database migrations:

```bash
# Ensure you are in /srv/helpdesk and venv is active
# If not using a .env file loaded by systemd, you might need to export them first:
# export FLASK_CONFIG=production
# export DATABASE_URL='your_database_url'
# ... etc.

flask --app app/__init__.py db upgrade
```
*(The `wsgi.py` file ensures `create_app` is called with `production` for Gunicorn. For Flask CLI commands, `FLASK_CONFIG=production` environment variable is a good way to ensure the production config is loaded by `create_app` if it's designed to check for it, or you can modify `app/__init__.py` to default to production if `FLASK_CONFIG` is set).*

Our `app/__init__.py` uses `config_name='development'` by default in `create_app`. The `wsgi.py` correctly calls `create_app(config_name='production')`. For CLI commands like `flask db upgrade` to use the production config, you should ensure `FLASK_CONFIG=production` is set in the environment where you run the command, and modify `create_app` in `app/__init__.py` to respect it:

```python
# In app/__init__.py
# Modify the create_app signature or logic:
# def create_app(config_name=None):
#     if config_name is None:
#         config_name = os.environ.get('FLASK_CONFIG', 'development')
#     app = Flask(__name__)
#     app.config.from_object(config[config_name])
# ...
```
*(This change to `app/__init__.py` is recommended for consistency).*

## 7. Set Up Gunicorn with Systemd

Create a systemd service file to manage the Gunicorn process. This allows your application to start on boot and be managed like other system services.

1.  Create `/etc/systemd/system/helpdesk.service`:
    ```bash
    sudo nano /etc/systemd/system/helpdesk.service
    ```

2.  Paste the following content, adjusting paths and user as necessary:

    ```ini
    [Unit]
    Description=Gunicorn instance to serve Flask Helpdesk
    After=network.target postgresql.service # Ensure PostgreSQL is up

    [Service]
    User=your_sudo_user # The user that owns the project files and venv
    Group=www-data # Or the group of your_sudo_user
    WorkingDirectory=/srv/helpdesk
    EnvironmentFile=/srv/helpdesk/.env # Path to your .env file (if using)
    ExecStart=/srv/helpdesk/venv/bin/gunicorn --workers 3 --bind unix:helpdesk.sock -m 007 wsgi:application

    [Install]
    WantedBy=multi-user.target
    ```
    *   Replace `your_sudo_user` with the actual username.
    *   If you are not using an `.env` file, you can set `Environment` directives directly in this file (e.g., `Environment="SECRET_KEY=yourvalue"`), but an `.env` file is cleaner.
    *   `--workers 3`: Adjust based on your server's CPU cores (e.g., `2 * num_cores + 1`).
    *   `wsgi:application` points to the `application` object in your `wsgi.py` file.

3.  **Reload systemd, start, and enable the service**:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl start helpdesk
    sudo systemctl enable helpdesk # To start on boot
    ```

4.  **Check the status**:
    ```bash
    sudo systemctl status helpdesk
    # Check for errors:
    sudo journalctl -u helpdesk
    ```
    You should see Gunicorn running and bound to `helpdesk.sock`.

## 8. Set Up Nginx as a Reverse Proxy

Nginx will act as a reverse proxy, forwarding client requests to Gunicorn. It can also serve static files directly and handle SSL termination.

1.  **Install Nginx**:
    ```bash
    sudo apt install nginx -y
    ```

2.  **Create an Nginx server block configuration file**:
    ```bash
    sudo nano /etc/nginx/sites-available/helpdesk
    ```

3.  Paste the following configuration, replacing `your_domain.com` with your server's domain name or IP address:

    ```nginx
    server {
        listen 80;
        server_name your_domain.com www.your_domain.com; # Or your server's IP

        location /static {
            alias /srv/helpdesk/app/static; # Path to your app's static files
        }

        location / {
            proxy_pass http://unix:/srv/helpdesk/helpdesk.sock;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    ```
    *   Adjust `/srv/helpdesk/app/static` if your static files are elsewhere.

4.  **Enable the Nginx configuration by creating a symbolic link**:
    ```bash
    sudo ln -s /etc/nginx/sites-available/helpdesk /etc/nginx/sites-enabled
    ```

5.  **Test Nginx configuration and restart Nginx**:
    ```bash
    sudo nginx -t
    # If successful:
    sudo systemctl restart nginx
    ```

6.  **Adjust Firewall (if using ufw)**:
    ```bash
    sudo ufw allow 'Nginx Full' # Or 'Nginx HTTP' if not using SSL yet
    sudo ufw enable
    sudo ufw status
    ```

## 9. Final Steps and Testing

*   **Access your application**: Open your web browser and navigate to `http://your_domain.com` (or your server's IP address).
*   **Troubleshooting**:
    *   Check Nginx logs: `/var/log/nginx/error.log` and `/var/log/nginx/access.log`.
    *   Check Gunicorn/application logs: `sudo journalctl -u helpdesk`.
    *   Ensure file permissions are correct for Nginx and Gunicorn to access project files and the socket.

## 10. Setting Up SSL with Let's Encrypt (Recommended)

If you have a domain name, secure your site with a free SSL certificate from Let's Encrypt using Certbot.

1.  **Install Certbot**:
    ```bash
    sudo apt install certbot python3-certbot-nginx -y
    ```

2.  **Obtain and install the certificate**:
    ```bash
    sudo certbot --nginx -d your_domain.com -d www.your_domain.com
    ```
    Follow the prompts. Certbot will automatically update your Nginx configuration for SSL and set up auto-renewal.

3.  Your Nginx configuration (`/etc/nginx/sites-available/helpdesk`) will be updated by Certbot to include SSL settings and redirect HTTP to HTTPS.

---

This `README.md` provides a comprehensive guide. Remember to replace placeholders like `your_username`, `your_repository.git`, `your_strong_password`, `your_sudo_user`, and `your_domain.com` with your actual values.