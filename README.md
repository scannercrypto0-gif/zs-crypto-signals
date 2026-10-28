# ZS Crypto Signals — SMART GATE

**مشروع مستقل** لبناء رادار بحثي لاكتشاف فرص الصعود والهبوط مبكرًا على **Binance Spot USDT**، مع خطط تداول Spot يدوية قابلة للتقييم العلمي، ومسارين منفصلين **Intraday** و**Swing**. لا يوجد تداول آلي حقيقي مصرح به.

## اقرأ المرجع الرسمي أولًا

**[ZS_SMART_GATE_MASTER.md — MASTER v1.4](./ZS_SMART_GATE_MASTER.md)** هو مصدر الحوكمة والمواصفات المُجمعة وقرارات المالك. يتضمن في بدايته **SMART GATE — UNIFIED DESIGN v2.1**، ثم خارطة **14 مرحلة (00–13)**، وإصدارات Score، وعقود Telegram/Analytical Data/Trade Plans، وسجل القرارات، والـTechnical Blueprint التاريخي محفوظًا. عند تعارض مقترح قديم مع قسم التصميم الموحد المعتمد، تُطبَّق قواعد الأسبقية داخل MASTER.

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

**الأوزان V2 نقطة انطلاق بحثية وافق المالك على اختبارها، وليست دقة مثبتة أو Probability.** تظل معادلات ونتائج **Scoring V1 (35/25/20/10/10)** محفوظة مستقلة. قيم EMA/RSI/MACD/POC/VWAP/OI/CVD/BTC وغيرها تُسجل مع مصدرها وزمنها وتخضع لاختبار الفائدة قبل أي أوزان جديدة. Score منخفض **لا يمنع إرسال Signal مؤهلة**؛ وعند فقد قيمة أساسية تظهر \`SCORE_UNAVAILABLE\` بدل رقم مختلق.

## نظام Telegram والتحليل المستقبلي

- **Primary Bot → Chat A + Chat B:** **كل Signal مؤهلة**، مع \`signal_id\` وScore والإطار والاتجاه و\`trade_plan_status\` و**Entry Zone/SL/TP1/TP2/TP3 إن ثبتت خطة صالحة**؛ وإلا \`RESEARCH_ONLY\` بوضوح. DOWN تحذير هبوط أو Sell Existing Spot؛ ليس Short.
- **Analytical Bot → Chat C واحد فقط:** ملخص إنساني و**JSON machine-readable** لكل Signal بمصدر/إصدار/بصمة SHA-256، يضم مكونات Score وOHLCV والشموع الداخلية والهيكل والفلاتر وجميع قيم المؤشرات **المنفذة والمتاحة** وبيانات القرار/الإرسال وخطة الصفقة وReason Codes. لا توثيق مزيف لمؤشر لم يُبنَ.
- **Shared Primary Key:** نفس \`signal_id\` في رسائل الوجهات الثلاث؛ معرفات \`bot/chat/message\` تخص عمليات الإرسال، وتُدمج صادرات Telegram في **إشارة واحدة** مع Deliveries منفصلة. بيانات JSON الدائمة على **GitHub** وفق آلية Storage سيتم اعتمادها؛ Telegram Export وحده ليس ضمانًا لوجود جميع المرفقات.
- **Interactive Primary Bot:** \`/analyze\`, \`/intraday\`, \`/swing\`, \`/structure\`, \`/indicators\`, \`/signal\`, \`/plan\`, \`/status\` لمستخدم/Chat مصرح له. كل طلب له \`analysis_request_id\` منفصل ولا يُحسب كإشارة Scanner جديدة.
- **Outcome Research:** تقييم الوصول إلى Entry وبعدها SL/TP بالترتيب **بعد وقت إتاحة الرسالة**، مع \`NOT_TRIGGERED\` و\`AMBIGUOUS_SEQUENCE\` عند عدم إمكان إثبات المسار، واحتفاظ بتاريخ الإشارة الأصلي دون إعادة كتابة.

## حالة الإنجاز — 28 أكتوبر 2026

**المراحل: 14**؛ **00 و01 VERIFIED / MERGED** بعد PR #1، باختبارات Offline **51/51 لكل بيئة من 4** وBinance Spot LIVE BTCUSDT بعينة واحدة، و[CI بعد الدمج](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/40658793880) ناجح. **02 — FOUNDATION-002 NEXT، [Draft PR #2](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/2) غير مدمج**. بقية 03–13 PLANNED، ولا نظام Telegram LIVE أو V2 Score أو Trade Plans أو Scanner 24/7 مُثبت بعد.

**تحديث خارطة التنفيذ داخل MASTER:** 03 هوية الإشارة وتأهيل 30m/4h وV2/Plan contracts؛ 04 سجلات GitHub؛ **05A/05B/05C** Primary/Analytics JSON/Interactive؛ **06A/06B** Outcomes/Telegram Export→SQL؛ 07 Intraday pre-move؛ 08 Swing Structure؛ 09 Volume Profile/Trade levels؛ 10–12 سياقات ونماذج؛ 13 تشغيل واسترداد كامل. العدد الإجمالي لا يتغير إلا بقرار جديد؛ تقسيمات A/B/C شرائح ضمن المراحل.

## قواعد العمل للمحادثات وSD / Coding

1. اقرأ أحدث MASTER v1.4 وREADME وحالة **main/PRs/CI** مباشرة قبل أي عمل؛ لا تعتمد على عبارات حالة تاريخية داخل Blueprint قديم أو على Project Resources متأخرة. **مزامنة Project Resources مع GitHub ليست تلقائية.**
2. **PR Conversation** للأوامر وتقارير الاختبارات وقبول PM. لا ملفات Markdown جديدة للحَوْكمة؛ **README وMASTER فقط**. الكود والاختبارات وCI/config والبيانات التشغيلية المعتمدة مسموحة حسب مراحلها.
3. **لا توسّع نطاق Draft PR #2 تلقائيًا** لمجرد تحديث التصميم؛ أعرض أثر المواصفة على التنفيذ وتبعيات المراحل وأي قرارات تقنية ناقصة، ونفّذ العمل المعتمد الحالي فقط حتى يصدر أمر جديد.
4. **GitHub هو مصدر الحقيقة لكل البيانات الدائمة**؛ Windows جهاز Runtime 24/7 فقط. لا أسرار داخل Repo، ولا قرارات Storage Backend/تكلفة/تداول حقيقي دون موافقة المالك. الاختبارات يجب أن تثبت تكامل المسار المنفذ فقط؛ لا ادعاء اكتمال SMART GATE غير المبني.

**Repository:** [scannercrypto0-gif/zs-crypto-signals](https://github.com/scannercrypto0-gif/zs-crypto-signals) · **Private** · **MASTER v1.4 / Unified Design v2.1** · **Verified phases 00–01 / 14**.
