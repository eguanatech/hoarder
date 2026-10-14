# PostgreSQL Setup and Systemd Timer Configuration for s3_injector.py

This guide provides step-by-step instructions for setting up PostgreSQL and configuring a systemd timer to run the `s3_injector.py` script automatically.

## Table of Contents
1. [PostgreSQL Installation and Setup](#postgresql-installation-and-setup)
2. [Database Configuration](#database-configuration)
3. [Django Application Setup](#django-application-setup)
4. [Systemd Service and Timer Configuration](#systemd-service-and-timer-configuration)
5. [Testing and Troubleshooting](#testing-and-troubleshooting)

---

## PostgreSQL Installation and Setup

### Step 1: Install PostgreSQL

#### On Ubuntu/Debian:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib postgresql-15-dev
```

#### On Fedora/CentOS/RHEL:
```bash
sudo dnf install postgresql-server postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### On macOS (using Homebrew):
```bash
brew install postgresql@15
brew services start postgresql@15
```

### Step 2: Verify PostgreSQL Installation
```bash
psql --version
sudo systemctl status postgresql  # On Linux
```

### Step 3: Access PostgreSQL
```bash
# Connect as the default postgres user
sudo -u postgres psql
```

---

## Database Configuration

### Step 1: Create a Database User
```sql
-- Connect to PostgreSQL as postgres user
sudo -u postgres psql

-- Inside the psql prompt:
CREATE USER hoarder WITH PASSWORD 'your_secure_password_here';
ALTER USER hoarder CREATEDB;
```

### Step 2: Create the Database
```sql
CREATE DATABASE hoarder OWNER hoarder;
GRANT ALL PRIVILEGES ON DATABASE hoarder TO hoarder;

-- Optional: Grant schema privileges for future operations
\c hoarder
GRANT ALL PRIVILEGES ON SCHEMA public TO hoarder;

-- Exit psql
\q
```

### Step 3: Verify the Setup
```bash
# Test connection with the new user
psql -U hoarder -d hoarder -h localhost -W
# Enter password when prompted

# Inside psql, you should see: hoarder=>
\q
```

---

## Django Application Setup

### Step 1: Install Python Dependencies
```bash
cd /home/philip/eguana/hoarder
pip install -r requirements.txt
# Or with virtual environment (recommended):
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Create or update a `.env` file or export environment variables:

```bash
# Option 1: Create a .env file (requires python-dotenv package)
cat > /home/philip/eguana/hoarder/.env << 'EOF'
USE_POSTGRES=1
DB_NAME=hoarder
DB_USER=hoarder
DB_PASSWORD=your_secure_password_here
DB_HOST=localhost
DB_PORT=5432
EOF

# Option 2: Export directly (add to ~/.bashrc or ~/.zshrc for persistence)
export USE_POSTGRES=1
export DB_NAME=hoarder
export DB_USER=hoarder
export DB_PASSWORD=your_secure_password_here
export DB_HOST=localhost
export DB_PORT=5432
```

### Step 3: Run Django Migrations
```bash
cd /home/philip/eguana/hoarder/hoarder
export USE_POSTGRES=1
export DB_NAME=hoarder
export DB_USER=hoarder
export DB_PASSWORD=your_secure_password_here
export DB_HOST=localhost
export DB_PORT=5432

python manage.py migrate
```

### Step 4: Verify Database Connection
```bash
python manage.py dbshell
# Should connect to PostgreSQL database
\dt  # List tables
\q
```

---

## Systemd Service and Timer Configuration

### Step 1: Create the Systemd Service File

Create `/etc/systemd/system/s3-injector.service`:

```bash
sudo nano /etc/systemd/system/s3-injector.service
```

Paste the following content (adjust paths as needed):

```ini
[Unit]
Description=S3 Injector Service for Hoarder
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=oneshot
User=philip
Group=philip
WorkingDirectory=/home/philip/eguana/hoarder/hoarder

# Load environment variables
EnvironmentFile=-/home/philip/eguana/hoarder/.env

# Set environment variables for Django
Environment="USE_POSTGRES=1"
Environment="DB_NAME=hoarder"
Environment="DB_USER=hoarder"
Environment="DB_PASSWORD=your_secure_password_here"
Environment="DB_HOST=localhost"
Environment="DB_PORT=5432"
Environment="PYTHONUNBUFFERED=1"

# Activate virtual environment if using one
ExecStart=/bin/bash -c 'source /home/philip/eguana/hoarder/venv/bin/activate && python /home/philip/eguana/hoarder/hoarder/s3_ingestion/s3_injestor.py'

# Standard output/error logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=s3-injector

# Restart policy
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Note:** If not using a virtual environment, change the `ExecStart` line to:
```ini
ExecStart=/usr/bin/python3 /home/philip/eguana/hoarder/hoarder/s3_ingestion/s3_injestor.py
```

### Step 2: Create the Systemd Timer File

Create `/etc/systemd/system/s3-injector.timer`:

```bash
sudo nano /etc/systemd/system/s3-injector.timer
```

Paste the following content:

```ini
[Unit]
Description=S3 Injector Timer for Hoarder
Requires=s3-injector.service

[Timer]
# Run daily at 2 AM
OnCalendar=daily
OnCalendar=*-*-* 02:00:00

# Run every 6 hours
# OnCalendar=*-*-* 00,06,12,18:00:00

# Run every hour at minute 0
# OnCalendar=hourly

# Run every 30 minutes
# OnBootSec=1min
# OnUnitActiveSec=30min

# Randomize start time by up to 5 minutes (prevents thundering herd)
RandomizedDelaySec=5min

# If the timer was missed, run it when the system boots back up
Persistent=true

# The service to run
Unit=s3-injector.service

[Install]
WantedBy=timers.target
```

### Step 3: Load and Enable the Timer

```bash
# Reload systemd daemon to recognize new service and timer
sudo systemctl daemon-reload

# Enable the timer to start automatically on boot
sudo systemctl enable s3-injector.timer

# Start the timer
sudo systemctl start s3-injector.timer

# Verify the timer is active
sudo systemctl status s3-injector.timer

# List all active timers
systemctl list-timers --all
```

---

## Testing and Troubleshooting

### Test the Service Manually
```bash
# Run the service once to test
sudo systemctl start s3-injector.service

# Check the status
sudo systemctl status s3-injector.service

# View the service logs
sudo journalctl -u s3-injector.service -n 50  # Last 50 lines
sudo journalctl -u s3-injector.service -f     # Follow logs in real-time
```

### Check Timer Status
```bash
# View timer status
sudo systemctl status s3-injector.timer

# View when the timer was last triggered and next trigger
systemctl list-timers s3-injector.timer

# View detailed timer information
systemctl show s3-injector.timer
```

### Common Issues and Solutions

#### Issue: Service fails to connect to PostgreSQL
**Solution:**
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check database credentials in environment variables
- Verify network connectivity: `psql -U hoarder -d hoarder -h localhost -W`

#### Issue: Script fails with "ModuleNotFoundError"
**Solution:**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Verify Python version compatibility: `python3 --version`
- Check that the virtual environment path is correct in the service file

#### Issue: Permission denied when running service
**Solution:**
- Verify the user specified in the service file has access to the script and database
- Check file permissions: `ls -la /home/philip/eguana/hoarder/`
- Ensure AWS credentials are accessible if using S3 access

#### Issue: Timer not running automatically
**Solution:**
- Verify timer is enabled: `sudo systemctl is-enabled s3-injector.timer`
- Check system time is correct: `date`
- Review timer configuration: `sudo systemctl show s3-injector.timer`
- Check systemd logs: `sudo journalctl -u s3-injector.timer`

### View Service and Timer Logs
```bash
# Last 100 lines of service logs
sudo journalctl -u s3-injector.service -n 100

# Logs from the last hour
sudo journalctl -u s3-injector.service --since "1 hour ago"

# Follow logs in real-time
sudo journalctl -u s3-injector.service -f

# View timer trigger history
sudo journalctl -u s3-injector.timer -n 20
```

---

## Timer Schedule Examples

### Common OnCalendar Patterns

```ini
# Daily at specific time
OnCalendar=daily
OnCalendar=*-*-* 02:00:00

# Every hour
OnCalendar=hourly

# Every 30 minutes
OnBootSec=1min
OnUnitActiveSec=30min

# Weekly (Monday at 2 AM)
OnCalendar=Mon *-*-* 02:00:00

# Twice a day (2 AM and 2 PM)
OnCalendar=*-*-* 02,14:00:00

# Every 6 hours
OnCalendar=*-*-* 00,06,12,18:00:00
```

---

## Production Best Practices

1. **Use Environment Files:** Store sensitive credentials in `/etc/hoarder/s3-injector.env` and load with `EnvironmentFile=`
2. **Restrict Permissions:** Limit read access to credential files:
   ```bash
   sudo chmod 600 /etc/hoarder/s3-injector.env
   sudo chown root:root /etc/hoarder/s3-injector.env
   ```
3. **Monitor Logs:** Set up log rotation for high-frequency timers
4. **Database Backups:** Schedule PostgreSQL backups separately with another timer
5. **Error Notifications:** Add email alerts on service failure:
   ```ini
   OnFailure=send-email@%n.service
   ```
6. **Resource Limits:** Add to service file to prevent resource exhaustion:
   ```ini
   MemoryMax=512M
   CPUQuota=50%
   ```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start the timer | `sudo systemctl start s3-injector.timer` |
| Stop the timer | `sudo systemctl stop s3-injector.timer` |
| Restart the timer | `sudo systemctl restart s3-injector.timer` |
| Enable auto-start | `sudo systemctl enable s3-injector.timer` |
| Disable auto-start | `sudo systemctl disable s3-injector.timer` |
| View timer status | `sudo systemctl status s3-injector.timer` |
| Run service manually | `sudo systemctl start s3-injector.service` |
| View recent logs | `sudo journalctl -u s3-injector.service -n 50` |
| Follow logs live | `sudo journalctl -u s3-injector.service -f` |
| List all timers | `systemctl list-timers --all` |

---

## Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Systemd Timer Documentation](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)
- [Django Database Configuration](https://docs.djangoproject.com/en/5.2/ref/settings/#databases)
- [Systemd Service Files](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
