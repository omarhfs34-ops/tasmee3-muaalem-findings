# تقرير اعتماد الإصلاح المحدود في V4.2

**التاريخ:** 2026-09-17

## الحكم التنفيذي

طُبِّق إصلاح واحد فقط في المصدر المركزي:

```text
/home/ubuntu/siraj_repro/source/siraj_alignment_baseline_v4_2.py
```

التغيير الوحيد هو نقل فحص word_boundary قبل فحص inside_word داخل locate_insertion(). لم تُعدَّل أي دالة أخرى في الملف، ولم تُعدَّل ملفات adaa.py أو ph_index.npy أو muqarin.py أو WordLocalAligner.

نجحت بوابات التحقق المطلوبة. بقيت حالة takrar_insan في اختبار الحالات الست موسومة false على مستوى الاختبار القديم، لأنها كانت فاشلة قبل الإصلاح ولأن توقعها القديم يطلب ملكية الكلمة [1] بدل تمثيل الحد الصحيح [1,2]. أما الحالات الخمس التي كانت ناجحة قبل الإصلاح فقد بقيت ناجحة وبالسجلات نفسها.

القرار: الإصلاح المحدود آمن بالنسبة إلى الاختبارات السابقة، وحقق التصحيح المقصود لملكية الإدراج عند حد الكلمة. تُحفظ حالة takrar_insan كاختبار يحتاج تحديث توقعه الدلالي في جولة منفصلة، لا كـregression ناتج عن الإصلاح.

## التغيير المطبق

قبل الإصلاح كان الكود يفحص احتواء group_idx داخل كلمة قبل فحص الحد. وبما أن نطاقات الكلمات متلاصقة، كانت المرساة التي تحقق نهاية كلمة وبداية الكلمة التالية تُصنَّف داخل الكلمة التالية.

بعد الإصلاح أصبح الترتيب:

```python
before = word_table[word_table["group_end"] == group_idx]
after = word_table[word_table["group_start"] == group_idx]

if not before.empty and not after.empty:
    words = [int(before.iloc[0]["word"]), int(after.iloc[0]["word"])]
    return words, "word_boundary"

inside = word_table[
    (word_table["group_start"] <= group_idx)
    & (group_idx < word_table["group_end"])
]
if len(inside) == 1:
    return [int(inside.iloc[0]["word"])], "inside_word"
```

نسخة الجذر الموجودة باسم siraj_alignment_baseline_v4_2.py بقيت دون تعديل. التشغيل والاختبارات استخدمت النسخة المركزية في source/، وهي النسخة المسجلة كمصدر الاختبارات الحالي.

## البوابة الأولى: KATHRA

أُعيد تشغيل KATHRA_ASR2_KAMIL/TAKRAR من خلال محلل التكرار المحفوظ.

النتيجة الجديدة من V4.2:

```text
display_type = insert
affected_word_indices = [1, 2]
anchor_kind = word_boundary
ref_group_anchor = [8, 8]
```

وهذه هي النتيجة المطلوبة. قبل الإصلاح كانت:

```text
affected_word_indices = [2]
anchor_kind = inside_word
```

بقيت assertions الخاصة بـadaa/explain_error على حالتها السابقة؛ إذ استمرت آثار الـcascade في لَفِى. لذلك انتهى اختبار KATHRA العام إلى 7/9 كما قبل الإصلاح، لكن سجل V4.2 نفسه أصبح صحيحًا في ملكية الحد.

## البوابة الثانية: 500 حالة بـLevenshtein الحقيقي

أُعيد تشغيل:

```text
scripts/test_baseline_v4_2_real_levenshtein.py
```

باستخدام:

```text
Levenshtein 0.27.4
seed=99
sample_size=500
```

النتائج:

| الاختبار | النتيجة |
|---|---|
| فحص اتساق حدود الكلمات في كامل الفهرس | passed؛ 71,197 حدًا، صفر فجوات، صفر تداخلات |
| 200 قراءة مطابقة بلا إنذارات كاذبة، seed=7 | passed؛ صفر فشل، صفر استثناءات |
| 500 حذفًا مفردًا، seed=99 | passed؛ 500/500، صفر سجلات متعددة، صفر cascade متعدد الكلمات، صفر استثناءات |
| اختبارات الحواف والكلمات المتعددة | passed |
| النتيجة الكلية | all_passed=true |

