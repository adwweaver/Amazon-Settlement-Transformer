"""
Notifications utility: sends email alerts when settlements are blocked.

Reads SMTP settings from config/config.yaml if available:

notifications:
  enabled: true
  smtp_server: smtp.office365.com
  smtp_port: 587
  username: user@example.com
  password: app_password_or_secret
  from: etl-bot@example.com
  to:
    - accounting@example.com
    - ops@example.com
"""

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
import logging
import yaml
from typing import List, Optional

logger = logging.getLogger(__name__)


def load_email_config():
    try:
        cfg_path = Path("config/config.yaml")
        if not cfg_path.exists():
            return None
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get('notifications')
    except Exception as e:
        logger.warning(f"Could not load email config: {e}")
        return None


def send_email(subject: str, body: str, attachments: Optional[List[Path]] = None) -> bool:
    conf = load_email_config()
    if not conf or not conf.get('enabled'):
        logger.info("Notifications disabled or not configured; skipping email")
        return False

    smtp_server = conf.get('smtp_server')
    smtp_port = int(conf.get('smtp_port', 587))
    username = conf.get('username')
    password = conf.get('password')
    sender = conf.get('from', username)
    recipients = conf.get('to') or []

    if not smtp_server or not username or not password or not recipients:
        logger.warning("Incomplete email configuration; skipping email")
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg.set_content(body)

    # Attach files
    for att in attachments or []:
        try:
            if att and Path(att).exists():
                with open(att, 'rb') as f:
                    data = f.read()
                msg.add_attachment(data, maintype='application', subtype='octet-stream', filename=Path(att).name)
        except Exception as e:
            logger.warning(f"Failed attaching {att}: {e}")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(username, password)
            server.send_message(msg)
        logger.info("Alert email sent")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False






