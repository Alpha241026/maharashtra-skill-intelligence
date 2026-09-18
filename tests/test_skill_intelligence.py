"""Unit tests for the Skill Intelligence component."""

import json
import tempfile
from pathlib import Path
import pytest

from engines.skill_intelligence import SkillIntelligenceEngine, CandidateMatch


@pytest.fixture
def toy_taxonomy():
    return [
        {
            "canonical_name": "Electrician",
            "category": "Electrical & Electronics",
            "description": "Installation, repair, and maintenance of electrical wiring and systems.",
            "aliases": ["Wireman", "Electrical Technician"],
        },
        {
            "canonical_name": "Welder",
            "category": "Manufacturing & Fabrication",
            "description": "Fusing metal components together using heat and arc welding equipment.",
            "aliases": ["Arc Welder", "TIG/MIG Welder"],
        },
        {
            "canonical_name": "Solar Panel Technician",
            "category": "Renewable Energy",
            "description": "Assembly, installation, and testing of solar photovoltaic systems.",
            "aliases": ["Solar PV Installer"],
        },
        {
            "canonical_name": "CNC Machine Operator",
            "category": "Manufacturing & Industrial Automation",
            "description": "Operating computer numerical control machines for metal cutting.",
            "aliases": ["CNC Operator", "Machinist"],
        },
    ]


def test_exact_and_alias_matching(toy_taxonomy):
    engine = SkillIntelligenceEngine(model_name="all-MiniLM-L6-v2")
    engine.load_taxonomy(toy_taxonomy)

    # Exact Match
    matches = engine.match_skill("Electrician")
    assert len(matches) > 0
    top_match = matches[0]
    assert isinstance(top_match, CandidateMatch)
    assert top_match.canonical_name == "Electrician"
    assert top_match.confidence == 1.0
    assert top_match.match_type == "exact"

    # Alias Exact Match
    matches_alias = engine.match_skill("Arc Welder")
    assert len(matches_alias) > 0
    top_alias = matches_alias[0]
    assert top_alias.canonical_name == "Welder"
    assert top_alias.confidence == 0.98
    assert top_alias.match_type == "alias_exact"


def test_semantic_matching(toy_taxonomy):
    engine = SkillIntelligenceEngine(model_name="all-MiniLM-L6-v2")
    engine.load_taxonomy(toy_taxonomy)

    # Semantic Match for solar photovoltaic installation
    matches = engine.match_skill("solar photovoltaic system repair", top_k=2)
    assert len(matches) > 0
    top_match = matches[0]
    assert top_match.canonical_name == "Solar Panel Technician"
    assert top_match.confidence > 0.5
    assert top_match.match_type in ["semantic", "semantic_description", "semantic_alias"]


def test_load_from_json_and_csv(toy_taxonomy):
    engine = SkillIntelligenceEngine(model_name="all-MiniLM-L6-v2")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # JSON loading
        json_file = tmp_path / "toy_taxonomy.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(toy_taxonomy, f)

        engine.load_taxonomy(json_file)
        matches_json = engine.match_skill("Wireman")
        assert matches_json[0].canonical_name == "Electrician"

        # CSV loading
        csv_file = tmp_path / "toy_taxonomy.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("canonical_name,category,description,aliases\n")
            f.write('Plumber,Construction,"Piping and water system maintenance","Pipefitter;Drainage Expert"\n')

        engine.load_taxonomy(csv_file)
        matches_csv = engine.match_skill("Pipefitter")
        assert matches_csv[0].canonical_name == "Plumber"
