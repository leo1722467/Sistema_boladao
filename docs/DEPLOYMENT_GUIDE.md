# Sistema Boladão - Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Configuration](#database-configuration)
4. [Application Configuration](#application-configuration)
5. [Security Configuration](#security-configuration)
6. [Performance Optimization](#performance-optimization)
7. [Monitoring and Logging](#monitoring-and-logging)
8. [Backup and Recovery](#backup-and-recovery)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

**Minimum Requirements:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 20GB SSD
- OS: Ubuntu 20.04+ / CentOS 8+ / Windows Server 2019+

**Recommended Requirements:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 50GB+ SSD
- OS: Ubuntu 22.04 LTS

### Software Dependencies

- Python 3.9+
- PostgreSQL 13+ or SQLite (for development)
- Redis 6+ (optional, for caching)
- Nginx (for reverse proxy)
- SSL Certificate (for HTTPS)

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/sistema-boladao.git
cd sistema-boladao
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

Create `.env` file in the project root:

```env
# Application Settings
APP_NAME=Sistema Boladão
APP_VERSION=1.0.0
DEBUG=false
ENVIRONMENT=production

# Security
SECRET_KEY=your-super-secret-key-here-change-this
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/sistema_boladao
# or for SQLite:
# DATABASE_URL=sqlite+aiosqlite:///./app.db

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# CORS
ALLOWED_ORIGINS=["https://yourdomain.com", "https://app.yourdomain.com"]
ALLOWED_HOSTS=["yourdomain.com", "app.yourdomain.com"]

# Email (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com

# External Integrations
WHATSAPP_API_URL=https://graph.facebook.com/v17.0
WHATSAPP_ACCESS_TOKEN=your-whatsapp-token
AI_API_URL=https://api.openai.com/v1
AI_API_KEY=your-openai-api-key

# File Storage
UPLOAD_DIR=/var/uploads/sistema-boladao
MAX_UPLOAD_SIZE=10485760  # 10MB

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/sistema-boladao/app.log
```

## Database Configuration

### PostgreSQL Setup (Recommended for Production)

#### 1. Install PostgreSQL

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# CentOS/RHEL
sudo dnf install postgresql postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

#### 2. Create Database and User

```sql
-- Connect as postgres user
sudo -u postgres psql

-- Create database
CREATE DATABASE sistema_boladao;

-- Create user
CREATE USER sistema_user WITH PASSWORD 'secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE sistema_boladao TO sistema_user;

-- Exit
\q
```

#### 3. Configure PostgreSQL

Edit `/etc/postgresql/13/main/postgresql.conf`:

```conf
# Connection settings
listen_addresses = 'localhost'
port = 5432
max_connections = 100

# Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_statement = 'all'
log_min_duration_statement = 1000
```

Edit `/etc/postgresql/13/main/pg_hba.conf`:

```conf
# Allow local connections
local   all             all                                     peer
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

### Database Migration

```bash
# Run migrations
alembic upgrade head

# Verify migration
alembic current
```

## Application Configuration

### 1. Create Systemd Service

Create `/etc/systemd/system/sistema-boladao.service`:

```ini
[Unit]
Description=Sistema Boladao FastAPI Application
After=network.target postgresql.service

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/opt/sistema-boladao
Environment=PATH=/opt/sistema-boladao/venv/bin
ExecStart=/opt/sistema-boladao/venv/bin/python -m app.main
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable sistema-boladao
sudo systemctl start sistema-boladao
sudo systemctl status sistema-boladao
```

### 3. Nginx Configuration

Create `/etc/nginx/sites-available/sistema-boladao`:

```nginx
upstream sistema_boladao {
    server 127.0.0.1:8081;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Gzip Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

    # Main Application
    location / {
        proxy_pass http://sistema_boladao;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # API Rate Limiting
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://sistema_boladao;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Auth Rate Limiting
    location /auth/ {
        limit_req zone=auth burst=10 nodelay;
        proxy_pass http://sistema_boladao;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static Files
    location /static/ {
        alias /opt/sistema-boladao/app/web/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health Check
    location /health {
        access_log off;
        proxy_pass http://sistema_boladao;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/sistema-boladao /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Security Configuration

### 1. SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 2. Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw deny 8081  # Block direct access to app

# Or iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8081 -s 127.0.0.1 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8081 -j DROP
```

### 3. Application Security

Update `.env` with production values:

```env
# Strong secrets (use: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=your-generated-secret-key
JWT_SECRET_KEY=your-generated-jwt-secret

# Disable debug
DEBUG=false

# Restrict CORS
ALLOWED_ORIGINS=["https://yourdomain.com"]
ALLOWED_HOSTS=["yourdomain.com"]
```

### 4. Database Security

```sql
-- Create read-only user for monitoring
CREATE USER monitoring WITH PASSWORD 'monitoring_password';
GRANT CONNECT ON DATABASE sistema_boladao TO monitoring;
GRANT USAGE ON SCHEMA public TO monitoring;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO monitoring;

-- Revoke unnecessary privileges
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO sistema_user;
```

## Performance Optimization

### 1. Redis Caching

Install and configure Redis:

```bash
# Install Redis
sudo apt install redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf
```

Redis configuration:

```conf
# Memory
maxmemory 512mb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000

# Security
requirepass your-redis-password
```

### 2. Database Optimization

PostgreSQL tuning:

```sql
-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_chamado_empresa_status ON chamado(empresa_id, status);
CREATE INDEX CONCURRENTLY idx_ativo_empresa_tag ON ativo(empresa_id, tag);
CREATE INDEX CONCURRENTLY idx_ordem_servico_chamado ON ordem_servico(chamado_id);
CREATE INDEX CONCURRENTLY idx_outbox_events_status ON outbox_events(status, created_at);

-- Analyze tables
ANALYZE;
```

### 3. Application Optimization

Enable caching in application:

```python
# In app/main.py
from app.core.cache import initialize_cache

@app.on_event("startup")
async def startup_event():
    await initialize_cache()
```

### 4. Monitoring Setup

Install monitoring tools:

```bash
# Prometheus Node Exporter
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz
tar xvfz node_exporter-1.6.1.linux-amd64.tar.gz
sudo mv node_exporter-1.6.1.linux-amd64/node_exporter /usr/local/bin/
```

Create systemd service for node_exporter:

```ini
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
```

## Monitoring and Logging

### 1. Application Logging

Configure structured logging:

```python
# In app/core/logging.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        return json.dumps(log_entry)
```

### 2. Log Rotation

Configure logrotate:

```bash
sudo nano /etc/logrotate.d/sistema-boladao
```

```conf
/var/log/sistema-boladao/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload sistema-boladao
    endscript
}
```

### 3. Health Monitoring

Create health check script:

```bash
#!/bin/bash
# /usr/local/bin/health-check.sh

HEALTH_URL="https://yourdomain.com/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "$(date): Health check passed"
    exit 0
else
    echo "$(date): Health check failed with status $RESPONSE"
    # Send alert
    systemctl restart sistema-boladao
    exit 1
fi
```

Add to crontab:

```bash
# Check every 5 minutes
*/5 * * * * /usr/local/bin/health-check.sh >> /var/log/health-check.log 2>&1
```

## Backup and Recovery

### 1. Database Backup

Create backup script:

```bash
#!/bin/bash
# /usr/local/bin/backup-db.sh

BACKUP_DIR="/var/backups/sistema-boladao"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="sistema_boladao"
DB_USER="sistema_user"

mkdir -p $BACKUP_DIR

# Create backup
pg_dump -h localhost -U $DB_USER -d $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: backup_$DATE.sql.gz"
```

Schedule daily backups:

```bash
# Add to crontab
0 2 * * * /usr/local/bin/backup-db.sh >> /var/log/backup.log 2>&1
```

### 2. Application Backup

```bash
#!/bin/bash
# /usr/local/bin/backup-app.sh

BACKUP_DIR="/var/backups/sistema-boladao"
DATE=$(date +%Y%m%d_%H%M%S)
APP_DIR="/opt/sistema-boladao"

# Backup configuration and uploads
tar -czf $BACKUP_DIR/app_config_$DATE.tar.gz \
    $APP_DIR/.env \
    $APP_DIR/uploads/ \
    /etc/nginx/sites-available/sistema-boladao \
    /etc/systemd/system/sistema-boladao.service

echo "Application backup completed: app_config_$DATE.tar.gz"
```

### 3. Recovery Procedures

Database recovery:

```bash
# Stop application
sudo systemctl stop sistema-boladao

# Restore database
gunzip -c /var/backups/sistema-boladao/backup_YYYYMMDD_HHMMSS.sql.gz | psql -h localhost -U sistema_user -d sistema_boladao

# Start application
sudo systemctl start sistema-boladao
```

## Troubleshooting

### Common Issues

#### Application Won't Start

```bash
# Check service status
sudo systemctl status sistema-boladao

# Check logs
sudo journalctl -u sistema-boladao -f

# Check application logs
tail -f /var/log/sistema-boladao/app.log

# Check configuration
python -c "from app.core.config import get_settings; print(get_settings())"
```

#### Database Connection Issues

```bash
# Test database connection
psql -h localhost -U sistema_user -d sistema_boladao -c "SELECT 1;"

# Check PostgreSQL status
sudo systemctl status postgresql

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-13-main.log
```

#### High Memory Usage

```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head

# Check application memory
sudo systemctl status sistema-boladao
```

#### SSL Certificate Issues

```bash
# Check certificate validity
openssl x509 -in /etc/letsencrypt/live/yourdomain.com/fullchain.pem -text -noout

# Test SSL configuration
openssl s_client -connect yourdomain.com:443

# Renew certificate
sudo certbot renew --dry-run
```

### Performance Issues

#### Slow Database Queries

```sql
-- Enable query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();

-- Check slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

#### High CPU Usage

```bash
# Check CPU usage
top -p $(pgrep -f "python -m app.main")

# Profile application
py-spy top --pid $(pgrep -f "python -m app.main")
```

### Maintenance Tasks

#### Weekly Maintenance

```bash
#!/bin/bash
# /usr/local/bin/weekly-maintenance.sh

# Update system packages
sudo apt update && sudo apt upgrade -y

# Vacuum database
sudo -u postgres psql -d sistema_boladao -c "VACUUM ANALYZE;"

# Clean old logs
find /var/log/sistema-boladao -name "*.log" -mtime +7 -delete

# Restart services
sudo systemctl restart sistema-boladao
sudo systemctl restart nginx

echo "Weekly maintenance completed"
```

#### Monthly Maintenance

```bash
#!/bin/bash
# /usr/local/bin/monthly-maintenance.sh

# Full database vacuum
sudo -u postgres psql -d sistema_boladao -c "VACUUM FULL;"

# Update statistics
sudo -u postgres psql -d sistema_boladao -c "ANALYZE;"

# Check disk usage
df -h

# Generate security report
curl -H "Authorization: Bearer $ADMIN_TOKEN" https://yourdomain.com/api/security/report

echo "Monthly maintenance completed"
```

This deployment guide provides comprehensive instructions for setting up Sistema Boladão in a production environment with proper security, monitoring, and maintenance procedures.