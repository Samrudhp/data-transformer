"""
CanonicalNormalizer — normalizes business values in candidate fragments
into a consistent canonical vocabulary.

Normalises:
  - Skills    (ReactJS → React, React.js → React)
  - Companies (Samsung Research → Samsung)
  - Locations (Bangalore → Bengaluru)
  - Job titles
  - Dates → ISO 8601 (YYYY-MM)
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.models.processing_context import ProcessingContext
from src.pipeline.stage import Stage
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Normalisation lookup tables (extend as needed)
# ---------------------------------------------------------------------------

SKILL_ALIASES: Dict[str, str] = {
    "reactjs": "React",
    "react.js": "React",
    "react js": "React",
    "vuejs": "Vue.js",
    "vue js": "Vue.js",
    "angularjs": "Angular",
    "angular js": "Angular",
    "nodejs": "Node.js",
    "node js": "Node.js",
    "node.js": "Node.js",
    "expressjs": "Express.js",
    "express.js": "Express.js",
    "express js": "Express.js",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "mongo db": "MongoDB",
    "elasticsearch": "Elasticsearch",
    "elastic search": "Elasticsearch",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "artificial intelligence": "AI",
    "c++": "C++",
    "c#": "C#",
    "golang": "Go",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "rest api": "REST API",
    "restapi": "REST API",
    "graphql": "GraphQL",
    "html5": "HTML",
    "css3": "CSS",
    "sass": "SASS",
    "scss": "SASS",
}

COMPANY_ALIASES: Dict[str, str] = {
    "samsung research": "Samsung",
    "samsung r&d": "Samsung",
    "samsung india": "Samsung",
    "google india": "Google",
    "amazon india": "Amazon",
    "microsoft india": "Microsoft",
    "infosys bpo": "Infosys",
    "wipro technologies": "Wipro",
    "tata consultancy services": "TCS",
    "tcs": "TCS",
    "hcl technologies": "HCL",
    "tech mahindra": "Tech Mahindra",
    "ibm india": "IBM",
}

LOCATION_ALIASES: Dict[str, str] = {
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "bombay": "Mumbai",
    "calcutta": "Kolkata",
    "madras": "Chennai",
    "new delhi": "Delhi",
    "gurugram": "Gurugram",
    "gurgaon": "Gurugram",
    "hyderabad": "Hyderabad",
    "pune": "Pune",
    "noida": "Noida",
    "san francisco": "San Francisco",
    "sf": "San Francisco",
    "nyc": "New York",
    "new york city": "New York",
}

TITLE_ALIASES: Dict[str, str] = {
    "sde": "Software Development Engineer",
    "sde-1": "Software Development Engineer I",
    "sde-2": "Software Development Engineer II",
    "sde1": "Software Development Engineer I",
    "sde2": "Software Development Engineer II",
    "swe": "Software Engineer",
    "sr. software engineer": "Senior Software Engineer",
    "sr software engineer": "Senior Software Engineer",
    "senior swe": "Senior Software Engineer",
    "lead swe": "Lead Software Engineer",
    "staff swe": "Staff Software Engineer",
    "principal swe": "Principal Software Engineer",
    "ml engineer": "Machine Learning Engineer",
    "mle": "Machine Learning Engineer",
    "data scientist": "Data Scientist",
    "ds": "Data Scientist",
    "product manager": "Product Manager",
    "pm": "Product Manager",
    "tpm": "Technical Program Manager",
    "em": "Engineering Manager",
    "vp engineering": "VP of Engineering",
    "vp of engineering": "VP of Engineering",
    "cto": "Chief Technology Officer",
    "ceo": "Chief Executive Officer",
}

# ---------------------------------------------------------------------------
# Date parsing patterns (most-specific first)
# ---------------------------------------------------------------------------
_DATE_PATTERNS = [
    (re.compile(r"(\d{4})-(\d{1,2})"), "%Y-%m"),           # 2023-05
    (re.compile(r"(\d{1,2})/(\d{4})"), "%m/%Y"),           # 05/2023
    (re.compile(r"(\d{4})/(\d{1,2})"), "%Y/%m"),           # 2023/05
    (re.compile(r"([A-Za-z]{3,9})\s+(\d{4})"), "%B %Y"),   # May 2023
    (re.compile(r"(\d{4})"), "%Y"),                          # 2023
]
_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class CanonicalNormalizer(Stage):
    """
    Pipeline stage that applies canonical business-value normalization
    to all extracted fields in the normalised fragments.

    Normalized fragments are updated in-place within
    ``context.normalized_fragments``.
    """

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Apply canonical normalization to all normalised fragments.

        Args:
            context: Shared pipeline context.

        Returns:
            Updated context with normalised field values.
        """
        logger.info(
            "CanonicalNormalizer: normalising %d fragment(s).",
            len(context.normalized_fragments),
        )
        updated: list = []
        for fragment in context.normalized_fragments:
            fields = dict(fragment.extracted_fields)

            # Skills
            raw_skills = fields.get("skills")
            if isinstance(raw_skills, list):
                fields["skills"] = [self.normalize_skill(s) for s in raw_skills]
            elif isinstance(raw_skills, str):
                fields["skills"] = [
                    self.normalize_skill(s.strip())
                    for s in raw_skills.split(",")
                    if s.strip()
                ]

            # Company
            for key in ("current_company", "company"):
                if key in fields and fields[key]:
                    fields[key] = self.normalize_company(str(fields[key]))

            # Location / city
            for key in ("city", "location"):
                if key in fields and fields[key]:
                    fields[key] = self.normalize_location(str(fields[key]))

            # Job title
            for key in ("current_title", "title"):
                if key in fields and fields[key]:
                    fields[key] = self.normalize_title(str(fields[key]))

            # Dates in education / experience lists
            for list_key in ("education", "experience"):
                raw_list = fields.get(list_key)
                if isinstance(raw_list, list):
                    fields[list_key] = [
                        self._normalize_date_fields(entry) if isinstance(entry, dict) else entry
                        for entry in raw_list
                    ]

            updated_fragment = fragment.model_copy(update={"extracted_fields": fields})
            updated.append(updated_fragment)

        context.normalized_fragments = updated
        logger.info("CanonicalNormalizer: completed.")
        return context

    # ------------------------------------------------------------------
    # Public normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_skill(skill: str) -> str:
        """
        Map a skill string to its canonical form.

        Falls back to title-casing the original string if no alias found.
        """
        if not skill:
            return skill
        key = skill.strip().lower()
        return SKILL_ALIASES.get(key, skill.strip())

    @staticmethod
    def normalize_company(company: str) -> str:
        """Map a company name to its canonical form."""
        if not company:
            return company
        key = company.strip().lower()
        return COMPANY_ALIASES.get(key, company.strip())

    @staticmethod
    def normalize_location(location: str) -> str:
        """Map a location/city string to its canonical form."""
        if not location:
            return location
        key = location.strip().lower()
        return LOCATION_ALIASES.get(key, location.strip())

    @staticmethod
    def normalize_title(title: str) -> str:
        """Map a job title to its canonical form."""
        if not title:
            return title
        key = title.strip().lower()
        return TITLE_ALIASES.get(key, title.strip())

    @staticmethod
    def normalize_date(value: Optional[str]) -> Optional[str]:
        """
        Parse a loosely formatted date string and return an ISO 8601
        YYYY-MM string, or ``None`` if parsing fails.

        Examples:
            "May 2023"   → "2023-05"
            "05/2023"    → "2023-05"
            "2023"       → "2023"
            "2023-07-01" → "2023-07"
        """
        if not value or not isinstance(value, str):
            return value

        text = value.strip()
        if text.lower() in ("present", "current", "now", "ongoing"):
            return "present"

        # Full ISO datetime — truncate to YYYY-MM
        try:
            dt = datetime.fromisoformat(text[:10])
            return dt.strftime("%Y-%m")
        except ValueError:
            pass

        # Month abbreviation + year: "May 2023"
        parts = text.split()
        if len(parts) == 2:
            month_str = parts[0].lower()[:3]
            year_str = parts[1]
            if month_str in _MONTH_ABBR and year_str.isdigit():
                return f"{year_str}-{_MONTH_ABBR[month_str]:02d}"

        # MM/YYYY or YYYY/MM
        slash_match = re.match(r"^(\d{1,2})/(\d{4})$", text)
        if slash_match:
            return f"{slash_match.group(2)}-{int(slash_match.group(1)):02d}"

        slash_match2 = re.match(r"^(\d{4})/(\d{1,2})$", text)
        if slash_match2:
            return f"{slash_match2.group(1)}-{int(slash_match2.group(2)):02d}"

        # YYYY-MM
        ym_match = re.match(r"^(\d{4})-(\d{1,2})$", text)
        if ym_match:
            return f"{ym_match.group(1)}-{int(ym_match.group(2)):02d}"

        # Year only
        if re.match(r"^\d{4}$", text):
            return text

        return value  # Return as-is if we can't parse.

    def _normalize_date_fields(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise start_date and end_date within an education/experience dict."""
        result = dict(entry)
        for date_key in ("start_date", "end_date"):
            if date_key in result:
                result[date_key] = self.normalize_date(result[date_key])
        return result
