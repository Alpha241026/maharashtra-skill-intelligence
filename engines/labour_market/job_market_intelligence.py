import pandas as pd
import numpy as np
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from sentence_transformers import SentenceTransformer, util

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CLEANED_JOB_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "jobs" / "cleaned_job_data.csv"
JOB_SKILLS_PATH = PROJECT_ROOT / "data" / "processed" / "jobs" / "job_skills.csv"
SKILL_DEMAND_PATH = PROJECT_ROOT / "data" / "processed" / "jobs" / "skill_demand.csv"

IT_KEYWORDS = ["software", "developer", "web development", "mobile development", "data", "ai", "machine learning", "cloud", "devops", "cybersecurity", "database", "qa", "testing", "networking", "it support", "analytics", "cse"]

class JobMarketIntelligence:
    def __init__(self, data_path=None, skills_path=None, demand_path=None):
        self.data_path = Path(data_path) if data_path else CLEANED_JOB_DATA_PATH
        self.skills_path = Path(skills_path) if skills_path else JOB_SKILLS_PATH
        self.demand_path = Path(demand_path) if demand_path else SKILL_DEMAND_PATH
        
        self.jobs_df = None
        self.skills_df = None
        self.demand_df = None
        self.model = None

    def _load_data(self):
        if self.jobs_df is None:
            self.jobs_df = pd.read_csv(self.data_path)
            self.jobs_df['jobId'] = self.jobs_df['jobId'].astype(str)
            # Pre-compute IT flag for speed
            self.jobs_df['is_it'] = self.jobs_df.apply(self._is_it_job, axis=1)

        if self.skills_df is None:
            self.skills_df = pd.read_csv(self.skills_path)
            self.skills_df['jobId'] = self.skills_df['jobId'].astype(str)

        if self.demand_df is None and self.demand_path.exists():
            self.demand_df = pd.read_csv(self.demand_path)

    def _is_it_job(self, row) -> bool:
        title = str(row.get('title', '')).lower()
        tags = str(row.get('tagsAndSkills', '')).lower()
        
        exclude_kws = ["sales", "customer service", "bpo", "hr", "human resources", "marketing", "business development", "telecaller", "support executive"]
        if any(kw in title for kw in exclude_kws):
            return False
            
        it_kws = ["software", "developer", "web development", "mobile development", "data scientist", "data engineer", "data analyst", "machine learning", "cloud", "devops", "cybersecurity", "database", "qa ", "testing", "networking", "it support", "analytics", "programmer", "backend", "frontend", "full stack", "fullstack", "java", "python", "sql", "react", "angular", "node", "aws", "azure"]
        
        text = f"{title} {tags}"
        # Only use word boundaries for short acronyms like AI or QA to prevent substring matching
        if " ai " in f" {text} " or " qa " in f" {text} " or " it " in f" {text} " or " ml " in f" {text} ":
            return True
            
        return any(kw in text for kw in it_kws)

    def _get_filtered_jobs(self, location: Optional[str] = None, domain: Optional[str] = None) -> pd.DataFrame:
        self._load_data()
        df = self.jobs_df.copy()
        
        if location:
            pat = r'(?i)' + re.escape(location)
            df = df[df['location'].astype(str).str.contains(pat, regex=True, na=False)]
            
        if domain and domain.upper() == "IT":
            df = df[df['is_it'] == True]
            
        return df

    def get_job_summary(self, location: Optional[str] = None, domain: Optional[str] = None) -> Dict[str, Any]:
        df = self._get_filtered_jobs(location, domain)
        total_jobs = len(df)
        
        if total_jobs == 0:
            return {"total_jobs": 0, "locations": [], "companies": 0, "avg_min_salary": None}
            
        locations = df['location'].value_counts().head(5).to_dict()
        companies = df['companyName'].nunique()
        avg_min_salary = df['minimumSalary'].mean() if 'minimumSalary' in df.columns else None
        
        return {
            "total_jobs": total_jobs,
            "top_locations": locations,
            "unique_companies": companies,
            "avg_min_salary": avg_min_salary
        }

    def get_top_skills(self, location: Optional[str] = None, domain: Optional[str] = None, top_n: int = 10) -> List[Dict[str, Any]]:
        df = self._get_filtered_jobs(location, domain)
        if df.empty:
            return []
            
        job_ids = df['jobId'].tolist()
        sk_df = self.skills_df[self.skills_df['jobId'].isin(job_ids)]
        
        if sk_df.empty:
            return []
            
        total_jobs = len(df)
        counts = sk_df['skill_normalized'].value_counts().head(top_n)
        
        res = []
        for sk, count in counts.items():
            res.append({
                "skill": sk,
                "job_count": int(count),
                "demand_percentage": (count / total_jobs) * 100
            })
        return res

    def get_top_roles(self, location: Optional[str] = None, domain: Optional[str] = None, top_n: int = 10) -> List[Dict[str, Any]]:
        df = self._get_filtered_jobs(location, domain)
        if df.empty:
            return []
            
        counts = df['title'].value_counts().head(top_n)
        total_jobs = len(df)
        
        res = []
        for role, count in counts.items():
            res.append({
                "role": role,
                "job_count": int(count),
                "demand_percentage": (count / total_jobs) * 100
            })
        return res

    def compare_locations(self, location_a: str, location_b: str, domain: Optional[str] = None) -> Dict[str, Any]:
        sum_a = self.get_job_summary(location_a, domain)
        sum_b = self.get_job_summary(location_b, domain)
        
        skills_a = self.get_top_skills(location_a, domain, 5)
        skills_b = self.get_top_skills(location_b, domain, 5)
        
        return {
            "location_a": {
                "name": location_a,
                "total_jobs": sum_a["total_jobs"],
                "top_skills": skills_a
            },
            "location_b": {
                "name": location_b,
                "total_jobs": sum_b["total_jobs"],
                "top_skills": skills_b
            }
        }
