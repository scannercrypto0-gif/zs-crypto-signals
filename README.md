# ZS Crypto Signals — SMART GATE

**مشروع مستقل** لبناء رادار بحثي لاكتشاف فرص الصعود والهبوط مبكرًا على **Binance Spot USDT**، مع خطط تداول Spot يدوية قابلة للتقييم العلمي، ومسارين منفصلين **Intraday** و**Swing**. لا يوجد تداول آلي حقيقي مصرح به.

## اقرأ المرجع الرسمي أولًا

**[ZS_SMART_GATE_MASTER.md — MASTER v1.14](./ZS_SMART_GATE_MASTER.md)** هو مصدر الحوكمة والمواصفات المُجمعة وقرارات المالك. يتضمن في بدايته **SMART GATE — UNIFIED DESIGN v2.1**، ثم خارطة **14 مرحلة (00–13)**، وإصدارات Score، وعقود Telegram/Analytical Data/Trade Plans، وسجل القرارات، والـTechnical Blueprint التاريخي محفوظًا. عند تعارض مقترح قديم مع قسم التصميم الموحد المعتمد، تُطبَّق قواعد الأسبقية داخل MASTER.

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

## حالة الإنجاز — 28 أكتوبر 2026

**المراحل: 14؛ 00 و01 و02 VERIFIED / MERGED.** PR #1 نواة PIT نجحت في 51/51 اختبارًا ×4 وBinance LIVE لعينة BTCUSDT. **[PR #2 — FOUNDATION-002 MERGED](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/2)** بالـCommit `babaab27fdab9172c7e2e425c54bb74f193269ac`؛ **[81/81 اختبار ×4 بيئات](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40670260147)**، و**[3/3 Binance LIVE عيّنات Ubuntu/Windows](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40670254662)**، و**[main post-merge CI 4/4 SUCCESS](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40671318148)**. *حدود الإنجاز:* جرد 770 زوج Spot USDT، منها 43 مؤهلًا في لحظة العينة، لكن جرى جلب شموع **2 أو 4 عملات فقط لكل دورة**؛ لا مسح كامل مستمر للسوق أو Telegram أو Scoring V2. **03 — IN PROGRESS: 03A/03B1 VERIFIED؛ دراسة 03B2 التاريخية مغلقة بدليل غير كاف؛ 03B3 الأصلية أُلغيت بقرار المالك (9 LATE + 3 ملغاة، 0/12 OBSERVED_PIT).** أزيلت جدولة GitHub من main. الدراسة البديلة الجديدة [Windows prospective Issue #11](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11) قيد التنفيذ/التسجيل المسبق، ولم تبدأ LIVE بعد. 04–13 غير مكتملة، ولا Scoring إنتاجي أو Signal أو تداول.

