"""
First Assurance IT Account Unlock Bot - Email Notification Service
Sends automated incident alert emails to IT Support staff when an employee
exceeds unlock limits or requires manual IT intervention.
"""

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import smtplib
import threading
from typing import Optional

logger = logging.getLogger("email-service")

# In-memory cooldown cache to prevent spamming IT with multiple emails for the same user
# Format: { "username_or_id": datetime_last_sent }
_ALERT_COOLDOWN: dict[str, datetime] = {}
_COOLDOWN_MINUTES = 30


def get_smtp_config():
    """Load SMTP settings from environment variables with safe enterprise defaults."""
    return {
        "host": os.getenv("SMTP_HOST", "firstassurance-co-ke.mail.protection.outlook.com").strip(),
        "port": int(os.getenv("SMTP_PORT", "25").strip() or "25"),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
        "from_addr": os.getenv("SMTP_FROM", "unlock-bot@firstassurance.co.ke").strip(),
        "to_addrs": [
            addr.strip()
            for addr in os.getenv("IT_ALERT_EMAIL", "itstaff@firstassurance.co.ke").split(",")
            if addr.strip()
        ],
    }


def generate_ticket_ref(audit_id: Optional[int] = None) -> str:
    """Generate a clean IT Incident Ticket reference string."""
    date_str = datetime.now().strftime("%Y%m%d")
    seq = f"{audit_id:04d}" if audit_id else datetime.now().strftime("%H%M")
    return f"FA-INC-{date_str}-{seq}"


