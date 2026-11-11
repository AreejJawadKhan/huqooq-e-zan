from backend.app.retrieval import Chunk, Retriever


def chunk(i, topic, jur, text, heading=""):
    return Chunk(i, "s", "Act", jur, topic, i, heading, text)


CORPUS = [
    chunk("1", "harassment", "pakistan", "complaint to the inquiry committee about harassment", "Complaint"),
    chunk("2", "property", "punjab", "woman deprived of property may complain to the ombudsperson", "Complaint"),
    chunk("3", "property", "ict", "woman deprived of property may complain to the ombudsperson islamabad", "Complaint"),
    chunk("4", "tenancy", "sindh", "landlord may seek eviction of tenant for non payment of rent", "Eviction"),
]


def test_topic_filter():
    hits = Retriever(CORPUS).search("complaint ombudsperson", topic="property")
    assert {c.id for c, _ in hits} <= {"2", "3"}


def test_jurisdiction_filter_keeps_nationwide_laws():
    r = Retriever(CORPUS)
    punjab = {c.id for c, _ in r.search("complaint property harassment", jurisdiction="punjab")}
    assert "1" in punjab and "2" in punjab and "3" not in punjab


def test_min_score_and_empty_query():
    r = Retriever(CORPUS)
    assert r.search("the of and") == []
    assert r.search("xyzzy", min_score=0.5) == []


def test_empty_index_is_safe():
    assert Retriever([]).search("anything") == []
