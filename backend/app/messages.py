"""Fixed bilingual messages and caveats. These are NOT model-generated, so they are predictable.

NOTE: the Urdu strings were drafted quickly. Have a native speaker review every one before the demo.
"""
from __future__ import annotations

from typing import Optional

from .schemas import Caveat, WageInfo

DISCLAIMER_EN = "This is legal information, not legal advice. It does not predict the outcome of any case."
DISCLAIMER_UR = "یہ قانونی معلومات ہیں، قانونی مشورہ نہیں۔ یہ کسی مقدمے کے نتیجے کی پیش گوئی نہیں کرتیں۔"

DANGER_EN = (
    "If you or someone else is in danger right now, call the police on 15 immediately. "
    "You can also reach the helplines below. You are not alone."
)
DANGER_UR = (
    "اگر آپ یا کوئی اور اس وقت خطرے میں ہے تو فوراً پولیس ہیلپ لائن 15 پر کال کریں۔ "
    "آپ نیچے دی گئی ہیلپ لائنز سے بھی مدد لے سکتے ہیں۔ آپ اکیلے نہیں ہیں۔"
)

# Used when no model could answer (all rate-limited, out of time, or not configured). Fixed text, never model-written.
URDU_UNAVAILABLE_UR = "اردو جواب تیار نہیں ہو سکا۔ براہِ کرم نیچے دیا گیا جواب اور قانونی دفعات دیکھیں۔"
BUSY_EN = "The answering service is not available right now. Please try again in a few minutes, or contact one of the helplines below."
BUSY_UR = "جواب تیار کرنے والی سروس ابھی دستیاب نہیں۔ براہِ کرم چند منٹ بعد دوبارہ کوشش کریں، یا نیچے دی گئی ہیلپ لائنز سے رابطہ کریں۔"
BUSY_ROMAN = "Jawab tayyar karne wali service abhi dastiyab nahi. Barah-e-karam kuch minute baad dobara koshish karein, ya neeche di gayi helplines se rabta karein."
DEGRADED_EN = "The service that writes explanations is not available right now. Below is the exact text of the sections of law that best match your question."
DEGRADED_UR = "وضاحت لکھنے والی سروس اس وقت دستیاب نہیں۔ نیچے آپ کے سوال سے سب سے زیادہ ملتی جلتی قانونی دفعات کا اصل متن ہے۔"
DEGRADED_ROMAN = "Wazahat likhne wali service abhi dastiyab nahi. Neeche aap ke sawal se sab se zyada milti julti qanooni dafaat ka asal matn hai."
DEGRADED_CAVEAT = Caveat(
    en="This is a basic result with no explanation: read the law text carefully or call a helpline.",
    ur="یہ بغیر وضاحت کا بنیادی نتیجہ ہے: قانون کا متن غور سے پڑھیں یا ہیلپ لائن پر بات کریں۔",
)

# Shown when the ONLY danger signal is self-harm (no violence against her). Fixed text, never model-written.
# Gender-neutral Urdu on purpose (the user may be any gender). Needs native-speaker review like every Urdu string here.
DANGER_SELFHARM_EN = (
    "If you are thinking about harming yourself, please tell someone you trust right now. "
    "If you are in immediate danger, call 15 now. You are not alone: you can talk to someone on the lines below."
)
DANGER_SELFHARM_UR = (
    "اگر آپ اپنی جان کو نقصان پہنچانے کے بارے میں سوچ رہے ہیں تو براہِ کرم ابھی کسی قابلِ اعتماد شخص کو بتائیں۔ "
    "اگر جان کو فوری خطرہ ہے تو ابھی 15 پر کال کریں۔ آپ تنہا نہیں ہیں، نیچے دی گئی لائنز پر کسی سے بات کی جا سکتی ہے۔"
)

NOT_FOUND_EN = (
    "I could not find the answer to this in the laws I have. Please contact one of the services below "
    "or speak to a lawyer."
)
NOT_FOUND_UR = (
    "مجھے اپنے پاس موجود قوانین میں اس سوال کا جواب نہیں ملا۔ براہِ کرم نیچے دی گئی سروسز سے رابطہ کریں "
    "یا کسی وکیل سے مشورہ کریں۔"
)

