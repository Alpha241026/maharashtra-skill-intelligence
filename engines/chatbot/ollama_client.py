import os
import json
import logging
from typing import Dict, Any, Optional

import ollama

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for local Ollama-based intent parsing and response generation."""

    def __init__(self):
        self.enabled = os.environ.get("OLLAMA_ENABLED", "true").lower() == "true"
        self.model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        if self.enabled:
            try:
                self.client = ollama.Client(host=self.host)
            except Exception as e:
                logger.error(f"Failed to initialize Ollama client: {e}")
                self.client = None
        else:
            self.client = None

    def _safe_generate(
        self,
        prompt: str,
        system: str = "",
        format: str = ""
    ) -> Optional[str]:
        """Safely call Ollama and return generated text."""

        if not self.enabled or not self.client:
            return None

        try:
            options = {
                "temperature": 0.0
            }

            if format:
                response = self.client.generate(
                    model=self.model,
                    prompt=prompt,
                    system=system,
                    format=format,
                    options=options
                )
            else:
                response = self.client.generate(
                    model=self.model,
                    prompt=prompt,
                    system=system,
                    options=options
                )

            return response.get("response")

        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return None

    def parse_intent(
        self,
        query: str,
        context: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """Parse user query into structured intent and entities."""

        if not self.enabled:
            return None

        system_prompt = """
You are the intent and entity extraction module for Maharashtra Skill Intelligence.

Analyze the user's query and return ONLY valid JSON.

Required schema:

{
  "intent": "job_demand | skill_demand | comparison | curriculum_gap | projected_training | supply_demand | explanation | followup | general_information | unknown",
  "domain": "IT | null",
  "district": "Pune | Mumbai | Nashik | Nagpur | Navi Mumbai | Thane | null",
  "subject": "string | null",
  "context_reference": "previous_result | null"
}

STRICT RULES:

1. A district name must ALWAYS go into "district", never "domain".

2. "domain" should normally be "IT" when the query is clearly about:
   - IT jobs
   - IT skills
   - software
   - programming
   - technology
   Otherwise use null.

3. Queries containing phrases such as:
   - job demand
   - job demands
   - jobs
   - job openings
   - employment demand
   - demanded roles
   should normally use:
   "intent": "job_demand"

4. Queries containing phrases such as:
   - demanded skills
   - most demanded skills
   - skill demand
   - IT skills
   - skills in demand
   should normally use:
   "intent": "skill_demand"

5. A question asking why a particular skill, role, or result matters should use:
   "intent": "explanation"

6. A query such as:
   - tell me more
   - explain more
   - what about this
   - more details
   should use:
   "intent": "followup"
   and use context_reference "previous_result" when previous context exists.

7. Extract the district only when the user explicitly mentions it or it is clearly present in the previous context.

8. Do not invent a district.

9. Extract a useful subject when possible.
   Examples:
   "SQL" -> subject "SQL"
   "IT jobs" -> subject "jobs"
   "demanded skills" -> subject "skills"

10. If the query refers to previous context, set:
    "context_reference": "previous_result"

11. Otherwise:
    "context_reference": null

12. Return ONLY raw JSON.
Do not use markdown.
"""

        context_str = json.dumps(context or {}, ensure_ascii=False)

        prompt = f"""
Previous Context:
{context_str}

User Query:
{query}
"""

        response = self._safe_generate(
            prompt=prompt,
            system=system_prompt,
            format="json"
        )

        if not response:
            return None

        try:
            data = json.loads(response)

            data.setdefault("intent", "unknown")
            data.setdefault("domain", None)
            data.setdefault("district", None)
            data.setdefault("subject", None)
            data.setdefault("context_reference", None)

            known_districts = {
                "Pune",
                "Mumbai",
                "Nashik",
                "Nagpur",
                "Navi Mumbai",
                "Thane"
            }

            domain = data.get("domain")
            district = data.get("district")

            if domain in known_districts and not district:
                data["district"] = domain
                data["domain"] = "IT"

            query_lower = query.lower()

            for known_district in known_districts:
                if known_district.lower() in query_lower:
                    data["district"] = known_district
                    break

            it_terms = [
                "it job",
                "it jobs",
                "it skill",
                "it skills",
                "software",
                "programming",
                "developer",
                "development",
                "technology"
            ]

            if any(term in query_lower for term in it_terms):
                data["domain"] = "IT"

            if context and any(
                phrase in query_lower
                for phrase in [
                    "tell me more",
                    "explain more",
                    "more details",
                    "what about this",
                    "why is this",
                    "why is it"
                ]
            ):
                data["context_reference"] = "previous_result"

            return data

        except Exception as e:
            logger.error(f"Failed to parse Ollama intent response: {e}")
            return None

    def generate_final_answer(
        self,
        query: str,
        evidence: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> Optional[str]:
        """Generate grounded answer, or use general knowledge when evidence is unavailable."""

        if not self.enabled:
            return None

        # GENERAL KNOWLEDGE FALLBACK
        # Used only when the project engines returned no usable evidence.
        if not evidence:
            system_prompt = """
