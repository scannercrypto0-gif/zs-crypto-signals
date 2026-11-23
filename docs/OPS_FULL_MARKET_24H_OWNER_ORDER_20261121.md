# P0 — Full Eligible-Market 24×7 Windows Operation: Owner Execution Direction

## تحديث «PM 1.15» — برنامج الإغلاق المرحلي — 23 نوفمبر 2026

**الأمر الحاكم:** [«OPS77-PM115-STAGE-GATED-COMPLETION-20261123-001»](OPS77_PM115_STAGE_GATED_COMPLETION_ORDER_20261123.md). **التكليف التنفيذي الفعلي:** https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7096856088

**الحزمة النشطة الوحيدة:** «OPS77-PM115-GATE2F-CUSTODY-PRECHECK-001»؛ بعد مراجعة ملف «SD Coding 2.13»، النتيجة «GATE2F_EVIDENCE_CUSTODY_HOLD»، وتبقى «R02 PARTIAL». سبب التعليق هو عدم تحقق مستقل من أصول الأربعة أحداث غير المحللة ومن عهدة الملفات القابلة للجلب والاسترجاع؛ أداة الفحص المشتقة الجديدة لم تختبر بعد على «Windows» ولا تستنسخ الاستعلام الأصلي. لم يُمنح إذن تنفيذها على الجهاز بعد؛ المطلوب مراجعة مصدر/اختبارات وأصول منقحة وتعليمات «PowerShell» قبل تمكين المالك من الفحص المحدود. نتيجة إثبات السببية الأصلي لبدء خدمة التعافي لا تُلغى.

**منهج الإغلاق:** كل مرحلة تُسلَّم بالأصل والبصمة والرأس والشجرة وتحقق القراءة الراجعة واختبار الاسترجاع ثم قرار «PM»؛ لا ترقيات إلى «PASS» كاملة بدون مطابقة كل معايير قبول المرحلة. «MASTER/README» و«PR #75/76/78» أُخطرت بالتكليف؛ تبقى الطلبات مسودات غير مدمجة. «STOP» محفوظ ومهمة التعافي معطلة وفق آخر إيصال مالك؛ لا إنتاج ولا إشارات غير مؤهلة أو تداول أو «SQL» أو تغيير صلاحيات بسبب هذا الأمر.

---


## تحديث «PM» — 23 نوفمبر 2026 — 11:46 الرياض — «Gate 2F»

**السجل التشغيلي الأحدث بعد مراجعة «GitHub».** يحفظ الدليل التاريخي ولا يغيّر حالة أي بوابة إلى موافقة إنتاجية. [محضر «Gate 2F»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7095515917). جميع نتائج «Windows» هنا مستمدة من مخرجات المالك المحلية المنقحة التي راجعتها «SD Coding»؛ لم يراجع «PM» الملفات الخام من الجهاز أو يعِد احتفاظ «GitHub» بالأصول قبل نقلها والتحقق منها.

| البوابة | الحالة الموثقة حتى الآن | المطلوب للإغلاق |
| --- | --- | --- |
| **R00** | «PARTIAL»: جرد المالك وتثبيت رؤوس الإصدارات و«STOP» و«Python»؛ قراءتا مهمتين قديمتين «READ_ERROR» | فحص الاستثناءات المتبقية ومراجعة الأدلة الأصلية عند الحاجة |
| **R01** | «OWNER-REPORTED SCOPED PASS / INDEPENDENT HOLD»: ثلاث قراءات جديدة 0.0990583–0.10333995 ثانية، وحساب العامل المجدول «Gate 1B» عدم يقين 0.1026955 ثانية تحت الحد 0.5؛ الفشل 3.848s أقدم وليس أحدث قياس | فحص الأدلة الأصلية المنقحة، ثم قياس حديث عند التفعيل لا إعادة اختبار الناجح بلا سبب |
| **R02** | «PASS_BOUNDED NATIVE_BOOT_CAUSATION_OBSERVED / R02 PARTIAL»: في «Gate 2C» سجل «SQLite» سليم 160 صفًا و112 نبضة بعد إقلاع 05:33:17Z في «Session 0» وصفر سوق/رسائل/«SQL»؛ في «Gate 2D» أحداث 100/200؛ في «Gate 2F» تأكد الحدث 118 بسبب الإقلاع وربط «InstanceId» نفسه بأحداث 100/200، مع الحدث 129. تم «ROLLBACK» وبقي «STOP» والمهمة معطلة. لا تكرر الإقلاع لإثبات نفس السبب | مراجعة مستقلة لأربعة أحداث لم تُحلل من أصل 176 وتقييد معنى غياب 110/119؛ حفظ الأدلة المسموح بها في «GitHub» والتحقق من رفعها واسترجاعها؛ استكمال تعافٍ الشبكة والانهيار والاستعادة الأوسع |
| **R03** | «PASS_LIVE_BOUNDED» تاريخية: جولة سوق أصلية 56/56 يوم 21 نوفمبر، وليست ماسحًا مستمرًا | نسخة حية حديثة مصدر/حصة/ساعة ثم تشغيل متواصل |
| **R04** | «PASS_BOUNDED» اختبارات الربط المحاكية 28/28؛ التجربة الحية الجديدة للبوتات «NOT_RUN» | اختبار بحثي حقيقي خاص دون إشارات غير مؤهلة |
| **R05** | «HOLD»: التأهيل العلمي الحقيقي «QV1» للإشارات «UP/DOWN» لم يُنجز | سياسات ومصادر وشواهد حقيقية و«DEV/OOS/Forward» مستقلة |
| **R06** | «NOT_RUN» للتكامل الحي الشامل من 00 حتى 13؛ هندسة 14/14 محدودة سابقًا | سجلات سلسلة حقيقية لكل مرحلة |
| **R07** | «PARTIAL/HOLD»: ثماني إعدادات سرية لدى المالك لا تعادل أسرار عامل الخدمة المستقل | حيازة عامل خدمة آمنة و«ACK» بعد العلم |
| **R08** | «NOT_RUN» لاختبار السوق البحثي 24 ساعة | 288 خانة صحة و48 فرصة سوق فعلية وغياب موثق |
| **R09** | «NOT_RUN / NO-GO» لإرسال إشارات مؤهلة على مدار 24 ساعة | إغلاق بوابات التشغيل والعلم والربط قبل الإنتاج |
| **R10** | «NOT_RUN» للمراقبة الأسبوعية والشهرية والسنوية | أدلة 7 و30 و90 و365 يومًا بعد الإطلاق |

