# «Stage03 C1–C4» — مصفوفة إغلاق المكوّنات، 8 نوفمبر 2026

**السلطة الحالية:** [قرار «PM» #6725877613](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6725877613)؛ [قرار التكامل](n03-v02-r2-timing-integration-decision-20261108.md). **المراجع الأصلية:** [تدقيق «PM» #6721751412](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6721751412). **الأساس:** «main» `a4f9208839ecdae767f2da082c9fa57d4d9ac2fc`. هذه مصفوفة حساب وبحث، لا اعتماد إشارة إنتاجية.

**الأحكام الحالية:** «REUSE» يعيد استخدام الأدلة السابقة ضمن حدودها، ولا يعني إعادة حساب مستقل جديد؛ «FIX» يشير إلى إصلاح محدد تم التحقق منه؛ «SCOPED_NON_EQUIVALENCE» يثبت اختلاف النطاق دون صيغة بديلة أو تحويل رقمي. تعريف «N03 V0.2» التشغيلي مقبول من المالك، بينما توقيت «R2» يبقى غير متاح.

## المؤشرات «N01–N12»

| المؤشر | التنفيذ والصيغة والوحدة/النافذة | دليل قائم دون إعادة اختبار | الفجوة أو عدم اليقين الفعلي | الحكم |
|---|---|---|---|---|
| «N01» | `close_parts` لـ«30m»: `(8k+6b+6w)/20`؛ اتجاه «UP/DOWN» ونطاق 0–1 | `test_basic_close_path_symmetric_and_unsupported_inputs`؛ `test_stage03_r2_offline.py` | مراجعة مرجع «C1» مستقل لإثبات قبول الصيغة لا مجرد وجود الاختبار | «REUSE» |
| «N02» | `path_parts` لـ6 شموع «5m»: `(8g+8e+4t)/20`؛ التتابع محفوظ | `test_r2_n02_n09_path_examples`، مرجع حساب سابق | «SEM-I-01» محسوم: **«SCOPED_NON_EQUIVALENCE»** بين الجودة المحددة و`internal_path`؛ لا ربط رقمي بـ«03C» | «REUSE / NO_NUMERIC_03C_MAPPING» |
| «N03» | `onset_timing` قياس توقيت مبكر مشروط بسجل كامل لكل شمعة؛ `evaluate_provisional_n03` «V0.2» يرصد حالة أحدث حلقة وسجل تأكيدات؛ تعريفه التشغيلي **مقبول** | «4/4» على `0aa25f831ee2565454e82f4e4f1e11e71995fd04`، [قرار التكامل](n03-v02-r2-timing-integration-decision-20261108.md) | ثبت **عدم التكافؤ**: `MOMENTUM_EARLY_TIMING=None` مع سبب أصلي؛ `n03_operational_proxy_review` تشخيصي فقط | «REUSE / R2_UNAVAILABLE_NOT_EQUIVALENT» |
| «N04» | `volume_continuity`: استمرارية حجم «quote» مع مرجع 20 شمعة «5m» | `test_n04_isolated_spike_vs_continuous_volume` | «SEM-I-02» محسوم: **«SCOPED_NON_EQUIVALENCE»** مع `volume` العام؛ بلا ربط رقمي بـ«03C» | «REUSE / NO_NUMERIC_03C_MAPPING» |
| «N05» | `prior_range_alignment` لـ21 شمعة «1h» و21 شمعة «4h»، تجميع `(10a+5b)/15` | `test_intraday_mixed_1h_source_blocks_n05_not_parent_arithmetic` لحارس المصدر؛ `test_determinism_and_network_forbidden` يثبت ناتج `MTF_NEARBY_STRUCTURE="0.5"` | **حد مرجع محدد:** لا يظهر في الاختبارين اشتقاق عددي مستقل كامل للتركيب `(10a+5b)/15`؛ لا خلل في الصيغة مثبت ولا شرط اختبار جديد | «REUSE / BOUNDED_REFERENCE» |
| «N06» | `liquidity` لـ«Intraday»: سعر «bid/ask» و«24hr quoteVolume» مستقلان؛ `(3s+2l)/5`؛ عمر «book» 5 ثوان و«ticker24» 60 ثانية **حدود بحثية غير مجمّدة** | «9/9» السابقة لاختبار الحقول والأحجام ومرجع الحساب، و«3/3» مدخل إيصالات «PR #46» | توثيق صلاحية حدود حداثة «R2» البحثية مقابل سلطة المصدر الحقيقي، **من دون اختلاق دليل «PIT»** | «REUSE» |
| «N07» | `structure` قمم وقيعان «4h» مؤكدة «2+2» و«BOS/CHoCH»؛ النمط يُشتق من سياق سابق مستقل «32 × 4h»، لا من «N10» | `test_n07_real_reachable_branch_with_prior_confirmed_pivots`، و«9/9» لحراسة المصدر و«prior mode»، و«3/3» مسار «Swing» | تثبيت قبول دلالة النمط السابق ومراجعة المرجع/صلاحية حدّه عند «C1»؛ لا اجتهاد بربط جديد | «REUSE» |
| «N08» | `close_parts` لـ«4h»: `.4k+.3b+.3w` | `test_n08_n09_n10_n11_n12_swing_contract_values_and_no_03c_calls` | مراجعة المرجع المستقل قبل الحكم النهائي؛ لا خلل برمجي مثبت يتطلب إعادة كتابة | «REUSE» |
| «N09» | `path_parts` لـ4 شموع «1h»: `.4g+.4e+.2t` | `test_r2_n02_n09_path_examples` وشواهد «Swing» السابقة | «SEM-S-01» محسوم: **«SCOPED_NON_EQUIVALENCE»** مع `internal_path` الأوسع؛ بلا ربط رقمي بـ«03C» | «REUSE / NO_NUMERIC_03C_MAPPING» |
| «N10» | `context_movement` لسياقي «1d/1w»؛ `.6 daily+.4 weekly` مع سبب عدم التوافر | «9/9» حدود التقويم و`test_n10_two_closed_frames_and_context_only` | «SEM-S-02» محسوم: **«SCOPED_NON_EQUIVALENCE»** مع `higher_context` الأوسع؛ بلا ربط رقمي بـ«03C» | «REUSE / NO_NUMERIC_03C_MAPPING» |
| «N11» | `MOMENTUM_VOLUME`: 20 شمعة «4h» قبل الأب، «ATR14» وحجم «quote»؛ `.6fpos(m)+.4fpos(v)` | `test_n08_n09_n10_n11_n12_swing_contract_values_and_no_03c_calls` | مراجعة مستقلة لمرجع «C1» والنافذة؛ لا تعديل حسابي بغير عيب محدد | «REUSE» |
| «N12» | نفس عقد `liquidity` الحسابي بوضع «Swing»، مع مصدرَي «book/ticker24» المنفصلين | «9/9» لمرجع حجم الأصل/عملة التسعير، و`test_n06_n12_quote24_units_reference_and_missingness` | حدود مصدر/توقيت واقعية غير مثبتة من المعطيات الصناعية؛ لا تُستنتج سيولة غير موجودة | «REUSE» |

**حد القبول:** أكد «PM» جرد أدلة «C1» الاثني عشر لإعادة الاستخدام فقط، لا بوصفه إعادة حساب مستقلة جديدة «12/12». لم يثبت عيب حسابي يستدعي حملة اختبارات. حد المرجع العددي الظاهر تحديدًا هو «N05» في `prior_range_alignment` واختبارَي المصدر والحتمية أعلاه؛ لا يُخلق منه شرط اختبار جديد. نتائج «9/9» و«3/3» و«3/3» السابقة محفوظة في نطاق بصماتها، وكذلك «3/3» لمسودة «C3» و«4/4» لإصلاح «N03» المقدم من المالك.

## القرارات الدلالية الأربع — حُسمت بعدم التكافؤ دون تحويل رقمي

| المعرّف | الربط في `stage03_contract_alignment.py` | اختلاف المجال | قرار «PM» المقبول | الحكم |
|---|---|---|---|---|
| «SEM-I-01» | `SIX_5M_INTERNAL_QUALITY` ↔ `internal_path` | جودة ست شموع لا تتطابق مع معنى المسار الأوسع | **«SCOPED_NON_EQUIVALENCE / NO_NUMERIC_03C_MAPPING»**؛ يبقى `UNMAPPED` | «RESOLVED_NON_EQUIVALENT» |
| «SEM-I-02» | `VOLUME_CONTINUITY` ↔ `volume` | الاستمرارية ليست تعريفًا عامًا للحجم | **«SCOPED_NON_EQUIVALENCE / NO_NUMERIC_03C_MAPPING»**؛ يبقى `UNMAPPED` | «RESOLVED_NON_EQUIVALENT» |
| «SEM-S-01» | `FOUR_1H_INTERNAL_QUALITY` ↔ `internal_path` | جودة الأبناء ليست المسار العام | **«SCOPED_NON_EQUIVALENCE / NO_NUMERIC_03C_MAPPING»**؛ يبقى `UNMAPPED` | «RESOLVED_NON_EQUIVALENT» |
| «SEM-S-02» | `DAILY_WEEKLY_CONTEXT` ↔ `higher_context` | السياق اليومي والأسبوعي نطاق أضيق | **«SCOPED_NON_EQUIVALENCE / NO_NUMERIC_03C_MAPPING»**؛ يبقى `UNMAPPED` | «RESOLVED_NON_EQUIVALENT» |

## إصلاح «C3» البرمجي المحدد — «FIX»

**الفجوة المثبتة:** مسار `stage03_r2_from_closed_receipts` قبل هذه الحزمة يرجع مرشحًا بحثيًا مع مجموعة `normalizers` و`missing_reasons` منفصلتين، أو يرمي `Unavailable` إذا فشلت صحة الإدخال. **لم يكن هناك مخرج واحد قابل للاستدعاء يربط «N01–N12» بأحكام القيم المفقودة وأسباب الرفض مع الاحتفاظ بالفصل الصريح بين البحث والتأهيل.**

**الإصلاح:** `stage03_c1c4_research_from_closed_receipts` داخل `src/zs_smart_gate/stage03_r2_closure.py` يستخدم الكود المقبول دون إعادة حساب الصيغ. يُرجع بصمة نتيجة حتمية، وصفوفًا فردية لكل مؤشر من الأفق المطلوب، وسبب فقده، وقائمة القرارات الأربع المعلّقة. أي إدخال منقوص/مختلط/مستقبلي **يُرفض مع رمز السبب، بلا صنع مرشح أو قيمة مفقودة تساوي الصفر**. كل الحسابات الرقمية تبقى «RESEARCH_VALUE_PRESENT_NOT_ACCEPTED» أو معلّقة دلاليًا؛ لا «production score»، ولا «signal_id».

**التحقق المعاد استخدامه:** نجحت «3/3» لحزمة «C3» على `fe76cb4743acdb189ec942e76ac4c296abb1c2fc` ثم «4/4» لإصلاح «N03 V0.2» وحالة عدم التوافر على `0aa25f831ee2565454e82f4e4f1e11e71995fd04` بحسب سجل المالك على «Windows»؛ لا إعادة اختبارات أو اختبارات جديدة لهذا القرار الوثائقي.

## ملخص الأبواب «C1–C4» وحالة التسليم

| الباب | الثابت/الموجود | المتبقي المحدد | الحكم |
|---|---|---|---|
| «C1» التعريف والمراجع | الجرد المرجعي لـ«N01–N12» مقبول لإعادة الاستخدام؛ تعريف «N03 V0.2» التشغيلي مقبول والأربع «SEM» محسومة بعدم التكافؤ | «N03» و«R2» **غير متكافئين**؛ الاقتران تشخيصي فقط. المتبقي مراجعة «PM» النهائية لعقد «C1–C4» | **«READY_FOR_PM_CLOSE_REVIEW»** |
| «C2» المصدر والسببية | حراسة إغلاق الشموع و«UTC/as-of» وحقول «24hr» وإيصالات مستقلة صناعية | لا شهادة «PIT» تاريخية؛ إثبات واقعي محدود فقط إذا لزم لسؤال حساب/سببية محدد | **«REUSE / UNVERIFIED_REAL_SOURCE»** |
| «C3» الربط وحالات الرفض | «03A/R2» والهوية البحثية وأسباب الرفض ومخرج المؤشرات | تم تصحيح «N03 UNAVAILABLE» والتحقق منه ضمن «4/4»، دون إنتاج أو تحويل رقمي | **«REUSE / BOUNDED_FIX_VALIDATED»** |
| «C4» أدلة القبول | الشواهد السابقة على بصماتها، و«3/3» ثم «4/4» محليًا على البصمتين المحددتين | قرار توثيقي دون كود؛ لا اختبارات أخرى. المتبقي مراجعة «PM» وقرار المالك | **«WINDOWS_EVIDENCE_REUSED / PM_SIGNOFF_PENDING»** |

**حدود ثابتة:** «Stage03» مفتوحة، ولا يُستعاض عن حكم «C1–C4» بنسبة إنجاز. لا اختبارات جديدة أو «OOS/Forward» أو ربحية أو سوق أو «Telegram» أو تداول أو «Stage05»، ولا تعديل لـ«MASTER/README» أو دمج قبل تصريح المالك.