**03A Contracts-Only مكتملة ومُدمجة:** [PR #3](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/3) بالـCommit `6b9267b6193423b305f8d8f72bf6b347c18cd9f7`، واختبارات [124/124 ×4](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40673906928) و[post-merge main CI 4/4](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40675804185) ناجحة. الموجود **عقود ومطابقة زمنية MTF/هوية بحثية وScore/Plan RESEARCH_ONLY فقط، مع E2E fixtures غير متصلة ببيانات LIVE 30m/4h**؛ لم تُطبّق قواعد Qualification/Score العددية أو إصدار `signal_id` أو Signal حقيقية. **03B1 LIVE MTF Research مكتملة ومُدمجة:** [PR #4](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/4) بالـCommit `7894e90598d2249e7ed81b4ab1cf616f302cdc60`، [144/144 اختبار ×4](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40677733914)، [Binance LIVE 4/4](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40677726583) عبر Ubuntu/Windows لمساري 30m و4h على **BTCUSDT فقط**، و[post-merge main CI](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40678707862) ناجح. المطابقة بين الشمعة الرئيسية والشموع الداخلية كانت صفر فروق في العينات؛ المخرجات **مقاييس وصفية RESEARCH_METRIC_UNAPPROVED** بلا Score أو Signal أو خطة جاهزة. **03B2 كود بحثي مقبول ومُدمج** بموافقة المالك الاستثنائية: [PR #5](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/5)، الدمج `8c0c4c302154babc1abef135eafa06bc27dd2100`، [161 اختبارًا ناجحًا ×4](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40682984765)، و[تشغيل Binance LIVE #40682977963](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40682977963) نتيجته الإجمالية **FAILURE**: 8/12 استرجاع ومطابقة ناجحة، 4 ADAUSDT رفضها فلتر السيولة الحالي؛ **النتيجة العلمية `INSUFFICIENT_EVIDENCE`**، والتاريخية المسترجعة لا تثبت المشاهدة الأصلية وقت الحدث؛ [post-merge CI #40685068223](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40685068223) ناجح. **03B2 RESEARCH CLOSED WITH INSUFFICIENT_EVIDENCE (original frozen 8/12; do not rerun/rewrite). 03B3 CODE ACCEPTED/MERGED:** [PR #6](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/6), merge `38f7fa6fff3bc3fd7520306b7dbb98fff400db65`، [182 اختبارًا ×4](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40688359811) ناجح، [post-merge main CI](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40693383443) ناجح. **REAL 30m/4h POST-CLOSE LIVE لم يُثبت بعد، 0/12 لحظة التسليم؛ 03B3 NOT FULLY VERIFIED.** لا استنتاجات تنبؤية أو قواعد تداول. تحديث خارطة التنفيذ داخل MASTER: 03 هوية الإشارة وتأهيل 30m/4h وV2/Plan contracts؛ 04 سجلات GitHub؛ **05A/05B/05C** Primary/Analytics JSON/Interactive؛ **06A/06B** Outcomes/Telegram Export→SQL؛ 07 Intraday pre-move؛ 08 Swing Structure؛ 09 Volume Profile/Trade levels؛ 10–12 سياقات ونماذج؛ 13 تشغيل واسترداد كامل. العدد الإجمالي لا يتغير إلا بقرار جديد؛ تقسيمات A/B/C شرائح ضمن المراحل.


### سجل القرارات والاختبارات غير المحسومة — مرجع واحد

المرجع الرسمي هو [Active Evidence & Release-Gate Register v1.12](./ZS_SMART_GATE_MASTER.md) (ثمانية بنود). **دراسة 03B3 المجمدة القديمة أُلغيت بناءً على طلب المالك** يوم 28 أكتوبر 2026، وليس لأنها أصبحت دراسة LIVE ناجحة: ثلاث تشغيلات فعلية في GitHub حدثت متأخرة أكثر من 40 دقيقة، وكل واحدة نتج عنها ثلاث حالات `LATE` وصفر طلبات Binance؛ أي **9 LATE + 3 CANCELLED_BEFORE_EVENT = 12 خانة إداريًا، 0/12 بيانات PIT**. [توثيق قرار الإلغاء على PR #7](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/7#issuecomment-6477236612)؛ حُذف `stage03b3-auto.yml` من `main` عند commit `283710e31ab91d8e53fb4a559cbee10512b62042`، وعُطلت متابعة إغلاقها القديمة. **لا تشغيل يدوي ولا إعادة تسجيل نفس الدراسة**. تُحفظ السجلات السابقة للأوديت فقط وتُستبعد من أي تقييم علمي.

**البداية الجديدة:** [Issue #11](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11) يأمر Codex بإعداد تجربة مستقبلية مستقلة تمامًا بمواعيد مطلقة جديدة و`study_id`/SHA جديد وتوقيت **Windows Task Scheduler المحلي فقط**. يجب اعتماد نسخة الكود/الساعة الحقيقية/سياسة حفظ GitHub قبل أول تشغيل LIVE؛ لا يمكن استرجاع الماضي كأنه رصد جديد. GitHub سيظل مستودع الكود والأدلة الدائمة، لا سيرفر تشغيل السوق.

### Windows local runner — no-console GUI and true scheduled simulations accepted; actual LIVE still BLOCKED

**2026-10-29 owner authorization (design/diagnostic only):** [Issue #11 consolidated implementation order](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11#issuecomment-6489732482) approves exactly ONE bounded read-only BTCUSDT Spot public market GET smoke directly on owner Windows D:, separately from prospective study, and approves the DESIGN/TEST of a GitHub-only small single-study evidence journal. PRIVATE repo branch rulesets API returned 403 requiring Pro/public; branch protection is not proven, so no runtime GitHub write credential or asserted immutable journal is authorized yet. No study LIVE, Score/Telegram/trading or claim of full 14-stage implementation. Stage00–03 current E2E administrative proof is pending actual on-device integrated evidence and clock/journal gates.


[PR #13 ACCEPTED AND MERGED](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/13), reviewed exact head `5be9c86642ec38f9266be5b7c90e944fdfadf160`, merge `27a381c7a8962a709c48545cb3993ab2d7a268bb`; [CI 242 tests ×4](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40823313293) PASS. Added date-accurate Windows TaskScheduler XML `StartBoundary` conversion, on-demand native GUI and pinned D: `pythonw.exe` no-console action. Owner-PC Codex report confirms **>=3 genuine scheduled Event107/201/result0 runs** on 2026-10-29 05:26–05:30 UTC, `HTTP=0`, GUI Start/Pause/Status/Recovery, and owner physically confirmed the black flash did not appear. PM verified source and GitHub CI, **not raw D: artifacts**. One task deliberately **PAUSED** after tests, lease ends 2026-10-30 05:26:55 UTC (08:26:55 Riyadh); no auto-renewal and requires owner sign-in/awake Windows.

**Owner local launcher:** `D:\ZS-SMART-GATE\SMART GATE Runner.lnk`. All project files/logs/env/cache on D; ordinary Windows-managed time/scheduler settings on system C allowed. No persistent Codex/LLM or GitHub Actions hosted market execution.

**Strict research block:** W32Time current root dispersion **7.8033984s** fails 1.0s prospective research policy; OS offset alone is insufficient. Only 3 public Binance server-time calibration GET (no market observations). New prospective Oct31 2026 cohort is an **UNAPPROVED/UNFROZEN PROPOSAL**, GitHub durable evidence branch/claim protocol and credentials are not implemented or approved. No LIVE, new scientific PIT sample, scoring, signal, Telegram, trading or 24/7 claim. Keep [Issue #11](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11) and [Issue #8](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/8) OPEN for distinct remaining gates.

**Old 03B3 remains CANCELED** with audited GitHub history retained; old samples excluded from evaluation, and no old cron/manual workflow remains active.
## قواعد العمل للمحادثات وSD / Coding

1. اقرأ أحدث MASTER v1.14 وREADME وحالة **main/PRs/CI** مباشرة قبل أي عمل؛ لا تعتمد على عبارات حالة تاريخية داخل Blueprint قديم أو على Project Resources متأخرة. **مزامنة Project Resources مع GitHub ليست تلقائية.**
2. **PR Conversation** للأوامر وتقارير الاختبارات وقبول PM. لا ملفات Markdown جديدة للحَوْكمة؛ **README وMASTER فقط**. الكود والاختبارات وCI/config والبيانات التشغيلية المعتمدة مسموحة حسب مراحلها.
3. **02 و03A و03B1 متحقق منها ضمن نطاق كل جزء، و03B2 التاريخية مغلقة بنتيجة غير كافية، و03B3 الأصلية CANCELLED_BY_OWNER ومستبعدة من تقييم البحث.** يُسمح فقط بالدراسة المستقبلية الجديدة الموافق عليها Windows Issue #11، بمواعيد وهوية جديدة؛ لا Scoring رقمي أو Signal أو تداول بدون اعتماد منفصل.
4. **GitHub هو مصدر الحقيقة لكل البيانات الدائمة**؛ Windows جهاز Runtime 24/7 فقط. لا أسرار داخل Repo، ولا قرارات Storage Backend/تكلفة/تداول حقيقي دون موافقة المالك. الاختبارات يجب أن تثبت تكامل المسار المنفذ فقط؛ لا ادعاء اكتمال SMART GATE غير المبني.

**Repository:** [scannercrypto0-gif/zs-crypto-signals](https://github.com/scannercrypto0-gif/zs-crypto-signals) · **Private** · **MASTER v1.14 / Unified Design v2.1** · **Verified full phases 00–02 / 14; 03A/03B1 VERIFIED; 03B2 code accepted, original study closed insufficient 8/12; original 03B3 GH study owner-cancelled, 0/12 observed, new Windows future study Issue #11 preparing; Phase 03 IN PROGRESS; no trading authorization**.
