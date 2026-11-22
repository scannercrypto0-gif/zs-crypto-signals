# ZS Crypto Signals — SMART GATE

## قرار PM/Owner الجديد — 22 نوفمبر 2026 — خطة READY/GO الحية ومصفوفة PASS/HOLD (SD Coding يدويًا)

**المرجع الحاكم الحالي الأعلى أولوية (لقطة مؤرخة وليست تحديثًا تلقائيًا):** [مصفوفة التنفيذ والقبول والتحديث المستمر](docs/OPS_FULL_MARKET_24H_OWNER_ORDER_20261121.md#pm-canonical-readiness-ledger--2026-11-22-1630-asiariyadh-v1) · [Issue #77](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77) · [تسليم SD Coding المؤرخ](https://github.com/scannercrypto0-gif/zs-crypto-signals/blob/13d82aa5fe749885ca4325fd38013900e4fc68ef/handoff/SD-CODING-20261122/HANDOFF.md). **Codex توقف بسبب limits؛ SD Coding يتولى تطوير GitHub وتجهيز حزم PowerShell؛ المالك ينفذ فقط الفحوص/التغييرات المحلية على Windows ويعيد سجلًا مُنقحًا من الأسرار.** يُعاد التحقق من GitHub HEAD/TREE وWindows عند كل حزمة. لا دمج تلقائي ولا ادعاء تشغيل بالخلفية.

**الحالة الحقيقية الآن:** 14/14 مراحل مقبولة في نطاق `BOUNDED_ENGINEERING` فقط؛ 56/56 زوج Spot USDT من سوق مؤهل في **جولة حقيقية واحدة بتاريخ 21 نوفمبر** (59.485s، 227 GET، missing0) وليس 24h؛ 28/28 اختبار Windows للربط البحثي في PR78 بوسائل اتصال fake وليس تسليم Telegram حقيقي؛ اتصال البوتات الثلاثة السابق نجح **منفصلًا**؛ حساب A+B للـInteractive مخزن Owner CurrentUser-DPAPI 8/8 لكنه لم ينتقل إلى scheduled worker. نجاح Service logoff/sign-in فعلًا محدود؛ **أول actual reboot FAIL**، وبعد الإصلاح لا يوجد reboot نظيف ناجح. STOP_REQUESTED لا يزال قائمًا وTask Ready≠Running. **الساعة الحالية HOLD**: عند 12:06:59Z/15:06:59 الرياض عدم يقين 3.8480093s وroot dispersion 3.7609734s > حد 0.5s؛ لا تُعاد تسمية القياس الصباحي الناجح 0.10536035s على أنه نجاح الآن. QV1 real policy/witness/source registries فارغة، والإشارات الإنتاجية **0**. لم تبدأ private pilot الجديدة أو full E2E/24h. PR75/PR76/PR78 **Draft/unmerged**؛ PR78 مبني فوق PR76. SQL **DEFERRED_BY_OWNER**؛ الأوامر المالية والتحويلات **غير مصرح بها**.

### ترتيب التنفيذ الإلزامي + ماذا يغلق كل مرحلة
| ID | البوابة المطلوبة | PASS الذي يغلقها (غير ذلك PARTIAL/HOLD/NOT_RUN) | الوضع الموثق الآن |
| --- | --- | --- | --- |
| **R00** | استلام SD Coding وجرد Windows قراءة فقط | تقرير فعلي بمطابقة HEAD/TREE والهوية وSTOP/الأسرار المغلقة والمسارات وحالة المهام | `PARTIAL` — تسليم موجود، جرد بعده مطلوب |
| **R01** | إصلاح الساعة أولًا | قياسات مستقلة حديثة تحت0.5s وبسياسة المصدر/ACL/حساب العامل وquorum4 | **`HOLD`** 3.848s |
| **R02** | تشغيل Windows/التعافي | actual service session0 كحساب عادي + reboot نظيف + logoff + network/crash + STOP/restore/rollback | `PARTIAL` مع reboot FAIL |
| **R03** | Binance full-market | جولة حقيقة حديثة same-boundary كاملة N/N و0 missing، قيود quota/clock/closed bars/sha | `PASS_LIVE_BOUNDED` تاريخية 56/56، إصدار جديد غير مقبول |
| **R04** | Telegram research pilot خاص | actual owner A+B replies و05B أرشيف C=A موثق، فقط TEST، بلا إشارات توصية غير مؤهلة | `PASS_BOUNDED` محاكاة؛ actual pilot `NOT_RUN` |
| **R05** | تأهيل علمي QV1 لـUP/DOWN | real verified policy+witness+source، DEV/OOS/Forward PIT frozen مع عينات/تكلفة/قياس مستقل لكل اتجاه | **`HOLD`** registries فارغة |
| **R06** | Full real 00→13 DAG | lineage لكل مرحلة وإشارة qualified/rejected+stable IDs+archive+outcome دون mock substitution | `NOT_RUN` LIVE |
| **R07** | Telegram unattended service | worker secrets/least privilege ثم 05A A+B نفس signal_id، 05B C، 05C A+B، ACK/dedup/recovery بعد Science GO | `PARTIAL/HOLD` worker & science |
| **R08** | 24h بحث حقيقي دون إشارات إنتاجية | 288 خانة 5min و48 فرصة 30min بملف نتائج وN/N/partial وuptime/recovery وأسباب missing | `NOT_RUN` |
| **R09** | 24h FULL live signals-only E2E | إثبات كل سلاسل المصدر/الساعة/الاستراتيجية/التأهيل/الأرشفة/Telegram/التعافي، وبعد دمج النسخ المعتمدة | `NOT_RUN / NO_GO` |
| **R10** | تشغيل ممتد أسبوع/شهر/سنة | أدلة متراكمة 7/30/90/365 يوم، نسخ واستعادة ومراقبة وتقرير SLA وإدارة أعطال وتحديثات | `NOT_RUN` |

**التنفيذ والأولوية:** R00→R01→R02→R03، ثم R08 جمع بحثي 24h **يمكن موازنته مع تنفيذ R05 العلمي**؛ R04 private TEST بعد قبول R01 وهوية A+B، وR06 دمج المراحل (البرمجة والاختبارات ممكنة بالتوازي دون GO)، ثم R07 بعد قبول العلم، ثم R09، ثم R10. لا تُختلق signals إذا لم يحدث تأهيل علمي، وعدم وجود qualified event لا يبيح توصية وهمية. كل بوابة لها دليل Windows أصلي مع HEAD/TREE وSHA256 وraw exit وPM acceptance؛ اختبار fake لا يغلق LIVE، ونجاح الأمس لا يغلق فشل اليوم. راجع العقد الكامل للبنود والـdependency والتراجع.

### بعد الإطلاق: day → week → month → year
- **24h:** مراقبة actual uptime و288 health slots و48 boundary scans، coverage N/N، latency p50/p95، ساعة/حصة/قرص/CPU/RAM، Telegram ACK/unknown/dedup وإثبات الاسترداد.
- **7 أيام:** تقرير يومي آلي + ملخص أسبوعي؛ خدمة تعمل بلا فتح PowerShell يوميًا، إنذار تدهور أو توقف، إعادة تشغيل/شبكة وrestore drill.
- **30 يومًا:** تقرير توافر شهري وأسباب الانقطاع، مراجعة الاستراتيجيات بعد استحقاق outcomes، أرشيف واستعادة، نسخة احتياطية، تغييرات Windows وتعافي.
- **90/365 يومًا:** مراجعات فصلية/سنوية بناءً على **وقت مرصود فعليًا** وليس وعدًا مسبقًا، دوران أسرار، نسخ متعددة وتراجع آمن، قياس الانقطاع/RTO/RPO. لا يمكن ضمان `100% uptime` سنويًا على جهاز واحد وإنترنت/كهرباء واحدة؛ لتوافر أعلى توضع خطة احتياطي وfencing/dedup منفصلة.

### عملية التحديث المستمر في GitHub
**SD Coding** بعد **كل** حدث Windows/Commit/اختبار/حالة HOLD يحدّث Issue77 والتعليق في PR76 أوPR78 مع evidence SHA وhead/tree والنطاق والحالة وما سيأتي؛ و**يوميًا أثناء التنفيذ** يكتب DAILY_STATUS حتى لو `NO_CHANGE`. **PM** بعد مراجعة الأدلة يحدّث مصفوفة PASS/HOLD الحالية في PR75 ثم أعلى MASTER وREADME، دون تحرير الملفات الجذرية من SD وبدون إعادة كتابة PASS/HOLD تاريخي أو حذف WIP قديم. لا تغيّر الحالة إلى PASS من مجرد وصف عمل أو Task Ready؛ كل انتقال نسخة/دليل مؤرخ. استقرار أسبوع/شهر/سنة يُحدَّث فقط بعد مرور نافذته ورصدها. **تم إنشاء متابعة ChatGPT مجدولة يومية ناجحة باسم `ZS Gate Status Audit` تبدأ 23 نوفمبر 2026 حوالي 08:00 بتوقيت الرياض؛ تُراجع GitHub ويمكنها محاولة تحديث فرع PM الحوكمي عند توفر دليل وصلاحيات صالحين، لكن لا تضمن وصولًا مستمرًا إلى GitHub ولا تشغّل Windows ولا تُنتج أدلة اختبار تلقائيًا. SD Coding يظل المسؤول عن رفع تقارير Windows/PR الجديدة.**

**حزمة PowerShell SD→Owner:** افصل `PRECHECK/APPLY/VERIFY/ROLLBACK` في أوامر قابلة للنسخ داخل D، ثبّت الرأس والشجرة وبيئة 3.12.10/PowerShell5.1، ميّز Administrator من Normal، حدّد network/Telegram calls وSTOP/rollback والـexpected output؛ لا تطلب tokens أو DPAPI أو private IDs في الدردشة ولا تُشغّل Restart/Logoff آليًا. لا تكرر اختبارات الـ28/28 المقبولة أو bot smoke سابق دون تغيير معني؛ أول طلب SD الآن `R00_READ_ONLY_INVENTORY` ثم `R01_CLOCK_DISPERSION_BOUNDED_REMEASUREMENT`.

**حاكم الدمج:** مع بقاء PR75/76/78 Draft، كل PR يخضع لمراجعة PM وWindows exact-final-head + قرار دمج مالك منفصل وفق سياسة الفرع؛ لا يعني دمج الكود صلاحية إرسال توصيات أو التداول. التسلسل التقني PR76 قبل PR78 لأن PR78 stacked. يُحفظ سجل 03B3 السابق/Stage07&13 WIP، ولا يُفعّل SQL المؤجل.

---


## تعديل قرار المالك — 21 نوفمبر 2026 — «AUTONOMOUS READ-ONLY / MAXIMUM SAFE CAPACITY»

**الأحدث والأعلى أولوية داخل نطاق الإشارات للقراءة فقط:** المالك ألغى الحاجة إلى موافقته المتكررة قبل طلبات «Binance Spot/time» العامة والجولات الحية وتشغيل خدمة البحث «Windows 24/7» منخفضة الصلاحيات؛ ينفذ «Codex/SD Coding» ذلك تلقائيًا **بعد** اجتياز اختبارات «Windows» الفعلية ومراجعة «PM» المستقلة وتأمين «Stop/Disable/Rollback»، من غير استئذان لكل جولة أو موعد أو تجربة استمرار. يسمح القرار بإتمام مسار الدمج والنشر الروتيني الآمن ضمن نفس النطاق بعد مراجعة رأس الكود وتحقق قواعد حماية «GitHub»، ولا يسمح بتجاوز تلك القواعد أو اختلاق نتيجة مراجعة.

**سياسة الاستغلال:** يُحذف أي سقف داخلي اعتباطي يعوق استيعاب السوق المؤهل، ويُستبدل بميزانية ديناميكية من حدود مزود الخدمة الفعلية لكل «interval/endpoint/IP». الهدف الاقتراب من الحد المسموح **بحسب الحصة المتبقية والمقاسة**: مثلًا حتى 5900 نقطة «REQUEST_WEIGHT» من 6000 نقطة/دقيقة، **وليس** 5900 طلبًا، وفقط إذا سمح الاستخدام الفعلي المشترك والمخزون الجاري وهامش الأمان المتغير بذلك. لا طلبات إضافية لملء الحصة إن انتهى الفحص. تُحترم «429/418/Retry-After»، وتظل صلاحية الساعة والشموع والسببية والاحتياطيات المتزامنة وإيقاف الأعطال إلزامية.

**توضيح الساعة:** مسار «PR #76» الجديد `WINDOWS_STATUS_PROTECTED_REGISTRY_V1` ليس مسار «Administrator» القديم؛ نجاحه على «Windows» ثلاث مرات موثق في التسليم، وهو بانتظار **مراجعة تقنية مستقلة مرة واحدة** لمكافأة الدليل وليس موافقة مالك جديدة. لا تُعاد بوابة «Access Denied» القديمة بعد قبول البديل ضمن نطاقها.

**حدود التفويض:** يخص التشغيل والتحسينات في بحث السوق العام للقراءة فقط. لا تداول أو تحويلات أو مفاتيح مالية، ولا إرسال «Telegram» حقيقي، ولا تغيير «SQL» أو أرشيف إنتاجي خارجي أو إنفاق جديد دون تفويض منفصل؛ ولا يثبت هذا القرار تشغيل 24 ساعة أو صلاحية إشارات «UP/DOWN» العلمية. [الأمر الرسمي «Issue #51»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-7061389384) · [تسليم «PR #76»](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/76).

**الحالة:** `STANDING_OWNER_READ_ONLY_AUTHORITY_GRANTED / QUOTA_DYNAMIC_CHANGE_PENDING / TECH_REVIEW_REQUIRED / 24H_NOT_YET_STARTED`.

---

## قرار المالك الأحدث — 21 نوفمبر 2026 — أولوية التشغيل الحقيقي «FULL MARKET / WINDOWS 24×7»

**توجيه المالك الصريح:** «الاولويه الأن هي تشغيل النظام بجاهزيه حقيقيه يشمل السوق بالكامل علي مدار 24 ساعه نفذ». هذا يحوّل «P0» من مجرد إعداد قرار معماري إلى **تنفيذ هندسي عاجل لالتقاط وتحليل جميع أزواج «Binance Spot USDT» المؤهلة طوال اليوم على «Windows» مع مراقبة واستعادة موثقة**. [الأمر التنفيذي الموحد «Issue #51»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-7059836760) · [عقد القبول](docs/OPS_FULL_MARKET_24H_OWNER_ORDER_20261121.md).

- **نطاق التفويض:** تطوير وتشخيص وتجهيز المسار المتكامل الآن؛ الاتصالات العامة للقراءة فقط ضمن ضوابط المصدر/الساعة/الحصة؛ تجربة استمرار 24 ساعة للبحث فقط **مشروطة** أولًا بإثبات تغطية سوق حقيقية متسقة، وتشغيل «Windows» محدود الصلاحيات مع «Stop/Disable/Rollback»، واختبارات محلية على الرأس النهائي، ومراجعة «PM» وموافقة المالك المنفصلة على دمج «PR» برأسه النهائي. لا تشغيل تلقائي قبل هذه البوابات، ولا تفعيل كامل من عبارة «نفذ» وحدها.
- **الحد الحالي:** إصلاح «CLOCK74» مدمج بـ«91/91 Windows Offline PASS»، لكنه لا يثبت تغطية السوق أو التشغيل الحي؛ سقف 11 طلبًا/زوجين لا يسمح بتغطية الـ45 زوجًا المؤهلة في آخر لقطة. التصميم التاريخي يحتاج 183 طلبًا تقديريًا لنفس 45 زوجًا، **وليس تصريحًا برفع الحصة**. يبدأ «SD Coding» بحزمة تنفيذ واحدة لمسح كامل متسق ومصدر/زمن/حصة ديناميكية، ويبرهن «N/N» داخل نفس هوية السوق والحدود السببية؛ لا تجميع دفعات زمنية مختلفة ولا رفع صوري لـ«PARTIAL» إلى «PASS».
- **معيار 24 ساعة:** سجل «Windows» حقيقي لمدة 24 ساعة مع 288 خانة صحة كل «5m» و48 فرصة قرار «30m» إذا استمر هذا العقد، وكل حالة «PASS/PARTIAL/BLOCKED» موثقة مع أسباب الغياب والاستعادة والوزن والزمن؛ مجرد تشغيل العملية 24 ساعة لا يكفي.
- **الحدود الثابتة:** لا مفاتيح تداول أو أوامر مالية، ولا إرسال «Telegram» إنتاجي أو «SQL» أو أرشيف خارجي دون تفويض مستقل. «UP/DOWN» البحثية ليست إشارات مؤهلة علميًا قبل «QV1» و«DEV/OOS/Forward». لا صلاحية تشغيل ماسح مستمر كمسؤول «Administrator» لمجرد نجاح تجربة الساعة المرتفعة.
- **مرجع الحفظ:** «GitHub» المرجع الرئيسي لأكواد واختبارات وسكربتات ووثائق وكل أدلة «Windows» التي يسمح بنشرها بعد فحص السرية، ويجب إثبات «Push/Remote Readback/Restore». «Windows» سلطة التطوير والاختبار والتشغيل الفعلي، لا «GitHub Actions». «PM» مسؤول التحرير في «MASTER/README»، ودمج أي «PR» جديد يحتاج قرارًا منفصلًا.

**حالة هذا القرار عند تحريره:** `P0_24H_FULL_MARKET_ENGINEERING_ORDERED / OPERATIONAL_ACCEPTANCE_OPEN / NO_24H_RUN_CLAIM / TRADING_AUTHORITY_NONE`. لا يعتبر دمج وثيقة الحوكمة إثبات تشغيل.

---

## قرار المالك الملزم — 18 نوفمبر 2026 — WINDOWS-ONLY ENGINEERING / SCIENCE / MERGE

**الأولوية القصوى:** إعداد نسخة Windows محلية قابلة للتثبيت والتشغيل والمراقبة 24/7، دون تحويل نجاح البرمجة وحده إلى إثبات جاهزية التشغيل الفعلي.

- **الاختبارات والقبول:** كل اختبار وحدة/تكامل/استعادة/تشغيل وسوق يُنفَّذ على Windows جهاز المالك عبر Python 3.12.10 وPowerShell، ويُثبت HEAD/TREE وEXIT والسجلات وبصمات SHA-256 وعدد حالات النجاح والفشل والتخطي والتجربة المستقلة. لا يُستخدم أي تشغيل مستضاف أو نتيجته معيارًا للقبول أو عائقًا للدمج. GitHub مستودع الكود والوثائق والمراجعات والتسليمات فقط، وليس منصة تشغيل المشروع.
- **PR #71:** تفويض مالك **مشروط بالدمج الفوري** بعد تسوية آخر `main`، وإزالة تعريفات المهام المستضافة، واختبارات Windows الكاملة على **الرأس النهائي نفسه**، ومراجعة PM الهندسية المستقلة، وعدم تفعيل إرسال Telegram/الأرشفة التشغيلية/SQL/التداول أو تجاوز حماية الفروع. لا تشترط نتائج الأبحاث العلمية المكتملة لدمج كود بحثي آمن؛ تتطلب قبل تحويل الإشارات البحثية إلى إشارات تشغيل حقيقية.
- **التأهيل العلمي الآن:** كلف SD Coding بتنفيذ جمع بيانات Spot أصلية كافية متعددة الأصول، وتحليل موجّه UP/DOWN بفرضيات مجمدة مسبقًا، وDEV/OOS/Forward وفحوص PIT والتطبيع والتكلفة والتغطية وقرار قبول/رفض علمي منفصل. لم يتم تأهيل أي اتجاه علميًا بعد؛ لا تُنشأ إشارة إنتاجية قبل مصدر وساعة وسياسة معتمدة.
- **تشغيل Windows 24/7:** تثبيت مسار SHADOW للقراءة العامة فقط أولًا، وفحوص الساعة والحصة والتعافي والمراقبة، وبعد موافقة نطاق تشغيل مستقل تُنفّذ تجربة استمرار 24 ساعة موثقة. الصلاحيات الخاصة بالتنبيهات الخارجية والتخزين التشغيلي والتداول منفصلة.
- **الاستمرارية:** كل أحكام الاختبار والتشغيل الأقدم المخالفة لهذا القرار ملغاة؛ سجل القرارات السابق محفوظ في تاريخ Git، ولا يُستعمل كمعيار حالي.

**الأمر التنفيذي المحدث:** https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/71#issuecomment-6972514747

---


## OWNER GOVERNING OVERRIDE — 17 November 2026 — LIVE CONNECTIVITY WITHOUT PER-RUN OWNER APPROVAL

**Binding current owner decision; supersedes all older clauses requiring separate owner permission for live connectivity, live public-source testing, or activation of the signals-only system.** Codex and SD Coding may initiate live network connections, collect public Binance Spot market/time data, test Windows time synchronization, and run the signals-only system whenever operationally needed, without asking the owner again for each connection, test, UTC window, or run. The owner also removed mandatory digital signatures on operator permit files; local operator approval signatures are not a prerequisite for these permitted connections.

**Standing authorization boundaries:** public/read-only market and time access only, no exchange trading/order placement, no trading API keys, no transfers or financial transactions. Do not interpret network-connectivity permission as authorization to send real Telegram messages, write to external operational GitHub archives, mutate SQL/production databases, expose credentials or private data, or enable persistent unattended operation; those side effects need their own defined operating policy. Local test logs and normal development commits/PRs remain permitted. Preserve request rate limits, bounded concurrency, safe stop, source/clock validity, deduplication, audit logs, service terms and zero-cost/no-unexpected-spend controls. Real signal qualification and scientific validity still require evidence; LIVE access alone never means LIVE_E2E_ACCEPTED or trading authorization.

**Operational rule:** Any historical instruction below stating "no live Binance/NTP/Windows network without separate owner approval" is superseded for the read-only live connections and signals-only testing above. Do not delete the historical decision trail; annotate it as historical where needed. PM retains MASTER/README editorial ownership, and PR merges still require separate explicit owner approval.


## OWNER APPROVAL — 16 November 2026 — Stage13 mock engineering merged; 14/14 bounded engineering stages complete; real operational acceptance OPEN

Owner expressly approved exact-head merge of PR #70, documenting completion of 14/14 bounded engineering stages and opening a separate actual operational acceptance track **without authorizing LIVE operations**. PR #70 merged on GitHub at `f0256229c9bbe3baef8ff7311b7d5c7a6b924c26` from evidence HEAD `4ba1de47abea423d13bcecfa74f1ad35d9d8c0ed`; tested code `55f2d898f487d95dda8791083f842aa4a87c7a0c`, tested TREE `ed75ffa7c7877e48344de7950a8befe3a4804226`. PM acceptance comment: [PR #70 comment 6923642503](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/70#issuecomment-6923642503). Owner Windows published targeted tests 9/9 PASS, 0 fail/error/skip, EXIT 0; original 6/6 retained. PM reviewed published GitHub evidence but did not rerun owner Windows or inspect local bytes.

**Stage13 engineering:** `CLOSED_BOUNDED_MOCK_ENGINEERING / MERGED`. **Engineering roadmap:** `14/14 BOUNDED_ENGINEERING_STAGES_ACCEPTED`. This is not real E2E or scientific market validation. **Operational readiness:** `NOT_READY / NOT_PROVEN_LIVE / NO_TRADING_AUTHORITY`. The 24h/288-cycle soak remains **PROPOSED_ONLY / NOT_APPROVED / NOT_RUN**. No genuine Binance receipt, Telegram A/B/C delivery, GitHub production archive/recovery, SQL import, real outcome adjudication, 24/7 Windows health, real API quota, latency or sustained soak has been independently accepted.

**Next governance track:** `OPS_ACCEPTANCE_TRACK_OPEN / EVIDENCE_AND_PREFLIGHT_ONLY`. PM and SD Coding may inventory gaps, propose risk-owned gates and non-live runbooks, and prepare a separate owner approval package for each specific LIVE capability. **No Binance GET, real Telegram send, SQL write, real GitHub archival side effect, persistent Windows scheduler, 24h soak, deployment, credentials exposure or real-money trading authorized by this approval.** Live access and any sustained Windows operation require separate exact-scope owner approval, controls, rollback and review; trading authorization is entirely separate.

---


## OWNER APPROVAL — 16 November 2026 — Stage12 merged / Stage13 engineering authorized

Owner explicitly approved merge of PR #69 at exact evidence HEAD `8f4d5694c15583b28eb1877114bb40b67d8000ca`, closure of Stage12 and start of Stage13. GitHub confirmed merge commit `c7929081f335ead6e607fea56ae08fbadd72b429`. Tested code `02da62a6baf55d8fcbed471e296166b727a006c0`, Git TREE `fb671a632b05781421a7891b334dc7d11b2e5a35`. PM acceptance: [PR #69 comment 6918151222](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/69#issuecomment-6918151222). Published Windows 12/12 PASS, zero failures/errors/skips, EXIT 0, Python 3.12.10; prior 9/9 evidence retained. PM reviewed published GitHub records, did not independently rerun owner-local Windows.

**Stage12 status:** `CLOSED_BOUNDED_ENGINEERING / MERGED / SCIENTIFIC_NOT_EVALUATED`. Engineering stages 00–12: **13/14** bounded accepted; this is not scientific validation or production/trading readiness. Authentic historical+prospective OOS/forward results remain `BLOCKED_REAL_DATA_NOT_VERIFIED / NOT_EVALUATED`. Registered embargo and walk-forward purging remain `NOT_IMPLEMENTED`.

**Stage13 status:** `OWNER_AUTHORIZED_FOR_ENGINEERING_ONLY / OPERATIONAL_ACCEPTANCE_PENDING`. Canonical blueprint: “Full Operational Acceptance on Windows / Recovery / Stability”: scanner→verified Binance data→qualified signal→same ID to Telegram A/B/C+JSON→GitHub readback/recovery→later SQL import with no duplication→outcome evaluator; Windows 24/7 stability, API weights/latency, storage ack/checksum, delivery receipts, source coverage/time drift, stale/future/incomplete candle and duplicate/recovery gates, soak, failure injection, resource health and p50/p95. **Those LIVE endpoints and real E2E are future acceptance requirements, not authorized by this merge approval.** Separate owner permissions and secret/credential handling, source verification, quotas, delivery routing, deployment, and all relevant gates are required before any real Binance GET, Telegram send, SQL write, persistent task or 24/7 run. No real-money trading authorization under any circumstance.

Stage13 immediate permitted deliverable: **offline/synthetic Windows operational harness, mock transport and receipts, restart/recovery/restore, dedup/idempotency, time/coverage/latency/quota/health instrumentation, failure injection, explicit `NOT_PROVEN_LIVE` module matrix and acceptance protocol.** No silent upgrade to operational readiness; fail-closed if any required LIVE evidence is absent. One Draft PR, deterministic tests, raw non-sensitive Windows evidence, PM review and separate owner merge approval. PM owns MASTER/README.

---


## OWNER APPROVAL — 16 November 2026 — «Stage11» merged and «Stage12» authorized

**Owner decision:** «موافق» على دمج «PR #68» بالبصمة المعتمدة، توثيق إغلاق «Stage11» والبدء في «Stage12». «PR #68» merged into `main` at `e1729dd9eaba8955c892908f796a83167ca6f9c9` from exact approved «HEAD» `9953f63ac943a884d3a0c0ac0da404d0ed148a56` (evidence commit), with tested code `1acef001b7b978d75f7d672bc50061a94bf9159a`, tested «TREE» `25ee004a1d1c041aeb0cd25f56be1817c6bab0b9`. «PM» bounded acceptance: [PR #68 comment 6916588246](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/68#issuecomment-6916588246). Published owner-Windows targeted test evidence: 11/11 pass, 0 fail/error/skip, `EXIT=0`, Python 3.12.10; original 7/7 evidence preserved. «PM» inspected GitHub code, test diff and published logs but did not replay the owner Windows run.

**Status:** «Stage11» `CLOSED_BOUNDED_ENGINEERING / MERGED`. Stages «00–11» = **12/14** engineering stages accepted within explicitly bounded scopes, **not** scientific OOS/forward validation, production readiness or trading authority. «Stage12» `OWNER_AUTHORIZED / ENGINEERING_PENDING / SCIENTIFIC_VALIDATION_BLOCKED_UNTIL_GENUINE_DATA`.

**Stage12 canonical scope from v2.1 blueprint:** «Predictive Research, Intraday/Swing Models, Trading Levels». Compare «V1 vs V2», «15m/30m, 1h/4h/8h» and «CONTINUATION/REVERSAL» cohorts; keep «Score» distinct from calibrated «Probability»; horizons «Intraday 1–24h» and «Swing 1–30d»; onset/lead time/persistence/MAE/MFE; trade-plan levels only when price structure, volatility and execution risk validated. Real scientific claims require independently verified historical+forward labeled datasets, frozen hypotheses, walk-forward/OOS/forward studies, realistic fees/slippage, PR-AUC/Brier/calibration/precision/recall, uncertainty and asset/year/regime splits. **Until genuine eligible data is supplied and independently validated, implement only synthetic/offline reproducible research scaffolding, fail-closed availability/label provenance gates, deterministic tests and explicit `NOT_EVALUATED` metrics; do not fabricate results or assert profitability.** Scientific ML is not authorized as predictive evidence absent baselines and validation.

**Governance:** one «Draft PR» from fresh `main`, deterministic targeted tests and non-sensitive Windows receipts when authorized, exact «HEAD/TREE», «PM» review and separate owner merge approval. «MASTER» and root «README» are «PM»-owned. No live «Binance/Telegram/SQL», real-money trading, secrets, production or unapproved data collection.

---


## OWNER APPROVAL — 16 November 2026 — «Stage10» merged and «Stage11» authorized

**Owner decision:** «موافق» على دمج «PR #67» بالبصمة الحالية، توثيق إغلاق المرحلة «10»، والبدء في «11». «PR #67» merged to `main` at `b6a16e0f1d0f2d698bba41a5f47d5e72302fc64e` from exact approved «HEAD» `c30f12942fee58460f9fea649d2fb947ec35615e` (evidence commit) containing tested code `ae621ec262e1935602dbfedeadd69481a6becb7f`, code «TREE» `683c25719698fb993d607f80d47aa2a8ced887ee`. «PM» acceptance: [PR #67 comment 6915503827](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/67#issuecomment-6915503827). «Windows» raw logs and SHA-256 receipts are **published on GitHub** for final targeted 15/15, zero failures/skips, `EXIT=0`, Python 3.12.10; original 12/12 evidence retained. «PM» read published logs and code but did not independently replay local execution.

**Status:** «Stage10» `CLOSED_BOUNDED_ENGINEERING / MERGED`. Stages «00–10» = **11/14** accepted engineering stages within bounded scopes, **not** scientific OOS/forward validation, market-source coverage, production readiness or trading authority. «Stage11» `OWNER_AUTHORIZED / ENGINEERING_PENDING`.

**Stage11 canonical scope from v2.1 blueprint:** «BTC Regime, Market Breadth, Relative Strength, optional News». Synthetic/offline first; «BTC» trend/volatility across MTF, market breadth over eligible universe, relative strength vs BTC, cross-asset correlations, optional ETH/BTC/dominance/event features **only with independently grounded, available-at and published-at timestamps**. «UP/DOWN» and Intraday/Swing context is research-only; missing regime/news must not silently reject a Spot candidate. Event/news discovery is a separate scope requiring approval. Validate PIT alignment, source coverage, no hindsight event tagging, descriptive ablation and hypothetical API cost/latency, with no predictive or trading claim.

**Governance:** single new «Draft PR» from fresh `main`, deterministic targeted tests, published non-sensitive Windows logs and SHA-256 receipts when access exists, exact «HEAD/TREE», independent «PM» review and separate owner merge approval. `ZS_SMART_GATE_MASTER.md` and root `README.md` are «PM»-owned. No live «Binance/Telegram/SQL», trading, secret disclosure, or unapproved data collection.

---


## OWNER APPROVAL — 16 November 2026 — «Stage09» merged and «Stage10» authorized

**Owner decision:** «يتم اعتماد الدمج و توثيق اغلاق المرحله 09 و البدء في المرحله 10». «PR #66» merged into `main` at `7aa03e3254172fad27be489e59d0126684b74a9d` from exact approved «HEAD» `b4ed1ba79b92632d21fc223d20360de8446640c0`, «TREE» `903a7abbe350c5050e4242c76fbd040ac90b3b96`. «PM» bounded engineering acceptance: [PR #66 comment 6912757739](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/66#issuecomment-6912757739). «Codex» reported owner-local «Windows» targeted tests 31/31 pass, zero failures/skips, `EXIT=0`; separate «SHA-256» stdout/stderr receipts stored privately on `D:`. «PM» reviewed source and final diff, but did not independently replay raw logs.

**Status:** «Stage09» `CLOSED_BOUNDED_ENGINEERING / MERGED`. Stages «00–09» = **10/14** engineering stages accepted within limited scopes, not scientific validation, profitability or production readiness. «Stage10» `OWNER_AUTHORIZED / ENGINEERING_PENDING`.

**Stage10 canonical scope from this document's v2.1 blueprint:** «Futures Context, Order Flow and Liquidity». Offline, synthetic-first research of source/availability-bound «OI» current/history and changes, funding rate and timing, long/short ratios, «AggTrades» «CVD» with buyer-is-maker semantics, depth/book imbalance and liquidity zones, and **actual liquidation events only if available**. Data gaps, API weights/costs and provenance are first-class. «OI» increase must not be equated to longs; missing values must not become zero; Futures context may support «UP/DOWN» research but must **never** be mandatory for Spot eligibility. Validate pagination, trade ID gaps/duplicates, source completeness, PIT windows and heavy-source isolation; report descriptive ablation and latency/cost without scientific predictive claims.

**Governance:** one new «Draft PR» from fresh `main`; targeted deterministic tests and research documentation; `ZS_SMART_GATE_MASTER.md` and root `README.md` are «PM»-owned. No live «Binance/Telegram», «SQL», production, trading, secrets or unapproved collection. Require exact «HEAD/TREE», owner-«Windows» evidence when access exists, «PM» review and separate owner authorization before merge.

---


## OWNER APPROVAL — 16 November 2026 — «Stage08» merged and «Stage09» authorized

**Owner decision:** «يتم اعتمد الدمج و توثيق الاغلاق للمرحله 08 و البدء في المرحله 09». «PR #65» merged into `main` at `4ada9c5f90fa13a91c1b88ae0c8495d8a88b414c` from exact approved «HEAD» `a65fd1cd67de1938a07b42af02b2e4d50359dde5`, «TREE» `29ffcdca95ce5cf5f66af2971fbc22d62726bd22`. «PM» bounded engineering acceptance: [PR #65 comment 6910611991](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/65#issuecomment-6910611991). «Codex» owner-local «Windows» report: final 25/25 targeted tests, zero failures/skips, `EXIT=0`; separate «SHA-256» stdout/stderr receipts held on private `D:`. «PM» reviewed the code diff and published hashes but did not independently open/replay raw logs.

**Status:** «Stage08» `CLOSED_BOUNDED_ENGINEERING / MERGED`. Stages «00–08» = **9/14** engineering stages accepted within limited scopes, not scientific validation or production readiness. «Stage09» `OWNER_AUTHORIZED / ENGINEERING_PENDING`.

**Stage09 canonical scope from this document's v2.1 blueprint:** «Fixed Range Volume Profile / POC / VWAP + Trade Plan Levels Research». Offline, synthetic-first, source/time-bound «1h/4h/Daily/Previous Completed Week» anchored windows; versioned objective price levels; deterministic binning/tie-breaks; «Spot Trades/AggTrades» exact when verifiably available, otherwise explicitly tagged «OHLCV APPROX» with provenance and completeness; «POC», optional «VAH/VAL», «VWAP» and signed/absolute distances, cross/retest/hold/rejection and time since cross. No conflation of developing with completed week; no automatic bullish interpretation of proximity to «POC». «Entry/SL/TP» are research-only hypotheses subject to price structure, costs/slippage, validation and comparative ablations, **never TRADE_READY** absent separate science and policy gates.

**Governance:** «SD Coding» executes a single new «Draft PR» based on fresh `main`, tests and research docs, leaving `ZS_SMART_GATE_MASTER.md` and root `README.md` «PM»-owned. Exact «HEAD/TREE», targeted owner «Windows» receipt and independent «PM» review before separate owner merge authorization. No live «Binance/Telegram», «SQL», production, trading, secrets, or unapproved source activation.

---


## OWNER APPROVAL — 16 November 2026 — «Stage07» merged and «Stage08» authorized

**Owner instruction:** approve, merge, document and close «Stage07», then start «Stage08». «PR #64» merged to «main» at merge commit `32e61d2cf4b4105791c3b57e727ab97372ac265c`, exact approved source «HEAD» `12fce8678eab79409dba6172858604d803a6fc92`, source «TREE» `64e3b90d959d8caada098d656ebcfec55894272e`. «PM» bounded engineering acceptance: [PR #64 comment 6908260903](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/64#issuecomment-6908260903). Owner-local «Windows» verification was reported as 16/16 on original and final heads, «EXIT=0» with separate «SHA-256» log digests; raw private logs on «D:» were not independently inspected by «PM».

**Stage accounting:** «00–07» = 8/14 stages accepted for their *bounded engineering scopes only*; not 8/14 of production readiness, scientific edge or profitability. «Stage07» is now **CLOSED_BOUNDED_ENGINEERING / MERGED**, with synthetic-only offline research, not real-source validation, «OOS/Forward» qualification, live alerts or trading authority.

**Next authorized stage:** «Stage08 — Swing Trend / Structure», research-only and offline, focused on «4h» with four source-available «1h» constituents and optional «8h» comparison; non-repainting confirmed «BOS/CHoCH» and swing high/low structure; «EMA/RSI/MACD/50-week MA» and daily/weekly context only when adequate verifiable historical coverage exists. Missing coverage must remain «INSUFFICIENT_HISTORY». No unapproved indicator definitions, weights, thresholds or qualified signal promotion. A separate consolidated engineering order will be recorded in «Issue #51» and require a new «Draft PR» and targeted «Windows» evidence. No new live «Binance/Telegram», «SQL» setup, production or trading.

---


## OWNER CLARIFICATION — 15 November 2026 — Telegram archive first, database import later

**Current binding scope:** The owner **does NOT require** creating, configuring, connecting to, or testing a **SQL Server** (or other analytical database) **now**. The objective is to make Telegram Desktop exports + attachments **verifiable today and importable into an analytical database later**, if and when the owner requests it. This clarification supersedes older README/MASTER or PR wording that treats a **real SQL roundtrip** as a current Stage06B acceptance prerequisite; historical notes are retained as evidence. [Authority: Issue #51 owner clarification](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6894360616) · [MASTER scope decision](./ZS_SMART_GATE_MASTER.md).

- **Prepared now:** versioned local export manifest, `bot_chat` / `personal_chat` ingestion, attachment hash and source-custody verification, canonical Stage05 analytics extraction, normalized candidate/signal/message/indicator/attachment staging, dedup/identity guards, opt-in SQL Server import code and versioned migration. **No SQL connection or actual database import executed**; do not confuse mocked SQL tests with a real database.
- **Owner Windows evidence (2026-11-15):** 2 genuine exported bot-chat JSONs, 39 messages, 5 staged media references, 3 canonical Stage05 archived documents verified offline; 3 archive-caption hash matches + 2 identical-byte media references not independently Telegram-origin authenticated. Scoped `PR #62` Windows bot-chat regressions 4/4 PASS. Zero formatted `ZS05 SIGNAL` entries in the signals export, so no real qualified signal A/B/C cross-chat proof; bot/chat/account role identity remains unverified from independent sources.
- **Do NOT ask for now:** provisioning a SQL instance or database, `pyodbc`, selecting a sandbox, testing database connectivity, applying migration, writing/inserting records, or authorizing SQL credentials/role mapping solely to test SQL. Keep raw exports, attachments, local hashes and private IDs **on the owner's Windows D: drive**, not GitHub.
- **Later, only upon request:** establish source/role authenticity and complete export/media manifests, choose an authorized analytical database/backend, apply the appropriate migration, perform actual transactional import, dedup and readback, and document the measured outcome. No claim of such future operations having already passed.
- **Status:** `FUTURE_DB_IMPORT_CODE_PREPARED / TELEGRAM_DESKTOP_OFFLINE_EXPORT_VALIDATED / LIVE_SQL_ROUNDTRIP_NOT_TESTED / SQL_SETUP_DEFERRED_BY_OWNER`. This decision does not authorize trading, production, additional live Telegram calls, or real signals.

---

## OWNER GOVERNING DECISION — 15 November 2026 — bounded engineering closure and Stage06 development

**Authority:** [Issue #51 owner order #6890458361](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6890458361), [simplified Stage04 #6875213132](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6875213132), and [pre-Stage06 scope #6873534849](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6873534849). **This is the current governing interpretation for Stage00–05 engineering acceptance and Stage06 development**; older inconsistent clauses below remain as historical records, not active gates.

- **Stage00–05:** engineering acceptance is **CLOSED only for the owner-authorized, tested bounded scope**, with source/clock/integrity, scanner/setup, multi-symbol Stage01/03 R0–R2 research with truthful `POLICY_HOLD`, Stage04 Windows continuity, and the accepted scoped Stage02/05 routes. It is **not** a declaration of full-universe/live-human-B-in-this-session/production/24x7/scientific qualification. Distinct evidence is indexed at [PR #55](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/55) and [Issue #51](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51). Owner's prior human A/B routing confirmation is preserved without falsely asserting a new live demonstration.
- **Stage04:** Windows durable local committed-record journal/outbox is operational canonical; restart, integrity, local backup/fresh-path restore, idempotency and unknown-delivery reconciliation stay mandatory. Telegram **05B** is human-facing analytics, not a pending-queue substitute. GitHub stores code/governance and optional bounded sanitized research evidence. **Independent encrypted external media/off-device recovery is OPTIONAL / OUT_OF_SCOPE**, not a prerequisite for engineering closure, Stage06 development or automatic production gating. No claim of physical disaster recovery is implied.
- **Science deferred:** genuine qualified signals, profitability/prediction, OOS/forward edge and numerical score policy are **NOT engineering prerequisites** for Stage06 development. No invented `signal_id`/`score`, no unqualified 05A send, no retrospective relabeling of `NO_BREAKOUT`.
- **Stage06 engineering coding is AUTHORIZED NOW** on pinned approved sources. Stage06A outcome chronology starts from provable post-delivery availability with `NO_ENTRY` and same-candle ambiguity reported conservatively; Stage06B is verified Telegram Desktop export/attachment to normalized SQL dedup/import, subject to actual files and separately checked database execution. No new Binance/Telegram calls or consumed-session replay. **Production and trading remain disabled.**
- The specific accepted Windows receipts remain valid for their tested SHAs; changes require only impacted tests. Engineering code acceptance, live operations and scientific claims are separate.
- **Source control vs local verification (owner clarification 2026-11-15):** The eventual operational target and primary engineering test environment is the owner's **local Windows** machine. **GitHub is the source/governance repository**, not the production runner or mandatory hosted-test service. Actual repository branch protection/review rules, where configured, still must be respected or changed through normal owner-controlled settings; do not force a bypass. Production/trading/live Telegram authorizations remain separate.


---

## Pre-Stage06 engineering acceptance — owner directive 6873534849

### Stage04 local continuity — owner decision 6875213132

**SUPERSEDED:** Earlier requirements for an external encrypted device or off-device recovery are optional under the [owner-approved simplified design](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6875213132). Windows durable local storage holds committed records and pending delivery state. Local backup/restore, fresh-process readback, SHA-256 integrity and duplicate protection remain required. Telegram 05B is the human-facing archive. Known offline delivery can wait locally; ambiguous sends require reconciliation before any retry. GitHub may hold bounded sanitized research evidence and is optional for runtime continuity.

**SUPERSEDED FOR PRE-STAGE06.** Any earlier requirement to observe or send a real qualified signal, prove prediction accuracy or profitability, or establish an out-of-sample or forward edge is deferred until the complete system is built and separately authorized. This clarification follows the [owner directive](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6873534849).

Engineering acceptance requires evidence for the implemented and authorized Stage00–Stage05 workflow, including source integrity and timing, journal readback and local recovery, and routing and duplicate prevention. A bounded live workflow may observe zero qualified signals. In that case 05A stays silent. Validate its qualified routing offline. 05B archives only authorized research/rejections. 05C requires actual authorized human A/B for live proof. Existing one-shot budgets and consumed-session guards apply. Scientific records, signal integrity rules and the independent recovery requirement remain in force. This clarification does not start Stage06 or authorize production, trading, or another live session.

---


## قرار موحد للمراحل 03–05 — 12 نوفمبر 2026 — صلاحية المالك المفوضة للتصحيح

**المرجعية الحديثة:** قرار المالك المباشر باستكمال مطابقة المراحل 03–05، مع الحفاظ على صحة البحث والأدلة. هذا الملحق **توضيح سياسة حاكم** ويعلو على العبارات التاريخية المتعارضة في هذا الملف، دون حذف سجلاتها. **لا يعني اعتماد التشغيل الحي أو تحقق اختبارات جديدة لم تقدم نتائجها بعد.**

| المجال | القرار التنفيذي الدائم | حدود الإثبات الحالي |
|---|---|---|
| **Stage03 / Intraday UP** | تشغيل تقييم بحثي مستقل عند إغلاق **30m + ست شموع 5m مغلقة** للأصول التي تصل من قائمة سوق مغلقة المصدر؛ اكتشاف **Setup v1.1 على 5m** مصدر اختياري للمرشح، **وليس شرطًا عامًا** لتقييم 30m. فحص السياق المغلق والسببية وBase/Quote منفصل عن بوابات التأهيل النهائي. | لا تُعد نتيجة **NO_BREAKOUT** القديمة رفضًا لإشارة 30m؛ ولا يجوز إنشاء Signal ID أو درجة نهائية أو تحديد حدود N01/N02/N04/N03/SEM دون معادلات متحققة ومعايرة خارج العينة وشاهد مصدر/وقت مستقل. |
| **Stage04 / authority** | **Windows** هو المرجع التشغيلي النهائي عند نشر النظام، وفق قرار **MASTER v1.36** الأحدث، مع سجل محلي متين واختبارات نسخ احتياطي مشفر خارجي واستعادة من جهاز/وسيط مستقل. **GitHub** هو المصدر الدائم للكود والقرارات والعقود والأدلة البحثية المسموح نشرها، وتحفظ فيه سجلات الدراسات التاريخية كما هي. قرار Windows التشغيلي ينسخ شروط **GitHub-all-runtime-data** القديمة *مستقبليًا فقط*. | وجود SQLite محلي أو تجربة GitHub application readback أو backup في مجلد آخر لا يثبت الاستعادة من قرص مستقل/تشفير الوسيط أو WORM؛ لا ترقية الإنتاج قبل إثبات مستقل. |
| **Stage05 / three bots** | ثلاث هويات بوت مستقلة: **05A Signals → Chat A+B** للإشارة المؤهلة الواحدة، **05B Analytics → Chat C**، و**C=A** على مستوى الحساب البشري عبر بوت مختلف؛ **05C Interactive → A+B** طلبات قراءة فقط، ولا تولّد إشارة. نفس Signal ID عبر وجهات إرسال المؤهل الثلاث، لكن لكل وجهة إيصال مستقل. أرشفة المرشحات المرفوضة الفعلية إلى 05B دون Signal ID مزيف. | بوابات الإشارة الحقيقية غير مصادق عليها بعد؛ لا يعتبر نجاح mock، أو 05C تاريخي على مستخدم واحد، إثباتًا لتكامل نشر/استرجاع حقيقي. لا تغيير لأسرار البوت أو المعرّفات الحقيقية في هذا المستند. |

**قواعد القبول:** (1) تطابق العقد مع الكود على بصمات Git محددة؛ (2) اختبارات «Windows» مستهدفة جديدة ومتأثرة وسجلاتها الخام مع SHA-256؛ (3) قرار علمي مبني على معايرة وأدلة زمن/مصدر قبل أي Qualified Signal حقيقية؛ (4) نسخ تشغيلي خارجي محمي واستعادة مستقلة قبل الجاهزية الإنتاجية؛ (5) تحقق تفصيلي لتوجيه وإيصالات A/B/C وعدم التكرار قبل الجاهزية الحية. **لا تُرفع المرحلة إلى FULL MATCH لمجرد تغيير نص الوثيقة أو قبول Fixtures اصطناعية.**

---


## أحدث توزيع معتمد لحسابات «Stage05» — 9 نوفمبر 2026

**قرار المالك الأحدث:** [«Issue #51» #6738346711](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6738346711). **ثلاثة بوتات مستقلة، وحسابان خاصان فقط؛ لا مجموعة أرشيف.**

| البوت | الحساب الشخصي «A» | الحساب الثاني «B» |
|---|---|---|
| «05A Signals» | إرسال الإشارة المؤهلة | إرسال الإشارة المؤهلة |
| «05C Interactive» | استعلام ورد مستقل | استعلام ورد مستقل |
| «05B Analytics» | «C» = نفس الحساب الشخصي «A» للأرشفة عبر البوت الثاني المستقل | لا إرسال |

التفرد المطلوب **بين هويات وتوكنات البوتات الثلاثة** وبين «A/B» في بوت الإشارات؛ **لا يصح اشتراط اختلاف رقم «C» عن «A»** عبر بوتين مستقلين. تبقى سجلات الإرسال منفصلة حسب هوية البوت والوجهة والحدث. أفاد المالك باكتشاف معرفَي الحسابين محليًا على «Windows»، ومطابقة الحساب الشخصي في بوت الأرشيف؛ هذا **إيصال محلي مبلّغ وليس إثبات إرسال حي أو تحقق «PM» بايتًا ببايت**. **القيم الرقمية الحقيقية والتوكنات تبقى محلية على «Windows» فقط**، ولا توضع في مستندات أو تعليقات أو سجلات منشورة على «GitHub». يلزم تصحيح شرط التهيئة في «PR #53» واختباره بمحاكاة «Windows» مستهدفة قبل أي تجربة اتصال حقيقية منفصلة التفويض. كل التشغيل الحي والإنتاج والسوق والتداول والدمج غير المفوض ما زال محظورًا.

---


## قرار Stage05 النهائي — ثلاثة بوتات Telegram مستقلة (9 نوفمبر 2026)

**هذا القرار أحدث من أي وصف تاريخي لبوتين أو إيقاف تطوير Stage05 في الأجزاء القديمة من README.** [العقد المعتمد في MASTER](./ZS_SMART_GATE_MASTER.md) و[Issue #51](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51) هما المرجع التنفيذي. **مسموح تطوير كود ناقل «Telegram Bot API» حقيقي وتجهيزه واختباره بمحاكاة محلية على «Windows» دون اتصال حي. «Offline» يصف أسلوب الاختبار والتشغيل الحالي، ولا يعني وجوب الاكتفاء بكود وهمي. كل اتصال «Telegram» حقيقي، إرسال/استقبال/«Polling»/رد، وإدخال أسرار أو تشغيل سوق/إنتاج/تداول محظور دون تفويض مالك مستقل محدد.**

| الجزء | البوت المستقل | الوجهات/الوظيفة |
|---|---|---|
| **05A Signals** | **البوت الرئيسي الموجود لدى المالك** | إرسال كل إشارة مؤهلة إلى **Chat A + Chat B**، بنفس `signal_id`، درجة متاحة أو سبب عدم توفرها، وخطة صحيحة أو `RESEARCH_ONLY` |
| **05B Analytics** | **بوت أرشفة مستقل** | **Chat C واحدة**: كل المؤهلة **وكل المرشحات المرفوضة** وأسبابها ونتائج Gates والمؤشرات المنفذة والقيم والمصادر والتوقيتات، مع ملخص + JSON بإصدار + SHA-256 ومرجع أصل |
| **05C Interactive** | **بوت استعلام ثالث مستقل** | استقبال `btcusdt`/`ethusdt`/`solusdt` مباشرة، والتحقق من الصلاحية والرمز والرد بقيم المؤشرات المبنية فعلًا ونتائجها/وقت البيانات/أسباب الغياب، دون إنشاء Signal أو بثها |

**SQL Server:** `candidate_id` PK للمؤهلة والمرفوضة؛ `signal_id` PK للمؤهلة فقط و**نفسه** في Chats A/B/C؛ المرفوضة ليس لها `signal_id` مزيف. سجلات الإرسال مستقلة بمفاتيحها وتوقيتها و`UNIQUE(bot_id,chat_id,telegram_message_id)`، وتربط PK/FK بين `candidates`, `signals`, `candidate_decisions`, `indicator_values`, `telegram_deliveries`, `signal_outcomes` وغيرها. التصدير من Telegram `result.json` يتطلب extractor والتحقق من المرفقات/البصمات ثم استيراد SQL، ولا يعد وحده أرشيفًا كاملًا. **Stage06B** يحتفظ بكود الاستيراد المعياري للمستقبل؛ **تجربة الإدخال والاسترجاع الحقيقي من قاعدة بيانات مؤجلة بقرار المالك 15 نوفمبر 2026، وليست شرطًا حاليًا**.

**التوقيت:** حفظ UTC ISO-8601 للتواريخ والساعات والدقائق والثواني، ومللي ثانية عندما تتوفر **فعليًا**، لوقت الشمعة والإتاحة والقرار ومحاولة الإرسال وقبول Telegram **لكل Chat على حدة**؛ حفظ دقة المصدر/عدم يقين الساعة وحالات `UNKNOWN_DELIVERY` دون اختلاق توقيت. `datetime2(3)` مناسب في SQL Server حين تسمح الدقة. لا استخدام بيانات مستقبلية في تقييم الإشارة.

**الحالة:** `STAGE05_THREE_BOTS_DESIGN_OWNER_APPROVED / OFFLINE_DEV_AUTHORIZED / LIVE_TELEGRAM_FULL_HOLD`. Stage00–04 synthetic E2E مقبولة 9/9 وPR #50 مدمجة؛ لا يعني ذلك وجود إشارات مؤهلة إنتاجيًا. تفاصيل المعايير والأمان والأرشفة في MASTER وIssue #51.

---

## قرار المالك الحاكم — 10 نوفمبر 2026 — تشغيل الاختبارات الحية دون بوابة موافقة «PM»

**الحالة: `OWNER_DIRECT_AUTHORIZATION / PM_PRELIVE_GATE_REMOVED / EFFECTIVE_IMMEDIATELY`.** أصدر المالك توجيهًا صريحًا بتصحيح سلسلة الأوامر «003» وإزالة اشتراط مراجعة أو موافقة «PM» على بصمة «SHA»، أو «HEAD/tree»، أو تقرير «Preflight»، أو الإذن بإطلاق **اختبار التكامل الحي المحدود الموافق عليه من المالك**. لا يجوز لـ«PM» أو «Codex» إيقاف تشغيل اختبار «Stage00→05» المأذون به لمجرد غياب `PM EXACT_SHA_GO` أو مطالبة المالك بجولة تفويض إضافية لنفس النطاق. ينسخ هذا القرار **شرط موافقة «PM» السابقة للتشغيل فقط** في أوامر «Issue #51» السابقة، وفي «PR #55» وعقد «LIVE_SESSION_CONTRACT — FINAL-003»؛ وتظل تقارير «PM» السابقة سجلًا تاريخيًا، ويمكن إجراء المراجعة المستقلة **بعد** التنفيذ دون جعلها شرط بدء.

**التفويض المباشر الحالي:** تنفيذ جلسة اختبار تكامل حي **واحدة، أمام المستخدم وعلى جهازه «Windows» فقط** في النطاق الهندسي «Stage00→05»، بعد فحوص محلية آلية تجتاز شروط الأمان، باستخدام بصمة الكود الفعلية المسجلة (للتتبع والتدقيق **لا للاعتماد الإداري**). العقد التنفيذي الأصلي للجلسة «FINAL-003» يحدد حدًا أقصى **6 طلبات «Binance Spot» عامة للقراءة فقط، و20 طلبًا إجماليًا إلى «Telegram Bot API»، و3 عمليات إرسال، و240 ثانية**، بلا إعادة محاولة تلقائية، بلا «WebSocket»، بلا مفاتيح سوق خاصة أو تداول، وبلا تشغيل دائم. المطلوب إثبات اللقطة الجديدة → «Scanner/Setup/Stage03» → حفظ «SQLite» واسترجاعه → أرشفة «05B» → ردَّي «05C» إلى الحسابين البشريين «A/B» من **اللقطة نفسها**؛ «05A» لا يرسل إشارة غير مؤهلة. يُعتد بنتائج الاختبارات السابقة ولا تُكرر تجربة اتصال البوتات المنفصلة.

**تعليمات ملزمة لـ«Codex/SD Coding»:**
1. ابدأ فورًا تصحيح **كود مشغّل «FINAL-003»** وأي حارس يفرض `PM EXACT_SHA_GO` أو `PM_REVIEW_APPROVED` أو `OWNER_SESSION_APPROVED` **إضافيًا لنفس جلسة الاختبار التي فوّضها المالك الآن**، مع استبداله بتحقق داخلي من مصدر هذا القرار وحدود الجلسة، وليس بتجاوز حراس المصدر والـ«SHA» والأسرار و«DPAPI/ACL» والجلسة المستهلكة أو الأعداد القصوى. اجعل تقرير الفحص المحلي الفاشل يوقف التشغيل بسبب **خلل تقني فقط**، لا بسبب عدم وجود توقيع «PM». عدم تطابق بصمة الكود مع التنفيذ الفعلي عيب تقني يُصحح، لكنه لا يستلزم موافقة «PM» على البصمة الجديدة.
2. شغّل الاختبارات الجديدة والمتأثرة **محليًا على «Windows»**، ثم الفحص المحلي الآلي، ثم الجلسة الحية مباشرة بعد نجاحهما وفق الحدود المثبتة. عند الحاجة لعمل بشري فعلي، وجّه المالك لإرسال `BTCUSDT` من حسابَي «Telegram» المستقلين «A/B» فقط بعد `READY`؛ **هذا إجراء تشغيلي، وليس طلب موافقة «PM» أو جولة موافقة مالك جديدة**. لا تنتحل رسائل بشرية ولا تُحمّل أسرارًا إلى «GitHub».
3. إذا اكتُشفت مخالفة صلاحيات أو تعارض مستهلك «getUpdates» أو اتصال/إرسال مجهول أو انتهاء الجلسة، **توقف لأسباب أمان فنية حقيقية** مع إيصال واضح؛ لا تمسح سجلات أو جلسات مستهلكة، ولا تُعِد الاتصال تلقائيًا، ولا تغيّر الميزانية لتجاوز التوقف. لا تستخدم تجربة «05C Round2» القديمة المعلقة لإعادة إثبات الاتصال، ولا تحول «TEST ONLY» إلى تشغيل إنتاجي.
4. سلّم في «Issue #51» و«PR #55» النتائج الفعلية وبصمات الكود والأدلة المنقحة وعدادات الطلبات وقرار `PASS/PARTIAL/BLOCKED`، ولا تكتب «100% LIVE» دون برهان. مراجعة «PM» اللاحقة **للتوثيق والتدقيق فقط**، وليست تصريح تشغيل.

**الحدود التي لا تتغير:** هذا القرار لا يعتمد سياسة «QV1-B» الرياضية غير المحسومة، ولا يسمح باختلاق إشارة أو «Score»، ولا يجيز دمجًا في «main» أو «Stage06» أو تداولًا أو تشغيلًا إنتاجيًا مستمرًا. **سلطة اختيار/اعتماد السياسة والدمج والإنتاج تبقى للمالك**. مبدأ العمل المستقبلي: **إذا فوّض المالك اختبارًا حيًا بنطاق محدد فلا توجد موافقة «PM» إضافية على بصمة الكود أو إطلاقه؛ حراس السلامة التقنية والحدود المصرح بها تظل إلزامية**.

**المرجع التنفيذي:** [«Issue #51» — أمر الإغلاق الموحد «003»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6767278722). هذا التصحيح أحدث منه ويعلو عليه عند تعارض الأذونات.

---


## إغلاق «Stage03» دون حلقة شروط — معيار «C1–C4» الحاكم، 8 نوفمبر 2026

**المرجع المُلزم:** [تدقيق «PM» النهائي](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6721751412)، و[قرار المالك لصحة المكونات أولًا](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6706564402). **إغلاق «03» أثناء البناء يثبت الحساب والمنطق والمصدر والتكامل، ولا يشترط جودة أو ربحية الإشارة النهائية.**

- **«C1»:** تعريف وحساب «N01–N12» صحيحان مع مراجعة الدلالات الأربع والمرجع الحسابي المستقل.
- **«C2»:** مصدر/وحدات/شموع مغلقة/توقيت «UTC» و«as-of» وحراس رفض المصدر والبيانات الخاطئة، دون ادعاء «PIT» تاريخي غير مثبت.
- **«C3»:** تكامل «03A/R2» و«Setup v1.1» والهوية البحثية وأسباب التأهيل/الرفض؛ لا تفعيل إنتاجي.
- **«C4»:** استخدام الاختبارات المقبولة، وتحقق «Windows» محلي موجّه للفجوات فقط، واختبار وظيفي للمرحلة ومراجعة «PM» وقبول المالك.

اختبارات «blind OOS/Forward/N_eff/Spot economics/predictive edge» **مؤجلة إلى ما بعد اكتمال بناء «SMART GATE»**؛ «00–04 E2E» الشامل بوابة لاحقة منفصلة. لا تُضاف شروط إغلاق جديدة إلا بخلل جوهري محدد أو قرار مالك. سجل «31.8%» التاريخي لا يقيس التقدم الهندسي بمعيار «C1–C4». «Stage05» لا تزال معلقة بالكامل. «PR #46» مدمج، **ولكن إغلاق «03» لم يُعتمد بعد**.

---


## سياسة المالك الأحدث — 8 نوفمبر 2026 — الاختبارات على «Windows» فقط

تبقى «GitHub» منصة الكود والمراجعات والطلبات والحوكمة، وليس بيئة التنفيذ المعتمدة للاختبارات الجديدة.

- تُثبت الاختبارات المحلية على بصمة «SHA» محددة، مع أمر التشغيل وبيئة «Python» والنتيجة ورمز الخروج والسجلات القابلة للمراجعة؛ لا تُعلن نتيجة ناجحة دون تنفيذ موثق، ولا تُعاد الاختبارات المقبولة بلا سبب.
- لا يجوز تجاوز حماية فرع إلزامية أو تغيير إعداداتها دون قرار مالك مستقل.
- هذا **تغيير لمكان تنفيذ التطوير والتحقق فقط**، وليس إذنًا جديدًا لتشغيل السوق أو «OOS/Forward» أو «Telegram» أو التداول أو «Stage05»، وليس تصريحًا بنشر النظام الكامل محليًا الآن.
- الأدلة التاريخية محفوظة؛ كل «PR» مفتوح أو مستقبلي يتبع القرار الأحدث. المرجع التفصيلي أعلى «ZS_SMART_GATE_MASTER.md».

---


## القرار المعماري الدائم — 5 نوفمبر 2026 — «MASTER v1.37»

**التفريق الإلزامي بين التطوير والاستضافة النهائية؛ المرجع الحاكم [«MASTER v1.37»](ZS_SMART_GATE_MASTER.md).**

- جميع حدود كل تجربة وأذوناتها تظل سارية.
- **بعد اكتمال المشروع واعتماد تسليمه:** ننزّل المشروع بالكامل على جهاز المالك «Windows» ليكون **المستضيف النهائي** للتشغيل المحلي 24/7، بما فيه المسح وجمع البيانات والتحليل وإرسال الإشارات عند اعتمادها والسجلات التشغيلية المحلية. يُبنى لاحقًا «Windows Runner» للتحكم في التشغيل والإيقاف والمراقبة والتعافي.
- التحقق من التكامل والاسترجاع واستمرارية التشغيل على جهاز المالك يتم عند مرحلة النشر النهائي.
- **«GitHub» يظل مرجع المصدر والإصدارات والحوكمة والتحديثات** حتى بعد النقل؛ استخدامه التطويري والتاريخي لا يتعارض مع استقلال الاستضافة النهائية.
- الأدلة والتاريخ السابقان محفوظان. **«Stage05» لا تزال معلّقة حتى إغلاق «Stage03» بالكامل.**

---

## سياق وسجل الحوكمة السابق — «v1.36»

## الحالة الحاكمة — 5 نوفمبر 2026 — «MASTER v1.36» وقرار الاستضافة النهائية

**المصدر الأعلى:** [«MASTER v1.36»](ZS_SMART_GATE_MASTER.md) و[قرار المالك/«PM 1.4» في «Issue #25»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6651311081). الأقسام الأقدم أدناه تاريخية إذا خالفت هذا القرار.

- **«Windows» للاستضافة النهائية 24/7:** تشغيل الماسح والإشارات والبوتات والسجلات التشغيلية المحلية. سيُصمَّم «Windows Runner» لاحقًا للتحكم في التشغيل والإيقاف. لا يشترط نجاح حفظ سجل على «GitHub» لإرسال «Telegram» النهائي. النسخ الاحتياطي واستعادة السجلات المحلية شرط قبول مستقبلي لا افتراض أن ذلك مُنفذ الآن.
- **المرحلة «04»:** إغلاق إداري ناجح **في نطاق اختبار حفظ/استرجاع «GitHub» التاريخي «APPLICATION_ONLY»**، لا يعني نجاح تشغيل «Windows» أو قاعدة سجلات محلية. لا تُحذف أدلة «GitHub» القديمة.
- **المرحلة «03»:** مقبولة هندسيًا جزئيًا، والعلم لم يُغلق. نُفضل مسار كشف بسيطًا شفافًا وإثبات ترتيب الاستلام المستقبلي مع شموع مغلقة و«DEV/OOS» منفصلين؛ لا ندّعي «historical PIT» أو احتمال نجاح مُعاير بلا دليل. إغلاق «03» بالكامل يحتاج عقد قبول مراجعًا ومراجعة مستقلة وقرار مالك.
- **المرحلة «05»:** `STAGE05_FULL_HOLD` — لا تطوير ولا محاكاة ولا إرسال قبل إغلاق «03» بالكامل. عقد البوتين والوجهات الثلاث يظل متطلبًا معتمدًا للمستقبل.
- **هوية الإشارة:** المرشح البحثي ليس تلقائيًا إشارة. الحدث المكتشف يتطلب شرط كشف حتميًا ذا إصدار على بيانات مؤهلة ومتاحة؛ لا تحجب الإشارات المكتشفة بسبب انخفاض «Score»، ولا تُرسل نسخ متكررة لنفس الحدث/الوجهة؛ سجل الإرسال النهائي محلي على «Windows».
- **«020-B» لم تُنفذ:** نافذة 5 نوفمبر 2026 الساعة 06:00 «UTC» انقضت التخزين المحلي والساعة والنافذة الجديدة تحتاج تحققًا قبل أي اختبار عام حي. تصريح المالك ببيانات «Binance» العامة للتكامل **محدود ومشروط بالجاهزية**، لا يسمح بالتداول أو التشغيل المستمر.
- **الدمج:** طلبات «PR #26–#31» تُراجع مستقلًا قبل الدمج حسب الاعتماديات وتغيير المعمارية.

---

## أحدث استرداد «020-A» — 4 نوفمبر 2026 — كود «Codex» موجود ومختبر خارج «GitHub»

**المرجع:** [«MASTER v1.35»](ZS_SMART_GATE_MASTER.md) و[تقرير «PM» بعد فحص الأرشيف #6633084680](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6633084680). استلمت «PM» أرشيف المالك `ZS_ORDER020_CODEX_RECOVERY.zip` وفيه **كود «020» الفعلي**، وليس مجرد سجل تقدم. ظهرت ملفات المشغل الأربعة `pilot020*.py`، واختباراته وسكربتات «Preflight» وخطة «020»؛ وثبت تطابق ملفات «019» السابقة **184/184** ببصمات «Git blob» مع رأس «PR #30». لم تُكتب الملفات المجمدة أو تُبدل.

**الاختبارات:** سجلا «Windows» المستردان يوثقان `617/617` ثم أحدث `619/619` دون تخطٍ. أعادت «PM» تشغيل نفس مصدر الكود خارج جهاز المالك على «Linux»: **38/38 اختبار «020»** و**618 منفذًا من 619 مكتشفًا** (واحد «Windows» غير منطبق)، ومحلل «WebSocket» دون اتصال سوق ناجح. النجاح هندسي Offline فقط، وليس تجربة سوق/أداء استراتيجية أو إثبات `UTC`.

**حزمة استكمال متاحة للمالك:** `ZS_ORDER020_RECOVERED_CODE_AUDITED.zip` تضم **17 ملفًا كوديًا/عقديًا + تقرير SHA256**، حجم 41,455 بايتًا، `SHA256=6f41c6b64534798b00c1ba5cdce8be669a941dfb62c9ebbca356e85628027026`. استُبعدت أسرار وملفات سوق/سجلات/بصمة المضيف من حزمة الكود المصغرة. **لم تُنشر بايتات كود «020» على «GitHub» بعد**؛ ملف الحزمة لا يُستدل عليه من اسم أرشيف المالك الأصلي، ويجب تسليمه إلى «SD Coding 2.2» عبر قناة معتمدة للنشر والفحص.

**التعليمات الحاكمة:** لا تعِد بناء مشغّل «020» من الصفر. ملف فحص «Windows» الأصلي ذكر مانع صلاحية «GitHub» المحلية لا تستخدم رموز متصفح بديلًا. «020-B» تحتاج `020_FIELD_PREFLIGHT_PASS` مستقلًا على الكود/«Manifest» والجهاز والتخزين والحقوق. الهدف المحدد في الخطة المستردة **5 نوفمبر 2026، 06:00 UTC** إذا فات أو لم يُجاز، لا ترحيل صامت. `PUBLISHABLE_FALSE / FORWARD_NOT_ARMED / NO_TRADING / NO_MERGE`.

## أحدث حالة عمل «020-A» — 4 نوفمبر 2026 — إنجازات «Codex» المحلية واستلام «SD Coding 2.2»

**الحقيقة الأساسية:** [«MASTER v1.34»](ZS_SMART_GATE_MASTER.md) و[أمر استلام «SD Coding 2.2» #6631590164](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6631590164) و[تقرير استلام «SD» #6632254398](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6632254398). توقف «Codex» بسبب حد الاستخدام **قبل نشر ملفات «020-A» وتسليمها**؛ لذلك يجب الفصل بين إنجازه المحلي المُبلّغ عنه والأدلة المتاحة.

**«Codex» أبلغ، دون «patch»/سجل محلي قابل للفحص حتى الآن، بأنه:** راجع صيغة «Binance» العامة وحسب وزن خطة الستة طلبات =10 ضمن سقف24 (غير مثبت كعدد GET فعلي)؛ بنى مشغل التقاط «WebSocket» يحجز قبل المحاولة ويحفظ الخام ويدير «GitHub» والإيصالات بأمان مع منع المحاولة/إعادة الاتصال التلقائي؛ اختبر قطع الشبكة وبتر/تجزئة الرسائل و`ping/pong` والفشل المبكر عند غياب التفويض أو تخزين معتمد، واحتفاظ الخام الذي سبق الفشل؛ شغّل **617 اختبارًا محليًا بلا تخطٍ حسب تقريره وحده**؛ وفحص حارس نوم «Windows» دون تعديل خدماته. ذكر أيضًا أن اعتماد «GitHub» المحلي للمشغل غير متاح؛ **لا تستخدم صلاحيات الوصلة المرتبطة بالمحادثة أو بيانات المتصفح لتعويضه**.

**حالة الإثبات المستقلة:** `020_REPORTED_ONLY/NOT_AUDITED`، لم يُنشر مشغل/اختبار/سجل `617`/«Manifest» جديد لـ«020» على [«PR #30»](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/30) تقرير «SD Coding 2.2» وجد أن **شجرة «Codex» المحلية على جهاز المالك غير متاحة من محادثته المنفصلة** لم يدّعِ فحص/تسليم بايتاتها ولا تشغيل «020-B».

**المطلوب لاستكمال «020-A» دون هدر:** من جهاز «Windows» الذي عمل عليه «Codex»، احفظ عمل `tracked/untracked` كما هو، وانقل **حزمة كود/patch واختبارات وسجلات بلا أسرار** عبر مسار معتمد إلى «SD Coding 2.2». **لا `reset --hard` أو `clean` أو إعادة بناء عمياء أو استخراج توكنات**.

**المنع مستمر:** `020_A_BLOCKED_LOCAL_WORKTREE_INACCESSIBLE / 020_FIELD_PREFLIGHT_PASS_NOT_GRANTED / 020_B_NOT_EXECUTED_BY_REVIEW_SESSIONS / NO_PRODUCTION / NO_TRADING / NO_MERGE`. تجربة المصدر الحية الواحدة تحتاج اعتماد «PM» مستقل على رأس الكود/«Manifest» والتخزين والجهاز؛ لا ترقي أي اختبار اصطناعي إلى اعتماد علمي.

## أحدث موافقة مالك — 4 نوفمبر 2026 — تجربة ميدانية قصيرة «020»

**[الأمر التنفيذي «020» في «Issue #25»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6629342692) — [«MASTER v1.35» الحاكم](ZS_SMART_GATE_MASTER.md).** بعد مراجعة «019» ونجاح البرهنة الهندسية على سلامة الترتيب النسبي، وافق المالك على تجربة بيانات سوق عامة **لمرة واحدة فقط** على جهاز «Windows» الفعلي لرصد علامة إغلاق شمعة مستقبلية «5m» واحدة لكل من `BTCUSDT` و`ETHUSDT`.

**السقف:** اتصال «WebSocket» عام واحد (12 دقيقة كحد أقصى، دون إعادة اتصال)، و6 طلبات «GET» عامة كحد أقصى موزعة على مرجعي `time` و`bookTicker` و`ticker/24hr`، بلا retries أو API key أو تداول. لا يبدأ الالتقاط قبل تجميد «Manifest» جديد، وفحص الإصدار والتخزين والحقوق والجهاز، وقرار مراجعة مستقل `020_FIELD_PREFLIGHT_PASS`. يثبت «Codex» أولًا الكود والاختبارات في مرحلة `020-A`؛ ولو تعذر قبولها، يتوقف قبل أول اتصال ويحفظ مانعًا محددًا.

**الحقيقة الحالية:** الأمر موثق ولكن **لم تُنفذ التجربة الميدانية عبر هذه الموافقة وحدها**؛ `FIELD_PREFLIGHT_PENDING / ABSOLUTE_UTC_PIT_HOLD / PUBLISHABLE_FALSE / SCORE_UNAVAILABLE / FORWARD_NOT_ARMED / NO_TRADING / NO_MERGE`. لا تشغيل «Forward» مستمر ولا رسائل إنتاجية؛ ملفات «010–019» المجمدة لا تُعاد كتابة نتيجتها.

## قرار مالك أحدث — 4 نوفمبر 2026 — حد زمن مستقبل «1.5 ثانية»

**[قرار المالك في «Issue #25»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6623892290) / [«MASTER v1.35» الحاكم](ZS_SMART_GATE_MASTER.md).** قرر المالك أن تكون عتبة **الحد المحافظ لعدم يقين «UTC» أقل من 1.5 ثانية** في بروتوكول **الرصد البحثي المستقبلي الجديد** بدل «أقل من ثانية». المقصود دقة إثبات وقت الاستلام والقرار، **وليس** مهلة وصول التنبيه أو سماحية استعمال معلومات متأخرة. لا تتغير نسخ الدراسات القديمة المجمدة ولا نتيجة فشل إثبات التوقيت في «017» بأثر رجعي.

أُمر «Codex» بإصدار عقد سببية مستقبلي جديد واختبارات حدود واضحة، مع الإبقاء على شرط المصدر الموثوق والانجراف المثبت والشموع المغلقة ومنع التسرب للمستقبل. القياسان السابقان `1.165s/1.216s` يحققان العدد الجديد شرطيًا، لكنهما غير مؤهلين مستقلًا بسبب غياب إثبات معايرة العداد والانجراف. **«Forward» غير مفعّل، ولا دمج/تداول مفوض.**

## أحدث قرار مالك وتنفيذ — 3 نوفمبر 2026 — التكامل الهندسي ومعيار السببية المستقبلية «016»

**[الأمر التنفيذي المجمع «016» في «Issue #25»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6602880341)** — **[«MASTER v1.35» الحاكم](ZS_SMART_GATE_MASTER.md)**. وافق المالك على خمسة مسارات متصلة: ترتيب مراجعة ودمج «PR #27/#28/#29» **دون دمج تلقائي**؛ اختبار تكامل شامل من «Binance» إلى قرار بحثي وأدلة «GitHub»؛ تطوير بروتوكول مستقبل مستقل `PROSPECTIVE_RECEIPT_CAUSALITY_V1` قائم على وصول المعلومات قبل القرار دون إلزام مراسلة دعم الناشر؛ تجربة معادلات مستقلة مجمدة وتصحيح الترابط والتعدد والتكاليف وتأهيل السيولة؛ ثم اختبار الجاهزية للرصد «Forward» والقبول العلمي عند تحقق الأدلة والموافقة على تشغيل محدد.

**ليس هذا تصريح تشغيل حي ممتدًا أو إغلاقًا علميًا فوريًا:** `HISTORICAL_PUBLISHER_PIT_FAIL_HOLD / FULL_V2_UNAVAILABLE / NO_QUALIFIED_SIGNAL / OOS_NEW_PENDING / FORWARD_NOT_ARMED / NO_PRODUCTION / NO_TRADING`. لا ترفع الدرجة العلمية بقبول سببية الاستلام؛ النشر الأصلي التاريخي يبقى غير مُثبت. الرصد الحقيقي الممتد والدمج يتطلبان بوابات أدلة وموافقة محددة. المصدر الدائم الوحيد لجميع الأكواد والبيانات المسموح بها «GitHub» الخاص؛ لا اعتماد على «D:»؛ استرجاع «015» قُبل هندسيًا ضمن نطاقه. كل الأقسام الأدنى تحتفظ بسجلات القرارات التاريخية، ويعلو عليها «MASTER v1.31» وقرار «016».


## «LIMIT WARNING» — نظام استمرارية المحادثات المعتمد — 31 أكتوبر 2026

**قرار المالك الإلزامي لكل المحادثات الحالية والمستقبلية:** [«Issue #25» #6547728703](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6547728703). التفاصيل الملزمة في [«MASTER v1.28»](ZS_SMART_GATE_MASTER.md) و[قالب طلبات الدمج «PR»](.github/PULL_REQUEST_TEMPLATE.md). **لا تغير هذه السياسة أي إذن تنفيذ أو حالة علمية**.

- **«NORMAL» — الوضع الطبيعي:** نواصل العمل من غير تنبيهات غير ضرورية. لا توجد وسيلة موثوقة لمعرفة عدد الرسائل أو الرموز المتبقية حتى حد المحادثة بدقة.
- **«LIMIT WARNING» — إنذار مبكر:** عند طول شديد أو مؤشرات ضعف الاستمرارية (نسيان آخر قرار/«SHA»، اختلاف التفويض، فقدان سياق العمل) يُبلغ المساعد المالك مرة مناسبة ويقترح تجهيز حزمة تسليم. لا مراقبة خلفية ولا وعد بإنذار تلقائي مضمون.
- لا تكرار مقبولات ولا إنشاء «Issue» للتسليم وحده.
- **بعد القراءة** تطلب `UPDATE MEMORY` للحقائق المستقرة غير الحساسة إن كانت ميزة التحديث متاحة، وتبلّغ بصدق `MEMORY_UPDATE_REQUESTED` أو `UNAVAILABLE/UNCONFIRMED`. لا يمكن افتراض أو ضمان أن تحديث «ChatGPT Memory» تم فعلًا أو فورًا، و**«GitHub» هو المرجع الدائم لا الذاكرة وحدها**.
- **«Project Instructions»:** النص المخصص لإعدادات مشروع «ChatGPT» يقدمه «PM» للمالك لإضافته يدويًا؛ تحديث هذا المستودع **لا يغيّر إعدادات واجهة «ChatGPT» تلقائيًا**. طلبات الدمج السابقة تظل أرشيفية؛ تطبيق القاعدة على «PRs» القادمة عبر القالب الجديد.
- **الحوكمة الثابتة:** «PM» وحدها تحدث «MASTER/README»، و«SD Coding» تراجع المستندات وتنفذ ضمن التفويض وتسلّم «Draft PR» دون دمج إلا بموافقة المالك. لا إعادة «Canary» أو تداول أو اتصال سوق أو تكاليف مدفوعة. `STAGE04_CLOSED_SUCCESS_APPLICATION_ONLY / STAGE03_SCIENTIFIC_RESUMED_WITH_PIT_FAIL_HOLD / NO_PRODUCTION`.

## الحالة الرسمية الأحدث — إغلاق المرحلة «04» واستئناف علم «03» — 31 أكتوبر 2026

التفاصيل الحاكمة في [«MASTER v1.27»](ZS_SMART_GATE_MASTER.md).

**القرار الإداري:** `STAGE04_ADMIN_CLOSED_SUCCESS_APPLICATION_ONLY` — **أُغلقت المرحلة «04» إداريًا بنجاح ضمن نطاق حفظ الأدلة البحثية على «GitHub» والقراءة والاسترجاع المستقل فقط**، ولا يشمل ذلك إنتاج الإشارات أو إثبات «PIT» أو «WORM».

- **إثبات فعلي واحد دون إعادة:** محاولة يدوية `completed/success` على `main=e96bd6b8ee22be6040549f0cfeeae423a33b4ba0`، تضم `35 GET + 12 PUT + 1 branch POST`، وفرع أدلة [`evidence-stage04-canary-e96bd6b8ee22be60`](https://github.com/scannercrypto0-gif/zs-crypto-signals/tree/evidence-stage04-canary-e96bd6b8ee22be60/studies/zs04-canary-e96bd6b8ee22be60) أضاف `7` ملفات «JSON» في `12` التزامًا؛ أدلة «Manifest/Claims/Receipts/Index» متسقة مع بصمات `SHA-256` محسوبة بصورة مستقلة. بصمة «manifest» = `2a596ac07730718e10a1e8ca57b5a250daa1ac105db726093a7dc0a6fe7b6629`. «GitHub» هو مستودع الأدلة الدائم، دون أي اتصالات سوق في هذه التجربة `market_http_attempts=0`.
- **الحدود الثابتة:** `APPLICATION_ONLY` و`server_enforced_worm=false`؛ فرع الأدلة و`main` غير محميين خادميًا، فلا ادعاء «WORM» أو عدم قابلية التعديل ذات الامتيازات. لا إثبات لوقت النشر أو الساعة المستقلة أو `PIT` الحقيقي. `PIT_FAIL_HOLD / SCORE_UNAVAILABLE / N_REQUIRED=UNDETERMINED / NO_PRODUCTION_SIGNAL / NO_TRADING` لا تتغير. لا «Binance LIVE»/«Windows Runner»/«Telegram» إنتاج، ولا إعادة تشغيل «Canary» المستهلكة.
- لا شراء أو ترقية أو رفع ميزانية. حفظ فرع الأدلة مستمر موعد `2026-11-30` لمراجعة الاحتفاظ وليس حذفًا تلقائيًا.
- **ما يلي:** المرحلة «03» لا تزال **مغلقة جزئيًا من الناحية الهندسية**، لكن قرار المالك يسمح **باستئناف العمل العلمي البحثي والتعريفات والاختبارات «Offline»** في [التكليف المستقل «Issue #25 — المعادلات والتطبيع و«PIT»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25). يتطلب قبول المعادلات والخيارات الدلالية الأربع والضوابط الزمنية **قرارات لاحقة موثقة**. تظل `PIT_FAIL_HOLD` ولا إغلاق علمي للمرحلة «03» إلى أن يُثبت خلاف ذلك باستقلال ويعتمده المالك.

**الأقسام التالية أرشيف لخطوات التنفيذ السابقة وليست الحالة الأحدث**.

## سجل تاريخي — مراجعة «PM1.2» لحزمة الجاهزية قبل تشغيل «Canary» (تم تجاوزه)

**الحالة الأحدث الحاكمة:** `READ_ONLY_CANARY_PREFLIGHT_PM_ACCEPTED / COST_GATE_UNVERIFIED / GITHUB_TOKEN_EFFECTIVE_WRITE_UNKNOWN / NO_OWNER_CANARY_AUTHORIZATION / CANARY_NOT_RUN / REAL_GITHUB_RESTORE_NOT_VERIFIED / STAGE04_NOT_ADMIN_CLOSED / STAGE03_SCIENTIFIC_PIT_HOLD`.

- الفحص التقني **مكتمل في نطاق القراءة فقط**، دون دليل كتابة حقيقية أو استرجاع شبكة.
- ولا عن الإتاحة الفعلية لصلاحية `GITHUB_TOKEN contents:write` أو تشغيل «Run workflow» لحساب المالك. الميزانية الجديدة قد لا تغطي استخدامًا سابقًا في الدورة التنبيهات ليست ضمانًا للمنع.
- **نطاق المخاطر المعروف:** `main protected=false`، صلاحية `contents:write` واسعة على المستودع لا فرع الأدلة وحده، ولا ادعاء حماية `WORM`. الاعتماد الفني على حدود الكود (`5min` و`64 GET/PUT` + `1 branch POST`) لا يثبت حق الكتابة أو سلامة التكلفة الفعلية.
- بعد تقييم المالك لبيانات الحساب وتأكيد «PM» للبوابة، يلزم **قرار مالك منفصل عند `main SHA` حديث** لتشغيل **«Canary» اصطناعي يدوي واحد**؛ بعده فقط تقرير `REAL_GITHUB_CANARY_E2E_EVIDENCE` والمراجعة والإغلاق الإداري المستقل. **لا تشغيل تلقائي، ولا حاجة لإعادة البرمجة/فتح «PR #24» المقبول.** «03/PIT» على «HOLD».
- التقارير التاريخية أدناه محفوظة لكن لا تعلو على هذه الحالة.

## التكليف التنفيذي الجاري — استكمال المرحلة «04» بعد الدمج — 31 أكتوبر 2026

**قرار المالك:** إصدار الأمر المجمع [`ZS-04-POSTMERGE-CANARY-READBACK-CLOSURE-002`](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/23#issuecomment-6542376003) إلى «SD Coding 2.1» لإكمال جميع بوابات المرحلة «04» المتبقية، مع بقاء تشغيل «Canary» الحقيقي والإغلاق الإداري خاضعين لتفويضات منفصلة.

**الحالة:** `STAGE04_POSTMERGE_PREFLIGHT_ORDER_ISSUED / PR24_MERGED_CI_4_4_PASS / CANARY_NOT_RUN / REAL_GITHUB_RESTORE_NOT_VERIFIED / NOT_ADMIN_CLOSED / STAGE03_SCIENTIFIC_PIT_HOLD`.

- يُعاد التحقق من «SHA» الحي قبل أي تجربة.
- **العمل المأذون الآن لـ«SD Coding 2.1»:** تجميع حزمة `CANARY_PREFLIGHT_PACKET` بقراءة فقط: إعدادات السعة المجانية والصفر تكلفة أو تسجيل `UNVERIFIED`، فحص «workflow»/الأذونات وفرع الأدلة ونطاق `GITHUB_TOKEN contents:write`، وثبوت عدم وجود تشغيل سابق؛ تسليم الأدلة إلى «PM1.2» في «Issue #23». **لا تشغيل يدوي أو تلقائي ل«Canary» الآن**.
- **العمل المشروط لاحقًا:** عند تحقق حزمة الجاهزية ومراجعة «PM» وقرار مالك **منفصل** بحد تشغيل واحد ورأس `main SHA` محدد، تنفيذ «Canary» اصطناعي يدوي واحد لا سوق فيه ولا أسرار جديدة ولا تكاليف، ثم «GitHub Write/Readback/Restore» فعلي مع `Manifest SHA-256` والعدادات و«UTC» وحالات الفشل، دون ادعاء «WORM» غير موجود أو إنتاج إشارات.
- **الإغلاق:** حزمة `REAL_GITHUB_CANARY_E2E_EVIDENCE` و`ACCEPTANCE_MATRIX` وتقويم «PM1.2» المستقل، ثم موافقة المالك على `STAGE04_ADMIN_CLOSED_SUCCESS` فقط إذا اجتازت جميع البوابات. «03» مغلقة جزئيًا، والمعادلات والتطبيع والتأهيل و«PIT FAIL/HOLD» باقية معلقة.
- «PM» فقط تعدل «MASTER/README»، و«SD» توثق الأدلة ولا تدمج أو تفعّل بإذن مستنتج.

## اعتماد المالك ودمج «PR #24» واختبارات ما بعد الدمج — 31 أكتوبر 2026

**القرار الحالي الحاكم (يلغي أوصاف `Draft/Merge pending` التاريخية أدناه):** `OWNER_APPROVED_PR24_MERGED / POSTMERGE_MAIN_CI_4_4_PASS / CANARY_NOT_RUN / REAL_GITHUB_READBACK_RESTORE_NOT_VERIFIED / STAGE04_NOT_ADMIN_CLOSED / STAGE03_SCIENTIFIC_HOLD`.

- **تم دمج [«PR #24»](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/24) بتفويض صريح من المالك، على الرأس المحدد وحده `df169ad998a9dbc1a58ff6e73cc61daa9579201d`.** تأكد «PM1.2» من المطابقة واستخدمت `expected_head_sha`؛ أكد «GitHub» نجاح الدمج `MERGED=true` عند [التزام `fadff0d57c9fe5d0b9408a0701904896eb6c2ede`](https://github.com/scannercrypto0-gif/zs-crypto-signals/commit/fadff0d57c9fe5d0b9408a0701904896eb6c2ede). [محضر الدمج في «PR #24»](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/24#issuecomment-6542245546) و[«Issue #23»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/23#issuecomment-6542249936).
- لا يعني نجاح التخزين الحقيقي.
- **لا مفتاح حساب أو «PAT/App» أو تكاليف مدفوعة أو اتصال سوق**.
- **بوابة الإغلاق المتبقية:** حفظ/«Readback/Restore» حقيقي مُفوَّض من «GitHub» مع «Manifest/SHA-256» وعدّ «GET/PUT/POST» وحالات الفشل؛ مراجعة «PM» ثم قرار المالك بالإغلاق الإداري. حتى ذلك الحين `STAGE04_NOT_ADMIN_CLOSED`. **«03» تبقى `PARTIALLY_CLOSED`، والمعادلات العلمية والتطبيع والتأهيل و«PIT FAIL/HOLD» مؤجلة**.
- لا تُقرأ أي فقرة تاريخية أقدم على أنها حالة الدمج الحالية.

## «PM1.2» — قبول كود PR #24 على الرأس النهائي — 31 أكتوبر 2026

**حالة العمل الحاكمة:** `STAGE04_DESIGN_APPROVED / PM_ACCEPT_CODE_AT_df169ad998a9dbc1a58ff6e73cc61daa9579201d / OWNER_MERGE_APPROVAL_PENDING / STAGE04_NOT_ADMIN_CLOSED`.

- **تم قبول كود [«PR #24»](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/24) إداريًا من «PM1.2» على الرأس المحدد فقط** `df169ad998a9dbc1a58ff6e73cc61daa9579201d`، وهو **ما زال `OPEN/DRAFT/NOT_MERGED`**. [نص قرار القبول وأدلة المراجعة](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/24#issuecomment-6542134146) و[تحديث «Issue #23»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/23#issuecomment-6542136594).
- التصحيح في ملف «Canary» واختباراته فقط (+8 اختبارات محاكاة) سد فجوة «POST 201/ref/SHA»، ومسار الكتابة/الاسترجاع المحاكى، الفشل المغلق والحد الأقصى 64 عملية.
- قبول كود «PM» لا يساوي أمر دمج أو تشغيل. لا يُطلب من «SD Coding 2.1» تكرار ما قُبل إلا عند رأس جديد أو عيب جديد مثبت.
- **لا كتابة حقيقية على «GitHub» حتى الآن:** `CANARY_NOT_RUN / REAL_GITHUB_READBACK_RESTORE_NOT_VERIFIED`. يظل تشغيل «Canary» الاصطناعي الواحد مشروطًا بفحص الحصة المجانية وعدم الكلفة والمخاطر والصلاحيات ورأس «main» ثم تصريح محدد، ولا يعتبر ملء خانة `zero_cost_verified` إثباتًا محاسبيًا. لا «WORM» مضمون للمستودع الخاص غير المحمي؛ ولا إغلاق «04» دون حفظ واسترجاع حقيقيين ومراجعة «PM» واعتماد المالك للإغلاق.
- **«03» و«PIT» كما هما:** `PARTIALLY_CLOSED/SCIENTIFIC_HOLD/PIT_FAIL_HOLD`، ولا إنتاج إشارات/«Telegram»/تداول/«Windows Runner».



**الحالة الصحيحة الآن:** `STAGE04_OWNER_DESIGN_APPROVED / PR24_DRAFT_CODE_REVIEW_HOLD / OFFLINE_CI_SUCCESS_4_4 / CANARY_NOT_RUN / STAGE04_NOT_ADMIN_CLOSED`. **المراجعة ليست رفضًا للتصميم أو الكود المقبول سابقًا؛ إنها طلب اختبار محدد قبل اعتماد دمج هذه المسودة.**

- [«PR #24»](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/24) سُلّم من «SD Coding 2.1» برأس `7a238ae1d05987a83749fbc6ac8344bd1a26545f`، أربعة ملفات لتجهيز سجلات «Stage04» و«Manifest/SHA-256»، الاسترجاع المستقل ومسار «Canary» صناعي يدوي. ما زال `OPEN/DRAFT/NOT_MERGED` على هذه البصمة.
- 335 اختبارًا في «Ubuntu 3.11» مع اختبار متجاوز واحد، و«Windows 3.11» بلا فشل. وصف `QUEUED` في تسليم المطور أصبح قديمًا.
- **قرار «PM» والتكليف التالي:** [تعليق المراجعة #6532712896 داخل «PR #24»](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/24#issuecomment-6532712896) و[ملخص «Issue #23» #6532721158](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/23#issuecomment-6532721158). يحتاج «SD Coding 2.1» **على نفس المسودة** إضافة اختبارات «Offline» تحاكي مسار «Canary» المصرح به حتى نجاح إنشاء الفرع عبر «GitHub REST POST» وعمليات الكتابة/«Readback/Restore» المستقلة، واستجابات الفشل وحماية الرموز وسقف الـ64 عملية دون شبكة حقيقية أو إعادة تصميم.
- **التفويضات ثابتة:** لا موافقة دمج «PR #24» بعد، ولا اختبار تخزين حي أو استرجاع من «GitHub» مثبت، ولا إغلاق «04». لا «Windows Runner» أو «Telegram» أو إشارات أو تداول، ولا استئناف المعادلات العلمية و«PIT» في «03» حتى قرار قبول «04» فعليًا. التصحيحات/التسليمات المؤثرة تُثبت في «PR/Issue #23/MASTER/README»، وأي محادثة جديدة تستلم أحدث الحالة من «main».

## اعتماد المالك لتصميم المرحلة 04 — 30 أكتوبر 2026 — التكليف البرمجي التالي

**`OWNER_APPROVED_STAGE04_DESIGN / STAGE04_P0_IMPLEMENTATION_AUTHORIZED_WITH_GATES / NOT_ADMIN_CLOSED`.** وافق المالك صراحة على تصميم التخزين الخاص بـ«GitHub» في [«Issue #23»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/23#issuecomment-6532397151). **بوابة التصميم مقبولة، لكن التخزين الدائم غير مُفعّل والمرحلة «04» غير مغلقة بعد**. هذا القرار أحدث من وصف «بانتظار اعتماد التصميم» في قسم الأولوية التاريخي أدناه.

- **التالي والمسؤول:** «SD Coding 2.1» ينفذ [الأمر المجمع `ZS-04-GITHUB-DURABLE-EVIDENCE-E2E-001`](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/23#issuecomment-6532397151): إعادة استخدام «PR #17/#18»، سد الثغرات الفعلية في عقد/حفظ/استرجاع الأدلة والبيانات البحثية، اختبارات «Offline» وتقدير حدود النمو والانقطاع، وتسليم **«Draft PR» واحد** دون دمج أو تعديل «MASTER».
- **التصميم المقبول:** مستودع خاص؛ فرع أدلة مخصص؛ «GitHub» حفظ دائم وحيد؛ «Schema/Manifest/SHA-256/source/received_at/available_at»، واختبارات «Readback/Recovery/Idempotency»؛ سقف `10 MiB/study` الحالي تجريبي فقط وتُراجع كفايته للتوسع. مراجعة الاحتفاظ بعد 30 يومًا **ليست حذفًا**. لا ادعاء «WORM»/حماية عدم التلاعب للفرع غير المحمي.
- **حدود التفويض:** لا كتابة حقيقية أو تفعيل تلقائي، ولا «PAT/App» أو أسرار جديدة أو كلفة مدفوعة أو تحويل المستودع إلى عام. قبل تشغيله يلزم مراجعة «PM» الدقيقة والحصة المجانية وأذونات العمل وموافقة دمج مستقلة لأي «PR» يجب دمجه أولًا. لا «Windows Runner» أو «Binance» أو «Telegram» إنتاجي أو تداول.
- حتى ذلك الحين `NOT_ADMIN_CLOSED`. بعد إغلاق «04» الحقيقي يعود بحث المعادلات والتطبيع والتأهيل و«PIT» بالمرحلة «03» المغلقة جزئيًا `PIT_FAIL_HOLD` حاليًا.
- تُحدّث القرارات والتسليمات في «PR/Issue/MASTER/README» أولًا بأول «PM» فقط تحرر «MASTER»، ولا تعتمد محادثة على ذاكرة محادثة قديمة.

## أولوية المالك السابقة لاعتماد التصميم — استكمال 04 ثم العودة العلمية إلى 03 — قرار 30 أكتوبر 2026

**`OWNER_PRIORITY_APPROVED / STAGE04_P0_DESIGN_GATED / STAGE03_PARTIALLY_CLOSED_SCIENTIFIC_HOLD`.** أمر المالك الجديد: **أكمل المرحلة «04» تنفيذًا وتحققًا ثم أغلقها إداريًا بنجاح بعد الأدلة**، وبعدها فقط ارجع إلى «03» المغلقة جزئيًا لحسم المعادلات العلمية والتطبيع والتأهيل وإثبات «Point-in-Time (PIT)» المستقل. **هذه أولوية وحالة عمل، وليست إعلان أن «04» قد نجحت أو أغلقت بالفعل.**

**مرجع الاستكمال:** [«MASTER v1.20»](./ZS_SMART_GATE_MASTER.md) أول قرار حاكم؛ [«Issue #23 — أمر إتمام المرحلة 04 وبوابة قرار التصميم»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/23)؛ [«Issue #11 — قرار المالك السابق وإثباتات المرحلة 03»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11#issuecomment-6531009764).

- **المرحلة «04» الآن:** `PRIORITY_P0 / DESIGN_OWNER_APPROVAL_PENDING / NOT_ADMIN_CLOSED`. يُعاد استخدام «PR #17/#18» الخاصين بدفتر الأدلة و«GitHub Contents API»، ولا يُعتبر كودهما المدمج نظام حفظ دائمًا مفعّلًا أو مختبرًا عمليًا. اعتماد وسيلة التخزين والحصص/التكلفة/الصلاحيات والاحتفاظ والاختبار الحي بالكتابة يحتاج **قرار مالك صريحًا قبل التنفيذ**. يبقى «GitHub» مصدر البيانات الدائم؛ لا وعد بحماية غير قابلة للعبث في المستودع الخاص غير المحمي.
- حالات `BLOCKED/UNKNOWN/FAIL` تمنع وصفها `ADMIN_CLOSED_SUCCESS`.
- **المرحلة «03» تظل:** `PARTIALLY_CLOSED_ENGINEERING_ACCEPTED`، المعادلات العلمية والـ12 مجموعة والتأهيل ودراسة `PIT FAIL/HOLD` مؤجلة حتى إكمال «04» وقرار علمي مستقل؛ لا درجات أو إشارات أو «Telegram» إنتاجي ولا تداول، ولا «Windows Runner» الآن.
- لا يعتمد تسليم المحادثات على ذاكرة محادثة.

**الخطوة التنفيذية الحالية:** مراجعة تصميم التخزين وآلية الحفظ داخل «GitHub» وحدودها لقرار المالك. لا تكليف برمجي مؤثر أو أسرار أو كتابة حقيقية قبل هذا الاعتماد.

## بيان قرار المالك السابق — 30 أكتوبر 2026 — إغلاق جزئي «03» والبدء بتحضير «04» (لا يزال نافذًا في حدوده)

**`OWNER_APPROVED` — الحالة الرسمية: `STAGE03_PARTIALLY_CLOSED_ENGINEERING_ACCEPTED / SCIENTIFIC_FORMULAS_AND_PIT_ON_HOLD_UNTIL_STAGE04_COMPLETION / STAGE04_NEXT_DESIGN_GATED`.**

- **«03» مغلقة إداريًا جزئيًا فقط:** العقود والتكامل البحثي واختبارات منع التسرب جرى قبولها ضمن نطاقها ودمج [PR #15](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/15) و[#19](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/19) و[#20](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/20) و[#21](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/21) و[#22](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/22). لا يعمّم نجاحه على «Swing G0» أو جميع الأصول.
- **«HOLD» مؤجل لا ملغى:** المعاني الأربع المتبقية، معادلات تقييم الـ12 مجموعة في «Intraday/Swing»، شروط تأهيل الإشارات والنتائج، كفاية العينات و«DEV/OOS/Forward»، **وإثبات «PIT» العلمي** (ما زال `FAIL/HOLD` و`N_REQUIRED=UNDETERMINED`). **يُستأنف هذا البحث بعد اكتمال متطلبات المرحلة «04»**، ولا تُحوّل نتيجة اتصال «Binance» الحية إلى إثبات علمي أو تصريح إشارة إنتاجية.
- **«04» هي المرحلة التالية:** التخزين الدائم والأدلة والبصمات و«Readback/Recovery» على «GitHub» فقط، بدءًا بالبيانات البحثية دون اختلاق `signal_id` أو `score` إنتاجي. **تصميم وسيلة التخزين والحصص/الرسوم والحفظ الفعلي يحتاج موافقة المالك قبل تنفيذ ما لم يُعتمد.** انتهاء «04» لا يساوي نجاحًا آليًا للمعادلات أو «PIT»، وسيعود قرار إغلاق «03» الكامل للمالك بعد التحقق العلمي.

- لا تعتمد على ملخص قديم، ولا تعيد فتح أعمال مقبولة، ولا توسع التفويض، ولا تحول «03» إلى `FULLY_VERIFIED` أو `IN_PROGRESS` مطلقة دون بيان الإغلاق الجزئي. الصلاحيات لا تنتقل أو تزيد بتغيير رقم المحادثة «PM» فقط تحرر «MASTER» و«SD Coding» تنفذ وتسلم الأدلة. **الرجوع إلى «GitHub» يضمن وجود مرجع دائم، لكنه لا يرسل إشعارًا تلقائيًا إلى المحادثات الأخرى.**

**الأولوية عند اختلاف السجل التاريخي:** هذا القرار الأحدث و[«MASTER v1.20»](./ZS_SMART_GATE_MASTER.md) يتقدمان على أوصاف «03B3» ودراسات «Windows» وأرقام الحالات القديمة. هذه الملفات التاريخية محفوظة للأدلة فقط، وليست أوامر تشغيل حاضرة.

> **قرار المالك الساري — 30 أكتوبر 2026:** المشروع الآن في وضع **التطوير الكامل على «GitHub» فقط** **نشر المشروع كاملًا على كمبيوتر «Windows» وتأليف «Windows Runner» محلي جديد مؤجلان حتى اكتمال المشروع وقبول النشر.** كل تكليفات المشغّل المحلي القديم وتجهيز تطبيق التخزين واختباره على الجهاز موقوفة في نطاقها السابق لا تطلب تثبيت مستودع على جهاز المالك ولا تفعّل تشغيل «Binance» إنتاجيًا أو «NTP» أو «Telegram» أو دراسة حية بموجب تفويض قديم المرجع الملزم: [«MASTER v1.20»](./ZS_SMART_GATE_MASTER.md) وقسم «قرار المالك الحاكم — 30 أكتوبر 2026»، مع [سجل «Issue #11»](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11). لا خادم مدفوع ولا تسجيل بطاقة بنكية.

**مشروع مستقل** لبناء رادار بحثي لاكتشاف فرص الصعود والهبوط مبكرًا على **Binance Spot USDT**، مع خطط تداول Spot يدوية قابلة للتقييم العلمي، ومسارين منفصلين **Intraday** و**Swing**. لا يوجد تداول آلي حقيقي مصرح به.

> **مراجعة PM العلمية الأحدث — 30 أكتوبر 2026:** [تسليم البروتوكول `ZS03-SCI-PRE-REG-DRAFT-0.1`](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11#issuecomment-6525015916) **مقبول كمسودة للقرار فقط** لا اعتماد معادلات/عينات/نتائج/PIT، ولا 100% للمرحلة 03. ملاحظة `PR #20 UNMERGED` في التقرير لقطة تاريخية سابقة [أمر SD Coding 2.1 السابق](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11#issuecomment-6526197674) كان للفحص العلمي `offline` حين صدر **نطاقه مكتمل وPR #21 مدمج، لكن السماح الجديد باختبارات `online smoke` قصيرة لا يُعد موافقة على دراسة رصد علمية أو تنفيذ حي مستمر.**

كل تشغيل يسجل الرأس والحدود والنتيجة الاختبار الحي لا يثبت «PIT» علميًا. واختبار Live سابق لـ«03B1» لا يثبت وظيفة «PR #21» الجديدة، التي تتطلب smoke تكامل مستقل إذا كان مناسبًا. المرجع [MASTER v1.20](./ZS_SMART_GATE_MASTER.md) — قسم «سياسة اختبارات Online المحدودة».

## السجل السابق قبل قرار الإغلاق الجزئي — 30 أكتوبر 2026 — Stage 03

**هذا سجل تاريخي سابق لقرار الإغلاق الإداري الجزئي أعلاه المرحلة «03» مغلقة جزئيًا هندسيًا، وليست مغلقة علميًا.** «PR #19» و«PR #15» دُمجا سابقًا بنجاح، ثم دُمج «PR #20» بعد موافقة المالك أحدث بصمة كود للتكامل `1dca61d42b4db3a6c6322763b9755d74e6b1b2ee`، واختبارات ما بعد كل دمج 4/4 PASS. تفاصيل [تقرير المجموعات الـ12](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11#issuecomment-6523776257): 8 توافقات مفاهيمية و4 خلافات دلالية، ولا معادلة تطبيع رقمية معتمدة لأي مجموعة كفاية العينات `UNDETERMINED`، و`PIT FAIL/HOLD`، ولا إشارات إنتاجية أو «Telegram» حي. **المرجع الملزم للتفاصيل وبوابات الإغلاق هو «MASTER v1.20»**، وقسم «PM checkpoint — 30 أكتوبر 2026». حالة «Windows» والنشر والتكاليف لم تتغير.

## اقرأ المرجع الرسمي أولًا

**[ZS_SMART_GATE_MASTER.md — MASTER v1.20](./ZS_SMART_GATE_MASTER.md)** هو مصدر الحوكمة والمواصفات المُجمعة وقرارات المالك. يتضمن في بدايته **SMART GATE — UNIFIED DESIGN v2.1**، ثم خارطة **14 مرحلة (00–13)**، وإصدارات Score، وعقود Telegram/Analytical Data/Trade Plans، وسجل القرارات، والـTechnical Blueprint التاريخي محفوظًا. عند تعارض مقترح قديم مع قسم التصميم الموحد المعتمد، تُطبَّق قواعد الأسبقية داخل MASTER.

**حالة الاعتماد:** المالك **وافق على تصميم SMART GATE v2.1 كهدف للمشروع** في 28 أكتوبر 2026؛ الحدود العددية غير المُختبرة ومعادلات BOS/CHoCH/Score النهائية، وسعر الخطة ونظام تخزين GitHub العملي تبقى **قيد التصميم والاختبار/الموافقة الفنية**؛ لا يصح وصف الميزات المخطط لها بأنها منفذة أو مجربة.

## دورة تشغيل SMART GATE المستهدفة

| الوظيفة | التوقيت / الدليل | المخرج |
|---|---|---|
| Market Watch | تحديثات خفيفة كل دقيقة | EARLY WATCH، ليس Signal تلقائية |
| Base Scanner | بعد كل إغلاق 5m | Price/RVOL/Impulse وCandidate |
| **Intraday** | **إغلاق 30m + تحليل 6×5m المغلقة** | إشارة UP/DOWN 1–24h مؤهلة بالأدلة |
| **Swing** | **إغلاق 4h + تحليل 4×1h المغلقة** | إشارة UP/DOWN 1–30d مع هيكل سعري مؤكد |
| Context | 1h/4h/Daily/Weekly؛ 8h للمقارنة البحثية | MTF/Market Structure وقياس أثر التأخر |
| Delivery & Research | بعد التأهيل | Signal ID موحد + Score/Plan + Analytics JSON + Outcome Tracking |

**أهلية Baseline:** Spot/USDT/TRADING، حجم 24h Quote ≥10M USDT، Spread ≤20bps، شموع صالحة متاحة وقت القرار، مع Research Cohort منفصل منخفض السيولة. Early Impulse المرجعي ±0.7% وRVOL≥2 ليس شرطًا لكل Pre-Move Candidate. الهيكل السعري في Swing يشمل continuation أو reversal بعد BOS/CHoCH مثبتين Point-in-Time؛ لا Replay غير واقعي ولا تأكيد مفرط يضيع الحركة.

## Scoring — Research V1 محفوظ وV2 بحسب الأفق

| المجموعة | Intraday V2 | المجموعة | Swing V2 |
|---|---:|---|---:|
| 30m Strong Close | 20 | Market Structure | 35 |
| 6×5m Internal Quality | 20 | 4h Strong Close | 15 |
| Momentum / Early Timing | 20 | 4×1h Internal Quality | 15 |
| Volume Strength / Continuity | 20 | Daily/Weekly Context | 15 |
| MTF / Nearby Structure | 15 | Momentum / Volume | 15 |
| Liquidity Quality | 5 | Liquidity Quality | 5 |
| **الإجمالي** | **100** | **الإجمالي** | **100** |

**الأوزان V2 نقطة انطلاق بحثية وافق المالك على اختبارها، وليست دقة مثبتة أو Probability.** تظل معادلات ونتائج **Scoring V1 (35/25/20/10/10)** محفوظة مستقلة. قيم EMA/RSI/MACD/POC/VWAP/OI/CVD/BTC وغيرها تُسجل مع مصدرها وزمنها وتخضع لاختبار الفائدة قبل أي أوزان جديدة. Score منخفض **لا يمنع إرسال Signal مؤهلة**؛ وعند فقد قيمة أساسية تظهر `SCORE_UNAVAILABLE` بدل رقم مختلق.

## نظام Telegram والتحليل المستقبلي

- **Primary Bot → Chat A + Chat B:** **كل Signal مؤهلة**، مع `signal_id` وScore والإطار والاتجاه و`trade_plan_status` و**Entry Zone/SL/TP1/TP2/TP3 إن ثبتت خطة صالحة**؛ وإلا `RESEARCH_ONLY` بوضوح. DOWN تحذير هبوط أو Sell Existing Spot؛ ليس Short.
- **Analytical Bot → Chat C واحد فقط:** ملخص إنساني و**JSON machine-readable** لكل Signal بمصدر/إصدار/بصمة SHA-256، يضم مكونات Score وOHLCV والشموع الداخلية والهيكل والفلاتر وجميع قيم المؤشرات **المنفذة والمتاحة** وبيانات القرار/الإرسال وخطة الصفقة وReason Codes. لا توثيق مزيف لمؤشر لم يُبنَ.
- **Shared Primary Key:** نفس `signal_id` في رسائل الوجهات الثلاث؛ معرفات `bot/chat/message` تخص عمليات الإرسال، وتُدمج صادرات Telegram في **إشارة واحدة** مع Deliveries منفصلة. بيانات JSON الدائمة على **GitHub** وفق آلية Storage سيتم اعتمادها؛ Telegram Export وحده ليس ضمانًا لوجود جميع المرفقات.
- **Interactive Primary Bot:** `/analyze`, `/intraday`, `/swing`, `/structure`, `/indicators`, `/signal`, `/plan`, `/status` لمستخدم/Chat مصرح له. كل طلب له `analysis_request_id` منفصل ولا يُحسب كإشارة Scanner جديدة.
- **Outcome Research:** تقييم الوصول إلى Entry وبعدها SL/TP بالترتيب **بعد وقت إتاحة الرسالة**، مع `NOT_TRIGGERED` و`AMBIGUOUS_SEQUENCE` عند عدم إمكان إثبات المسار، واحتفاظ بتاريخ الإشارة الأصلي دون إعادة كتابة.

## سجل الإنجاز التاريخي — 28 أكتوبر 2026

> السطور أدناه سجل تاريخي لحالة ذلك التاريخ؛ أي نص عن دراسة «Windows» أو مرحلة «03» `IN_PROGRESS` تجاوزه قرار المالك الأحدث في أعلى الملف. لا تعُد لتنفيذ تكليف قديم بناء عليه.

**المراحل: 14 00 و01 و02 VERIFIED / MERGED.** PR #1 نواة PIT نجحت في 51/51 اختبارًا ×4 وBinance LIVE لعينة BTCUSDT. **[PR #2 — FOUNDATION-002 MERGED](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/2)** بالـCommit `babaab27fdab9172c7e2e425c54bb74f193269ac` *حدود الإنجاز:* جرد 770 زوج Spot USDT، منها 43 مؤهلًا في لحظة العينة، لكن جرى جلب شموع **2 أو 4 عملات فقط لكل دورة** لا مسح كامل مستمر للسوق أو Telegram أو Scoring V2. **03 — IN PROGRESS: 03A/03B1 VERIFIED دراسة 03B2 التاريخية مغلقة بدليل غير كاف 03B3 الأصلية أُلغيت بقرار المالك (9 LATE + 3 ملغاة، 0/12 OBSERVED_PIT).** أزيلت جدولة GitHub من main. الدراسة البديلة الجديدة [Windows prospective Issue #11](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11) قيد التنفيذ/التسجيل المسبق، ولم تبدأ LIVE بعد. 04–13 غير مكتملة، ولا Scoring إنتاجي أو Signal أو تداول.

الموجود **عقود ومطابقة زمنية MTF/هوية بحثية وScore/Plan RESEARCH_ONLY فقط، مع E2E fixtures غير متصلة ببيانات LIVE 30m/4h** لم تُطبّق قواعد Qualification/Score العددية أو إصدار `signal_id` أو Signal حقيقية. المطابقة بين الشمعة الرئيسية والشموع الداخلية كانت صفر فروق في العينات المخرجات **مقاييس وصفية RESEARCH_METRIC_UNAPPROVED** بلا Score أو Signal أو خطة جاهزة. **النتيجة العلمية `INSUFFICIENT_EVIDENCE`**، والتاريخية المسترجعة لا تثبت المشاهدة الأصلية وقت الحدث **03B2 RESEARCH CLOSED WITH INSUFFICIENT_EVIDENCE (original frozen 8/12; do not rerun/rewrite). **REAL 30m/4h POST-CLOSE LIVE لم يُثبت بعد، 0/12 لحظة التسليم 03B3 NOT FULLY VERIFIED.** لا استنتاجات تنبؤية أو قواعد تداول. تحديث خارطة التنفيذ داخل MASTER: 03 هوية الإشارة وتأهيل 30m/4h وV2/Plan contracts 04 سجلات GitHub **05A/05B/05C** Primary/Analytics JSON/Interactive **06A/06B** Outcomes/Telegram Export→SQL 07 Intraday pre-move 08 Swing Structure 09 Volume Profile/Trade levels 10–12 سياقات ونماذج 13 تشغيل واسترداد كامل. العدد الإجمالي لا يتغير إلا بقرار جديد تقسيمات A/B/C شرائح ضمن المراحل.


### سجل القرارات والاختبارات غير المحسومة — مرجع واحد

المرجع الرسمي هو [Active Evidence & Release-Gate Register v1.12](./ZS_SMART_GATE_MASTER.md) (ثمانية بنود). **دراسة 03B3 المجمدة القديمة أُلغيت بناءً على طلب المالك** يوم 28 أكتوبر 2026، وليس لأنها أصبحت دراسة LIVE ناجحة: ثلاث تشغيلات فعلية في GitHub حدثت متأخرة أكثر من 40 دقيقة، وكل واحدة نتج عنها ثلاث حالات `LATE` وصفر طلبات Binance؛ أي **9 LATE + 3 CANCELLED_BEFORE_EVENT = 12 خانة إداريًا، 0/12 بيانات PIT**. [توثيق قرار الإلغاء على PR #7](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/7#issuecomment-6477236612)؛ حُذف `stage03b3-auto.yml` من `main` عند commit `283710e31ab91d8e53fb4a559cbee10512b62042`، وعُطلت متابعة إغلاقها القديمة. **لا تشغيل يدوي ولا إعادة تسجيل نفس الدراسة**. تُحفظ السجلات السابقة للأوديت فقط وتُستبعد من أي تقييم علمي.

**الخطة التاريخية التي أوقفها قرار المالك بتاريخ 30 أكتوبر 2026 (ليست تكليفًا قائمًا):** [Issue #11](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11) يأمر Codex بإعداد تجربة مستقبلية مستقلة تمامًا بمواعيد مطلقة جديدة و`study_id`/SHA جديد وتوقيت **Windows Task Scheduler المحلي فقط**. يجب اعتماد نسخة الكود/الساعة الحقيقية/سياسة حفظ GitHub قبل أول تشغيل LIVE؛ لا يمكن استرجاع الماضي كأنه رصد جديد. GitHub سيظل مستودع الكود والأدلة الدائمة، لا سيرفر تشغيل السوق.

### سجل «Windows Runner» القديم — إنجاز هندسي تاريخي، لا مسار تنفيذ أو نشر حالي

**2026-10-29 owner authorization (design/diagnostic only):** [Issue #11 consolidated implementation order](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11#issuecomment-6489732482) approves exactly ONE bounded read-only BTCUSDT Spot public market GET smoke directly on owner Windows D:, separately from prospective study, and approves the DESIGN/TEST of a GitHub-only small single-study evidence journal. PRIVATE repo branch rulesets API returned 403 requiring Pro/public; branch protection is not proven, so no runtime GitHub write credential or asserted immutable journal is authorized yet. No study LIVE, Score/Telegram/trading or claim of full 14-stage implementation. Stage00–03 current E2E administrative proof is pending actual on-device integrated evidence and clock/journal gates.


Added date-accurate Windows TaskScheduler XML `StartBoundary` conversion, on-demand native GUI and pinned D: `pythonw.exe` no-console action. Owner-PC Codex report confirms **>=3 genuine scheduled Event107/201/result0 runs** on 2026-10-29 05:26–05:30 UTC, `HTTP=0`, GUI Start/Pause/Status/Recovery, and owner physically confirmed the black flash did not appear. One task deliberately **PAUSED** after tests, lease ends 2026-10-30 05:26:55 UTC (08:26:55 Riyadh); no auto-renewal and requires owner sign-in/awake Windows.

**Owner local launcher:** `D:\ZS-SMART-GATE\SMART GATE Runner.lnk`. All project files/logs/env/cache on D; ordinary Windows-managed time/scheduler settings on system C allowed.

**Strict research block:** W32Time current root dispersion **7.8033984s** fails 1.0s prospective research policy; OS offset alone is insufficient. Only 3 public Binance server-time calibration GET (no market observations). New prospective Oct31 2026 cohort is an **UNAPPROVED/UNFROZEN PROPOSAL**, GitHub durable evidence branch/claim protocol and credentials are not implemented or approved. No LIVE, new scientific PIT sample, scoring, signal, Telegram, trading or 24/7 claim. Keep [Issue #11](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11) and [Issue #8](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/8) OPEN for distinct remaining gates.

**Old 03B3 remains CANCELED** with audited GitHub history retained; old samples excluded from evaluation, and no old cron/manual workflow remains active.
## قواعد العمل للمحادثات وSD / Coding

1. لا تعتمد على عبارات حالة تاريخية داخل Blueprint قديم أو على Project Resources متأخرة. **مزامنة Project Resources مع GitHub ليست تلقائية.**
2. **PR Conversation** للأوامر وتقارير الاختبارات وقبول PM. لا ملفات Markdown جديدة للحَوْكمة **README وMASTER فقط**.
3. **02 و03A و03B1 متحقق منها ضمن نطاق كل جزء، و03B2 التاريخية مغلقة بنتيجة غير كافية، و03B3 الأصلية CANCELLED_BY_OWNER ومستبعدة من تقييم البحث.** دراسة «Windows» المستقبلية المنصوص عليها تاريخيًا في «Issue #11» مؤجلة بقرار المالك في 30 أكتوبر 2026؛ لا «Scoring» رقمي أو إشارة إنتاجية أو تداول بدون اعتماد منفصل.
4. **GitHub هو مصدر الحقيقة لكل البيانات الدائمة**؛ بعد اكتمال المشروع وقبول النشر يصبح كمبيوتر «Windows» خادم التنفيذ الفعلي؛ لا نشر محلي كامل الآن. لا أسرار داخل Repo، ولا قرارات Storage Backend/تكلفة/تداول حقيقي دون موافقة المالك. الاختبارات يجب أن تثبت تكامل المسار المنفذ فقط؛ لا ادعاء اكتمال SMART GATE غير المبني.

**Repository:** [scannercrypto0-gif/zs-crypto-signals](https://github.com/scannercrypto0-gif/zs-crypto-signals) · **Private** · **MASTER v1.20 / Unified Design v2.1** · **Verified full phases 00–02 / 14; 03A/03B1 VERIFIED; 03B2 code accepted, original study closed insufficient 8/12; original 03B3 GH study owner-cancelled, 0/12 observed, former Windows future study Issue #11 deferred by owner; Phase 03 IN PROGRESS; no trading authorization**.
