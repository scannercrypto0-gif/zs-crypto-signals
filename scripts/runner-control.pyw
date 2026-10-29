"""User-opened native control window. Closing it does not stop Task Scheduler."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime,timedelta,timezone

ROOT=Path('D:/ZS-SMART-GATE')
for key,suffix in {'TEMP':'temp','TMP':'temp','TMPDIR':'temp','PIP_CACHE_DIR':'cache/pip',
                   'PYTHONPYCACHEPREFIX':'cache/pycache','XDG_CACHE_HOME':'cache','UV_CACHE_DIR':'cache/uv'}.items():
    os.environ[key]=str(ROOT/suffix)
parser=argparse.ArgumentParser()
parser.add_argument('--config',required=True);parser.add_argument('--config-sha',required=True)
args=parser.parse_args()
window=tk.Tk();window.title('SMART GATE — Windows Runner');window.geometry('780x540')
window.minsize(700,480);window.configure(bg='#eef2f6')
ttk.Label(window,text='SMART GATE | تحكم المشغّل المحلي',font=('Segoe UI',18,'bold')).pack(pady=(18,4))
ttk.Label(window,text='محاكاة فقط • لا تداول • يعمل المجدول بعد إغلاق هذه النافذة',font=('Segoe UI',11)).pack(pady=5)
status_label=ttk.Label(window,text='جارٍ التحقق...',font=('Segoe UI',15,'bold'));status_label.pack(pady=10)
buttons=ttk.Frame(window);buttons.pack(pady=5)
details=tk.Text(window,height=15,wrap='word',font=('Segoe UI',11),padx=12,pady=12,
                bg='white',relief='flat');details.pack(fill='both',expand=True,padx=22,pady=12)
footer=ttk.Label(window,text='لا حاجة إلى Codex أو اتصال بنموذج. أغلق الواجهة متى شئت.',font=('Segoe UI',10));footer.pack(pady=(0,12))
controls=[];busy=False

def render(data):
    global busy
    busy=False
    for b in controls:b.configure(state='normal')
    names={'RUNNING':'مفعّل — محاكاة فقط','PAUSED':'متوقف مؤقتًا','EXPIRED':'انتهت مدة الاختبار','BLOCKED':'محجوب — يلزم إجراء'}
    status_label.configure(text=names.get(data.get('state'),'غير معروف'))
    reason=data.get('reason','UNKNOWN')
    advice={'CLOCK_UNTRUSTED':'زامن ساعة Windows ثم اضغط فحص الاستعادة.',
            'LEASE_EXPIRED':'انتهت المهلة؛ لا تُجدد تلقائيًا. اطلب اعتماد إعداد جديد.',
            'PIN_OR_D_PATH_INVALID':'تغيّرت الملفات أو مسار D. أبقِ التشغيل متوقفًا وراجع الإعداد.',
            'TASK_MISSING':'المهمة غير مثبّتة. راجع الإعداد المعتمد.',
            'TASK_ACTION_MISMATCH':'تعريف المهمة لا يطابق النسخة المثبتة. لا تبدأ التشغيل.',
            'WINDOWS_QUERY_FAILED':'تعذّر قراءة إعدادات Windows. افحص الصلاحيات.',
            'SIMULATION_ONLY':'تشغيل مستقل وآمن؛ لا توجد بيانات سوق حية أو إشارة تداول.'}.get(reason,reason)
    clock=data.get('clock',{});health=data.get('health',{})
    next_utc=data.get('next_utc')
    try: local=datetime.fromisoformat(next_utc.replace('Z','+00:00')).astimezone(timezone(timedelta(hours=3))).isoformat()
    except (ValueError,AttributeError):local='—'
    lines=[advice,'',f"الدورة التالية UTC: {next_utc or '—'}",f'الدورة التالية بالرياض: {local}',
           f"آخر تشغيل UTC: {data.get('last_utc') or '—'} | رمز الخروج: {data.get('exit_code','—')}",
           f"آخر نجاح: {health.get('last_success_utc') or '—'}",f"آخر فشل: {health.get('last_failure_utc') or '—'}",
           f"فئة الخطأ: {health.get('current_error_category') or 'لا يوجد'}",
           f"مصدر الساعة: {clock.get('source','UNKNOWN')} | عمر المزامنة: {clock.get('sync_age_seconds','—')} ثانية",
           f"اتصال Windows: {data.get('internet','UNKNOWN')} (المحاكاة لا تحتاج الإنترنت)",
           'ساعة Binance: UNKNOWN | LIVE: OFF | أدلة GitHub: بانتظار الاعتماد',
           f"انتهاء المهلة: {data.get('expires','—')}",f"النسخة: {data.get('revision','—')}",
           'بعد إعادة التشغيل: سجّل الدخول ثم افتح هذا الاختصار. لا تعويض للفترات الفائتة.']
    details.configure(state='normal');details.delete('1.0','end');details.insert('1.0','\n'.join(lines));details.configure(state='disabled')

try:
    cp=Path(args.config).resolve(strict=True)
    if cp.drive.upper()!='D:' or cp.stat().st_size>65536:raise ValueError('PIN_OR_D_PATH_INVALID')
    config=json.loads(cp.read_text(encoding='utf-8-sig'))
    digest=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if digest!=args.config_sha:raise ValueError('PIN_OR_D_PATH_INVALID')
    repo=ROOT/'repo'
    for name,checksum in config['files'].items():
        item=(repo/name).resolve(strict=True)
        if not item.is_relative_to(repo) or hashlib.sha256(item.read_bytes()).hexdigest()!=checksum:
            raise ValueError('PIN_OR_D_PATH_INVALID')
    from zs_smart_gate.windows_control import Control
    control=Control(cp,args.config_sha,repo,ROOT/'runtime',ROOT/'logs',ROOT/'.venv/Scripts/pythonw.exe')
except Exception:
    control=None

def invoke(action):
    global busy
    if busy:return
    busy=True
    for b in controls:b.configure(state='disabled')
    status_label.configure(text='جارٍ التحقق...')
    def worker():
        try:
            result=getattr(control,action)() if control else {'state':'BLOCKED','reason':'PIN_OR_D_PATH_INVALID'}
        except Exception:result={'state':'BLOCKED','reason':'WINDOWS_QUERY_FAILED'}
        try:window.after(0,lambda:render(result))
        except RuntimeError:pass
    threading.Thread(target=worker,daemon=True).start()

for label,action in [('تشغيل / Resume','resume'),('إيقاف / Pause','pause'),('الحالة / Status','status'),('فحص الاستعادة / Recovery','status')]:
    b=ttk.Button(buttons,text=label,command=lambda a=action:invoke(a));b.pack(side='left',padx=5);controls.append(b)
window.after(100,lambda:invoke('status'))
window.mainloop()
