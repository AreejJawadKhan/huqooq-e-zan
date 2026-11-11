from scripts.ingest import build_chunks, clean_text, pack, split_sections

# A toy "Act" laid out like a gazette extraction: contents first, then body, then a schedule.
FIXTURE = """
THE GAZETTE OF PAKISTAN, EXTRA, MARCH 11, 2010 [PART I]
CONTENTS
1. Short title and commencement.
2. Definitions.
3. Complaint.
4. Penalty.
THE TOY WORKPLACE ACT, 2010
1. Short title, extent and commencement.- (1) This Act may be called the Toy Workplace Act, 2010. (2) It extends to the whole of Pakistan. (3) It shall come into force at once.
2. Definitions.- In this Act, unless there is anything repugnant in the subject or context, (a) "employee" means any person employed by an employer whether full time or part time, and (b) "workplace" means any place where work is done.
3
3. Complaint.- (1) Any employee may make a written complaint to the Inquiry Committee about harassment at the workplace.
(2) The Inquiry Committee shall hold an inquiry and report within thirty days of the complaint being received by it.
4. Penalty.- Whoever is found guilty of harassment shall be liable to a penalty as the Competent Authority may decide according to the rules made under this Act.
SCHEDULE
CODE OF CONDUCT
(i) Every employer shall display this code of conduct at a conspicuous place in the workplace.
"""

SRC = {"id": "toy", "act": "Toy Workplace Act, 2010", "jurisdiction": "pakistan", "topic": "harassment", "url": "http://x"}


def test_clean_removes_gazette_noise():
    out = clean_text(FIXTURE)
    assert "GAZETTE" not in out
    assert "\n3\n" not in out  # lone page number removed


def test_sections_use_body_not_contents():
    secs = split_sections(clean_text(FIXTURE))
    nums = [s.num for s in secs]
    assert nums == ["1", "2", "3", "4", "Schedule"]
    s3 = next(s for s in secs if s.num == "3")
    assert "Inquiry Committee" in s3.body  # real body, not the contents line
    assert s3.heading == "Complaint"


def test_build_chunks_metadata():
    chunks, warnings = build_chunks(SRC, clean_text(FIXTURE), "2026-11-11")
    ids = [c.id for c in chunks]
    assert ids[0] == "toy:s1" and "toy:sSchedule" in ids
    assert all(c.act == SRC["act"] and c.topic == "harassment" and c.as_of == "2026-11-11" for c in chunks)
    assert not any("contiguous" in w for w in warnings)


def test_falls_back_to_windows_when_no_sections():
    chunks, warnings = build_chunks(SRC, "just some prose without numbered sections " * 50, "2026-11-11")
    assert chunks and chunks[0].section.startswith("window-")
    assert any("fell back" in w for w in warnings)


def test_pack_splits_long_sections_on_subsections():
    # real statute sub-sections end with a full stop before the next "(n)" marker
    body = " ".join(f"({i}) " + "word " * 79 + "word." for i in range(1, 8))
    parts = pack(body, max_words=200)
    assert len(parts) > 1
    assert all(len(p.split()) <= 300 for p in parts)


def test_bracketed_amendment_headings_are_sections():
    text = "\n".join(
        [
            "1. Short title. – This Act.",
            "2. Definitions. – In this Act.",
            "3[7. Ombudsperson.– The Government shall appoint.",
            "(2) A person shall be qualified.]",
            "8. 5[Ombudsperson] to enquire into complaint. – (1) Any employee.",
            "9. Representation. – x",
        ]
    ).replace("1. Short", "1. Short").replace("2. Definitions", "2. Definitions")
    # sequence must be contiguous, so add 3..6 placeholders
    extra = "\n".join(f"{n}. Heading {n}. – body text {n}." for n in (3, 4, 5, 6))
    text = text.replace("3[7.", extra + "\n3[7.")
    nums = [s.num for s in split_sections(text)]
    assert nums == ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    assert [s.heading for s in split_sections(text) if s.num == "8"] == ["Ombudsperson to enquire into complaint"]
