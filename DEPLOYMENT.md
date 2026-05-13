# Deployment Guide

This guide covers deploying Tax Buddy in various environments, from local development to production.

## Table of Contents

- [Quick Start](#quick-start)
- [Docker Deployment](#docker-deployment)
- [Podman Deployment](#podman-deployment)
- [Production Deployment](#production-deployment)
- [Environment Variables](#environment-variables)
- [Security Best Practices](#security-best-practices)
- [Scaling Guidelines](#scaling-guidelines)
- [Monitoring and Logging](#monitoring-and-logging)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Local Development

**Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Access:**
- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

---

## Docker Deployment

### Development with Docker Compose

```bash
# Clone repository
git clone https://github.com/BackBenchDreamer/tax-buddy.git
cd tax-buddy

# Set environment variables
export GROQ_API_KEY=your_key_here

# Start services
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Production Docker Build

```bash
# Build production image
docker build -t tax-buddy:latest .

# Run container
docker run -d \
  --name tax-buddy \
  -p 8000:8000 \
  -v $(pwd)/backend/data:/app/data \
  -v $(pwd)/backend/logs:/app/logs \
  -e DEBUG=false \
  -e GROQ_API_KEY=your_production_key \
  -e DATABASE_URL=sqlite:///./data/taxbuddy.db \
  --restart unless-stopped \
  tax-buddy:latest

# Check logs
docker logs -f tax-buddy

# Stop container
docker stop tax-buddy

# Remove container
docker rm tax-buddy
```

### Multi-stage Build (Optimized)

The Dockerfile uses multi-stage builds for optimization:

```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim as builder
# Install build dependencies
# Create wheel files

# Stage 2: Runtime
FROM python:3.11-slim
# Copy only necessary files
# Install runtime dependencies
# Run as non-root user
```

---

## Podman Deployment

### Development with Podman Compose

```bash
# Clone repository
git clone https://github.com/BackBenchDreamer/tax-buddy.git
cd tax-buddy

# Set environment variables
export GROQ_API_KEY=your_key_here

# Start services
podman-compose up --build

# Run in background
podman-compose up -d --build

# View logs
podman-compose logs -f

# Stop services
podman-compose down
```

### Clean Rebuild with Podman

Use the provided script for a complete clean rebuild:

```bash
# Make script executable
chmod +x rebuild-podman.sh

# Run rebuild script
./rebuild-podman.sh
```

The script performs:
1. Stops all running containers
2. Removes all containers
3. Removes all tax-buddy images
4. Cleans up dangling images
5. Prunes system cache
6. Rebuilds from scratch
7. Starts fresh containers
8. Shows logs

### Production Podman Build

```bash
# Build production image
podman build -t tax-buddy:latest .

# Run container
podman run -d \
  --name tax-buddy \
  -p 8000:8000 \
  -v $(pwd)/backend/data:/app/data:Z \
  -v $(pwd)/backend/logs:/app/logs:Z \
  -e DEBUG=false \
  -e GROQ_API_KEY=your_production_key \
  --restart unless-stopped \
  tax-buddy:latest

# Check logs
podman logs -f tax-buddy

# Generate systemd service
podman generate systemd --new --name tax-buddy > /etc/systemd/system/tax-buddy.service
systemctl enable tax-buddy
systemctl start tax-buddy
```

---

## Production Deployment

### Prerequisites

- Linux server (Ubuntu 20.04+ or RHEL 8+)
- 2+ CPU cores
- 4GB+ RAM
- 20GB+ disk space
- Docker or Podman installed
- Nginx or Traefik for reverse proxy
- SSL certificate (Let's Encrypt recommended)

### Production Environment Setup

#### 1. System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
  tesseract-ocr \
  tesseract-ocr-eng \
  poppler-utils \
  nginx \
  certbot \
  python3-certbot-nginx

# Install Docker (if not using Podman)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Or install Podman
sudo apt install -y podman podman-compose
```

#### 2. Application Setup

```bash
# Create application directory
sudo mkdir -p /opt/tax-buddy
cd /opt/tax-buddy

# Clone repository
git clone https://github.com/BackBenchDreamer/tax-buddy.git .

# Create production .env file
cat > backend/.env << EOF
PROJECT_NAME="Tax Buddy Production"
API_V1_STR=/api/v1
DEBUG=false

# Database
DATABASE_URL=sqlite:///./data/taxbuddy.db
UPLOAD_DIR=data/uploads

# OCR
OCR_CONFIDENCE_THRESHOLD=0.80
OCR_DPI=200

# NER
NER_USE_TRANSFORMER=false
NER_CONFIDENCE_THRESHOLD=0.70

# Tax
DEFAULT_TAX_REGIME=old

# Groq API
GROQ_API_KEY=your_production_key_here
GROQ_MODEL=llama3-70b-8192
GROQ_TIMEOUT=30

# Security
ALLOWED_ORIGINS=https://yourdomain.com
EOF

# Set proper permissions
sudo chown -R $USER:$USER /opt/tax-buddy
chmod 600 backend/.env
```

#### 3. Build and Run

```bash
# Build production image
docker-compose -f docker-compose.yml build

# Start services
docker-compose up -d

# Verify services are running
docker-compose ps
```

#### 4. Nginx Reverse Proxy

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/tax-buddy

# Add configuration:
server {
    listen 80;
    server_name yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeouts for large file uploads
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        client_max_body_size 50M;
    }

    # API Documentation
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_set_header Host $host;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/tax-buddy /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

#### 5. SSL Certificate

```bash
# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is configured by default
# Test renewal
sudo certbot renew --dry-run
```

#### 6. Systemd Service (Optional)

```bash
# Create systemd service
sudo nano /etc/systemd/system/tax-buddy.service

# Add configuration:
[Unit]
Description=Tax Buddy Application
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/tax-buddy
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target

# Enable and start service
sudo systemctl enable tax-buddy
sudo systemctl start tax-buddy
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key for AI features | `gsk_...` |
| `DATABASE_URL` | Database connection string | `sqlite:///./data/taxbuddy.db` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode |
| `PROJECT_NAME` | `AI Tax Filing System` | Application name |
| `API_V1_STR` | `/api/v1` | API prefix |
| `UPLOAD_DIR` | `data/uploads` | Upload directory |
| `OCR_CONFIDENCE_THRESHOLD` | `0.70` | OCR confidence threshold |
| `OCR_DPI` | `200` | OCR DPI setting |
| `NER_USE_TRANSFORMER` | `false` | Use transformer for NER |
| `NER_CONFIDENCE_THRESHOLD` | `0.60` | NER confidence threshold |
| `DEFAULT_TAX_REGIME` | `old` | Default tax regime |
| `GROQ_MODEL` | `llama3-70b-8192` | Groq model to use |
| `GROQ_TIMEOUT` | `30` | Groq API timeout (seconds) |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins |

### Production Recommendations

```bash
# Production .env
DEBUG=false
OCR_CONFIDENCE_THRESHOLD=0.80
NER_CONFIDENCE_THRESHOLD=0.70
GROQ_TIMEOUT=30
ALLOWED_ORIGINS=https://yourdomain.com
```

---

## Security Best Practices

### 1. Environment Variables

- Never commit `.env` files to version control
- Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- Rotate API keys regularly
- Use different keys for dev/staging/production

### 2. Network Security

- Use HTTPS only in production
- Configure firewall (UFW, iptables)
- Restrict access to backend port (8000)
- Use VPN for administrative access

```bash
# Configure UFW
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 3. Container Security

- Run containers as non-root user (already configured)
- Use read-only file systems where possible
- Limit container resources
- Scan images for vulnerabilities

```bash
# Scan Docker image
docker scan tax-buddy:latest

# Run with resource limits
docker run -d \
  --memory="2g" \
  --cpus="2" \
  --read-only \
  --tmpfs /tmp \
  tax-buddy:latest
```

### 4. Database Security

- Use PostgreSQL for production (not SQLite)
- Enable SSL for database connections
- Regular backups
- Restrict database access

### 5. File Upload Security

- Validate file types
- Scan uploads for malware
- Limit file sizes
- Store uploads outside web root

---

## Scaling Guidelines

### Horizontal Scaling

```yaml
# docker-compose.yml for scaling
version: '3.8'

services:
  backend:
    image: tax-buddy:latest
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 2G
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/taxbuddy
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
```

### Load Balancing

Use Nginx or HAProxy for load balancing:

```nginx
upstream backend {
    least_conn;
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}

server {
    location /api/ {
        proxy_pass http://backend;
    }
}
```

### Database Scaling

For production, use PostgreSQL:

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb taxbuddy
sudo -u postgres createuser taxbuddy_user

# Update DATABASE_URL
DATABASE_URL=postgresql://taxbuddy_user:password@localhost:5432/taxbuddy
```

---

## Monitoring and Logging

### Application Logs

```bash
# View Docker logs
docker-compose logs -f backend

# View specific service
docker logs -f tax-buddy-backend-1

# Save logs to file
docker-compose logs > logs/app.log
```

### System Monitoring

```bash
# Install monitoring tools
sudo apt install htop iotop nethogs

# Monitor resources
htop
docker stats
```

### Log Rotation

```bash
# Configure logrotate
sudo nano /etc/logrotate.d/tax-buddy

# Add configuration:
/opt/tax-buddy/backend/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        docker-compose -f /opt/tax-buddy/docker-compose.yml restart backend
    endscript
}
```

### Health Checks

```bash
# Check backend health
curl http://localhost:8000/api/v1/system/health

# Automated health check script
#!/bin/bash
HEALTH_URL="http://localhost:8000/api/v1/system/health"
if curl -f -s $HEALTH_URL > /dev/null; then
    echo "Service is healthy"
else
    echo "Service is down!"
    # Send alert
fi
```

---

## Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Find process using port
sudo lsof -i :8000
sudo lsof -i :3000

# Kill process
sudo kill -9 <PID>
```

#### Container Won't Start

```bash
# Check logs
docker-compose logs backend

# Rebuild without cache
docker-compose build --no-cache

# Remove volumes and rebuild
docker-compose down -v
docker-compose up --build
```

#### Database Errors

```bash
# Reset database
rm backend/data/taxbuddy.db*
docker-compose restart backend
```

#### OCR Not Working

```bash
# Verify Tesseract installation
tesseract --version

# Check PaddleOCR
docker-compose exec backend python -c "from paddleocr import PaddleOCR; print('OK')"

# View OCR logs
docker-compose logs backend | grep OCR
```

#### High Memory Usage

```bash
# Check memory usage
docker stats

# Limit container memory
docker update --memory="2g" tax-buddy-backend-1

# Or in docker-compose.yml:
services:
  backend:
    mem_limit: 2g
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Set in .env
DEBUG=true

# Restart services
docker-compose restart
```

### Performance Issues

```bash
# Check system resources
htop
df -h
free -h

# Optimize database
docker-compose exec backend python -c "
from app.core.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text('VACUUM'))
    conn.execute(text('ANALYZE'))
"
```

---

## Backup and Recovery

### Backup Script

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/opt/backups/tax-buddy"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
cp /opt/tax-buddy/backend/data/taxbuddy.db $BACKUP_DIR/taxbuddy_$DATE.db

# Backup uploads
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /opt/tax-buddy/backend/data/uploads

# Backup configuration
cp /opt/tax-buddy/backend/.env $BACKUP_DIR/.env_$DATE

# Remove old backups (keep last 30 days)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

### Automated Backups

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * /opt/tax-buddy/backup.sh >> /var/log/tax-buddy-backup.log 2>&1
```

---

## Support

For deployment issues:
- Check [README.md](README.md) for setup instructions
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system details
- Open an issue on [GitHub](https://github.com/BackBenchDreamer/tax-buddy/issues)

---

**Last Updated:** 2026-05-13  
**Version:** 1.0.0