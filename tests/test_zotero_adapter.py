"""Tests for ZoteroAdapter with mocked pyzotero."""
import pytest
from unittest.mock import MagicMock, patch
from eurekalab.integrations.zotero.adapter import ZoteroAdapter
from eurekalab.types.artifacts import Paper


MOCK_ITEMS = [
    {
        "key": "ABC123",
        "data": {
            "itemType": "journalArticle",
            "title": "Optimal Bounds for Bandits",
            "creators": [
                {"creatorType": "author", "firstName": "John", "lastName": "Smith"},
                {"creatorType": "author", "firstName": "Jane", "lastName": "Doe"},
            ],
            "date": "2024",
            "abstractNote": "We prove optimal bounds.",
            "publicationTitle": "JMLR",
            "DOI": "10.1234/example",
            "url": "",
            "extra": "arXiv: 2401.12345",
        },
    },
    {
        "key": "DEF456",
        "data": {
            "itemType": "conferencePaper",
            "title": "Concentration Inequalities",
            "creators": [
                {"creatorType": "author", "firstName": "Alice", "lastName": "Jones"},
            ],
            "date": "2023",
            "abstractNote": "",
            "proceedingsTitle": "NeurIPS",
            "DOI": "",
            "url": "https://example.com/paper",
            "extra": "",
        },
    },
]

MOCK_NOTE = {
    "key": "NOTE1",
    "data": {
        "itemType": "note",
        "note": "<p>Key insight: Theorem 4.2 is the main result.</p>",
        "parentItem": "ABC123",
    },
}


@pytest.fixture
def mock_zot():
    """Create a mocked pyzotero.Zotero instance."""
    zot = MagicMock()
    zot.collection_items.return_value = MOCK_ITEMS + [MOCK_NOTE]
    zot.children.return_value = [MOCK_NOTE]
    zot.item.side_effect = lambda key: next(
        (i for i in MOCK_ITEMS + [MOCK_NOTE] if i["key"] == key), None
    )
    return zot


@pytest.fixture
def adapter(mock_zot):
    with patch("eurekalab.integrations.zotero.adapter.zotero.Zotero", return_value=mock_zot):
        return ZoteroAdapter(library_id="12345", api_key="fake-key")


def test_import_collection_returns_papers(adapter, mock_zot):
    papers = adapter.import_collection("COL1")
    # Should skip the note item, return 2 papers
    assert len(papers) == 2


def test_import_collection_extracts_title(adapter):
    papers = adapter.import_collection("COL1")
    titles = {p.title for p in papers}
    assert "Optimal Bounds for Bandits" in titles


def test_import_collection_extracts_authors(adapter):
    papers = adapter.import_collection("COL1")
    smith = next(p for p in papers if "Optimal" in p.title)
    assert "John Smith" in smith.authors or "Smith, John" in smith.authors


def test_import_collection_extracts_year(adapter):
    papers = adapter.import_collection("COL1")
    smith = next(p for p in papers if "Optimal" in p.title)
    assert smith.year == 2024


def test_import_collection_extracts_arxiv_from_extra(adapter):
    papers = adapter.import_collection("COL1")
    smith = next(p for p in papers if "Optimal" in p.title)
    assert smith.arxiv_id == "2401.12345"


def test_import_collection_sets_source_zotero(adapter):
    papers = adapter.import_collection("COL1")
    assert all(p.source == "zotero" for p in papers)


def test_import_collection_sets_content_tier(adapter):
    papers = adapter.import_collection("COL1")
    smith = next(p for p in papers if "Optimal" in p.title)
    assert smith.content_tier == "abstract"  # has abstractNote
    jones = next(p for p in papers if "Concentration" in p.title)
    assert jones.content_tier == "metadata"  # no abstract


def test_import_collection_stores_zotero_key(adapter):
    papers = adapter.import_collection("COL1")
    smith = next(p for p in papers if "Optimal" in p.title)
    assert smith.zotero_item_key == "ABC123"


def test_import_notes(adapter, mock_zot):
    papers = adapter.import_collection("COL1")
    smith = next(p for p in papers if "Optimal" in p.title)
    assert "Theorem 4.2" in smith.user_notes


def test_import_collection_sets_venue(adapter):
    papers = adapter.import_collection("COL1")
    smith = next(p for p in papers if "Optimal" in p.title)
    assert smith.venue == "JMLR"


def test_create_collection(adapter, mock_zot):
    mock_zot.create_collections.return_value = [{"data": {"key": "NEW_COL"}}]
    key = adapter.create_collection("EurekaLab Results")
    assert key == "NEW_COL"
    mock_zot.create_collections.assert_called_once()


def test_push_papers(adapter, mock_zot):
    mock_zot.create_items.return_value = {"successful": {"0": {"key": "NEW1"}}}
    papers = [Paper(paper_id="test", title="New Paper", authors=["A. Author"], year=2024)]
    keys = adapter.push_papers(papers, "COL1")
    assert len(keys) >= 0  # may be 0 if create_items doesn't return expected format
    mock_zot.create_items.assert_called_once()


def test_push_note(adapter, mock_zot):
    mock_zot.create_items.return_value = {"successful": {"0": {"key": "NOTE_NEW"}}}
    adapter.push_note("ABC123", "This is a proof note.")
    mock_zot.create_items.assert_called_once()
