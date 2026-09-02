from types import SimpleNamespace

import pytest

from helvetic_lens.diffing import DIFF_SCHEMA_VERSION, compare_passages
from helvetic_lens.identity import assess_comparison_identity


def passage(identifier: str, text: str, page: int = 1, **metadata):
    return {"id": identifier, "text": text, "page": page, **metadata}


def test_flattened_hyphen_space_is_not_guessed_to_be_a_pdf_line_wrap():
    diff = compare_passages(
        [passage("old", "Die Personengesell- schaft reicht den Bericht ein.")],
        [passage("new", "Die Personengesellschaft reicht den Bericht ein.")],
    )

    assert diff["schema_version"] == DIFF_SCHEMA_VERSION
    assert diff["counts"]["modified"] == 1
    assert diff["classification_counts"]["substantive"] == 1
    assert diff["material_count"] == 1
    assert diff["items"][0]["change_type"] == "modified"


def test_inserted_article_does_not_turn_following_renumbering_into_modified_text():
    old = [
        passage("o1", "Art. 1 Purpose"),
        passage("o2", "Art. 2 Scope"),
        passage("o3", "Art. 3 Procedure"),
    ]
    new = [
        passage("n1", "Art. 1 Purpose"),
        passage("n2", "Art. 2 New reporting duty"),
        passage("n3", "Art. 3 Scope"),
        passage("n4", "Art. 4 Procedure"),
    ]

    diff = compare_passages(old, new)

    assert diff["counts"] == {"added": 1, "removed": 0, "modified": 2, "unchanged": 1}
    assert diff["classification_counts"]["substantive"] == 1
    assert diff["classification_counts"]["structural"] == 2
    assert [item["change_type"] for item in diff["items"] if item["kind"] == "modified"] == [
        "renumbered",
        "renumbered",
    ]


def test_numeric_page_shape_without_metadata_remains_substantive():
    diff = compare_passages(
        [passage("old", "3 / 102")],
        [passage("new", "3 / 104")],
    )
    assert diff["material_count"] == 1
    assert diff["classification_counts"]["substantive"] == 1


def test_explicit_layout_metadata_cannot_hide_a_numeric_change():
    diff = compare_passages(
        [passage("old", "3 / 102", layout_role="page_counter")],
        [passage("new", "3 / 104", layout_role="page_counter")],
    )
    assert diff["material_count"] == 1
    assert diff["classification_counts"]["substantive"] == 1


def test_real_number_change_remains_substantive():
    diff = compare_passages(
        [passage("old", "Records must be retained for 30 days.")],
        [passage("new", "Records must be retained for 60 days.")],
    )
    assert diff["material_count"] == 1
    assert diff["items"][0]["change_type"] == "modified"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("100", "200"),
        ("Betrag: 2.5 Millionen", "Betrag: 25 Millionen"),
        ("Spalte A | 3.50 | CHF", "Spalte A | 3,50 | CHF"),
        ("The duty applies; unless exempt.", "The duty applies, unless exempt."),
    ],
)
def test_numeric_decimal_table_and_punctuation_changes_are_never_hidden(old, new):
    diff = compare_passages([passage("old", old)], [passage("new", new)])
    assert diff["material_count"] >= 1
    assert all(item["significance"] == "substantive" for item in diff["items"])


@pytest.mark.parametrize("size", [200, 201])
def test_large_similar_replacement_has_no_size_dependent_alignment_cliff(size):
    old = [passage(f"o{i}", f"Clause {i}: records must be retained for 30 days.") for i in range(size)]
    new = [passage(f"n{i}", f"Clause {i}: records must be retained for 60 days.") for i in range(size)]
    diff = compare_passages(old, new)
    assert diff["counts"] == {"added": 0, "removed": 0, "modified": size, "unchanged": 0}


def test_unique_exact_passage_reorder_is_reported_as_a_move():
    old = [
        passage("o1", "Article Alpha establishes the purpose."),
        passage("o2", "Article Beta establishes the scope."),
        passage("o3", "Article Gamma establishes the procedure."),
    ]
    new = [old[2] | {"id": "n1"}, old[0] | {"id": "n2"}, old[1] | {"id": "n3"}]
    diff = compare_passages(old, new)
    moved = [item for item in diff["items"] if item["change_type"] == "moved"]
    assert len(moved) == 1
    assert moved[0]["old_position"] == 3 and moved[0]["new_position"] == 1
    assert diff["classification_counts"]["structural"] == 1


def test_large_unrelated_replacement_is_not_paired_by_position():
    old = [passage(f"o{i}", f"Legacy alpha clause {i}.") for i in range(205)]
    new = [passage(f"n{i}", f"Unrelated zeta schedule {i}.") for i in range(205)]
    diff = compare_passages(old, new)
    assert diff["counts"]["modified"] == 0
    assert diff["counts"]["removed"] == diff["counts"]["added"] == 205


def test_comparison_identity_detects_documents_attached_to_the_wrong_law():
    law = SimpleNamespace(
        name="Bundesbeschluss über die erleichterte Einbürgerung von Personen der dritten Ausländergeneration",
        url="https://fedlex.data.admin.ch/eli/oc/2017/259",
    )
    versions = [
        SimpleNamespace(
            title="910.13",
            source_url=None,
            passages=[
                passage("p1", "910.13"),
                passage(
                    "p2",
                    "Verordnung über die Direktzahlungen an die Landwirtschaft (Direktzahlungsverordnung, DZV)",
                ),
            ],
        ),
        SimpleNamespace(
            title="Verordnung über die Direktzahlungen an die Landwirtschaft",
            source_url=None,
            passages=[],
        ),
    ]
    assert assess_comparison_identity(law, *versions)["status"] == "mismatch"


def test_matching_eli_identifier_wins_over_multilingual_title_difference():
    law = SimpleNamespace(
        name="Bundesgesetz über den Datenschutz",
        url="https://fedlex.data.admin.ch/eli/cc/2022/491/de",
    )
    old = SimpleNamespace(
        title="Bundesgesetz über den Datenschutz",
        source_url="https://fedlex.data.admin.ch/eli/cc/2022/491/20230901/de/html",
        passages=[],
    )
    new = SimpleNamespace(
        title="Loi fédérale sur la protection des données",
        source_url="https://fedlex.data.admin.ch/eli/cc/2022/491/20250101/fr/html",
        passages=[],
    )

    assert assess_comparison_identity(law, old, new)["status"] == "match"


def test_one_conflicting_eli_identifier_blocks_the_comparison():
    law = SimpleNamespace(
        name="Bundesgesetz über den Datenschutz",
        url="https://fedlex.data.admin.ch/eli/cc/2022/491/de",
    )
    correct = SimpleNamespace(
        title=law.name,
        source_url="https://fedlex.data.admin.ch/eli/cc/2022/491/20230901/de/html",
        passages=[],
    )
    wrong = SimpleNamespace(
        title=law.name,
        source_url="https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de/html",
        passages=[],
    )

    assert assess_comparison_identity(law, correct, wrong)["status"] == "mismatch"
