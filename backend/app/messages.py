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

NOT_FOUND_EN = (
    "I could not find the answer to this in the laws I have. Please contact one of the services below "
    "or speak to a lawyer."
)
NOT_FOUND_UR = (
    "مجھے اپنے پاس موجود قوانین میں اس سوال کا جواب نہیں ملا۔ براہِ کرم نیچے دی گئی سروسز سے رابطہ کریں "
    "یا کسی وکیل سے مشورہ کریں۔"
)

OUT_OF_SCOPE_EN = (
    "This question is outside what this app covers. I can explain what the law says on workplace harassment, "
    "minimum wage, women's property rights and tenancy, and where to go. I cannot calculate shares, give "
    "opinions on a case, or help with anything unlawful."
)
OUT_OF_SCOPE_UR = (
    "یہ سوال اس ایپ کے دائرے سے باہر ہے۔ میں کام کی جگہ پر ہراسانی، کم از کم اجرت، خواتین کے جائیداد کے حقوق اور "
    "کرایہ داری کے بارے میں قانون بتا سکتا ہوں اور یہ کہ کہاں رجوع کریں۔ میں حصوں کا حساب، کسی مقدمے پر رائے، "
    "یا غیر قانونی کام میں مدد نہیں دے سکتا۔"
)

PREDICTION_EN = (
    "I cannot predict whether you will win a case. I can tell you what the law says and where to file a complaint."
)
PREDICTION_UR = (
    "میں یہ نہیں بتا سکتا کہ آپ کا مقدمہ جیتا جائے گا یا نہیں۔ میں یہ بتا سکتا ہوں کہ قانون کیا کہتا ہے اور شکایت کہاں درج کرائی جائے۔"
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
    if topic == "property" and jurisdiction == "punjab":
        out.append(
            Caveat(
                en="The law aims for a decision preferably within 60 days, but delays at the Ombudsperson's office have been reported.",
                ur="قانون کا مقصد ہے کہ فیصلہ ترجیحاً 60 دن میں ہو، لیکن محتسب کے دفتر میں تاخیر کی اطلاعات ہیں۔",
            )
        )
    if topic == "property" and jurisdiction == "ict":
        out.append(
            Caveat(
                en="The Islamabad property Act was challenged in the Islamabad High Court and the ruling against it was suspended in 2023. Check its current status.",
                ur="اسلام آباد کے جائیداد کے قانون کو اسلام آباد ہائیکورٹ میں چیلنج کیا گیا تھا اور اس کے خلاف فیصلہ 2023 میں معطل ہوا۔ اس کی موجودہ حیثیت معلوم کر لیں۔",
            )
        )
    if topic == "property" and jurisdiction in ("sindh", "balochistan"):
        out.append(
            Caveat(
                en="No dedicated women's property rights law was found for this province. Contact the Ministry of Human Rights helpline 1099.",
                ur="اس صوبے کے لیے خواتین کے جائیداد کے حقوق کا الگ قانون نہیں ملا۔ وزارتِ انسانی حقوق کی ہیلپ لائن 1099 سے رابطہ کریں۔",
            )
        )
    return out
