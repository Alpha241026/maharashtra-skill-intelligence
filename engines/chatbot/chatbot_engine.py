"""Grounded Chatbot Engine querying ProjectedTrainingIntelligence, SupplyAlignmentEngine, ITI Supply, and Official Reference data."""

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
from engines.labour_market.job_market_intelligence import JobMarketIntelligence
from engines.labour_market.skill_gap_engine import SkillGapEngine

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

        self.job_data_path = PROJECT_ROOT / "data" / "processed" / "jobs" / "cleaned_job_data.csv"
        self.skill_demand_path = PROJECT_ROOT / "data" / "processed" / "jobs" / "skill_demand.csv"
        self.job_skills_path = PROJECT_ROOT / "data" / "processed" / "jobs" / "job_skills.csv"
        
        self._job_df = None
        self._skill_demand_df = None
        self._job_skills_df = None

        self.intel_engine = ProjectedTrainingIntelligence(
            model_path=model_path,
            data_path=self.data_path,
        )
        self.supply_engine = SupplyAlignmentEngine(
            model_path=model_path,
            data_path=self.data_path,
            iti_path=self.iti_path,
        )
        self.jmi = JobMarketIntelligence()
        self.sge = SkillGapEngine()
        self.curriculum_path = PROJECT_ROOT / "data" / "processed" / "curriculum" / "cse_it_curriculum.csv"


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

    def reset_context(self) -> None:
        """Reset internal session context."""
        self.context = {
            "district": None,
            "sector": None,
            "trade": None,
            "last_intent": None,
            "last_result": None,
        }

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
                    answer = (
                        f"In {active_dist}, the total ITI intake capacity is {tot_cap:.0f} seats "
                        f"against an estimated total projected training demand of ~{tot_dem:.0f} trainees "
                        f"(Potential Training-Capacity Alignment Gap: {gap:+.0f}, Status: {status_lbl})."
                    )
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
                    answer = f"In {active_dist}, estimated projected training demand for {active_sec} is ~{pred_val:.0f} trainees ({band} Demand Band)."
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
            answer = f"In {district}, the ITI trade '{trade}' has a total intake capacity of {total_intake} seats across {inst_count} ITIs."
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

            answer = (
                f"The trade '{trade}' is offered across {district_summary['district'].nunique()} districts in Maharashtra "
                f"with a total intake capacity of {total_intake} seats. Top offering districts include: {dist_list_str}."
            )
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

            answer = "\n".join(lines)
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

        answer = f"Official curriculum competencies for {row['trade']} (Source: {source}): {comp}"
        return {
            "query": query,
            "status": "success",
            "matched_trade": str(row["trade"]),
            "answer": answer,
            "details": {"competency_summary": comp, "official_source": source},
        }

    def _handle_job_demand(self, query: str, district: Optional[str]) -> Optional[Dict[str, Any]]:
        q_lower = query.lower()
        domain = "IT"
        self.context["last_intent"] = "job_demand"
        loc_str = district or 'Maharashtra'
        
        wants_roles = "job" in q_lower or "role" in q_lower
        wants_skills = "skill" in q_lower or "technolog" in q_lower
        
        if wants_roles and not wants_skills:
            roles = self.jmi.get_top_roles(location=district, domain=domain, top_n=5)
            if not roles:
                return {
                    "query": query, "status": "success", "matched_district": district, "matched_sector": None,
                    "answer": f"The available dataset does not contain sufficient evidence to report major IT roles for {loc_str}.", "details": None
                }
            
            top_roles_list = [r['role'] for r in roles[:3]]
            ans = [f"**Direct Answer**\n{top_roles_list[0]} is the most frequently observed IT role in the {loc_str} listings analyzed, followed by {top_roles_list[1]} and {top_roles_list[2]}.", ""]
            
            ans.append("**Evidence**")
            for r in roles[:5]:
                ans.append(f"- {r['role']} ({r['demand_percentage']:.1f}%)")
            ans.append("")
            
            ans.append("**What the data indicates**")
            if "Developer" in top_roles_list[0] or "Engineer" in top_roles_list[0]:
                ans.append(f"The role distribution shows that software engineering and development positions make up a particularly visible part of the available {loc_str} listings. The presence of {top_roles_list[0]} at {roles[0]['demand_percentage']:.1f}% indicates concentrated demand for core development tasks, while the remaining roles show demand across multiple technical specializations.")
            else:
                ans.append(f"The high concentration of {top_roles_list[0]} listings reflects its frequent appearance in the available data for {loc_str}. This pattern suggests a strong regional focus on the specific responsibilities associated with this role.")
            ans.append("")
            
            ans.append("**Practical implication**")
            ans.append("For skill-development planning, these role patterns provide a basis for examining whether training pathways provide the technical skills and practical experience associated with the most frequently observed roles.")
            ans.append("")
            
            ans.append("**Continue the conversation:**")
            ans.append(f"• Which specific technical skills are required for {top_roles_list[0]}?")
            ans.append("• Are there observable curriculum gaps for these roles?")
            if loc_str == 'Maharashtra':
                ans.append("• How does the role distribution differ in Pune vs Mumbai?")
            else:
                ans.append(f"• How does {loc_str} compare with Mumbai?")
            
            return {
                "query": query, "status": "success", "matched_district": district, "matched_sector": None,
                "answer": "\n".join(ans), "details": roles
            }
        
        # Default to skills
        skills = self.jmi.get_top_skills(location=district, domain=domain, top_n=5)
        if not skills:
            return {
                "query": query, "status": "success", "matched_district": district, "matched_sector": None,
                "answer": f"The available dataset does not contain sufficient evidence to report major IT skills for {loc_str}.", "details": None
            }
            
        top_skills_list = [s['skill'] for s in skills[:3]]
        ans = [f"**Direct Answer**\n{top_skills_list[0]} is the most frequently observed IT skill in the {loc_str} dataset, appearing in {skills[0]['demand_percentage']:.1f}% of analyzed listings, followed closely by {top_skills_list[1]} and {top_skills_list[2]}.", ""]
        
        ans.append("**Evidence**")
        for s in skills[:5]:
            ans.append(f"- {s['skill']} ({s['demand_percentage']:.1f}%)")
        ans.append("")
        
        ans.append("**What the data indicates**")
        diff = skills[0]['demand_percentage'] - skills[1]['demand_percentage']
        if "SQL" in top_skills_list and ("Python" in top_skills_list or "Java" in top_skills_list):
            ans.append(f"The concentration of these skills is notable: all are represented across a substantial share of the available listings, indicating that database knowledge and core programming skills form an important foundational part of the observed {loc_str} IT job market. The difference between the leading skills is relatively small ({diff:.1f}%), suggesting they are often co-requested.")
        else:
            ans.append(f"The concentration of {top_skills_list[0]} and {top_skills_list[1]} indicates a strong structural requirement for these technologies in the {loc_str} market. The observed data highlights a clear technical foundation.")
        ans.append("")
            
        ans.append("**Practical implication**")
        ans.append(f"Training providers could consider maintaining strong foundations in {top_skills_list[0]} and {top_skills_list[1]} while using role-specific projects to connect these skills with actual job requirements.")
        ans.append("")
        
        ans.append("**Continue the conversation:**")
        ans.append(f"• Which IT roles use {top_skills_list[0]} most frequently?")
        ans.append("• Which of these skills are currently missing from the state curriculum?")
        if loc_str == 'Maharashtra':
            ans.append("• How does the skill demand differ between Pune and Mumbai?")
        else:
            ans.append("• What are the most frequently observed IT roles in this region?")
        
        return {
            "query": query, "status": "success", "matched_district": district, "matched_sector": None,
            "answer": "\n".join(ans), "details": skills
        }

    def _handle_skill_gap(self, query: str, district: Optional[str]) -> Optional[Dict[str, Any]]:
        self.context["last_intent"] = "skill_gap"
            
        gaps = self.sge.analyze(self.curriculum_path, location=district, domain="IT")
        loc_str = district or 'Maharashtra'
        
        if gaps.empty or (len(gaps) > 0 and gaps.iloc[0].get('gap_status') == 'INSUFFICIENT_DATA'):
            return {
                "query": query, "status": "success", "matched_district": district, "matched_sector": None,
                "answer": f"The available industry data is currently insufficient to perform a reliable curriculum gap analysis for {loc_str}.", "details": None
            }
            
        covered = gaps[gaps['gap_status'] == 'COVERED']
        real_gaps = gaps[gaps['gap_status'] == 'GAP']
        
        ans = [f"**Direct Answer**\nThe curriculum analysis identifies several alignment areas as well as observable gaps when compared with {loc_str} job market data.\n"]
        
        ans.append("**Current alignment**")
        if not covered.empty:
            top_covered = covered.head(3)['industry_skill'].tolist()
            cov_str = top_covered[0] if len(top_covered) == 1 else f"{', '.join(top_covered[:-1])} and {top_covered[-1]}"
            ans.append(f"The analyzed curriculum already covers {cov_str}, which maps directly to observed industry demand in {loc_str}.")
        else:
            ans.append(f"No direct alignment with the top industry skills was observed in the current curriculum.")
        ans.append("")
        
        if real_gaps.empty:
            ans.append(f"The curriculum looks well aligned with the top skills in {loc_str}. No major gaps detected based on current data.")
            return {
                "query": query, "status": "success", "matched_district": district, "matched_sector": None,
                "answer": "\n".join(ans), "details": None
            }
            
        top_gaps = real_gaps.head(3)
        gap_list = [r['industry_skill'] for _, r in top_gaps.iterrows()]
        
        ans.append("**Observed gaps**")
        for _, r in top_gaps.iterrows():
            ans.append(f"- {r['industry_skill']} (demanded by {r['demand_percentage']:.1f}%)")
        ans.append("")
            
        ans.append("**Interpretation**")
        ans.append(f"In this analysis, {gap_list[0]} is flagged because it appears in {top_gaps.iloc[0]['demand_percentage']:.1f}% of the available job dataset while no sufficiently similar curriculum topic was found. This does not automatically prove it must be added, but indicates the skill deserves formal review due to its high observed frequency.")
        ans.append("")
        
        ans.append("**Practical consideration**")
        if "Project Management" in gap_list or "Communication" in gap_list:
            ans.append(f"Since {gap_list[0]} represents a broad or non-technical competency, curriculum planners could review whether it can be integrated into existing practical labs or mapped to soft-skills training rather than requiring a dedicated technical module.")
        else:
            ans.append(f"Curriculum planners may want to review whether a dedicated module on {gap_list[0]} should be introduced or if practical lab coverage could be strengthened to align training with this observed demand.")
        ans.append("")
        
        ans.append("**Continue the conversation:**")
        ans.append(f"• Which job roles are associated with the {gap_list[0]} gap?")
        ans.append(f"• How does Pune's demand compare with the current curriculum?")
        ans.append("• Which gaps are strongest in the available data?")
        
        return {
            "query": query, "status": "success", "matched_district": district, "matched_sector": None,
            "answer": "\n".join(ans), "details": top_gaps.to_dict(orient="records")
        }

    def _handle_comparison(self, query: str) -> Optional[Dict[str, Any]]:
        import re
        q_lower = query.lower()
        
        districts = []
        for d in ["Pune", "Mumbai", "Nashik", "Nagpur", "Thane", "Aurangabad", "Chhatrapati Sambhajinagar"]:
            if d.lower() in q_lower:
                if d not in districts:
                    districts.append(d)
        
        if len(districts) < 2:
            return None
            
        d1 = districts[0]
        d2 = districts[1]
        
        d1_roles = self.jmi.get_top_roles(location=d1, domain="IT", top_n=3)
        d2_roles = self.jmi.get_top_roles(location=d2, domain="IT", top_n=3)
        
        d1_skills = self.jmi.get_top_skills(location=d1, domain="IT", top_n=3)
        d2_skills = self.jmi.get_top_skills(location=d2, domain="IT", top_n=3)
        
        if not d1_roles or not d2_roles or not d1_skills or not d2_skills:
            return {
                "query": query, "status": "success", "matched_district": f"{d1}, {d2}", "matched_sector": None,
                "answer": f"I don't have enough data to comprehensively compare the IT markets of {d1} and {d2}.", "details": None
            }
            
        ans = [f"**Overall comparison**\n{d1} and {d2} share several core IT competencies, but the distribution of job roles and specific technical demands is not identical in the available listings.\n"]
        
        ans.append("**Role comparison**")
        for i in range(min(3, len(d1_roles), len(d2_roles))):
            ans.append(f"- {d1}: {d1_roles[i]['role']} ({d1_roles[i]['demand_percentage']:.1f}%) | {d2}: {d2_roles[i]['role']} ({d2_roles[i]['demand_percentage']:.1f}%)")
        ans.append("")
        
        ans.append("**Skill comparison**")
        for i in range(min(3, len(d1_skills), len(d2_skills))):
            ans.append(f"- {d1}: {d1_skills[i]['skill']} ({d1_skills[i]['demand_percentage']:.1f}%) | {d2}: {d2_skills[i]['skill']} ({d2_skills[i]['demand_percentage']:.1f}%)")
        ans.append("")
        
        ans.append("**What the comparison indicates**")
        if d1_skills[0]['skill'] == d2_skills[0]['skill']:
            ans.append(f"At the skill level, {d1_skills[0]['skill']} leads both markets, suggesting a shared technical foundation. However, {d1}'s leading role is {d1_roles[0]['role']} ({d1_roles[0]['demand_percentage']:.1f}%), while {d2} shows {d2_roles[0]['role']} at {d2_roles[0]['demand_percentage']:.1f}%.")
            ans.append(f"This comparison points to a common core curriculum requirement across the two cities, alongside differences in role composition that could influence advanced specialization tracks. Regional training planning could use these differences to examine whether the exact same curriculum emphasis is appropriate for both markets.")
        else:
            ans.append(f"The data highlights distinct regional concentrations: {d1} is led by {d1_skills[0]['skill']} while {d2} prioritizes {d2_skills[0]['skill']}. Regional training planning could use these differences to tailor practical labs to local market demands.")
        ans.append("")
            
        ans.append("**Continue the conversation:**")
        ans.append(f"• Which skills differ most significantly between {d1} and {d2}?")
        ans.append(f"• What curriculum changes could be considered for {d1}?")
        ans.append("• How does the projected training supply compare across these districts?")
        
        return {
            "query": query, "status": "success", "matched_district": f"{d1}, {d2}", "matched_sector": None,
            "answer": "\n".join(ans), "details": None
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

        lines = [f"Sure! Here's a quick look at {district}'s skill and training situation. ≡ƒæç", ""]
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
            f"ΓÇó which ITI trades are currently available in {district}, or\n"
            f"ΓÇó how specific sector demand compares with training capacity."
        )

        answer = "\n".join(lines)

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
        q_lower = q_norm.lower()

        # 1. Greetings, Conversation
        greeting_res = self._handle_greetings_and_conversation(q_norm)
        if greeting_res:
            self.context["last_result"] = greeting_res
            return greeting_res

        # 2. INTENT-FIRST ROUTING BEFORE ENTITY EXTRACTION
        is_comparison = any(kw in q_lower for kw in ["compare", "difference", "differ", "versus", "vs", "between"])
        is_gap = any(kw in q_lower for kw in ["gap", "missing", "curriculum", "add", "based on industry demand"])
        is_it_demand = ("skill" in q_lower and "demand" in q_lower) or ("most demanded it skills" in q_lower) or ("technical skill" in q_lower) or ("skill" in q_lower and ("common" in q_lower or "learn" in q_lower))
        is_it_jobs = ("job" in q_lower or "role" in q_lower) and ("it " in q_lower or "software" in q_lower or "developer" in q_lower or "common" in q_lower)
        
        # Check comparison
        if is_comparison:
            comp_res = self._handle_comparison(q_norm)
            if comp_res:
                return comp_res
                
        # Extract entities but don't commit them to context yet
        raw_dist, raw_sec, raw_tr = self.extract_entities(q_norm)
        
        # Resolve district for single intents
        if not raw_dist:
            if "maharashtra" in q_lower:
                district = None
            elif any(p in q_lower for p in ["this region", "there", "that district", "what about", "here"]):
                district = self.context.get("district")
            else:
                district = None
        else:
            district = raw_dist
            
        if is_gap:
            gap_res = self._handle_skill_gap(q_norm, district)
            if gap_res:
                self.context.update({"district": district, "sector": raw_sec, "trade": raw_tr, "last_result": gap_res})
                return gap_res
                
        if is_it_demand or is_it_jobs:
            job_res = self._handle_job_demand(q_norm, district)
            if job_res:
                self.context.update({"district": district, "sector": raw_sec, "trade": raw_tr, "last_result": job_res})
                return job_res

        # If no specific intent matched above, do legacy entity assignment
        sector = raw_sec or self.context.get("sector")
        trade = raw_tr or self.context.get("trade")

        followup_res = self._handle_followups_and_explanations(q_norm, district, sector, trade)
        if followup_res:
            self.context.update({"district": district, "sector": sector, "trade": trade, "last_result": followup_res})
            return followup_res

        curr_res = self._handle_curriculum_and_skills_reference(q_norm, trade)
        if curr_res:
            self.context.update({"district": district, "sector": sector, "trade": trade, "last_result": curr_res})
            return curr_res

        ranking_keywords = ["which sectors", "top sectors", "high demand sectors", "sectors have", "list sectors", "show sectors", "what sectors", "overall iti capacity", "which trades", "top trades", "show trades", "what trades"]
        if raw_dist and not sector and not trade and not any(kw in q_lower for kw in ranking_keywords):
            return self._comprehensive_district_analysis(raw_dist)

        return self._legacy_ask_logic(q_norm, district, sector, trade)
        
    def _legacy_ask_logic(self, q_norm, district, sector, trade):
        q_lower = q_norm.lower()
        if "supply" in q_lower or "capacity" in q_lower or "capacity mismatch" in q_lower or "training" in q_lower or "projected" in q_lower:
            loc = district or "Maharashtra"
            try:
                res = self.supply_engine.analyze_district_alignment(loc)
                if not res or res.get("status") != "success":
                    return {"query_type": "supply", "status": "insufficient_data", "answer": f"The available evidence is insufficient to calculate a model-estimated projected training demand for {loc}."}
                
                ans = [
                    "**Direct Answer**",
                    f"The model-estimated projected training demand for {loc} suggests a {res['alignment_status'].lower()} when compared against ITI capacity.",
                    "",
                    "**Evidence**",
                    f"- Predicted total training demand: {res['predicted_total_training_demand']:.0f} seats",
                    f"- Total ITI capacity: {res['total_iti_capacity']:.0f} seats",
                    f"- Alignment gap: {res['alignment_gap']:.0f} seats",
                    "",
                    "**What the data indicates**",
                    "This estimate represents projected training demand based on available industry and demographic signals, compared against existing training supply. The result indicates potential areas where training supply may need alignment with demand. It serves as a directional planning signal, not a certain future employment guarantee.",
                    "",
                    "**Practical implication**",
                    "Government and training planners could consider using this data alongside local industry surveys to review whether training seat allocations should be adjusted to better match the projected requirement.",
                    "",
                    "**Continue the conversation:**",
                    "• Which districts show potential shortages?",
                    "• How does projected training compare with ITI capacity across sectors?",
                    "• Which sectors have the strongest available evidence?"
                ]
                return {"query_type": "supply", "status": "success", "answer": "\n".join(ans), "matched_district": loc}
            except Exception as e:
                return {"query_type": "supply", "status": "error", "answer": f"Error analyzing supply: {str(e)}"}

        
        ranking_keywords = ["which sectors", "top sectors", "high demand sectors", "sectors have", "list sectors", "show sectors", "what sectors", "overall iti capacity", "which trades", "top trades", "show trades", "what trades"]
        if any(kw in q_lower for kw in ranking_keywords):
            if "trade" in q_lower:
                if sector:
                    trades_info = self.model.predict_top_trades(district, sector, top_n=5)
                    if not trades_info:
                        return {"query_type": "ranking", "status": "insufficient_data", "answer": f"Not enough data to rank trades in {sector} for {district}."}
                    lines = [f"Here are the top trades for {sector} in {district}:"]
                    for t in trades_info:
                        lines.append(f"- {t['trade']}: ~{t['predicted_projected_training']} trainees ({t['demand_band']} demand)")
                    return {"query_type": "ranking", "status": "success", "answer": "\n".join(lines)}
            else:
                top_sectors = self.model.predict_top_sectors(district, top_n=5)
                if not top_sectors:
                    return {"query_type": "ranking", "status": "insufficient_data", "answer": f"Not enough data to rank sectors for {district}."}
                lines = [f"Here are the top sectors in {district}:"]
                for s in top_sectors:
                    lines.append(f"- {s['sector']}: ~{s['predicted_projected_training']} trainees ({s['demand_band']} demand)")
                return {"query_type": "ranking", "status": "success", "answer": "\n".join(lines)}

        if district and sector and trade:
            return self._predict_single(q_norm, district, sector, trade)
        if district and sector:
            return self._predict_single(q_norm, district, sector, None)
            
        return {
            "query_type": "unknown",
            "status": "needs_clarification",
            "matched_district": district,
            "matched_sector": sector,
            "answer": "Please specify a Maharashtra district (e.g., Pune, Mumbai City, Nashik), sector (e.g., Construction, Agriculture, BFSI), or ITI trade (e.g., Electrician, Fitter) to explore training data.",
            "details": None
        }