**حدود الإثبات:** إقلاع 23 نوفمبر الساعة 05:33:17.500 بالتوقيت العالمي؛ الحدث 118 الساعة 05:34:27.685، وأحداث 129/100/200 الساعة 05:34:27.93. الفاحص «Gate 2F» بصمة «SHA-256» e65436f4a2dd060ff71f8a623a835f3e687e3ca5e34b1738f1ae00bc3c11e180، وسجل «Gate 2C» بصمة c23dde8d89880c66275bc323d9770068e42171ba7093f641056cb85457140b70. هذه أرقام نقلها محضر «Issue #77»، لا فحص جديد لأصول المالك. غياب تشغيل يدوي 110 أو تسجيل دخول 119 مقيد بأحداث الاستعلام فقط؛ أربعة من 176 لم تُفسر بعد.

**الأولوية التالية:** «SD Coding» و«Audit» يرفَعان النسخة المنقحة المسموح بها من أدلة «Gate 2F» إلى «GitHub» ويتحققان من البصمة والقراءة الراجعة والاسترجاع المستقل، ثم يغلقان ما تبقى من «R02» دون إعادة تجربة الإقلاع؛ لا فكّ «STOP» ولا تشغيل سوق أو بوتات أو قواعد بيانات أو دمج. الملفات التاريخية التي تصف الإقلاع بأنه لم يُجرّب أصبحت لقطات أقدم فقط.

---

## تحديث مراجعة PM — 23 نوفمبر 2026 — 08:42 الرياض

**الحالة الحاكمة الجديدة للبوابات R00–R02 (التقارير المرسلة من المالك، وليست قبولًا مستقلًا للأصول):** تم التحقق من رأس PR76 `809a8c19814e48c1ae77984ea216a88d2430b773` وشجرته `22592f3a4e74a6146812fcbd96577d89d2d3394c` عبر GitHub. لم تُتح ملفات Windows الأصلية للتحقق المستقل من SHA256 أو كامل نافذة القياس. لذلك لا تُرفع أي بوابة إلى PASS نهائي.

| البوابة | التطور الموثق / القرار |
| --- | --- |
| R00 | PARTIAL — [جرد المالك](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7080197380): تطابق النسخ، STOP، Python3.12.10، عمليتان تشخيصيتان قديمتان READ_ERROR. SHA256 التقرير المحلي `ad9f5f3c9d82f2f1f3b8142440d26059b44d7fe87c6194a9227d017da7515f95`. |
| R01 | HOLD مستقل / OWNER_REPORTED_SCOPED_PASS — [ثلاث قراءات](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7080197380) متباعدة 90 ثانية: 0.0990583، 0.1009754، 0.10333995 ثانية. [Gate1B](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7080330566): عامل مجدول Session0/LeastPrivilege/Password، 0.1026955s مقابل 0.5s، dispersion 0.0139234s، sync age 64.7525259s، cleanup/STOP reported true. SHA256 محلي `d6904a2c08dfc86446857d9b8632120c24889535e5ab738d955e6e64ab7d9187`. الفشل السابق 3.8480093s تاريخي؛ لا يُعامل كآخر قياس مبلغ عنه. مطلوب أصل منقح قابل للتحقق وقياس حديث عند التفعيل. |
| R02 | PARTIAL/HOLD — [Gate2A](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7092224015) preflight only، SHA256 محلي `76b5c89a9fdf64946455a487cd0612d6169d2fd22e3803778105447589563e2b`. [Gate2B ARM](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7092515326) تشغيل تعافٍ فقط قبل الإقلاع Session0 مبلغ عنه، SHA256 قبل الإقلاع `24ddc3260e44407538199433a0a713785702e182648205fa01b2bb4684303a2d`. POST_PENDING؛ لا إثبات إعادة إقلاع أو تعافٍ تلقائي. لا تفترض استمرار STOP من لقطة 2A بعد ARM. |

