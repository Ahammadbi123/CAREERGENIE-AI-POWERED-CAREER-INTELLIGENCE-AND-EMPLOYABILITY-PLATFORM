# extractor.py

import re
from collections import defaultdict
from career_intelligence.skill_taxonomy import SKILL_TAXONOMY


class SkillExtractor:

    def __init__(self):
        self.taxonomy = SKILL_TAXONOMY

    def clean_text(self, text):
        """
        Basic text cleaning
        """
        text = text.lower()
        text = re.sub(r'[^\w\s+]', ' ', text)
        return text

    def extract_skills(self, job_text):
        """
        Extract skills from a single job description
        """
        cleaned_text = self.clean_text(job_text)

        extracted = defaultdict(list)

        for category, skills in self.taxonomy.items():
            for skill in skills:
                pattern = r'\b' + re.escape(skill) + r'\b'
                if re.search(pattern, cleaned_text):
                    extracted[category].append(skill)

        return dict(extracted)

    def count_skill_frequency(self, job_descriptions):
        """
        Count frequency of skills across multiple job descriptions
        """
        frequency = defaultdict(int)

        for job in job_descriptions:
            extracted = self.extract_skills(job)

            for category, skills in extracted.items():
                for skill in skills:
                    frequency[skill] += 1

        return dict(frequency)