# تقرير تجميد V4.2 بعد تحديث توقع `takrar_insan`

**التاريخ:** 2026-09-17

## الحكم التنفيذي

تم تحديث **توقع الاختبار فقط** في:

```text
scripts/test_baseline_v4_2_real_muaalem_data_v2.py
```

ولم يُجرَ أي تعديل جديد على مصدر V4.2:

```text
source/siraj_alignment_baseline_v4_2.py
```

أصبح توقع حالة takrar_insan:

```text
expected_records = [("insert", [1, 2] )]
allow_multi_word = True
```

وذلك لأن الإدراج عند المرساة [8,8] يقع على حد بين كلمتين، وتمثيله الصحيح هو word_boundary مع الكلمتين [1,2].

## الاختبار المنفرد

شُغّل takrar_insan وحده بواسطة:

```text
scripts/v42_freeze_20260917/run_takrar_expectation_only.py
```

والنتيجة:

```text
passed = true
num_records = 1
display_type = insert
affected_word_indices = [1, 2]
anchor_kind = word_boundary
reason = طابق التوقع تمامًا
```

## إعادة تشغيل الحالات الست

أُعيد تشغيل المشغل الكامل للحالات الحقيقية الست باستخدام natai_phonemes_hafiz.json.

النتيجة:

```text
all_passed = true
6/6 cases passed
```

الحالات:

| الحالة | النتيجة |
|---|---|
| hadhf_huwa | passed |
| hadhf_insan | passed |
| takrar_insan | passed بعد تحديث التوقع |
| sahih_vs_sahih | passed |
| maqtoo_juzyan | passed |
| harakah_lillahi | passed |

وتظل الصياغة المنهجية الصحيحة هي أن نجاح 6/6 تحقق بعد تحديث توقع الاختبار، لا بعد تعديل خوارزمية V4.2 جديد.

## توضيح regression

سجل المقارنة الآلي يبين أن old_all_passed=false وnew_all_passed_under_legacy_expectations=false، مع بقاء الحالات الخمس التي كانت ناجحة سابقًا دون تغيير. لذلك لا تُسمى 6/6 regression خالصة. الأدق هو:

```text
5 previously-passing cases unchanged and still passing
1 takrar_insan behavior changed by the authorized V4.2 patch
1 test expectation updated to accept the intended word_boundary result
```

هذه ليست مشكلة نزاهة؛ فالتحول مقصود وموثق. لكنها تفرق بين سلامة regression للحالات السابقة وبين قبول السلوك الجديد في takrar_insan. صحة [1,2]/word_boundary هي نتيجة هندسية مدعومة بالمرساة [8,8]، وليست اعتمادًا تربويًا من الشيخ.

## إثبات عدم تعديل النواة

بصمة مصدر V4.2 بعد التجميد:

```text
45ce96e73d4cf731b4d84e86b8a949a32228e1914563d564f7683978718e5d7f
```

وهي البصمة نفسها التي كانت بعد إصلاح word_boundary السابق. التغيير الحالي محصور في ملف الاختبار، والمشغل الصغير الخاص بالاختبار، وملفات النتائج والتوثيق.

لم تُلمس:

```text
adaa.py
ph_index.npy
muqarin.py
WordLocalAligner
source/siraj_alignment_baseline_v4_2.py
```

## قرار التجميد

يُجمَّد V4.2 في هذه النقطة. لا تُجرى إصلاحات إضافية على مصدره في الجولة الحالية.

الحالة النهائية:

```text
V4.2 boundary patch       = passed
Levenshtein 500           = passed
real six cases            = 6/6 بعد تحديث التوقع
live bridge               = 22/22
KATHRA end-to-end / adaa  = 7/9، بمشكلة مستقلة في adaa/explain_error
```

## السؤال المعماري التالي لـV5-local

لا يزال السؤال المفتوح هو مصدر حدود كلمات الطالب:

```text
Muaalem flat phoneme stream
        ↓
هل يمكن استخراج حدود كلمات موثوقة منه وحده؟
        ↓
WordLocalAligner
```

يجب عدم اعتبار حدود ph_index.npy المرجعية دليلًا على أن التوطين التلقائي من Muaalem قد حُلّ. في الجسر السابق كانت الحدود reference-assisted. لذلك تكون الخطوة التالية تجربة صغيرة على الحالات الموجودة، تقارن صراحة بين:

```text
automatic segmentation from Muaalem
```

و:

```text
reference-assisted segmentation from ph_index.npy
```

ولا يُبنى V5-local كبير قبل حسم هذه النقطة بالتجربة.

## الأدلة

اختبار takrar المنفرد:
`results/v42_freeze_20260917/takrar_expectation_only.json`

نتيجة الحالات الست بعد تحديث التوقع:
`results/v42_freeze_20260917/v42_real_muaalem_data_after_expectation_update.json`

خرج الحالات الست:
`results/v42_freeze_20260917/v42_real_muaalem_data_after_expectation_update.stdout.txt`

مشغل الاختبار المنفرد:
`scripts/v42_freeze_20260917/run_takrar_expectation_only.py`

مشغل الحالات الست المحدث:
`scripts/test_baseline_v4_2_real_muaalem_data_v2.py`

تقرير الإصلاح السابق:
`docs/V42_PATCH_VERIFICATION_REPORT_20260917.md`