R03–R10 بلا تغيير. لا إنتاج ولا 24h ولا دمج. الخطوة التالية: تنسيق إعادة تشغيل بشرية بعد حفظ العمل وفق حزمة SD المعتمدة، ثم ADMIN POST مرة واحدة، والتحقق من التنظيف وSTOP وROLLBACK عند الحاجة. نشر أدلة منقحة قابلة للتحقق مع التوقيت والهوية والبصمات، دون أسرار. السجل المؤرخ أدناه محفوظ تاريخيًا.

---


## PM canonical readiness ledger — 2026-11-22 16:30 Asia/Riyadh (v1, owner-requested)
**الحالة ليست LIVE ولا 24/7 الآن.** هذا هو سجل الحالة الحالي الأعلى أولوية بالنسبة للقرارات التاريخية أدناه. تُبقى جميع الإخفاقات والاختبارات السابقة كما هي، ولا يُستخدم نجاح اختبار قديم كتصديق تلقائي للحالة الحالية. هذا القسم يُحدَّث بناءً على أدلة أصلية من جهاز Windows وليس بناءً على التوقعات أو كلام PR وحده.

**مرجع التنفيذ:** [Issue #77](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77) و[أمر SD Coding باستخدام PowerShell يدويًا](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7079726379). **مرجع التسليم المؤرخ:** [HANDOFF.md](https://github.com/scannercrypto0-gif/zs-crypto-signals/blob/13d82aa5fe749885ca4325fd38013900e4fc68ef/handoff/SD-CODING-20261122/HANDOFF.md). **فروع التنفيذ:** [PR75 PM docs](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/75) (Draft)، [PR76 Windows/Market](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/76) (Draft)، [PR78 stacked Telegram/clock](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/78) (Draft؛ base=PR76 branch). **نسخ مرجعية للمقارنة فقط وليست pins أبدية:** main `7b7bb0ebdf0bb601cf1f468c0146c784cb8e0a5f`؛ PR76 `809a8c19814e48c1ae77984ea216a88d2430b773`؛ PR78 `0263c7819c3004a91a79563f1f24f47c609b539d`.

### 1. Status vocabulary / طريقة الحساب
- `PASS_BOUNDED`: نجاح اختبار هندسي أو تجربة واقعية **في حدودها المحددة فقط**، ولا يرقّيها إلى إنتاج.
- `PASS_LIVE_BOUNDED`: نجاح تنفيذ حقيقي واحد أو أكثر ببيانات/خدمة حقيقية مع دليل محدد، وليس استمرارًا مضمونًا.
- `PARTIAL`: جزء من معيار القبول قد تحقق والباقي مفتوح؛ لا تُساوى PASS.
- `HOLD`: عائق نشط أو رفض قياس/فحص، والفعل المحمي **ممنوع** حتى ينتج دليل جديد.
- `NOT_RUN`: لا يوجد دليل تنفيذ فعلي لهذه البوابة، حتى لو وُجدت سكربتات أو اختبارات محاكاة.
- `DEFERRED_BY_OWNER`: نطاق مؤجل صراحة، لا يجوز اعتباره عطلًا أو مطلبًا P0.
- أي حالة يجب أن تذكر: `as_of_utc`, `evidence_url`, `source_head`, `tree`, `Windows actual/fake`, `tests_pass/fail/skip`, `decision_owner/reviewer`, `blockers`, `next_action`. في حالة انعدام الدليل تُسجّل `NOT_RUN`، ولا يُستنتج PASS من حالة `Ready` في Task Scheduler، أو عدم ورود إشارة مؤهلة.

### 2. Stable delivery gates — التنفيذ بالترتيب وشروط الإغلاق
| ID / priority | المطلوب، واعتماد الخطوات السابقة | ما يُعد PASS لإغلاق البوابة | الحالة الحالية بدليل |
| --- | --- | --- | --- |
| **R00 — P0** | SD Coding takeover / read-only baseline، التحقق من main وPR75/76/78 وSTOP وأسماء المهام ونسخة Python3.12.10 وWindows PowerShell5.1 ومسارات D/أدلة SHA | تقرير Windows قراءة فقط يطابق GitHub HEAD/TREE والهوية/الوقت/STOP مع عدم كشف الأسرار | **PARTIAL**: تسليم مؤرخ [HANDOFF](https://github.com/scannercrypto0-gif/zs-crypto-signals/blob/13d82aa5fe749885ca4325fd38013900e4fc68ef/handoff/SD-CODING-20261122/HANDOFF.md)؛ لا يوجد بعد جرد PowerShell جديد لـSD بعد الاستلام |
| **R01 — P0** | إصلاح صلاحية الساعة **قبل** أي جولة LIVE جديدة؛ STOP موجود | قراءة أو قراءات جديدة متباعدة بحساب الخدمة المعتاد، `OPERATIONAL_TIME_ACCEPTED`؛ عدم اليقين ≤0.5s، قِدم التزامن ≤600s، quorum4، step≤0.05s وتوقيع OS/ACL/source صالح، مع ثبات في فترات القياس، لا إعادة استخدام شاهد قديم | **HOLD**: 22 نوفمبر 12:06:59Z `3.8480093s` uncertainty / `3.7609734s` dispersion، رغم نجاح 08:29Z التاريخي `0.10536035s`. [أصل التقييم](https://github.com/scannercrypto0-gif/zs-crypto-signals/blob/13d82aa5fe749885ca4325fd38013900e4fc68ef/handoff/SD-CODING-20261122/clock/normal-assessment.json) |
| **R02 — P0** | Windows least-privilege Serve recovery / STOP, reboot, logoff, crash, network, restore/rollback؛ نبدأ `NO_MARKET` | إثبات Task Scheduler session0/standard-worker دون admin، استمرار سجل الصحة بعد Logoff، إقلاع تلقائي **فعلي بعد Restart بدون STOP متعمد**، استعادة/rollback موثقة ومنع التكرار ولا إرسال سوق/Telegram/SQL في نمط recovery | **PARTIAL/HOLD physical reboot**: Serve/logoff PASS محدود مع 95 heartbeats؛ أول إعادة إقلاع FAIL exit1؛ الإصلاح14/14 Windows code PASS، لكن الإقلاع التالي كان STOP ولا يُحسب PASS. [تقرير الفشل](https://github.com/scannercrypto0-gif/zs-crypto-signals/tree/c0e710a5b1924c74c9056513e3344c7a880acadf/evidence/OPS77-REBOOT-FAILURE-AND-BOOT-FIX-20261122) |
| **R03 — P0** | Source live all eligible Binance Spot USDT same B؛ causal frozen inventory، أربع أطر، حصص API ديناميكية مشروطة | تجربة فعليّة حديثة من إصدار التشغيل الجديد تنتج N/N same-boundary، missing0، hashes/availability/cost/latency/clock PASS؛ كل 429/418/shared-IP HOLD صحيح | **PASS_LIVE_BOUNDED history / RELEASE_VALIDATION_PENDING**: 21 نوفمبر سجل `56/56`، missing0، 59.485s،227 GET،552 weight؛ ليس إثبات جولة الإصدار الجديد أو 24h. [أصل الدليل](https://github.com/scannercrypto0-gif/zs-crypto-signals/blob/3978d7cabc921300e8e9d74d4810b582349d2154/evidence/OPS24-20261121/bounded-full-market/result.json) |
| **R04 — P0** | actual finite Telegram research-only pilot من owner normal token بعد R01؛ 05B C=A، 05C A+B منفصلين؛ لا إشارات غير مؤهلة من05A | raw public response/hash + Telegram owner-private TEST actual API ACK/reply A **و** B بمسارين مستقلين، dedup/unknown failure STOP، دون توصيات تداول | **PASS_BOUNDED offline 28/28 / ACTUAL_NEW_PILOT_NOT_RUN**: اختبارات النقل fake؛ smoke الثلاثة مستقلًا سبق قبوله (7 outputs) لكنه ليس pipeline. [PR78](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/78) |
| **R05 — P0** | QV1 genuine source verifier/science؛ بيانات PIT حقيقية، frozen hypothesis، DEV/OOS/Forward، اتجاهات UP/DOWN منفصلة، costs/uncertainty/baselines | شهادة علمية مستقلة بالإيجاب أو الرفض لكل اتجاه/أفق مع evidence IDs، verified policy/witness/source registries مصدرها إثبات حقيقي، لا fake score/label؛ إنتاج بلا GO = صفر تنبيهات | **HOLD**: `APPROVED_REAL_POLICIES`, `VERIFIED_REAL_WITNESSES`, `VERIFIED_REAL_SOURCES` ما زالت فارغة، VerifiedUpstream يقبل حالات REJECTED فقط. الإشارة الإنتاجية الحقيقية `0` |
| **R06 — P0** | Real Stage00→13 integrated DAG (بدون mock Stage13)؛ data lineage/IDs/archive/outcome | تتبّع أصل بيانات → مدخل/مخرج كل مرحلة → قرار qualified/rejected → 05A/05B/05C → readback → later outcomes، مع SHA وfail-closed لكل انقطاع؛ كود WIP Stage07/13 لا يُقبل تلقائيًا | **NOT_RUN fully live**؛ Stage00–13 `14/14 PASS_BOUNDED` كـهندسة مدمجة في main **لا** تساوي E2E |
| **R07 — P0** | تشغيل Telegram من هوية worker غير حساب المالك؛ DPAPI/ACL، طلبات واستلام، 3 bots منفصلة | 8-field secret custody بهوية worker آمنة دون نشر/صلاحيات زائدة، source/science GO R05، 05A same signal_id A+B و05B archive C=A و05C interactive A+B؛ ACK/de-dup/recovery مثبت | **PARTIAL/HOLD worker**: owner DPAPI fields 8/8 موجودة ومؤمنة؛ worker secret provisioning غير منفذ، production sends=0 |
| **R08 — P0** | Windows public-read-only 24h research **بعد R01/R02/R03** (يمكن موازاته مع R05 علميًا)، لا Telegram production | 24h فعلية UTC/Riyadh، 288 health slots/5min و48 boundary opportunities/30min مع per-boundary N/N/partial/missing، watchdog/clock/quota/cost/reboot/uptime وno silent gaps، PM review | **NOT_RUN**؛ `Ready`/نافذة finite 86400s لا تعني PASS |
| **R09 — P0** | FULL production signals-only E2E 24h بعد R04–R08 + owner exact release merge | إصدار مرتبط بـGitHub HEAD/TREE فعلي، clock/data/science/ack كلها مقبولة، read-only trades=NONE، stage ledger لكل دورة، 288/48 فعلية، تدقيق duplicate/unknown/restore، owner A/B/C routes؛ لا إشارات مختلقة إذا لا فرص مؤهلة | **NOT_RUN / PRODUCTION_NO_GO**؛ PR75/76/78 Draft ولا دمج |
| **R10 — P1** | continuous lifetime after initial production: day/week/month/year | تقارير متكررة day/7d/30d/90d/365d تشمل uptime/downtime, missing boundaries, recovery, disk/backup, API bans, clock drift, all eligible scans, qualified and rejected, Telegram ACK unknown, score/science drift؛ تدريبات restore وتحديثات بإصدارات مع rollback | **NOT_RUN**؛ لا يمكن تصديق عام كامل قبل مرور عام فعلي |

**فرق حاسم:** `PASS_BOUNDED` للكود ليس `PASS_LIVE_BOUNDED` وليس `GO_PRODUCTION`. R03 يثبت جولة واحدة، R08 يثبت 24h قراءة عامة، وR09 يثبت pipeline إشارات بعد التأهيل. احتمال عدم توليد إشارات مؤهلة صحيحة خلال نافذة زمنية لا يُعتبر فشلًا للآلة ولا إذنًا بتصنيع توصيات؛ تُقاس جاهزية مسار إرسال الإشارات بإثباتات الرسائل التجريبية وبأحداث مؤهلة حقيقية إن وجدت.

### 3. تشغيل بعد الإطلاق — acceptance is measured, never assumed
| فترة | مراقبة إلزامية وقرار الإغلاق |
| --- | --- |
| **24h** | 288 health slots +48 فرص مصدر 30m (عند اعتماد cadence)، تغطية N/N/partial، latency p50/p95، quota/headroom، clock/source flags، heartbeat، STOP، سجل إيصال Telegram/ID، حالات فشل وتعافٍ حقيقة |
| **7 days** | تشغيل بلا تشغيل PowerShell يدوي يوميًا، تقرير كل يوم وملخص أسبوعي، reboot/logoff/network recovery، سجل الانقطاعات/ACK UNKNOWN، backup restore check، SLA للمراقبة والتنبيه |
| **30 days** | أرشيف قابل للفحص والاسترجاع، معدل توافر مقاس، تقييم outcomes بعد أفقها، تحديثات Windows والقرص، اختبار rollback ونسخ احتياطي، مقارنة علمية مع baseline بدون هندسة نتائج |
| **90/365 days** | مراقبة شهرية/فصلية وسنوية، incident/RCA، اختبار استعادة متكرر وrotations للأسرار، مراقبة vendor constraints/time/CI portability، وسجلات uptime الحقيقية فقط |
**لا يوجد ضمان علمي 100% uptime لعام على Windows PC/ISP/power واحد.** وضع أهداف availability/SLO وتحديد شروط استثناء الانقطاعات ومقاييس RTO/RPO يحتاج عقد تشغيل منفصل؛ للاقتراب من توافر أعلى يلزم مصدر كهرباء/شبكة احتياطي وربما عقدة failover مع fencing/dedup لا تُضاف بلا دراسة. SQL Server وارد سابقًا لكن **DEFERRED_BY_OWNER** وليس شرط R09، والتداول المالي والأوامر/money transfers **NOT_AUTHORIZED**.

### 4. Continuous evidence update contract — «التحديث المستمر»
1. **Immediately on each real event** (new PR HEAD, Windows PowerShell batch, PASS/HOLD, service STOP/START, reboot, delivery receipt, scientific acceptance, version bump): SD Coding يرفع النتائج غير السرية إلى PR التنفيذي المعني وIssue77 ثم يطلب من PM تحديث هذا الجدول وMASTER/README ضمن **PR75 governance branch**. التحديث لا يتم تلقائيًا لمجرد إرسال رسالة؛ صاحبه/وقته يجب أن يُثبت. إذا غابت أدلة أصلية يبقى `HOLD/NOT_RUN`.
2. **At least daily during execution**: SD Coding يقدم `DAILY_STATUS` في Issue77: latest git HEAD/TREE, gates changed, evidence link and SHA, time of last actual Windows observation, next batch, blocker/owner action, effect on readiness. لا يُدعي أن خدمة تعمل بمجرد عدم وصول إخطار توقف. **After release**, Windows monitor يولّد day/week/month/year reports تلقائيًا مع فحص PM لمخرجات جديدة.
3. **No cross-source rewriting:** PM-owned MASTER/README sections only via PR75 (or successor PM governance PR); SD can comment with evidence, must not edit root docs directly; do not overwrite accepted 28/28, legacy 14/14 or immutably pinned failed reboot. Update front-of-file current section and mark historical material preserved, not silently erased.
4. **Operator batch contract (SD→Owner):** phase ID, exact PR HEAD/TREE clean, D-only paths, Python/PS version, `PRECHECK`/ `APPLY`/ `VERIFY`/ `ROLLBACK` one-line runnable commands, normal/Admin labeling, affected file/test list, expected stdout/exit, STOP/recovery behavior, expected network and secret side effects, no auto reboot or file deletion. Owner executes from local PowerShell, returns **redacted** stdout+exit, retains private raw evidence under D; SD republishes safe SHA receipts and independent GitHub readback. No owner micro-consent loop for already authorized read-only scope, but real admin/UAC/logoff/reboot still require controlled owner participation.
5. **Merge rule:** PR75 governance, PR76 service, PR78 stacked bridge are each Draft and independent exact-head PM/Windows review must be resolved; PR78 cannot be naively merged on main while its base is PR76. Any final merge needs owner exact-head decision and protected GitHub workflow; code merge ≠ production readiness and science qualification. No CI PASS claimed when no runs.
6. **Review cadence:** update the front-of-file status and evidence links after every accepted new original receipt and for each daily checkpoint; a completed gate is permanently tied to its original source version and scope. If a new version regresses, record **new** HOLD, do not rewrite the historical PASS. Keep 03B3 canceled/deferred, and preserve unpublished Stage07/13 WIP without promotion.
7. **Current next command to SD:** `R00_READ_ONLY_INVENTORY`, then `R01_CLOCK_DISPERSION_BOUNDED_REMEASUREMENT`. No next-market or new Telegram calls until clock GO. Existing STOP remains; don't overwrite `D:\ZS-SMART-GATE\repo`.

**Automation status (newly created after v1 publication):** ChatGPT task `ZS Gate Status Audit` ID `6b02ef6a023c8191a341b6b24978bb8d`, DAILY FLEXIBLE, Asia/Riyadh first scheduled 2026-11-23 08:00+03:00, enabled=true. Task checks GitHub and requests evidence-driven PM draft updates only when connector permissions and original pinned receipts permit. It cannot act on owner's Windows, does not guarantee uninterrupted repo sync, and never itself certifies a PASS; SD Coding must still publish real local Windows source receipts and owner run PowerShell batches. A scheduled status check is not a Windows production monitor or an accepted 24h soak.**

---


**Date:** 2026-11-21 (Asia/Riyadh)
**Authority:** Owner's explicit instruction in PM 1.14 conversation to prioritize actual 24-hour, all-market readiness.
**Order:** [Issue #51 — P0-OPS-FULL-MARKET-24H-001](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-7059836760).
**Status:** `ENGINEERING_AUTHORIZED / FULL_MARKET_LIVE_NOT_PROVEN / WINDOWS_24H_NOT_STARTED / NO_TRADING_AUTHORITY`.
**This document is a governance/acceptance contract, not a running service or approval to merge code.**

## Source-of-truth snapshot and prior acceptance

At this direction, `main=7b7bb0ebdf0bb601cf1f468c0146c784cb8e0a5f`, TREE `ac9b9fd8b0c7801183589b027cba1082d616f32b`; PR #74 merged at tested source `3e360d7471fa6d7270ededd77660392e80c8b250` and identical TREE. CLOCK74 accepted **91/91 offline Windows tests**, not a live full-market scan. Last live CLOCK73 on 2026-11-20: 45 historically eligible, 1/45 source-validated, AAVEUSDT both directions NO_TRIGGER, partial exit. Main limits: 11 GET, 140 estimated weight, two pairs, 90-second entry, 110-second capture and 120-second watchdog. The currently checked-in Windows release controller does NOT install an unattended schedule, and last live installed revision is not proven upgraded to CLOCK74.

## Owner priority and staged operating authority

- **P0:** complete all eligible Binance **Spot USDT** source-verified scanning throughout each declared 24-hour period on the owner Windows machine; recover safely from restart, transient network failure, timing issues, quota stalls and power outages without fabricating coverage.
- The owner directs engineering and a **controlled read-only 24-hour research soak**, but starting it is gated by real measured full-market feasibility, a safe least-privilege Windows service and verified stop/rollback. This direction does **not** waive the need for independent PM review and an owner approval of the **exact final merge head**.
- Public read-only market/time calls only under valid source/time/quota guardrails. No trading or keys, real Telegram sends, production external archive, SQL writes, elevated persistent scanner, or unreviewed spend. QV1/real UP and DOWN scientific validity must be decided separately before any production signal.
- Windows 11 / Python 3.12.10 / PowerShell 5.1 on `D:\ZS-SMART-GATE` is the operational and acceptance environment. GitHub is the authoritative repository for ALL permitted nonsecret Windows source, tests, docs, scripts and verifiable evidence. Publish safely screened evidence; never upload secrets/private raw responses without a custody decision.

## Coherent full-market definition

For each candidate 30-minute boundary B, a frozen eligible inventory I of size N forms a declared cohort. Inclusion/exclusion rules and `inventory_id` must be immutable for the boundary. Under the current four-frame cold REST design the *estimate* is `R(N)=3+4N` and `W(N)=104+8N`; the old N=45 suggests 183 GET / 464 estimated weight, NOT an executable limit or authorization. Actual endpoint weight, IP headroom, latency, request/response size and clock viability need measured evidence.

At final decision time D, verify for **each** eligible pair: four closed frames, 22 consecutive closed 5m bars when required, 30m reconciliation with six 5m bars, causally available 1h/4h, original payload hashes, and `as-of/available-at/received-at`. Reassess *all* inputs at D. `MARKET_COVERAGE_VERIFIED` is only justified for N/N valid pairs from the same inventory, boundary and causal decision, never from combining different boundary samples. Missing/late/unknown/stale inputs are `PARTIAL` or `BLOCKED` with reasons.

First candidate: versioned B1 REST budgets with atomic in-flight reservations, measured bounded concurrency, explicit earliest deadline, cumulative weight/bytes/requests, 429/418 safe backoff and durable uncertainty ledger. Do not blindly raise `MAX_REQUESTS` or reclassify partial. If B1 cannot meet a validated snapshot window, propose versioned B2 stream-backed closed-bar cache with reconnect, gaps, retention and PIT controls. Repeating B3 partial batches is NOT full-market acceptance. Preserve CLOCK74 valid 11th receipt and blocked 12th regression.

## Windows service and 24-hour validation contract

Deploy only reviewed exact SHA/TREE and retain `DISABLED` as default. Scanner must run with a least-privilege **nonadministrator** token; isolate a minimal time witness or equally reviewed clock evidence, never turn one-shot Administrator pilot into a persistent elevated task. Explicit, operator-initiated enablement is required after live/full-market acceptance and independent PM review. All service state, original evidence and rollback data remain on D:.

Implement and test: singleton lock; bounded retries/restarts with backoff/circuit breaker; watchdog; atomic journal and cursor; reconcile reception/commit uncertainty on restart; no duplicate reservations or signal events; heartbeat; disk/CPU/RAM/storage retention caps; operator `Status/Stop/Disable/Rollback/Restore`; reboot/network loss; owner-visible summary; source time, request IP quota and source checksum audit. A stop request or untrusted clock, stale data, HTTP 429/418, exhausted budget, corrupted receipts, stale cache or unknown state must degrade or stop safely. Never retry through bans or widen time windows silently.

**24-hour proof** should identify a measured start/end in UTC and Asia/Riyadh, actual continuous process/service uptime, and **288** planned 5m health slots in the day; if the selected full-market policy remains 30m, enumerate **48** eligible boundary opportunities with inventory and N/N/partial statuses individually. Record missing opportunities and downtime. A running process for 24h is not evidence of 48/48 full-market research coverage. The exact intended cadence and availability SLO must be explicit before testing; do not label a 24h experiment 100% ready if an agreed mandatory boundary fails.

## Independent acceptance gates and evidence

| Gate | PASS evidence | Otherwise |
| --- | --- | --- |
| G0 — Code/release | Exact GitHub head/tree, clean Windows checkout, impacted offline tests with original stdout/stderr, exits and SHA256, restore from GitHub | ENGINEERING_PENDING |
| G1 — Live full-market | Frozen I/N, same-B fully causal and fresh N/N pairs at final D, all four frames and raw original hash receipts, actual weight/latency | MARKET_COVERAGE_PARTIAL / BLOCKED |
| G2 — Runtime safety | Least-privilege time and worker, singleton, watchdog, failures, stop/disable, rollback, reboot recovery proven | RUNTIME_UNSAFE |
| G3 — 24h soak | 24h measured Windows read-only run, each intended 5m/30m opportunity enumerated, health/downtime/recovery, zero unauthorized effect | 24H_STABILITY_NOT_PROVEN |
| G4 — Science | Pre-registered real-source PIT DEV/OOS/forward for UP/DOWN QV1, uncertainty/cost/baselines and independent review | SCIENCE_NOT_QUALIFIED |
| G5 — Dispatch | Separate explicit owner authorization, real Telegram A/B/C ACK/dedup/isolation and 05C human inbound, archive readback/restore | LIVE_E2E_NOT_PROVEN |
| G6 — Trading | Not within project; no orders/transfers/keys | TRADING_AUTHORITY_NONE |

G1/G2/G3 enable evidence of a **read-only marketwide 24×7 research service** only; G4 and G5 are required for trustworthy real production signals/delivery. SQL deferred by owner. Never claim 100% launch readiness from G0–G3 alone.

## Mandatory delivery route

1. SD Coding starts from fresh main, ONE focused Draft implementation PR (code, deterministic failure tests, disabled safe install, operator runbook, real-source measurement plan); do not edit MASTER/README root files.
2. Pin exact final implementation HEAD/TREE; owner Windows performs targeted offline tests and bounded live marketwide acceptance, preserving D: raw logs and SHA256. Reuse accepted CLOCK74 91/91 evidence unless affected paths require rerun.
3. PM independently reviews code and privacy-screened GitHub-synchronized originals; owner separately authorizes exact-head merge/deploy. Remote restore verifies the tested code and permitted evidence hashes.
4. Only after G1/G2: start controlled **read-only 24h soak** using the reviewed installed release, with hourly snapshots and post-run acceptance report. If any mandatory gate fails, stop safely, retain durable evidence and return a precise blocker and corrective PR rather than claiming progress.
5. Stage QV1 science and delivery E2E as separately owned workstreams, not as excuses to call mock signals production.

This order is accompanied by the owner instruction recorded on Issue #51. No step above represents a claim that the current Windows machine is running or that all-market coverage was already achieved.

## Owner latest override — 2026-11-21: no per-run approval and maximum safe dynamic capacity

The newer standing owner directive [Issue #51 comment 7061389384](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-7061389384) supersedes references in earlier sections of this document requiring *fresh owner permission* for each public-read-only request, live research boundary, finite 24h nontrading soak, and routine read-only reviewed release. After PM independent technical review, original Windows pinned tests, proved stop/recovery and GitHub branch-rule compliance, SD Coding/Codex may automatically perform these actions under standing permission; PM does not have to solicit ceremonial owner approval repeatedly. This does not eliminate evidence gates or permit unsafe/external side effects. It does not itself merge PR76 or start Windows.

Dynamic rate control replaces unnecessary caps: target up to 98.333% of **measured available legal quota**, illustrated as 5900/6000 REQUEST_WEIGHT points/minute (not request count), reduced by shared-IP observed use, in-flight reservations, all enforceable interval limits and an adaptive uncertainty margin. Never exceed source limits or Retry-After, provoke bans, remove clock/data causal validity, or waste quota when the market snapshot has already completed. PR76 currently still hardcodes 5500 maximum, so implementing this policy requires new source, tests and Windows evidence; no acceptance claim can rely on its old 41/41 tests for modified code.

The PR76 normal-user protected-registry clock profile passed owner-reported real witnesses and replaces the obsolete elevated-only limitation after an independent equivalence assessment, not a new owner permit. The prohibition on trading, transfers, live Telegram/SQL writes and unapproved spending remains. All actual nontrading operation must pass restart/rollback safety checks and continuously report partial/blocked outcomes truthfully.
