# Huqooq: hackathon submission

Build with Google, GDGoC CUI, CUI Tech Fest FA'26. Domain: Women's Empowerment.

## Project title
Huqooq (حقوق): a voice-first Urdu assistant that explains your legal rights and where to go next.

## Problem statement
Most women in Pakistan who face workplace harassment, withheld inheritance or unpaid wages do not know which law protects them, which forum to approach, or how to write a complaint. Legal text is in English, helplines are scattered, and lawyers cost money. Punjab alone reported thousands of pending women's inheritance complaints, and labour inspectors are too few to police minimum wage. People get wrong advice from relatives or give up.

Huqooq answers in Urdu, by voice or text, cites the exact law and section, points to the right helpline or forum, and drafts a complaint letter. If it cannot find an answer in the laws it holds, it says so instead of guessing.

## Who is affected
Working women, women denied inheritance, and low-wage workers, mainly in Punjab, who cannot easily read English legal texts or afford advice.

## SDG alignment
- SDG 5, Gender Equality: harassment protection and women's property rights.
- SDG 8, Decent Work: minimum wage and unpaid wages.
- SDG 16, Peace, Justice and Strong Institutions: access to legal information and complaint forums.

## What we built
1. Ask by voice (Chrome speech recognition, Urdu) or text, in Urdu, Roman Urdu or English.
2. A safety check runs first: messages about violence or self-harm show an emergency banner (call 15) before anything else, with no model call.
3. A small model turns the question into English search terms. Retrieval (BM25) finds the matching sections in the statutes we hold.
4. A stronger model writes the answer in Urdu and English using only those sections. Every claim must cite a retrieved section; an answer with no valid citation is replaced by "not found".
5. Referral numbers, minimum-wage figures, caveats and disclaimers come from reviewed data files, never from the model.
6. A Word (.docx) draft complaint letter can be downloaded.

## Technology stack
- Models: Google Gemini (Flash-Lite for query analysis, Flash for the answer) through the Gemini API; Groq (Llama) as an automatic fallback.
- Backend: Python, FastAPI, rank-bm25, python-docx.
- Frontend: React, TypeScript, Vite; Chrome Web Speech API for Urdu voice input.
- Data: public statutes (FOSPAH, Punjab Laws, Pakistan Code), a CC BY 4.0 dataset (Pakistani Law Dataset, Umair Ahmed, Zenodo), listed in `data/sources.yaml`.
- Tests: 42 offline tests, a 15-question acceptance set, and an evaluation script.

## Responsible AI
- **Disclosure:** the app's answers come from Google Gemini (Groq Llama if Gemini is unavailable). The code was written with the help of Claude (Anthropic), including this scaffold, tests and documents. Urdu text in fixed messages is reviewed by a native speaker.
- **No unvalidated facts:** answers cite statute sections or are refused. Wage figures and phone numbers carry an as-of date and a verified flag; unverified items are labelled.
- **Limitations:** covers only workplace harassment, women's property and Punjab minimum wage, and only the statutes in `data/sources.yaml`. It is legal information, not legal advice, and laws change. It does not predict case outcomes. The Islamabad property Act has been challenged in court. Urdu quality is still being reviewed.
- **Privacy:** questions are not stored by our app. Free model tiers may use prompts to improve the provider's products, so the demo uses synthetic questions only.
- **Data:** only public legal texts and one openly licensed dataset; no confidential or personal datasets.

## Honesty note on timing
The first repository commit (the scaffold) is timestamped 10:23 AM, seven minutes before the stated 10:30 AM start. The topic was chosen before kick-off; the provider layer, data ingestion, frontend, evaluation, Urdu review and the submission were all built during the event.

## Repository
https://github.com/AreejJawadKhan/huqooq
