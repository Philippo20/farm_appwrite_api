"""Shared, email-client-friendly templates for every account role."""
import os
from html import escape
from urllib.parse import urlsplit


def render_alert(subject, body, *, recipient_name='', recipient_role='', category=None,
                 brand='Farm Estates'):
    """Return plain text and HTML; notification data is always treated as text."""
    url = os.getenv('EMAIL_APP_URL', 'https://apps.farmestates.farm/').strip()
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        url = 'https://apps.farmestates.farm/'
    label = {'farm_alerts': 'Farm alert', 'workflow_alerts': 'Workflow update',
             'account_alerts': 'Account & security'}.get(category, 'Platform update')
    name = str(recipient_name or '').strip()
    role = str(recipient_role or '').replace('_', ' ').replace('-', ' ').strip().title()
    greeting = f'Hello {name},' if name else 'Hello,'
    brand = str(brand or 'Farm Estates')
    plain = f'{brand}\n{label}\n\n{greeting}\n\n{subject}\n\n{body}\n\nOpen Farm Estates: {url}\n\n'
    plain += 'This is an automated notification from Farm Estates.'
    role_line = f'<div style="margin-top:6px;color:#64748b;font-size:12px;">{escape(role)}</div>' if role else ''
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(str(subject))}</title></head>
<body style="margin:0;padding:0;background-color:#f3f5f4;color:#172b24;font-family:Arial,Helvetica,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{escape(str(subject))}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f3f5f4;"><tr><td align="center" style="padding:24px 12px;">
<!--[if mso]><table role="presentation" width="560"><tr><td><![endif]-->
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;table-layout:fixed;background-color:#ffffff;border:1px solid #dde5e0;border-radius:16px;overflow:hidden;">
<tr><td style="padding:24px;border-bottom:1px solid #e8edea;overflow-wrap:anywhere;word-break:break-word;">
<div style="font-size:18px;font-weight:600;color:#216b45;">{escape(brand)}</div>
<div style="margin-top:8px;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#64748b;">{escape(label)}</div></td></tr>
<tr><td style="padding:28px 24px;overflow-wrap:anywhere;word-break:break-word;">
<div style="font-size:14px;line-height:22px;">{escape(greeting)}</div>{role_line}
<h1 style="margin:24px 0 14px;font-size:22px;line-height:30px;font-weight:600;color:#172b24;">{escape(str(subject))}</h1>
<div style="font-size:14px;line-height:24px;color:#475569;">{escape(str(body)).replace(chr(10), '<br>')}</div>
<table role="presentation" cellspacing="0" cellpadding="0" style="margin-top:28px;"><tr><td bgcolor="#216b45" style="border-radius:8px;mso-padding-alt:14px 22px;">
<a href="{escape(url, quote=True)}" style="display:inline-block;padding:14px 22px;color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;">Open Farm Estates</a></td></tr></table>
<p style="margin:18px 0 0;font-size:12px;line-height:20px;color:#64748b;">Sign in to your account to view the details.</p></td></tr>
<tr><td style="padding:20px 24px;border-top:1px solid #e8edea;font-size:11px;line-height:18px;color:#64748b;">This is an automated notification from Farm Estates.<br>You received this email because it relates to your account or assigned work.</td></tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->
</td></tr></table></body></html>'''
    return plain, html