OUT_OF_SCOPE_EN = (
    "This question is outside what this app covers. It gives information on what the law says about workplace "
    "harassment, minimum wage and unpaid wages, and women's property rights, and where to go. It cannot calculate "
    "shares, give an opinion on a case, or help with anything unlawful."
)
OUT_OF_SCOPE_UR = (
    "یہ سوال اس ایپ کے دائرے سے باہر ہے۔ یہاں کام کی جگہ پر ہراسانی، کم از کم اجرت اور واجب الادا تنخواہ، اور خواتین کے "
    "جائیداد کے حقوق کے بارے میں قانون کی معلومات اور رجوع کی جگہ بتائی جاتی ہے۔ حصوں کا حساب، کسی مقدمے پر رائے، "
    "یا غیر قانونی کام میں مدد نہیں دی جا سکتی۔"
)

PREDICTION_EN = (
    "I cannot predict whether you will win a case. I can tell you what the law says and where to file a complaint."
)
PREDICTION_UR = (
    "یہ بتانا ممکن نہیں کہ آپ کا مقدمہ جیتا جائے گا یا نہیں۔ یہ بتایا جا سکتا ہے کہ قانون کیا کہتا ہے اور شکایت کہاں درج "
    "کروائی جا سکتی ہے۔"
)


def caveats_for(topic: str, jurisdiction: Optional[str], wage: Optional[WageInfo]) -> list[Caveat]:
    out: list[Caveat] = []
    if topic == "wages":
        out.append(
            Caveat(
                en="Minimum wage rates are revised every year. Confirm the current rate with your provincial Labour Department.",
                ur="کم از کم اجرت ہر سال تبدیل ہوتی ہے۔ موجودہ شرح اپنے صوبے کے محکمۂ محنت سے تصدیق کریں۔",
            )
        )
        if wage and wage.status != "notified_reported":
            out.append(
                Caveat(
                    en="The figure for this province is a proposal or unconfirmed report, not a verified notification.",
                    ur="اس صوبے کی رقم تجویز یا غیر تصدیق شدہ اطلاع ہے، تصدیق شدہ نوٹیفکیشن نہیں۔",
                )
            )
    # SOURCING RULE: a caveat may only state what the statute text we hold or a cited source says. Each one names its source.
    if topic == "property" and jurisdiction == "punjab":
        # Source: Punjab Enforcement of Women's Property Rights Act 2021, s.4(1)-(2) and s.6: orders "preferably within
        # sixty days of receipt of the complaint". (An earlier draft added "delays have been reported": unsourced, removed.)
        out.append(
            Caveat(
                en="Under section 4 of the Act the Ombudsperson should decide preferably within 60 days of receiving the complaint. This is a target, not a guarantee.",
                ur="قانون کی دفعہ 4 کے مطابق محتسب کو شکایت ملنے کے بعد ترجیحاً 60 دن کے اندر فیصلہ کرنا چاہیے۔ یہ ایک ہدف ہے، ضمانت نہیں۔",
            )
        )
    if topic == "property" and jurisdiction == "ict":
        # Source: Federal Ombudsman (FOSPAH) orders published at fospah.gov.pk record that the Islamabad High Court, in
        # Writ Petition 529/2021, declared the 2020 Act ultra vires the Constitution, that a Division Bench suspended the
        # operation of that judgment (ICA 85/2023), and that the Ombudsman has continued to apply the Act. The date of the
        # suspension and the current status of the appeal were NOT confirmed (2026-11-11), so neither is stated here.
        out.append(
            Caveat(
                en="The Islamabad High Court (writ petition 529/2021) declared this Act contrary to the Constitution. That judgment was suspended on appeal (ICA 85/2023) and the Federal Ombudsman has continued to apply the Act. Please confirm its current status.",
                ur="اسلام آباد ہائیکورٹ نے (رٹ پٹیشن 529/2021 میں) اس قانون کو آئین کے خلاف قرار دیا تھا۔ اپیل (ICA 85/2023) میں اس فیصلے پر عمل درآمد معطل ہوا اور وفاقی محتسب اس قانون کو لاگو کرتا رہا ہے۔ براہِ کرم اس کی موجودہ حیثیت کی تصدیق کر لیں۔",
            )
        )
    if topic == "property" and jurisdiction in ("sindh", "balochistan"):
        # Source: our own data. We say only what this app holds, not what exists in law.
        out.append(
            Caveat(
                en="This app does not hold a women's property rights law for this province. Contact the Ministry of Human Rights helpline 1099 or a lawyer.",
                ur="اس صوبے کے لیے خواتین کے جائیداد کے حقوق کا کوئی قانون اس ایپ میں موجود نہیں۔ وزارتِ انسانی حقوق کی ہیلپ لائن 1099 یا کسی وکیل سے رابطہ کریں۔",
            )
        )
    return out
