"""Simple SMTP email sender for PackTrack notifications.

Required environment variables:
  MAIL_FROM  – Gmail address (e.g. packtrack@gmail.com)
  MAIL_PASS  – Gmail App Password (16 chars, no spaces)
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

MAIL_FROM = os.environ.get("MAIL_FROM", "")
MAIL_PASS = os.environ.get("MAIL_PASS", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
APP_URL   = "https://packtrack-vsf7.onrender.com"


def send_inventory_reminder(to_email: str, year: int, month: int, month_name: str):
    """Send monthly inventory reminder email."""
    if not MAIL_FROM or not MAIL_PASS:
        raise RuntimeError(
            "Email not configured. Set MAIL_FROM and MAIL_PASS environment variables."
        )

    subject = f"PackTrack – Připomínka inventury za {month_name} {year}"
    inv_url = f"{APP_URL}/inventory/{year}/{month}"

    html = f"""<!DOCTYPE html>
<html lang="cs"><body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f1f5f9;">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
      <!-- Header -->
      <tr><td style="background:#1e293b;padding:24px 32px;">
        <span style="font-size:22px;font-weight:bold;color:#fff;">📦 PackTrack</span>
        <span style="color:#94a3b8;font-size:14px;margin-left:12px;">Připomínka inventury</span>
      </td></tr>
      <!-- Body -->
      <tr><td style="padding:32px;">
        <p style="margin:0 0 12px;font-size:16px;color:#334155;">Dobrý den,</p>
        <p style="margin:0 0 24px;color:#475569;line-height:1.6;">
          Blíží se konec měsíce. Prosíme o zadání měsíční inventury obalového materiálu
          za <strong>{month_name} {year}</strong> do systému PackTrack.
        </p>
        <!-- Month box -->
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:24px;">
          <tr><td style="padding:16px 20px;">
            <div style="font-size:13px;color:#64748b;margin-bottom:4px;">📋 Inventura za</div>
            <div style="font-size:24px;font-weight:bold;color:#1e293b;">{month_name} {year}</div>
          </td></tr>
        </table>
        <!-- CTA button -->
        <a href="{inv_url}"
           style="display:inline-block;background:#3b82f6;color:#fff;padding:14px 28px;
                  border-radius:7px;text-decoration:none;font-weight:bold;font-size:15px;">
          ✏️ Zadat inventuru
        </a>
      </td></tr>
      <!-- Footer -->
      <tr><td style="padding:16px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;">
        <p style="margin:0;font-size:12px;color:#94a3b8;">
          PackTrack – Evidence obalového materiálu · Zpráva odeslána automaticky
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = MAIL_FROM
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
        srv.ehlo()
        srv.starttls()
        srv.login(MAIL_FROM, MAIL_PASS)
        srv.sendmail(MAIL_FROM, [to_email], msg.as_string())