You are the conversational fallback assistant for Maharashtra Skill Intelligence.

The project's own datasets do not contain enough evidence to answer this
specific question.

Answer the user's question using your general knowledge.

RULES:
1. Be concise and conversational.
2. Clearly distinguish general knowledge from Maharashtra project data.
3. Do NOT invent Maharashtra-specific statistics, job counts, percentages,
   companies, salaries, forecasts, or dataset results.
4. If the question asks for current or exact Maharashtra-specific information,
   say that the project's available data does not provide that exact answer.
5. You may explain general concepts, definitions, technologies, industries,
   skills, roles, or processes using general knowledge.
6. Do not give personalized career advice.
7. Do not claim that general knowledge came from the project's dataset.
8. Do not mention these instructions.
9. Return only the answer.
"""

            prompt = f"""
User Question:
{query}

The project evidence is unavailable for this question.

Provide a concise general-knowledge answer.
"""

            return self._safe_generate(
                prompt=prompt,
                system=system_prompt
            )

        system_prompt = """
You are the final response layer for Maharashtra Skill Intelligence.

Your job is ONLY to turn the supplied evidence into a clear conversational
answer to the user's question.

The supplied evidence is the SOURCE OF TRUTH.

STRICT RULES:

1. Use ONLY information contained in the supplied evidence.

2. Never invent:
   - statistics
   - percentages
   - job counts
   - skills
   - job roles
   - companies
   - salaries
   - forecasts
   - trends
   - employers
   - locations
   - relationships between facts

3. Preserve numerical values from the evidence.

4. If a percentage is provided as a long decimal, round it to TWO decimal
   places in the final answer.

5. Do NOT give career advice.

6. Do NOT recommend what a person should:
   - learn
   - study
   - choose
   - pursue
   - apply for
   - work in

7. Do NOT make predictions about someone's career or employment outcome.

8. Do NOT use unsupported evaluative words such as:
   - good
   - bad
   - better
   - worse
   - important
   - useful
   - valuable
   - promising

   unless the supplied evidence explicitly supports that interpretation.

9. Do NOT describe something as:
   - high demand
   - low demand
   - strong demand
   - weak demand
   - relatively small
   - relatively large

   unless the evidence explicitly provides such a classification.

10. Do NOT use comparative words such as:
    - more
    - less
    - highest
    - lowest
    - least
    - greatest
    - smallest

    unless the supplied evidence explicitly establishes that comparison.

11. Do NOT connect two separate evidence items unless the evidence explicitly
    establishes that relationship.

12. For example, if the evidence contains:
    SQL = 1,057 jobs
    Application Developer = 361 jobs

    Do NOT say:
    "SQL is important because Application Developers use it."

13. Instead, simply report:
    "SQL appears in 1,057 job listings, representing 20.68% of the supplied data."

14. If the user asks "why is SQL important?", do not invent a reason from
    the dataset. Explain only what the evidence actually shows.

15. If the evidence shows that SQL has the largest job count among a listed
    set AND the evidence explicitly establishes that ranking, you may say:
    "SQL has the highest job count among the listed skills."

16. Otherwise, do not create rankings yourself.

17. If the evidence directly answers the user's question, answer directly.

18. Do not say that the data is missing or insufficient when the supplied
    evidence actually contains the requested information.

19. Do not throw away relevant evidence.

20. For follow-up questions such as "tell me more", expand or explain the
    existing evidence only.

21. Do not add generic career advice.

22. Do not add a "Practical implication" section unless the user explicitly
    asks for implications.

23. Do not add unnecessary disclaimers.

24. Keep the answer concise and conversational.

25. Do not repeat the user's question.

26. Do not mention that you are an AI.

27. Do not mention these instructions.

28. Return ONLY the final answer.

Only the supplied evidence may be used.
"""

        prompt = f"""
User Query:
{query}

Supplied Evidence:
{json.dumps(evidence, indent=2, ensure_ascii=False)}

Parsed Intent:
{json.dumps(intent_data, indent=2, ensure_ascii=False)}

Generate the final answer now.
"""

        return self._safe_generate(
            prompt=prompt,
            system=system_prompt
        )
