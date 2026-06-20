"""JD parser for Module 1 of the P.R.I.S.M AI hackathon project.

This parser is intentionally tailored to the Redrob AI Senior AI Engineer JD.
It converts the free-text role description into the structured ``JDProfile``
used by downstream candidate scoring, semantic matching, recruitability, and
authenticity modules.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

try:
    from .jd_config import (
        DEFAULT_WEIGHTS,
        GOOD_TO_HAVE_KEYWORDS,
        MUST_HAVE_KEYWORDS,
        NEGATIVE_SIGNALS,
    )
    from .jd_schema import JDProfile
except ImportError:
    from jd_config import (  # type: ignore[no-redef]
        DEFAULT_WEIGHTS,
        GOOD_TO_HAVE_KEYWORDS,
        MUST_HAVE_KEYWORDS,
        NEGATIVE_SIGNALS,
    )
    from jd_schema import JDProfile  # type: ignore[no-redef]


DEFAULT_JD_PATH = Path(
    "/Users/harshitagupta/Downloads/[PUB] India_runs_data_and_ai_challenge/"
    "India_runs_data_and_ai_challenge/job_description.docx"
)


class JDParser:
    """Parse the attached Redrob AI job description into a structured profile."""

    def __init__(self, jd_path: Path | str = DEFAULT_JD_PATH) -> None:
        self.jd_path = Path(jd_path)
        self._jd_text: str | None = None

    def load_jd(self) -> str:
        """Load the JD text from a supported source file."""
        if self._jd_text is not None:
            return self._jd_text

        if not self.jd_path.exists():
            raise FileNotFoundError(f"JD file not found: {self.jd_path}")

        suffix = self.jd_path.suffix.lower()
        if suffix == ".docx":
            self._jd_text = self._load_docx_text(self.jd_path)
        elif suffix in {".txt", ".md"}:
            self._jd_text = self.jd_path.read_text(encoding="utf-8")
        else:
            raise ValueError(f"Unsupported JD file format: {suffix}")

        return self._jd_text

    def extract_title(self) -> str:
        """Extract the role title from the JD heading."""
        jd_text = self.load_jd()
        match = re.search(r"Job Description:\s*(.+)", jd_text)
        if not match:
            return "Senior AI Engineer - Founding Team"
        return self._clean_text(match.group(1))

    def extract_must_have(self) -> list[str]:
        """Extract must-have hiring requirements from the JD."""
        return self._filter_present_requirements(MUST_HAVE_KEYWORDS)

    def extract_good_to_have(self) -> list[str]:
        """Extract preferred but non-disqualifying requirements from the JD."""
        return self._filter_present_requirements(GOOD_TO_HAVE_KEYWORDS)

    def extract_negative_signals(self) -> list[str]:
        """Extract explicit candidate disqualifiers and down-ranking signals."""
        return self._filter_present_requirements(NEGATIVE_SIGNALS)

    def extract_experience_range(self) -> tuple[int | None, int | None]:
        """Extract the target experience range from the JD."""
        jd_text = self.load_jd()
        match = re.search(r"Experience Required:\s*(\d+)\s*[–-]\s*(\d+)\s*years", jd_text)
        if match:
            return int(match.group(1)), int(match.group(2))

        fallback = re.search(r"(\d+)\s*[–-]\s*(\d+)\s+years total experience", jd_text)
        if fallback:
            return int(fallback.group(1)), int(fallback.group(2))

        return None, None

    def extract_locations(self) -> list[str]:
        """Extract preferred candidate locations from the JD."""
        jd_text = self.load_jd()
        preferred_locations = [
            "Pune",
            "Noida",
            "Delhi NCR",
            "Hyderabad",
            "Mumbai",
        ]
        normalized_text = jd_text.lower()
        return [location for location in preferred_locations if location.lower() in normalized_text]

    def parse(self) -> JDProfile:
        """Parse the JD into a structured ``JDProfile`` object."""
        experience_min, experience_max = self.extract_experience_range()
        return JDProfile(
            title=self.extract_title(),
            must_have=self.extract_must_have(),
            good_to_have=self.extract_good_to_have(),
            negative_signals=self.extract_negative_signals(),
            experience_min=experience_min,
            experience_max=experience_max,
            preferred_locations=self.extract_locations(),
            weights=DEFAULT_WEIGHTS.copy(),
        )

    def _filter_present_requirements(self, configured_requirements: list[str]) -> list[str]:
        """Return configured requirements whose core evidence appears in the JD."""
        jd_text = self.load_jd().lower()
        return [
            requirement
            for requirement in configured_requirements
            if self._requirement_is_supported(requirement, jd_text)
        ]

    def _requirement_is_supported(self, requirement: str, jd_text: str) -> bool:
        """Check whether a curated requirement is supported by the attached JD."""
        evidence_terms = {
            "embeddings-based retrieval": ("embeddings", "retrieval"),
            "vector databases": ("pinecone", "weaviate", "qdrant", "milvus", "faiss"),
            "strong python": ("strong python",),
            "evaluation frameworks": ("ndcg", "mrr", "map", "a/b test"),
            "ranking, search, recommendation": ("ranking", "search", "recommendation"),
            "candidate-jd matching": ("candidate-jd matching",),
            "scrappy product-engineering": ("scrappy product-engineering", "ship a working ranker"),
            "product-company": ("product companies", "product-company"),
            "production coding": ("production code", "writes code"),
            "llm fine-tuning": ("lora", "qlora", "peft"),
            "learning-to-rank": ("learning-to-rank", "xgboost"),
            "hr-tech": ("hr-tech", "recruiting tech", "marketplace"),
            "distributed systems": ("distributed systems", "large-scale inference"),
            "open-source": ("open-source",),
            "mentoring": ("mentoring",),
            "written async": ("async-first", "write a lot"),
            "active job-market": ("active on redrob", "job market"),
            "pure research": ("pure research", "academic labs"),
            "langchain": ("langchain",),
            "last 18 months": ("last 18 months",),
            "title progression": ("title-chasers", "senior", "staff", "principal"),
            "consulting or services": ("tcs", "infosys", "wipro", "accenture", "cognizant"),
            "computer vision": ("computer vision", "speech", "robotics"),
            "closed-source": ("closed-source proprietary",),
            "stable, mature": ("stable, mature codebase",),
            "keyword-heavy": ("skills section contains the most ai keywords",),
            "stale platform": ("logged in for 6 months", "recruiter response rate"),
        }
        normalized_requirement = requirement.lower()
        for key_phrase, terms in evidence_terms.items():
            if key_phrase in normalized_requirement:
                return any(term in jd_text for term in terms)
        return True

    @staticmethod
    def _load_docx_text(path: Path) -> str:
        """Read paragraph text from a DOCX file without external dependencies."""
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with ZipFile(path) as document:
            xml_content = document.read("word/document.xml")

        root = ET.fromstring(xml_content)
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", namespace):
            text_parts = [
                node.text or ""
                for node in paragraph.findall(".//w:t", namespace)
            ]
            paragraph_text = "".join(text_parts).strip()
            if paragraph_text:
                paragraphs.append(paragraph_text)

        return "\n".join(paragraphs)

    @staticmethod
    def _clean_text(value: str) -> str:
        """Normalize whitespace and punctuation variants in extracted text."""
        return re.sub(r"\s+", " ", value).strip().replace("—", "-")


def main() -> None:
    """Parse the attached JD and print the core structured profile fields."""
    profile = JDParser().parse()
    print(
        json.dumps(
            {
                "title": profile.title,
                "must_have": profile.must_have,
                "good_to_have": profile.good_to_have,
                "negative_signals": profile.negative_signals,
                "experience_min": profile.experience_min,
                "experience_max": profile.experience_max,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
