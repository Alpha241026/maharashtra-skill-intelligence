import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
import torch

class CurriculumSkillGapAnalyzer:
    def __init__(self, semantic_threshold=0.8):
        self.semantic_threshold = semantic_threshold
        self.model = None

    def _load_model(self):
        if self.model is None:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def analyze(self, demand_df, curriculum_df):
        """
        Analyzes the gap between industry demand and curriculum supply.
        """
        results = []
        
        # Prepare curriculum skills
        # We need a unique list of normalized curriculum skills for matching
        # However, a skill might map to multiple colleges/courses. 
        # For this global gap analysis, we usually check if the industry skill exists IN THE CURRICULUM at all,
        # but the prompt asks to "Include college and curriculum skill information."
        # This implies we do a left join from Industry Skills -> Curriculum Skills.
        
        curr_skills_map = {}
        for _, row in curriculum_df.iterrows():
            sn = row['skill_normalized']
            if pd.isna(sn):
                continue
            if sn not in curr_skills_map:
                curr_skills_map[sn] = []
            curr_skills_map[sn].append({
                'college': row.get('college', ''),
                'course': row.get('course', ''),
                'topic': row.get('topic', '')
            })
            
        curr_unique_skills = list(curr_skills_map.keys())
        
        # We only need the model if there are unmatched skills
        curr_embeddings = None
        
        for _, ind_row in demand_df.iterrows():
            ind_skill = ind_row['skill_normalized']
            if pd.isna(ind_skill):
                continue
                
            job_count = ind_row.get('job_count', 0)
            demand_pct = ind_row.get('demand_percentage', 0.0)
            
            # 1. Exact Match
            if ind_skill in curr_skills_map:
                # Get the first college/course for simplicity or join them
                colleges = ", ".join(list(set(x['college'] for x in curr_skills_map[ind_skill])))
                courses = ", ".join(list(set(x['course'] for x in curr_skills_map[ind_skill])))
                
                results.append({
                    'industry_skill': ind_skill,
                    'job_count': job_count,
                    'demand_percentage': demand_pct,
                    'gap_status': 'present',
                    'matched_curriculum_skill': ind_skill,
                    'colleges': colleges,
                    'courses': courses
                })
                continue
                
            # 2. Semantic Match
            if curr_embeddings is None and curr_unique_skills:
                self._load_model()
                curr_embeddings = self.model.encode(curr_unique_skills, convert_to_tensor=True)
                
            if curr_unique_skills and self.model is not None:
                ind_emb = self.model.encode([ind_skill], convert_to_tensor=True)
                cos_scores = util.cos_sim(ind_emb, curr_embeddings)[0]
                best_idx = torch.argmax(cos_scores).item()
                best_score = cos_scores[best_idx].item()
                
                if best_score >= self.semantic_threshold:
                    best_match = curr_unique_skills[best_idx]
                    colleges = ", ".join(list(set(x['college'] for x in curr_skills_map[best_match])))
                    courses = ", ".join(list(set(x['course'] for x in curr_skills_map[best_match])))
                    
                    results.append({
                        'industry_skill': ind_skill,
                        'job_count': job_count,
                        'demand_percentage': demand_pct,
                        'gap_status': 'partial/semantic_match',
                        'matched_curriculum_skill': best_match,
                        'colleges': colleges,
                        'courses': courses
                    })
                    continue
                    
            # 3. Missing / Unmatched
            # A skill is a confirmed_gap if it has significant demand (e.g. >= 0.5% or job_count >= 50)
            if demand_pct >= 0.5 or job_count >= 50:
                gap_status = 'confirmed_gap'
            else:
                gap_status = 'unmatched'

            results.append({
                'industry_skill': ind_skill,
                'job_count': job_count,
                'demand_percentage': demand_pct,
                'gap_status': gap_status,
                'matched_curriculum_skill': None,
                'colleges': None,
                'courses': None
            })
            
        df = pd.DataFrame(results)
        # Ensure None values stay as None and don't become NaN (which breaks tests)
        df = df.replace({np.nan: None})
        return df