def _send_email_worker(
    ticket_ref: str,
    subject: str,
    plain_text: str,
    html_content: str,
    target_identifier: str,
):
    """Worker function executed in background thread to avoid blocking bot execution."""
    config = get_smtp_config()
    host = config["host"]
    port = config["port"]
    from_addr = config["from_addr"]
    to_addrs = config["to_addrs"]

    if not host or not to_addrs:
        logger.warning("SMTP host or recipient list not configured. Skipping email alert.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"First Assurance IT Unlock Bot <{from_addr}>"
    msg["To"] = ", ".join(to_addrs)
    msg["X-Priority"] = "1"  # High priority header for IT helpdesk systems

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        logger.info("Connecting to SMTP relay %s:%s to send alert for ticket %s...", host, port, ticket_ref)
        if config["use_tls"]:
            server = smtplib.SMTP(host, port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(host, port, timeout=10)

        if config["user"] and config["password"]:
            server.login(config["user"], config["password"])

        server.sendmail(from_addr, to_addrs, msg.as_string())
        server.quit()
        logger.info("Successfully dispatched IT alert email for ticket %s to %s", ticket_ref, to_addrs)
    except Exception as e:
        logger.warning(
            "Could not deliver IT alert email via SMTP (%s:%s): %s. (Alert details logged in audit database).",
            host,
            port,
            e,
        )


def send_it_limit_alert(
    employee_name: str,
    employee_id: Optional[str] = None,
    department: Optional[str] = None,
    requester_name: Optional[str] = None,
    audit_id: Optional[int] = None,
    attempts: int = 3,
    reason: str = "Daily unlock attempt limit reached (3/3)",
    is_colleague_assist: bool = False,
) -> str:
    """
    Format and send an incident ticket notification email to IT support staff.
    Runs asynchronously in a background thread to prevent any user delay in Teams.
    Returns the generated ticket reference (e.g. FA-INC-20261102-0042).
    """
    target_key = (employee_id or employee_name).strip().lower()

    # Cooldown check
    now = datetime.now()
    last_sent = _ALERT_COOLDOWN.get(target_key)
    if last_sent and (now - last_sent).total_seconds() < (_COOLDOWN_MINUTES * 60):
        logger.info("Alert email for '%s' suppressed by cooldown (sent %s minutes ago)", target_key, int((now - last_sent).total_seconds() / 60))
        return generate_ticket_ref(audit_id)

    _ALERT_COOLDOWN[target_key] = now
    ticket_ref = generate_ticket_ref(audit_id)

    # Email Subject
    subject = f"[Ticket Created: {ticket_ref}] Account Unlock Limit Reached - {employee_name}"

    emp_id_display = employee_id or "N/A"
    dept_display = department or "General"
    now_formatted = now.strftime("%d %b %Y, %I:%M %p EAT")

    request_context = (
        f"Assisted by colleague: {requester_name} (Cross-user unlock)"
        if (is_colleague_assist and requester_name and requester_name != employee_name)
        else f"Direct self-service request by {requester_name or employee_name}"
    )

    # Plain text version
    plain_text = f"""FIRST ASSURANCE IT SERVICE DESK - INCIDENT NOTIFICATION
Ticket Reference: {ticket_ref}
Event: Account Unlock Limit Reached / Verification Failure

An employee has reached the maximum allowed self-service account unlock limit ({attempts}/3 attempts) and has been locked out from further automated attempts.

EMPLOYEE DETAILS:
• Full Name:       {employee_name}
• Employee ID/AD:  {emp_id_display}
• Department:      {dept_display}
• Request Type:    {request_context}
• Trigger Reason:  {reason}
• Incident Time:   {now_formatted}
• Audit Log ID:    #{audit_id or 'N/A'}

RECOMMENDED IT ACTIONS:
1. Verify the employee's identity.
2. Check account status on Active Directory Domain Controller (172.17.0.220).
3. If legitimate, unlock the account manually or initiate a password reset.

--
First Assurance IT Account Unlock Portal
Insure • Secure • Assure
"""

    # Rich HTML version for Microsoft Outlook
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; color: #333333; margin: 0; padding: 20px; background-color: #f7f9fa; }}
    .card {{ background-color: #ffffff; border-radius: 8px; border: 1px solid #e1dfdd; max-width: 620px; margin: 0 auto; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
    .header {{ background-color: #F78723; color: #ffffff; padding: 18px 24px; }}
    .header h2 {{ margin: 0; font-size: 20px; letter-spacing: 0.5px; }}
    .header p {{ margin: 4px 0 0; font-size: 13px; opacity: 0.9; }}
    .badge {{ display: inline-block; background-color: #d13438; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-bottom: 15px; }}
    .content {{ padding: 24px; }}
    .ticket-box {{ background-color: #f3f2f1; border-left: 4px solid #F78723; padding: 12px 16px; margin-bottom: 20px; border-radius: 0 4px 4px 0; }}
    .table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
    .table td {{ padding: 8px 10px; border-bottom: 1px solid #edebe9; }}
    .table td.label {{ font-weight: 600; color: #605e5c; width: 35%; }}
    .table td.value {{ color: #201f1e; }}
    .action-box {{ background-color: #eff6fc; border: 1px solid #c7e0f4; border-radius: 6px; padding: 14px 18px; margin-top: 20px; }}
    .action-box h4 {{ margin: 0 0 8px 0; color: #005a9e; font-size: 14px; }}
    .action-box ol {{ margin: 0; padding-left: 20px; font-size: 13px; color: #323130; }}
    .footer {{ background-color: #faf9f8; border-top: 1px solid #edebe9; padding: 12px 24px; font-size: 12px; color: #8a8886; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h2>First Assurance IT Service Desk</h2>
      <p>Automated IT Account Unlock Alert • <em>Insure • Secure • Assure</em></p>
    </div>
    <div class="content">
      <div class="badge">⚠️ INCIDENT ALERT</div>
      <div class="ticket-box">
        <strong>Ticket Reference:</strong> <span style="font-family: monospace; font-size: 15px; color: #107c41;">{ticket_ref}</span><br>
        <strong>Event:</strong> Account Unlock Limit Reached ({attempts}/3 requests today)
      </div>

      <p style="font-size: 14px; line-height: 1.5; margin-bottom: 15px;">
        An employee has exceeded the maximum permitted self-service unlock requests within 24 hours. The bot has referred them to the IT Service Desk.
      </p>

      <table class="table">
        <tr>
          <td class="label">Employee Name:</td>
          <td class="value"><strong>{employee_name}</strong></td>
        </tr>
        <tr>
          <td class="label">Employee ID / AD:</td>
          <td class="value"><code>{emp_id_display}</code></td>
        </tr>
        <tr>
          <td class="label">Department:</td>
          <td class="value">{dept_display}</td>
        </tr>
        <tr>
          <td class="label">Request Context:</td>
          <td class="value">{request_context}</td>
        </tr>
        <tr>
          <td class="label">Trigger Reason:</td>
          <td class="value"><span style="color: #d13438; font-weight: 600;">{reason}</span></td>
        </tr>
        <tr>
          <td class="label">Incident Timestamp:</td>
          <td class="value">{now_formatted}</td>
        </tr>
        <tr>
          <td class="label">Database Audit ID:</td>
          <td class="value">#{audit_id or 'N/A'}</td>
        </tr>
      </table>

      <div class="action-box">
        <h4>Recommended IT Actions:</h4>
        <ol>
          <li>Verify user identity with the employee or department manager.</li>
          <li>Check the Active Directory Domain Controller (<code>172.17.0.220</code>) for repeated bad password locks.</li>
          <li>If confirmed legitimate, unlock the user account in AD or guide them through a password reset.</li>
        </ol>
      </div>
    </div>
    <div class="footer">
      This is an automated notification dispatched by the First Assurance IT Account Unlock Bot.
    </div>
  </div>
</body>
</html>
"""

    thread = threading.Thread(
        target=_send_email_worker,
        args=(ticket_ref, subject, plain_text, html_content, target_key),
        daemon=True,
    )
    thread.start()

    return ticket_ref