لم يظهر أي regression في اختبار 500 حالة.

## البوابة الثالثة: الحالات الست الحقيقية

أُعيد تشغيل:

```text
scripts/test_baseline_v4_2_real_muaalem_data_v2.py
```

على natai_phonemes_hafiz.json المحلي.

| الحالة | قبل الإصلاح | بعد الإصلاح | مقارنة السجلات |
|---|---|---|---|
| hadhf_huwa | passed | passed | مطابقة تمامًا: delete [2] ثم insert [3] |
| hadhf_insan | passed | passed | مطابقة تمامًا: delete [1] |
| sahih_vs_sahih | passed | passed | مطابقة تمامًا: صفر سجلات |
| maqtoo_juzyan | passed | passed | مطابقة تمامًا: replace [1] ثم delete [2,3] |
| harakah_lillahi | passed | passed | مطابقة تمامًا: replace [1] |
| takrar_insan | failed | failed على الاختبار القديم | تغير مقصود من [2]/inside_word إلى [1,2]/word_boundary |

إذن حافظت الحالات الخمس الناجحة سابقًا على نجاحها وعلى شكل سجلاتها. أما takrar_insan فلم تكن حالة ناجحة قبل التعديل؛ بل كان فشلها هو الدافع للإصلاح. التغير فيها يطابق السلوك المطلوب، وليس regression.

## البوابة الرابعة: الجسر الحي

أُعيد تشغيل:

```text
scripts/bridge_20260917/run_live_bridge.py
```

على:

```text
IBDAL_QADR1
ISQAT_KTR3
```

النتيجة:

```text
IBDAL_QADR1: 11/11
ISQAT_KTR3:  11/11
المجموع:     22/22
```

لم تتأثر نتيجة الإبدال ز→ذ، ولا نتيجة حذف هُوَ، ولا التحويل المحلي إلى العالمي، ولا ربط ph_index بموضع الرسم.

## البوابة الخامسة: التوثيق والحماية

تم تسجيل هذا الإصلاح بوصفه أول تعديل فعلي على V4.2 منذ بداية المشروع. وحُفظت روابط كل نتائج التحقق في سجل القرار وسجل التغييرات.

كما أُجري فحص الصياغة البرمجية بـpy_compile، وفحص JSON، وgit diff --check. لم تُعدَّل ملفات خارج النطاق المأذون به باستثناء ملفات النتائج والتوثيق الناتجة عن الاختبارات.

## الملفات والأدلة

ملف المصدر المعدل:
`/home/ubuntu/siraj_repro/source/siraj_alignment_baseline_v4_2.py`

نتيجة KATHRA بعد الإصلاح:
`/home/ubuntu/siraj_repro/results/v42_patch_20260917/kathra_repetition_analysis.json`

نتيجة 500 حالة:
`/home/ubuntu/siraj_repro/results/v42_patch_20260917/v42_real_levenshtein_after_patch.json`

نتيجة الحالات الست:
`/home/ubuntu/siraj_repro/results/v42_patch_20260917/v42_real_muaalem_data_after_patch.json`

والتحقق الدلالي المستقل من بقاء الحالات الخمس الناجحة دون تغيير:
`/home/ubuntu/siraj_repro/results/v42_patch_20260917/real6_semantic_verification.json`

وسكربته:
`/home/ubuntu/siraj_repro/scripts/v42_patch_20260917/verify_real6_after_patch.py`

نتيجة الجسر الحي:
`/home/ubuntu/siraj_repro/results/v42_patch_20260917/live_bridge_after_patch.json`

## القرار التالي

يمكن اعتماد تغيير ترتيب الفحص في locate_insertion() بوصفه إصلاحًا محدودًا ناجحًا. ولا يُسمح بإضافة إصلاحات أخرى إلى V4.2 في هذه الجولة. التغيير التالي، إن أُريد، يجب أن يكون منفصلًا، مع اختبار regression مستقل، ولا سيما تحديث توقع takrar_insan ليقبل صراحةً تمثيل word_boundary [1,2] بدل خلطه مع فشل التوطين أو الـcascade.

## المراجع

[1] مكتبة Levenshtein المستخدمة في اختبار المحاذاة

[2] المستودع الرسمي لمكونات الربط الفونيمي والنصي
