"""Grounded Chatbot Engine querying ProjectedTrainingIntelligence, SupplyAlignmentEngine, ITI Supply, and Official Reference data.

Groq Integration:
    GroqAnswerGenerator is the ONLY component that calls the Groq API.
    It receives pre-retrieved, verified evidence from the existing data engines
    and converts it into natural-language answers.  It never queries databases,
    runs ML models, or invents data.
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Set
import pandas as pd

from engines.ml.projected_training_intelligence import (
    ProjectedTrainingIntelligence,
    DEFAULT_DATA_PATH,
    DEFAULT_MODEL_PATH,
)
from engines.ml.supply_alignment import SupplyAlignmentEngine, DEFAULT_ITI_PATH

logger = logging.getLogger("maharashtra_skill_intelligence")

# ---------------------------------------------------------------------------
# Groq system prompt — enforces grounding on backend evidence only
# ---------------------------------------------------------------------------
_GROQ_SYSTEM_PROMPT = (
    "You are the Maharashtra Skill Intelligence Assistant.\n"
    "Answer using ONLY the verified evidence supplied below.\n"
    "The backend evidence is the sole source of truth.\n\n"
    "Rules:\n"
    "- Do not invent values, sources, projections, or recommendations.\n"
    "- Clearly distinguish source facts from model-derived values.\n"
    "- If evidence is insufficient, say so honestly.\n"
    "- Use terms like 'Projected Training Demand' not 'skill shortage'.\n"
    "- Do not guess employment outcomes or placement rates.\n"
    "- Explain the evidence in clear, professional language.\n"
    "- Keep answers concise and well-structured.\n"
    "- Do not use outside knowledge to fill in missing project-specific facts.\n"
    "- Do not fabricate numbers or data sources.\n"
)


class GroqAnswerGenerator:
    """Thin wrapper around the Groq API used exclusively for natural-language generation.

    Responsibilities:
        - Convert structured backend evidence into readable answers.
        - Enforce grounding via the system prompt.

    NOT responsible for:
        - Database queries, ML inference, entity extraction, or context tracking.
    """

    def __init__(self) -> None:
        self.api_key: Optional[str] = os.environ.get("GROQ_API_KEY")
        self.model: str = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
        self._client: Any = None
        self._available: Optional[bool] = None

        if self.api_key:
            try:
                from groq import Groq  # type: ignore
                self._client = Groq(api_key=self.api_key)
                self._available = True
                logger.info("[GroqAnswerGenerator] Groq client initialised (model=%s)", self.model)
            except Exception as exc:
                logger.warning("[GroqAnswerGenerator] Could not initialise Groq client: %s", exc)
                self._available = False
        else:
            logger.warning("[GroqAnswerGenerator] GROQ_API_KEY not set — Groq generation disabled")
            self._available = False

    @property
    def is_available(self) -> bool:
        return bool(self._available and self._client)

    def generate(self, question: str, evidence_context: str) -> Optional[str]:
        """Send the user question + compact evidence context to Groq and return the answer.

        Returns ``None`` if Groq is unavailable or the request fails — the caller
        should fall back to the existing deterministic answer.
        """
        if not self.is_available:
            return None

        user_message = (
            f"User question: {question}\n\n"
            f"=== VERIFIED BACKEND EVIDENCE (source of truth) ===\n"
            f"{evidence_context}\n"
            f"=== END OF EVIDENCE ===\n\n"
            f"Answer the user's question using only the evidence above."
        )

        try:
            logger.info("[Groq] Request started — model=%s, question=%r", self.model, question[:80])
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _GROQ_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            answer = response.choices[0].message.content.strip()
            logger.info("[Groq] Response received — %d chars", len(answer))
            return answer
        except Exception as exc:
            logger.error("[Groq] API call failed: %s", exc)
            return None

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_REF_PATH = PROJECT_ROOT / "data" / "processed" / "training" / "official_trade_skills_reference.csv"


def format_readable_feature_name(raw_feature: str) -> str:
    """Format raw scikit-learn feature name into clean, human-readable text."""
    mapping = {
        "num__industry_size": "Industry size",
        "num__organization_count": "Organization count",
        "num__candidate_aspiration": "Candidate aspiration",
        "num__mssds_trained_2022_23": "Existing MSSDS training",
        "num__dsdp_training": "DSDP training",
        "num__evidence_confidence": "Evidence confidence",
        "bool__projection_available": "Projection available",
    }
    if raw_feature in mapping:
        return mapping[raw_feature]

    if raw_feature.startswith("cat__sector_"):
        sector_name = raw_feature.replace("cat__sector_", "").strip()
        return f"{sector_name} sector"

    if raw_feature.startswith("cat__district_"):
        district_name = raw_feature.replace("cat__district_", "").strip()
        return f"{district_name} district"

    clean = raw_feature.split("__")[-1].replace("_", " ").title()
    return clean


class GroundedChatbotEngine:
    """Deterministic, grounded chatbot answering district, sector, ITI trade supply, demand, and curriculum queries."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        data_path: Optional[Path] = None,
        iti_path: Optional[Path] = None,
        ref_path: Optional[Path] = None,
    ):
        self.data_path = Path(data_path) if data_path else DEFAULT_DATA_PATH
        self.iti_path = Path(iti_path) if iti_path else DEFAULT_ITI_PATH
        self.ref_path = Path(ref_path) if ref_path else DEFAULT_REF_PATH

        self.intel_engine = ProjectedTrainingIntelligence(
            model_path=model_path,
            data_path=self.data_path,
        )
        self.supply_engine = SupplyAlignmentEngine(
            model_path=model_path,
            data_path=self.data_path,
            iti_path=self.iti_path,
        )

        self._districts: List[str] = []
        self._sectors: List[str] = []
        self._trade_names: List[str] = []
        self._trade_clean_map: Dict[str, str] = {}
        self._iti_df: Optional[pd.DataFrame] = None
        self._ref_df: Optional[pd.DataFrame] = None

        self.context: Dict[str, Any] = {
            "district": None,
            "sector": None,
            "trade": None,
            "last_intent": None,
            "last_result": None,
        }

        self._load_vocabularies()
        self._groq = GroqAnswerGenerator()

    def reset_context(self) -> None:
        """Reset internal session context."""
        self.context = {
            "district": None,
            "sector": None,
            "trade": None,
            "last_intent": None,
            "last_result": None,
        }

    def _generate_grounded_answer(
        self,
        query: str,
        evidence_context: str,
        fallback_answer: str,
    ) -> str:
        """Generate a natural-language answer with Groq grounded strictly in evidence.

        If Groq is disabled, unavailable, or encounters an API error, returns fallback_answer.
        """
        if not self._groq.is_available:
            return fallback_answer

        groq_ans = self._groq.generate(query, evidence_context)
        if groq_ans and groq_ans.strip():
            return groq_ans.strip()

        return fallback_answer

    def _normalize_query(self, query: str) -> str:
        """Normalize casual spellings, punctuation, and common chat abbreviations."""
        q = query.strip()
        replacements = [
            (r"\bhlo\b", "hello"),
            (r"\bhii+\b", "hi"),
            (r"\bheyy+\b", "hey"),
            (r"\bplz\b", "please"),
            (r"\bwbu\b", "what about you"),
            (r"\bwhat's\b", "what is"),
            (r"\bwhats\b", "what is"),
            (r"\bhow's\b", "how is"),
            (r"\bhows\b", "how is"),
            (r"\bu\b", "you"),
        ]
        for pattern, repl in replacements:
            q = re.sub(pattern, repl, q, flags=re.IGNORECASE)
        return q

    def _load_vocabularies(self) -> None:
        """Load unique district, sector, and ITI trade vocabularies from real datasets."""
        if self.data_path.exists():
            df = pd.read_csv(self.data_path)
            if "district" in df.columns:
                self._districts = sorted(
                    df["district"].dropna().unique().tolist(),
                    key=len,
                    reverse=True,
                )
            if "sector" in df.columns:
                self._sectors = sorted(
                    df["sector"].dropna().unique().tolist(),
                    key=len,
                    reverse=True,
                )

        if self.iti_path.exists():
            self._iti_df = pd.read_csv(self.iti_path)
            if "trade_name" in self._iti_df.columns:
                raw_trades = self._iti_df["trade_name"].dropna().unique().tolist()
                for t in raw_trades:
                    # Strip (NSQF) or parentheses for matching
                    clean_t = re.sub(r"\s*\(.*?\)", "", str(t)).strip()
                    if clean_t:
                        self._trade_clean_map[clean_t.lower()] = t
                        self._trade_clean_map[str(t).lower()] = t

        if self.ref_path.exists():
            self._ref_df = pd.read_csv(self.ref_path)
            if "trade" in self._ref_df.columns:
                ref_trades = self._ref_df["trade"].dropna().unique().tolist()
                for t in ref_trades:
                    clean_t = re.sub(r"\s*\(.*?\)", "", str(t)).strip()
                    if clean_t:
                        self._trade_clean_map[clean_t.lower()] = t
                        self._trade_clean_map[str(t).lower()] = t

        self._trade_names = sorted(
            list(set(self._trade_clean_map.keys())),
            key=len,
            reverse=True,
        )

    def extract_entities(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract matched district, sector, and trade from query text."""
        matched_district: Optional[str] = None
        matched_sector: Optional[str] = None
        matched_trade: Optional[str] = None

        text_lower = text.lower()

        for d in self._districts:
            pattern = r"\b" + re.escape(d.lower()) + r"\b"
            if re.search(pattern, text_lower):
                matched_district = d
                break

        for s in self._sectors:
            pattern = r"\b" + re.escape(s.lower()) + r"\b"
            if re.search(pattern, text_lower):
                matched_sector = s
                break

        for t in self._trade_names:
            pattern = r"\b" + re.escape(t) + r"\b"
            if re.search(pattern, text_lower):
                matched_trade = self._trade_clean_map[t]
                break

        return matched_district, matched_sector, matched_trade

    def extract_district_and_sector(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Backward compatible helper for extract_district_and_sector."""
        d, s, _ = self.extract_entities(text)
        return d, s

    def _handle_greetings_and_conversation(self, query: str) -> Optional[Dict[str, Any]]:
        """Identify conversational inputs, greetings, capabilities, thanks, and trivia."""
        q_lower = query.lower().strip()

        # Greetings
        greetings = [
            "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
            "good night", "namaste", "hello chatbot", "hi there", "how are you"
        ]
        # Capabilities
        capabilities = [
            "who are you", "what can you do", "what can i ask you", "help",
            "what are your features", "who r u", "what r u"
        ]
        # Thanks
        thanks = ["thanks", "thank you", "thank you so much", "thx", "tq"]
        # Farewells
        farewells = ["bye", "goodbye", "see you", "exit", "quit", "cya"]

        # Trivia / Out-of-scope general knowledge checks
        if "capital of india" in q_lower:
            return {
                "query": query,
                "status": "conversation",
                "matched_district": self.context.get("district"),
                "matched_sector": self.context.get("sector"),
                "answer": "New Delhi. If you'd like, I can also help you explore Maharashtra skill-development data, projected training demand, or ITI capacity.",
                "details": None,
            }
        if "capital of maharashtra" in q_lower:
            return {
                "query": query,
                "status": "conversation",
                "matched_district": self.context.get("district"),
                "matched_sector": self.context.get("sector"),
                "answer": "Mumbai. If you'd like, I can also help you explore Maharashtra skill-development data, projected training demand, or ITI capacity.",
                "details": None,
            }

        for g in greetings:
            if q_lower == g or q_lower.startswith(g + " ") or q_lower.endswith(" " + g) or q_lower == (g + " 👋"):
                return {
                    "query": query,
                    "status": "greeting",
                    "matched_district": self.context.get("district"),
                    "matched_sector": self.context.get("sector"),
                    "answer": "Hello! 👋 I'm the Maharashtra Skill Intelligence Assistant. I can help you explore Maharashtra skill-development data, projected training demand, ITI capacity, sector rankings, trade supply, competencies, and training-alignment insights.",
                    "details": None,
                }

        for c in capabilities:
            if c in q_lower or q_lower == c:
                return {
                    "query": query,
                    "status": "conversation",
                    "matched_district": self.context.get("district"),
                    "matched_sector": self.context.get("sector"),
                    "answer": (
                        "I am the specialized Maharashtra Skill Intelligence Assistant. I can help you with:\n"
                        "• District-level projected training demand & sector rankings\n"
                        "• ITI training capacity & trade supply lookup\n"
                        "• Potential training-capacity alignment gaps\n"
                        "• Official ITI trade curriculum competencies\n"
                        "\nYou can ask me about any district (e.g. Pune, Nashik, Mumbai City), sector (e.g. Construction, Agriculture), or ITI trade (e.g. Electrician, Welder)."
                    ),
                    "details": None,
                }

        for t in thanks:
            if q_lower == t or q_lower.startswith(t + " "):
                return {
                    "query": query,
                    "status": "conversation",
                    "matched_district": self.context.get("district"),
                    "matched_sector": self.context.get("sector"),
                    "answer": "You're welcome! Let me know if you need any more details on Maharashtra skill development, ITI intake, or projected training demand.",
                    "details": None,
                }

        for f in farewells:
            if q_lower == f or q_lower.startswith(f + " "):
                return {
                    "query": query,
                    "status": "conversation",
                    "matched_district": self.context.get("district"),
                    "matched_sector": self.context.get("sector"),
                    "answer": "Goodbye! Feel free to return anytime for Maharashtra skill intelligence and training data insights.",
                    "details": None,
                }

        return None

    def _handle_followups_and_explanations(
        self, query: str, district: Optional[str], sector: Optional[str], trade: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Handle conversational follow-ups like 'why?', 'tell me more', 'and supply?', 'compare them'."""
        q_lower = query.lower().strip()

        # Explanation requests
        if q_lower in ["why", "why?", "how", "how?", "how did you get this?", "explain", "explain this", "how was this calculated?"]:
            last_res = self.context.get("last_result")
            last_district = district or self.context.get("district")
            last_sector = sector or self.context.get("sector")

            lines = [
                "Here is how this intelligence insight was calculated:",
                "1. District-sector projected training requirements are estimated by a Random Forest ML model trained on historical DSDP/MSSDS training records, candidate aspirations, industry size, and organization counts.",
                "2. Top model features overall across the trained model include: Industry size, Candidate aspiration, Organization count, Existing MSSDS training, and DSDP training.",
                "3. District ITI capacity alignment compares total ITI intake capacity against total projected training demand to identify potential alignment gaps.",
            ]
            if last_district:
                lines.append(f"Currently active context: District = {last_district}" + (f", Sector = {last_sector}" if last_sector else ""))

            return {
                "query": query,
                "status": "success",
                "matched_district": last_district,
                "matched_sector": last_sector,
                "answer": "\n".join(lines),
                "details": last_res.get("details") if last_res else None,
            }

        # Tell me more / details
        if q_lower in ["tell me more", "tell me more.", "more details", "elaborate", "details", "what about that?"]:
            last_res = self.context.get("last_result")
            if last_res and last_res.get("answer"):
                return {
                    "query": query,
                    "status": "success",
                    "matched_district": district or self.context.get("district"),
                    "matched_sector": sector or self.context.get("sector"),
                    "answer": f"Expanding on the previous result:\n{last_res['answer']}",
                    "details": last_res.get("details"),
                }
            if district and sector:
                return self.ask(f"What is the training demand for {sector} in {district}?")
            if district:
                return self._comprehensive_district_analysis(district)

        # Supply follow-ups ("and supply?", "what about supply?", "how much capacity is there?")
        if any(ph in q_lower for ph in ["and supply", "what about supply", "capacity is there", "how much capacity", "what is the capacity", "total capacity"]):
            active_dist = district or self.context.get("district")
            if active_dist:
                alignment_res = self.supply_engine.analyze_district_alignment(active_dist)
                if alignment_res["status"] == "success":
                    tot_cap = alignment_res["total_iti_capacity"]
                    tot_dem = alignment_res["predicted_total_training_demand"]
                    gap = alignment_res["alignment_gap"]
                    status_lbl = alignment_res["alignment_status"]
                    fallback_answer = (
                        f"In {active_dist}, the total ITI intake capacity is {tot_cap:.0f} seats "
                        f"against an estimated total projected training demand of ~{tot_dem:.0f} trainees "
                        f"(Potential Training-Capacity Alignment Gap: {gap:+.0f}, Status: {status_lbl})."
                    )
                    evidence_text = (
                        f"District: {active_dist}\n"
                        f"Total ITI Intake Capacity: {tot_cap:.0f} seats\n"
                        f"Estimated Total Projected Training Demand: ~{tot_dem:.0f} trainees\n"
                        f"Training-Capacity Alignment Gap: {gap:+.0f}\n"
                        f"Alignment Status: {status_lbl}"
                    )
                    answer = self._generate_grounded_answer(query, evidence_text, fallback_answer)
                    return {
                        "query": query,
                        "status": "success",
                        "matched_district": active_dist,
                        "matched_sector": sector or self.context.get("sector"),
                        "answer": answer,
                        "details": alignment_res,
                    }

        # Demand follow-ups ("and demand?", "what about demand?")
        if any(ph in q_lower for ph in ["and demand", "what about demand", "projected demand"]):
            active_dist = district or self.context.get("district")
            active_sec = sector or self.context.get("sector")
            if active_dist and active_sec:
                intel = self.intel_engine.predict_district_sector(active_dist, active_sec)
                if intel["status"] == "success" and intel.get("predicted_projected_training") is not None:
                    pred_val = intel["predicted_projected_training"]
                    band = intel["demand_band"]
                    fallback_answer = f"In {active_dist}, estimated projected training demand for {active_sec} is ~{pred_val:.0f} trainees ({band} Demand Band)."
                    evidence_text = (
                        f"District: {active_dist}\n"
                        f"Sector: {active_sec}\n"
                        f"Projected Training Demand: ~{pred_val:.0f} trainees\n"
                        f"Demand Band: {band}"
                    )
                    answer = self._generate_grounded_answer(query, evidence_text, fallback_answer)
                    return {
                        "query": query,
                        "status": "success",
                        "matched_district": active_dist,
                        "matched_sector": active_sec,
                        "answer": answer,
                        "details": intel,
                    }

        # What is currently taught / which trades / which skills
        if any(ph in q_lower for ph in ["currently taught", "currently being taught", "which trades", "what trades"]):
            active_dist = district or self.context.get("district")
            if active_dist:
                trade_res = self._handle_iti_trade_questions(f"What trades are taught in {active_dist} ITIs?", active_dist, None)
                if trade_res:
                    return trade_res

        # Compare supply and demand / compare them
        if any(ph in q_lower for ph in ["compare them", "compare supply and demand", "compare supply & demand", "is supply aligned"]):
            active_dist = district or self.context.get("district")
            if active_dist:
                return self._comprehensive_district_analysis(active_dist)

        # What should we do / recommendation / focus
        if any(ph in q_lower for ph in ["what should we do", "what should we focus on", "recommendation", "priorities"]):
            active_dist = district or self.context.get("district")
            if active_dist:
                return self._comprehensive_district_analysis(active_dist)

        return None

    def _handle_iti_trade_questions(
        self, query: str, district: Optional[str], trade: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Handle queries about ITI trades offered, intake capacity, and trade offerings in districts."""
        if self._iti_df is None or self._iti_df.empty:
            return None

        q_lower = query.lower()
        trade_keywords = [
            "trade", "trades", "iti", "itis", "taught", "offered", "offer", "offers", "offering", "intake", "capacity"
        ]

        if not trade and not any(kw in q_lower for kw in trade_keywords):
            return None

        # Case 1: District specified + Trade specified (e.g. "How much Electrician training capacity exists in Pune?")
        if district and trade:
            clean_t = re.sub(r"\s*\(.*?\)", "", trade).strip()
            match = self._iti_df[
                (self._iti_df["district"].astype(str).str.lower() == district.lower())
                & (self._iti_df["trade_name"].astype(str).str.lower().str.contains(clean_t.lower()))
            ]
            if match.empty:
                answer = f"According to actual ITI directory data, the trade '{trade}' is not currently offered in {district} ITIs."
                return {
                    "query": query,
                    "status": "success",
                    "matched_district": district,
                    "matched_sector": None,
                    "matched_trade": trade,
                    "answer": answer,
                    "details": {"intake": 0, "institutes": 0},
                }

            total_intake = int(match["intake"].sum())
            inst_count = int(match["iti_name"].nunique())
            fallback_answer = f"In {district}, the ITI trade '{trade}' has a total intake capacity of {total_intake} seats across {inst_count} ITIs."
            evidence_text = (
                f"District: {district}\n"
                f"Trade: {trade}\n"
                f"Total ITI Intake Capacity: {total_intake} seats\n"
                f"Number of Offering ITIs: {inst_count}"
            )
            answer = self._generate_grounded_answer(query, evidence_text, fallback_answer)
            return {
                "query": query,
                "status": "success",
                "matched_district": district,
                "matched_sector": None,
                "matched_trade": trade,
                "answer": answer,
                "details": {"intake": total_intake, "institutes": inst_count},
            }

        # Case 2: Trade specified across districts (e.g. "Which districts offer Welder training?")
        if trade and not district and any(kw in q_lower for kw in ["district", "districts", "where", "offer", "offers", "offering", "capacity", "intake", "iti", "available", "training"]):
            clean_t = re.sub(r"\s*\(.*?\)", "", trade).strip()
            match = self._iti_df[
                self._iti_df["trade_name"].astype(str).str.lower().str.contains(clean_t.lower())
            ]
            if match.empty:
                answer = f"According to actual ITI directory data, the trade '{trade}' was not found in the offered ITI directory."
                return {
                    "query": query,
                    "status": "success",
                    "matched_district": None,
                    "matched_sector": None,
                    "matched_trade": trade,
                    "answer": answer,
                    "details": None,
                }

            district_summary = (
                match.groupby("district")["intake"]
                .sum()
                .reset_index()
                .sort_values(by="intake", ascending=False)
            )
            top_districts = district_summary.head(5)["district"].tolist()
            dist_list_str = ", ".join(top_districts)
            total_intake = int(match["intake"].sum())

            fallback_answer = (
                f"The trade '{trade}' is offered across {district_summary['district'].nunique()} districts in Maharashtra "
                f"with a total intake capacity of {total_intake} seats. Top offering districts include: {dist_list_str}."
            )
            evidence_text = (
                f"Trade: {trade}\n"
                f"Districts Offering Trade: {district_summary['district'].nunique()}\n"
                f"Total Statewide Intake Capacity: {total_intake} seats\n"
                f"Top Offering Districts: {dist_list_str}"
            )
            answer = self._generate_grounded_answer(query, evidence_text, fallback_answer)
            return {
                "query": query,
                "status": "success",
                "matched_district": None,
                "matched_sector": None,
                "matched_trade": trade,
                "answer": answer,
                "details": {"total_districts": district_summary["district"].nunique(), "total_intake": total_intake},
            }

        # Case 3: District specified, asking for trades/what is taught (e.g. "What trades are taught in Pune ITIs?")
        case3_keywords = ["trade", "trades", "iti", "itis", "taught", "offered", "offer", "offers", "offering", "intake", "being taught", "what is taught"]
        if district and not trade and any(kw in q_lower for kw in case3_keywords):
            match = self._iti_df[
                self._iti_df["district"].astype(str).str.lower() == district.lower()
            ]
            if match.empty:
                answer = f"No ITI directory records found for district '{district}'."
                return {
                    "query": query,
                    "status": "insufficient_data",
                    "matched_district": district,
                    "matched_sector": None,
                    "answer": answer,
                    "details": None,
                }

            trade_summary = (
                match.groupby("trade_name")["intake"]
                .sum()
                .reset_index()
                .sort_values(by="intake", ascending=False)
            )
            total_trades = trade_summary["trade_name"].nunique()
            total_intake = int(match["intake"].sum())
            top_trades = trade_summary.head(5)

            lines = [f"In {district} ITIs, {total_trades} trades are currently offered with a total intake of {total_intake} seats.", "Top trades by intake capacity:"]
            for idx, r in enumerate(top_trades.iterrows(), 1):
                tname = r[1]["trade_name"]
                tcap = int(r[1]["intake"])
                lines.append(f"{idx}. {tname}: {tcap} seats")

            fallback_answer = "\n".join(lines)
            top_trades_detail = "\n".join(f"- {r['trade_name']}: {int(r['intake'])} seats" for _, r in top_trades.iterrows())
            evidence_text = (
                f"District: {district}\n"
                f"Total ITI Trades Offered: {total_trades}\n"
                f"Total Intake Capacity: {total_intake} seats\n"
                f"Top Trades by Intake Capacity:\n{top_trades_detail}"
            )
            answer = self._generate_grounded_answer(query, evidence_text, fallback_answer)
            return {
                "query": query,
                "status": "success",
                "matched_district": district,
                "matched_sector": None,
                "answer": answer,
                "details": {"total_trades": total_trades, "total_intake": total_intake},
            }

        return None

    def _handle_curriculum_and_skills_reference(
        self, query: str, trade: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Provide competency/skills reference summary if official reference dataset supports it."""
        if self._ref_df is None or self._ref_df.empty or not trade:
            return None

        q_lower = query.lower()
        curr_keywords = ["curriculum", "syllabus", "competency", "competencies", "skills taught", "what is taught in"]
        if not any(kw in q_lower for kw in curr_keywords):
            return None

        # Clean trade name match against reference CSV
        clean_t = re.sub(r"\s*\(.*?\)", "", trade).strip()
        ref_match = self._ref_df[
            self._ref_df["trade"].astype(str).str.lower().str.contains(clean_t.lower())
        ]

        if ref_match.empty:
            answer = f"The official trade reference dataset does not contain curriculum competency records for '{trade}'."
            return {
                "query": query,
                "status": "insufficient_data",
                "matched_trade": trade,
                "answer": answer,
                "details": None,
            }

        row = ref_match.iloc[0]
        comp = row["competency_summary"]
        source = row["official_source"]

        fallback_answer = f"Official curriculum competencies for {row['trade']} (Source: {source}): {comp}"
        evidence_text = (
            f"Trade: {row['trade']}\n"
            f"Official Source: {source}\n"
            f"Curriculum Competency Summary: {comp}"
        )
        answer = self._generate_grounded_answer(query, evidence_text, fallback_answer)
        return {
            "query": query,
            "status": "success",
            "matched_trade": str(row["trade"]),
            "answer": answer,
            "details": {"competency_summary": comp, "official_source": source},
        }

    def _comprehensive_district_analysis(self, district: str) -> Dict[str, Any]:
        """Perform comprehensive district analysis combining top ML-predicted sector rankings & ITI supply alignment."""
        if not self.data_path.exists():
            return {
                "query_type": "comprehensive_district_analysis",
                "matched_district": district,
                "matched_sector": None,
                "status": "insufficient_data",
                "answer": f"Data is insufficient for district '{district}'.",
                "top_sectors": [],
                "supply_alignment": None,
            }

        df = pd.read_csv(self.data_path)
        district_df = df[df["district"].astype(str).str.lower() == district.lower()].copy()

        if district_df.empty:
            return {
                "query_type": "comprehensive_district_analysis",
                "matched_district": district,
                "matched_sector": None,
                "status": "insufficient_data",
                "answer": f"Data is insufficient for district '{district}'.",
                "top_sectors": [],
                "supply_alignment": None,
            }

        available_sectors = district_df["sector"].dropna().unique().tolist()
        sector_results = []
        top_factors_aggregate: List[str] = []

        for sector in available_sectors:
            intel = self.intel_engine.predict_district_sector(district, sector)
            if intel["status"] == "success" and intel.get("predicted_projected_training") is not None:
                sector_results.append({
                    "sector": sector,
                    "predicted_projected_training": intel["predicted_projected_training"],
                    "demand_band": intel["demand_band"],
                    "evidence_confidence": intel["evidence_confidence"],
                    "details": intel,
                })
                for f in intel.get("top_feature_importances", [])[:2]:
                    fname = format_readable_feature_name(f["feature"])
                    if fname not in top_factors_aggregate:
                        top_factors_aggregate.append(fname)

        if not sector_results:
            return {
                "query_type": "comprehensive_district_analysis",
                "matched_district": district,
                "matched_sector": None,
                "status": "insufficient_data",
                "answer": f"Data is insufficient for any sector in district '{district}'.",
                "top_sectors": [],
                "supply_alignment": None,
            }

        # Rank descending by predicted_projected_training
        sector_results.sort(key=lambda x: x["predicted_projected_training"], reverse=True)
        top_5 = sector_results[:5]

        # Call SupplyAlignmentEngine for ITI capacity alignment
        alignment_res = self.supply_engine.analyze_district_alignment(district)

        top_sector_names = [s["sector"] for s in top_5[:3]]
        if len(top_sector_names) > 1:
            sec_list_str = ", ".join(top_sector_names[:-1]) + " and " + top_sector_names[-1]
        else:
            sec_list_str = top_sector_names[0]

        lines = [f"Sure! Here's a quick look at {district}'s skill and training situation. 👇", ""]
        lines.append(f"Based on available data, the strongest projected training needs in {district} are in {sec_list_str}:")
        for idx, item in enumerate(top_5, 1):
            lines.append(
                f"{idx}. {item['sector']}: Estimated requirement of ~{item['predicted_projected_training']:.0f} trainees ({item['demand_band']} Demand Band)"
            )

        lines.append("")
        if alignment_res["status"] == "success":
            pred_demand = alignment_res["predicted_total_training_demand"]
            iti_cap = alignment_res["total_iti_capacity"]
            gap = alignment_res["alignment_gap"]

            if gap < 0:
                comp_phrase = "substantially higher than"
            elif gap > 0:
                comp_phrase = "below"
            else:
                comp_phrase = "closely aligned with"

            lines.append(
                f"{district} has about {iti_cap:.0f} ITI intake seats, compared with an estimated total projected training requirement of about {pred_demand:.0f} trainees. "
                f"Based on this comparison, the available ITI capacity is {comp_phrase} the projected requirement captured by our model (Potential Training-Capacity Alignment Gap: {gap:+.0f})."
            )
        else:
            lines.append(f"Detailed ITI capacity records for {district} are limited in our current supply dataset.")

        lines.append("")
        lines.append("(Note: This is a potential training-capacity alignment signal, not an exact employment or job-shortage figure.)")

        if top_factors_aggregate:
            lines.append(f"Top model features overall: {', '.join(top_factors_aggregate[:4])}.")

        lines.append("")
        lines.append(
            f"If you'd like, I can also show you:\n"
            f"• which ITI trades are currently available in {district}, or\n"
            f"• how specific sector demand compares with training capacity."
        )

        fallback_answer = "\n".join(lines)

        # Compact structured evidence for Groq
        evidence_lines = [
            f"District: {district}",
            "Top Ranked Sectors by Projected Training Demand:",
        ]
        for idx, item in enumerate(top_5, 1):
            evidence_lines.append(
                f"  {idx}. {item['sector']}: Estimated requirement of ~{item['predicted_projected_training']:.0f} trainees ({item['demand_band']} Demand Band)"
            )
        if alignment_res["status"] == "success":
            evidence_lines.extend([
                f"District ITI Intake Capacity: {alignment_res['total_iti_capacity']:.0f} seats",
                f"Total Projected Training Demand: {alignment_res['predicted_total_training_demand']:.0f} trainees",
                f"Training-Capacity Alignment Gap: {alignment_res['alignment_gap']:+.0f} (Status: {alignment_res['alignment_status']})",
            ])
        if top_factors_aggregate:
            evidence_lines.append(f"Top Model Features: {', '.join(top_factors_aggregate[:4])}")
        evidence_lines.append("Note: Potential training-capacity alignment signal, not an exact employment or job-shortage figure.")

        evidence_text = "\n".join(evidence_lines)
        answer = self._generate_grounded_answer(
            f"Provide a skill and training intelligence overview for {district}",
            evidence_text,
            fallback_answer,
        )

        return {
            "query_type": "comprehensive_district_analysis",
            "matched_district": district,
            "matched_sector": None,
            "status": "success",
            "answer": answer,
            "top_sectors": top_5,
            "supply_alignment": alignment_res,
        }

    def ask(self, query: str) -> Dict[str, Any]:
        """Process user query and return grounded natural language answer and structured metadata."""
        q_norm = self._normalize_query(query)

        # 1. Greetings, Conversation, Out-of-Scope Trivia
        greeting_res = self._handle_greetings_and_conversation(q_norm)
        if greeting_res:
            self.context["last_result"] = greeting_res
            return greeting_res

        # 2. Entity Extraction
        raw_dist, raw_sec, raw_tr = self.extract_entities(q_norm)

        # Trade across districts check (e.g. "Which districts offer Welder training?")
        is_trade_across_districts = bool(
            raw_tr and not raw_dist and any(
                kw in q_norm.lower() for kw in ["district", "districts", "where", "offer", "offers", "offering", "available", "which"]
            )
        )

        # 3. Context Resolution & Context Safety
        if is_trade_across_districts:
            district = None
            sector = None
            trade = raw_tr
        elif raw_dist:
            if self.context["district"] and raw_dist.lower() != self.context["district"].lower() and not raw_sec:
                district = raw_dist
                sector = None
            else:
                district = raw_dist
                sector = raw_sec or self.context.get("sector")
            trade = raw_tr or self.context.get("trade")
        else:
            district = self.context.get("district")
            sector = raw_sec or self.context.get("sector")
            trade = raw_tr or self.context.get("trade")

        # 4. Follow-ups & Conversational intent resolution
        followup_res = self._handle_followups_and_explanations(q_norm, district, sector, trade)
        if followup_res:
            self._save_context(district, sector, trade, followup_res)
            return followup_res

        # 5. Curriculum / Competencies reference check
        curr_res = self._handle_curriculum_and_skills_reference(q_norm, trade)
        if curr_res:
            self._save_context(district, sector, trade, curr_res)
            return curr_res

        # 6. District-level comprehensive or ranking query intent
        q_lower = q_norm.lower()
        ranking_keywords = [
            "which sectors", "top sectors", "high demand sectors", "sectors have",
            "list sectors", "show sectors", "what sectors", "overall iti capacity",
            "capacity sufficient", "overall capacity", "training demand, and", "skill gaps",
            "important sectors", "should maharashtra focus", "where are the training needs",
            "priorities for", "compare training supply", "training supply and demand",
            "tell me about", "what's happening in", "whats happening in", "skills in",
            "focus on in", "overview for", "overview of", "district jobs", "jobs", "employment"
        ]
        is_comprehensive_or_ranking = any(kw in q_lower for kw in ranking_keywords)

        if district and not sector and is_comprehensive_or_ranking:
            comp_res = self._comprehensive_district_analysis(district)
            self._save_context(district, None, trade, comp_res)
            return comp_res

        if district and not sector and not trade and (q_lower.startswith("tell me about") or q_lower.startswith("what about") or q_lower == district.lower()):
            comp_res = self._comprehensive_district_analysis(district)
            self._save_context(district, None, trade, comp_res)
            return comp_res

        # 7. ITI Trade specific questions (what is taught / intake / offerings)
        trade_res = self._handle_iti_trade_questions(q_norm, district, trade)
        if trade_res:
            self._save_context(district if not is_trade_across_districts else None, sector, trade, trade_res)
            return trade_res

        # 8. Unsupported precise job demand queries (e.g. "How many software engineers will Pune need in 2030?")
        unsupported_keywords = ["software engineer", "2030", "data scientist", "ai engineer"]
        if any(ukw in q_lower for ukw in unsupported_keywords):
            answer = "I don't have enough data to answer that reliably. The available dataset does not provide a trade-level employment demand signal for this specific query."
            res = {
                "query": query,
                "status": "insufficient_data",
                "matched_district": district,
                "matched_sector": sector,
                "answer": answer,
                "details": None,
            }
            self.context["last_result"] = res
            return res

        # 9. Clarifications handling (Do NOT lock context if query is incomplete / needs clarification)
        if not district and not sector and not trade:
            answer = "Please specify a Maharashtra district (e.g., Pune, Mumbai City, Nashik), sector (e.g., Construction, Agriculture, BFSI), or ITI trade (e.g., Electrician, Fitter) to explore training data."
            return {
                "query": query,
                "status": "needs_clarification",
                "matched_district": None,
                "matched_sector": None,
                "answer": answer,
                "details": None,
            }

        if not district and sector:
            answer = f"I identified the sector '{sector}'. Which district would you like to analyze (e.g., Pune, Mumbai City, Nashik)?"
            return {
                "query": query,
                "status": "needs_clarification",
                "matched_district": None,
                "matched_sector": sector,
                "answer": answer,
                "details": None,
            }

        if not sector and district and not is_comprehensive_or_ranking:
            answer = f"I identified the district '{district}'. Which sector are you interested in (e.g., Construction, Agriculture, BFSI, Retail)?"
            return {
                "query": query,
                "status": "needs_clarification",
                "matched_district": district,
                "matched_sector": None,
                "answer": answer,
                "details": None,
            }

        if not district or not sector:
            answer = f"Please specify both a district and sector to view projected training demand."
            return {
                "query": query,
                "status": "needs_clarification",
                "matched_district": district,
                "matched_sector": sector,
                "answer": answer,
                "details": None,
            }

        # 10. Single District + Sector ML inference
        intel = self.intel_engine.predict_district_sector(district, sector)

        if intel["status"] == "insufficient_data" or intel["predicted_projected_training"] is None:
            answer = f"Data is insufficient for {sector} in {district}. No verified projected training requirement is available for this combination."
            res = {
                "query": query,
                "status": "insufficient_data",
                "matched_district": district,
                "matched_sector": sector,
                "answer": answer,
                "details": intel,
            }
            self._save_context(district, sector, trade, res)
            return res

        pred_val = intel["predicted_projected_training"]
        band = intel["demand_band"]
        conf = intel["evidence_confidence"]
        top_factors = intel.get("top_feature_importances", [])

        factor_str = ""
        if top_factors:
            readable_names = [format_readable_feature_name(f["feature"]) for f in top_factors[:3]]
            factor_str = f" Top model features overall include: {', '.join(readable_names)}."

        conf_str = f" (Data coverage: {conf * 100:.0f}%)" if conf is not None else ""

        fallback_answer = (
            f"In {district}, the projected training requirement for the {sector} sector is estimated at "
            f"about {pred_val:.0f} trainees ({band} Demand Band){conf_str}.{factor_str}"
        )

        top_feature_names = [format_readable_feature_name(f["feature"]) for f in top_factors[:3]] if top_factors else []
        evidence_lines = [
            f"District: {district}",
            f"Sector: {sector}",
            f"Predicted Projected Training Requirement: ~{pred_val:.0f} trainees",
            f"Demand Band: {band}",
            f"Data Evidence Confidence / Coverage: {conf * 100:.0f}%" if conf is not None else "Data Evidence Confidence: N/A",
        ]
        if top_feature_names:
            evidence_lines.append(f"Top Influencing Features: {', '.join(top_feature_names)}")
        evidence_lines.append("Note: Source facts are derived from official DSDP/MSSDS training records and candidate aspiration data.")

        evidence_text = "\n".join(evidence_lines)
        answer = self._generate_grounded_answer(query, evidence_text, fallback_answer)

        res = {
            "query": query,
            "status": "success",
            "matched_district": district,
            "matched_sector": sector,
            "answer": answer,
            "details": intel,
        }
        self._save_context(district, sector, trade, res)
        return res

    def _save_context(
        self, district: Optional[str], sector: Optional[str], trade: Optional[str], result: Dict[str, Any]
    ) -> None:
        """Helper to save successful turn context."""
        if district is not None:
            self.context["district"] = district
        if sector is not None:
            self.context["sector"] = sector
        if trade is not None:
            self.context["trade"] = trade
        self.context["last_result"] = result
