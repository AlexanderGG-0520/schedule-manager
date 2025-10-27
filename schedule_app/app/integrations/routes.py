from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from ..models import ExternalAccount
from sqlalchemy import exc as sa_exc
from .. import db
from flask import request, send_file
from ..models import Event
import tempfile
from datetime import datetime
import os
try:
    from icalendar import Calendar
except Exception:
    Calendar = None

integrations_bp = Blueprint("integrations", __name__, template_folder="../../schedule_app/app/templates", url_prefix="/integrations")


@integrations_bp.route("/")
@login_required
def index():
    # list connected external accounts for current user
    try:
        accounts = ExternalAccount.query.filter_by(user_id=current_user.id).all()
    except sa_exc.ProgrammingError:
        # Likely the external_accounts table doesn't exist yet (migration not applied).
        current_app.logger.exception("integrations.index: database table missing or programming error")
        flash("連携テーブルがまだセットアップされていません。管理者に連絡してください。", "error")
        accounts = []
    return render_template("integrations/index.html", accounts=accounts)


@integrations_bp.route("/disconnect/<int:account_id>", methods=["POST"])
@login_required
def disconnect(account_id: int):
    acc = ExternalAccount.query.get_or_404(account_id)
    if acc.user_id != current_user.id:
        flash("アカウントの解除権限がありません。", "error")
        return redirect(url_for("integrations.index"))
    try:
        db.session.delete(acc)
        db.session.commit()
        flash("連携を解除しました。", "success")
    except Exception:
        db.session.rollback()
        flash("連携解除に失敗しました。", "error")
    return redirect(url_for("integrations.index"))



@integrations_bp.route('/ical/import', methods=['POST'])
@login_required
def ical_import():
    if 'ics' not in request.files:
        flash('ICS ファイルが添付されていません。', 'error')
        return redirect(url_for('integrations.index'))
    f = request.files['ics']
    if not Calendar:
        flash('icalendar パッケージがインストールされていません。', 'error')
        return redirect(url_for('integrations.index'))
    data = f.read()
    cal = Calendar.from_ical(data)
    imported = 0
    for component in cal.walk():
        if component.name == 'VEVENT':
            summary = str(component.get('summary'))
            dtstart = component.get('dtstart').dt
            dtend = component.get('dtend').dt if component.get('dtend') else dtstart
            ev = Event(user_id=current_user.id, title=summary, start_at=dtstart if isinstance(dtstart, datetime) else datetime.fromtimestamp(dtstart.timestamp()), end_at=dtend if isinstance(dtend, datetime) else datetime.fromtimestamp(dtend.timestamp()))
            db.session.add(ev)
            imported += 1
    db.session.commit()
    flash(f'ICS から {imported} 件のイベントを取り込みました。', 'success')
    return redirect(url_for('integrations.index'))


@integrations_bp.route('/events/<int:event_id>/ical')
@login_required
def ical_export(event_id: int):
    ev = Event.query.get_or_404(event_id)
    # build minimal ICS
    ics = 'BEGIN:VCALENDAR\nVERSION:2.0\n'
    ics += 'BEGIN:VEVENT\n'
    ics += f'SUMMARY:{ev.title}\n'
    ics += f'DTSTART:{ev.start_at.strftime("%Y%m%dT%H%M%SZ")}\n'
    ics += f'DTEND:{ev.end_at.strftime("%Y%m%dT%H%M%SZ")}\n'
    ics += 'END:VEVENT\nEND:VCALENDAR\n'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.ics')
    tmp.write(ics.encode())
    tmp.flush()
    tmp.close()
    return send_file(tmp.name, as_attachment=True, download_name=f'{ev.id}.ics')



@integrations_bp.route('/accounts/<int:account_id>')
@login_required
def account_detail(account_id: int):
    acc = ExternalAccount.query.get_or_404(account_id)
    if acc.user_id != current_user.id:
        flash('アカウントの表示権限がありません。', 'error')
        return redirect(url_for('integrations.index'))
    # summary info and recent logs
    logs = acc.logs if hasattr(acc, 'logs') else []
    recent_logs = sorted(logs, key=lambda l: l.created_at, reverse=True)[:20]
    return render_template('integrations/detail.html', account=acc, recent_logs=recent_logs)


@integrations_bp.route('/accounts/<int:account_id>/history')
@login_required
def account_history(account_id: int):
    acc = ExternalAccount.query.get_or_404(account_id)
    if acc.user_id != current_user.id:
        return {'error': 'forbidden'}, 403
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    q = acc.logs
    # ensure q is a query-like object
    try:
        q = q.order_by(db.desc('created_at'))
    except Exception:
        # if not query (e.g., list), keep as-is
        pass
    # If SQLAlchemy query
    if hasattr(q, 'paginate'):
        pag = q.paginate(page=page, per_page=per_page, error_out=False)
        items = [
            {
                'id': it.id,
                'level': it.level,
                'message': it.message,
                'created_at': it.created_at.isoformat() + 'Z',
            }
            for it in pag.items
        ]
        return {
            'items': items,
            'page': pag.page,
            'per_page': pag.per_page,
            'total': pag.total,
        }
    else:
        # fallback list handling
        arr = sorted(list(q), key=lambda l: l.created_at, reverse=True)
        start = (page - 1) * per_page
        chunk = arr[start:start+per_page]
        items = [
            {'id': it.id, 'level': it.level, 'message': it.message, 'created_at': it.created_at.isoformat() + 'Z'}
            for it in chunk
        ]
        return {'items': items, 'page': page, 'per_page': per_page, 'total': len(arr)}


@integrations_bp.route('/accounts/<int:account_id>/sync', methods=['POST'])
@login_required
def account_sync(account_id: int):
    acc = ExternalAccount.query.get_or_404(account_id)
    if acc.user_id != current_user.id:
        return {'error': 'forbidden'}, 403
    provider = acc.provider
    created = 0
    from ..models import IntegrationLog
    try:
        if provider == 'google':
            from .google import import_events_for_account, refresh_access_token as google_refresh
            # attempt to refresh if expired
            if acc.expires_at and acc.expires_at <= datetime.utcnow():
                refreshed = google_refresh(acc)
                if not refreshed:
                    db.session.add(IntegrationLog(provider='google', account_id=acc.id, level='error', message='Token refresh failed'))
                    db.session.commit()
                    return {'error': 'token_refresh_failed'}, 400
            created = import_events_for_account(acc)
        elif provider == 'outlook':
            from .outlook import import_events_for_account, refresh_access_token as outlook_refresh
            if acc.expires_at and acc.expires_at <= datetime.utcnow():
                refreshed = outlook_refresh(acc)
                if not refreshed:
                    db.session.add(IntegrationLog(provider='outlook', account_id=acc.id, level='error', message='Token refresh failed'))
                    db.session.commit()
                    return {'error': 'token_refresh_failed'}, 400
            created = import_events_for_account(acc)
        else:
            db.session.add(IntegrationLog(provider=provider, account_id=acc.id, level='error', message='Unsupported provider for manual sync'))
            db.session.commit()
            return {'error': 'unsupported_provider'}, 400
        db.session.add(IntegrationLog(provider=provider, account_id=acc.id, level='info', message=f'manual sync created {created} events'))
        db.session.commit()
        return {'created': created}
    except Exception as e:
        db.session.add(IntegrationLog(provider=provider, account_id=acc.id, level='error', message=str(e)))
        db.session.commit()
        return {'error': 'sync_failed', 'message': str(e)}, 500
