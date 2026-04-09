"""SMTP email sender for PackTrack notifications.

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

_STATUS_COLOR = {"critical": "#dc2626", "warning": "#d97706"}
_STATUS_LABEL = {"critical": "🔴 Kritické", "warning": "🟡 Objednat"}


def _stock_alerts_html(alerts: list) -> str:
    """Render the low-stock section for the email body."""
    if not alerts:
        return ""

    rows = ""
    for a in alerts:
        m      = a["material"]
        color  = _STATUS_COLOR.get(a["status"], "#64748b")
        label  = _STATUS_LABEL.get(a["status"], "")
        rows += f"""
        <tr style="border-bottom:1px solid #e2e8f0;">
          <td style="padding:10px 12px;font-weight:600;color:#1e293b;">{m['name']}</td>
          <td style="padding:10px 12px;text-align:right;color:#334155;">{a['current_stock']:,} ks</td>
          <td style="padding:10px 12px;text-align:right;color:#64748b;">~{a['avg_monthly']:,} ks/měs.</td>
          <td style="padding:10px 12px;text-align:center;font-weight:700;color:{color};">
            {a['months_remaining']} měs.
          </td>
          <td style="padding:10px 12px;text-align:center;">
            <span style="background:{color};color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;">
              {label}
            </span>
          </td>
        </tr>"""

    return f"""
    <!-- Low stock alert -->
    <tr><td style="padding:24px 32px 0;">
      <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;overflow:hidden;">
        <div style="background:#dc2626;padding:10px 16px;">
          <span style="color:#fff;font-weight:bold;font-size:14px;">
            ⚠️ Upozornění – nízký stav skladu ({len(alerts)} materiálů)
          </span>
        </div>
        <div style="padding:0 0 8px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px;">
            <thead>
              <tr style="background:#fee2e2;">
                <th style="padding:8px 12px;text-align:left;color:#7f1d1d;font-weight:600;">Materiál</th>
                <th style="padding:8px 12px;text-align:right;color:#7f1d1d;font-weight:600;">Sklad</th>
                <th style="padding:8px 12px;text-align:right;color:#7f1d1d;font-weight:600;">Ø spotřeba</th>
                <th style="padding:8px 12px;text-align:center;color:#7f1d1d;font-weight:600;">Zásoby na</th>
                <th style="padding:8px 12px;text-align:center;color:#7f1d1d;font-weight:600;">Stav</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        <div style="padding:8px 16px 12px;">
          <a href="{APP_URL}/materials"
             style="font-size:13px;color:#dc2626;text-decoration:none;font-weight:600;">
            → Otevřít správu materiálů
          </a>
        </div>
      </div>
    </td></tr>"""


def send_monthly_report(recipients: list, year: int, month: int,
                        month_name: str, stock_alerts: list = None):
    """
    Send combined monthly report email:
    - Inventory reminder for the given month
    - Low-stock alert section (if any alerts exist)

    Parameters
    ----------
    recipients   : list of email addresses
    year, month  : int
    month_name   : Czech month name
    stock_alerts : output of reports.get_low_stock_alerts()
    """
    if not MAIL_FROM or not MAIL_PASS:
        raise RuntimeError(
            "Email not configured. Set MAIL_FROM and MAIL_PASS environment variables."
        )

    stock_alerts = stock_alerts or []
    inv_url      = f"{APP_URL}/inventory/{year}/{month}"
    n_critical   = sum(1 for a in stock_alerts if a["status"] == "critical")

    if n_critical:
        subject = f"PackTrack ⚠️ – Inventura + {n_critical} krit. materiálů – {month_name} {year}"
    elif stock_alerts:
        subject = f"PackTrack – Připomínka inventury + nízký stav skladu – {month_name} {year}"
    else:
        subject = f"PackTrack – Připomínka inventury za {month_name} {year}"

    stock_section = _stock_alerts_html(stock_alerts)

    html = f"""<!DOCTYPE html>
<html lang="cs"><body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f1f5f9;">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="580" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:10px;overflow:hidden;
                  box-shadow:0 2px 8px rgba(0,0,0,.08);">

      <!-- Header -->
      <tr><td style="background:#1e293b;padding:20px 32px;">
        <span style="font-size:22px;font-weight:bold;color:#fff;">📦 PackTrack</span>
        <span style="color:#94a3b8;font-size:13px;margin-left:12px;">Měsíční přehled</span>
      </td></tr>

      <!-- Inventory reminder -->
      <tr><td style="padding:28px 32px 16px;">
        <p style="margin:0 0 10px;font-size:16px;color:#334155;">Dobrý den,</p>
        <p style="margin:0 0 20px;color:#475569;line-height:1.65;">
          Blíží se konec měsíce – prosíme o zadání měsíční inventury obalového materiálu
          za <strong>{month_name} {year}</strong>.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#f8fafc;border:1px solid #e2e8f0;
                      border-radius:8px;margin-bottom:20px;">
          <tr><td style="padding:14px 20px;">
            <div style="font-size:12px;color:#64748b;margin-bottom:4px;">📋 Inventura za</div>
            <div style="font-size:22px;font-weight:bold;color:#1e293b;">{month_name} {year}</div>
          </td></tr>
        </table>
        <a href="{inv_url}"
           style="display:inline-block;background:#3b82f6;color:#fff;
                  padding:12px 26px;border-radius:7px;text-decoration:none;
                  font-weight:bold;font-size:15px;">
          ✏️ Zadat inventuru
        </a>
      </td></tr>

      {stock_section}

      <!-- Footer -->
      <tr><td style="padding:16px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;margin-top:24px;">
        <p style="margin:0;font-size:12px;color:#94a3b8;">
          PackTrack – Evidence obalového materiálu ·
          <a href="{APP_URL}" style="color:#94a3b8;">Otevřít PackTrack</a> ·
          Zpráva odeslána automaticky
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = MAIL_FROM
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
        srv.ehlo()
        srv.starttls()
        srv.login(MAIL_FROM, MAIL_PASS)
        srv.sendmail(MAIL_FROM, recipients, msg.as_string())
