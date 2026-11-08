# «Stage03» — تقرير تكافؤ «GitHub / Windows» وعهدة أدلة اختبار «Quick30»

**التاريخ:** 8 نوفمبر 2026 — **فرع المصدر:** `stage03-r2-offline-dev-candidate-sd23` — **طلب الدمج:** «PR #39» (مسودة مفتوحة غير مدمجة).  
**نطاق التقرير:** الحفاظ على جميع ملفات المصدر والاختبارات وسكربتات التشغيل وتوثيق المنهجية في «GitHub»، وتقييد «Windows» بتنفيذ اختبار ميداني محلي وتخزين أدلته الخاصة، وفق «MASTER v1.37». هذا السجل لا يثبت تطابق كل ملف على جهاز المالك مع المستودع إلا بعد إجراء مقارنة محلية مستقلة.

## التوزيع الملزم للملفات

| الفئة | النسخة المعتمدة | موضعها |
|---|---|---|
| كود «Stage03» ومسار «Quick30» | ملف مصدر متتبع | «GitHub PR #39» |
| ملفات اختبارات «Quick30» | ملف اختبار متتبع | «GitHub PR #39» |
| مشغّل «PowerShell» ودليل التشغيل والقيود | ملفات متتبعة | «GitHub PR #39» |
| بصمات الأدلة دون محتويات السوق | هذا التقرير وسجل «Issue #25» | «GitHub» |
| «PRE»، و«POST»، ونتيجة التكامل، وإقرار الحقوق | **ملفات اختبار محلية خاصة فقط** | مجلد `_local_evidence/` على جهاز «Windows» |
| أسرار الحسابات أو مفاتيح الواجهة أو أجسام استجابات مزود البيانات | محظورة في المستودع | لا تُنشر |

**حماية المستودع:** `.gitignore` يتضمن الآن `/_local_evidence/`، لمنع رفع مجلد أدلة المصدر المحلي عرضًا. لا يعني الاستثناء حذف الملفات المحلية أو توفير نسخ احتياطية منها.

## ملفات المصدر والاختبارات والتوثيق المتتبعة على «PR #39»

- `src/zs_smart_gate/stage03_field_clock.py`
- `src/zs_smart_gate/stage03_windows_field_capture.py`
- `src/zs_smart_gate/stage03_windows_field_review.py`
- `src/zs_smart_gate/stage03_field_real_e2e.py`
- `src/zs_smart_gate/stage03_field_quick30.py`
- `research/order025/run-stage03-field.ps1`
- `research/order025/run-stage03-quick30.ps1`
- `research/order025/stage03-p0-windows-field-v2.md`
- `research/order025/stage03-quick30-fast-track.md`
- `tests/test_stage03_windows_field.py`
- `tests/test_stage03_field_real_e2e.py`
- `tests/test_stage03_field_quick30.py`
- `.github/workflows/03-field-offline.yml`

وهناك ملفات تطوير «R2» إضافية واختباراتها على نفس طلب الدمج. لا تُعامل هذه الملفات على أنها دخلت `main` إلى أن يصدر قرار دمج مستقل.

## بصمات بايتات الملفات المحلية — كما ظهرت في شاشة المالك

**هذه قيم «SHA256» لبايتات الملفات الكاملة، مُبلّغ بها من جهاز المالك وليست فحصًا عن بُعد على تلك البايتات.**

| ملف محلي خاص | «SHA256» الكامل |
|---|---|
| `rights-attestation.json` | `cf096f1ef3428bf0ae45c9640527cde1acd779ed0eb0ab6b146be09fea67d0ac` |
| `zs03-20261108T0800Z-pre.json` | `69f23afdb57b21702201b82514c1c6fe57b98e371821256ffcb89ad1857fe30a` |
| `zs03-20261108T0800Z-quick30-post.json` | `d6d4ab5d21e47da3a5b7500901f10a1bf13a3658fef00cb59e64cb73f831c84a` |
| `zs03-20261108T0800Z-quick30-e2e.json` | `12efe03e93aff2601fcefdedeed8d47623fe3b15e0423e7d9792333af4563d11` |

### البصمات الداخلية المستقلة عن تنسيق ملف «JSON»

- `PRE RECORD_SHA256=c8ad245d8fbabc7cd08eb28be659793509e1b97da40fed398792ee5e36398e9b`
- `QUICK30 POST RECORD_SHA256=6a3ff37a6fa5d5a4aa344069f3d296eaede04631eaf5feee3512a4a53eb4b8cf`
- `E2E RESEARCH_RESULT_SHA256=e5fe44eca8a16e5845652f9a47626f0354d6c1f72fce791df4098ba4ad26cd5d`

بصمات السجلات الداخلية «canonical» لا يُشترط تطابقها مع بصمات بايتات ملفات «JSON» الكاملة. بصمة إقرار الحقوق هي بصمة ملفه الكامل وقد تطابقت.

## نتائج تشغيل «Windows» كما أفاد بها المالك

```text
LOCAL_QUICK30_TESTS=6/6_OK
QUICK30_PRECHECK=PASS
QUICK30_POST_CAPTURE=PASS_UNREVIEWED
REAL_30M_03A_E2E=PASS
REAL_03A_STATUS=RESEARCH_CANDIDATE
STAGE03_CLOSED=false
```

نجاح تكامل البحث لا يساوي اعتماد علم «N01–N12» أو وجود «signal_id» أو إثبات حقوق مزود البيانات أو توقيت نشره أو تأهيل بيانات تاريخية. الساعة الشبكية العامة غير موثَّقة المصادقة، وملفات الاستلام على الجهاز الخاص لم يُعَد حسابها استقلالًا من قِبل المراجع.

## ما يلزم لإثبات تطابق جهاز «Windows» مع «GitHub»

بعد أن يجلب المالك أحدث رأس «PR #39» ويُحدّث فرعه محليًا:

```powershell
git fetch origin stage03-r2-offline-dev-candidate-sd23
git merge --ff-only FETCH_HEAD
git rev-parse HEAD
git rev-parse origin/stage03-r2-offline-dev-candidate-sd23
git status --porcelain=v1 --untracked-files=all
git ls-files --others --exclude-standard
```

قبول التكافؤ يحتاج تطابق أول بصمتين، وعدم وجود تعديلات في الملفات المتتبعة، وعدم ظهور أي كود/اختبارات/توثيق محلي فقط ضمن قائمة الملفات غير المتتبعة. مجلد `_local_evidence/` مستثنى قصدًا. لا ترفع الملفات المخفية أو الأسرار أو الخام لمجرد جعل المجلد خاليًا.

## بوابات الاعتماد

- **مصدر الحقيقة:** «GitHub» للكود والأدلة الوصفية والقرارات؛ «Windows» لتنفيذ الاختبارات المحلية وعهدة أدلة المصدر الخاصة، وفق «MASTER v1.37».
- **وضع النشر:** «PR #39» `DRAFT / UNMERGED`، وبالتالي كود «Quick30» **غير موجود على `main` بعد**. حظر الدمج لا يُرفع دون مراجعة علمية مستقلة وقرار المالك.
- **حالة الأتمتة:** نتائج «GitHub Actions» الأخيرة لرأس المسار الجديد لا تشكل نجاحًا معتمدًا؛ التشغيل الجديد يحتاج مراجعة حالات الوظائف وآلية الفشل.
- **التقدم العلمي:** `7 VERIFIED / 9 PARTIAL / 6 BLOCKED = 31.8%` حتى قبول «PM» المستقل.
- **مرحلة الإشارات:** `STAGE05_FULL_HOLD`.

**مرجع:** https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6719348128
