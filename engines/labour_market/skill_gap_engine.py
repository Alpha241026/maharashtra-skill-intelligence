import pandas as pd
import numpy as np
import torch
from pathlib import Path
from typing import Dict, Any, Union, Optional, List
from sentence_transformers import SentenceTransformer, util

from engines.labour_market.job_market_intelligence import JobMarketIntelligence

class SkillGapEngine:
    def __init__(self, semantic_threshold: float = 0.82):
        self.semantic_threshold = semantic_threshold
        self.model = None
        self.jmi = JobMarketIntelligence()
        
    def _load_model(self):
        if self.model is None:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def analyze(self, curriculum_data: Union[str, Path, pd.DataFrame], location: Optional[str] = None, domain: str = "IT") -> pd.DataFrame:
        if isinstance(curriculum_data, (str, Path)):
            curr_df = pd.read_csv(curriculum_data)
        else:
            curr_df = curriculum_data.copy()
            
        # Detect skill-like columns
        possible_cols = ['skill', 'skill_normalized', 'topic', 'technology', 'subject', 'module', 'learning_outcome', 'description', 'course']
        skill_col = None
        for col in possible_cols:
            if col in curr_df.columns or col.lower() in [c.lower() for c in curr_df.columns]:
                actual_col = [c for c in curr_df.columns if c.lower() == col.lower()][0]
                skill_col = actual_col
                break
                
        if not skill_col:
            raise ValueError(f"Could not automatically detect a curriculum skill column. Found: {list(curr_df.columns)}")

        # Extract unique curriculum skills
        curr_skills_raw = curr_df[skill_col].dropna().astype(str).unique().tolist()
        curr_skills_lower = [s.lower().strip() for s in curr_skills_raw]
        curr_skill_map = {s.lower().strip(): s for s in curr_skills_raw}
        
        # Get Industry Demand
        top_industry_skills = self.jmi.get_top_skills(location=location, domain=domain, top_n=200)
        
        if not top_industry_skills:
            # Insufficient data
            return pd.DataFrame([{
                'industry_skill': 'INSUFFICIENT_DATA',
                'job_count': 0,
                'demand_percentage': 0.0,
                'gap_status': 'INSUFFICIENT_DATA',
                'priority_score': 0.0,
                'matched_curriculum_skill': None
            }])
            
        results = []
        
        # Precompute embeddings if needed
        curr_embeddings = None
        
        for ind_sk in top_industry_skills:
            skill_name = ind_sk['skill']
            skill_lower = skill_name.lower().strip()
            job_count = ind_sk['job_count']
            demand_pct = ind_sk['demand_percentage']
            
            # Exact Match
            if skill_lower in curr_skills_lower:
                results.append({
                    'industry_skill': skill_name,
                    'job_count': job_count,
                    'demand_percentage': demand_pct,
                    'gap_status': 'COVERED',
                    'matched_curriculum_skill': curr_skill_map[skill_lower],
                    'similarity_score': 1.0,
                    'location': location or "Maharashtra",
                    'domain': domain
                })
                continue
                
            # Normalized match (substring / partial)
            matched = False
            for c_sk in curr_skills_lower:
                if skill_lower in c_sk or c_sk in skill_lower:
                    if len(skill_lower) > 2 and len(c_sk) > 2: # prevent 'c' matching 'c++'
                        results.append({
                            'industry_skill': skill_name,
                            'job_count': job_count,
                            'demand_percentage': demand_pct,
                            'gap_status': 'PARTIALLY_COVERED',
                            'matched_curriculum_skill': curr_skill_map[c_sk],
                            'similarity_score': 0.9,
                            'location': location or "Maharashtra",
                            'domain': domain
                        })
                        matched = True
                        break
            if matched:
                continue
                
            # Semantic Match
            if curr_embeddings is None and curr_skills_raw:
                self._load_model()
                curr_embeddings = self.model.encode(list(curr_skill_map.keys()), convert_to_tensor=True)
                
            if curr_skills_raw and self.model is not None:
                ind_emb = self.model.encode([skill_lower], convert_to_tensor=True)
                cos_scores = util.cos_sim(ind_emb, curr_embeddings)[0]
                best_idx = torch.argmax(cos_scores).item()
                best_score = cos_scores[best_idx].item()
                
                if best_score >= self.semantic_threshold:
                    best_match_lower = list(curr_skill_map.keys())[best_idx]
                    results.append({
                        'industry_skill': skill_name,
                        'job_count': job_count,
                        'demand_percentage': demand_pct,
                        'gap_status': 'PARTIALLY_COVERED',
                        'matched_curriculum_skill': curr_skill_map[best_match_lower],
                        'similarity_score': round(best_score, 3),
                        'location': location or "Maharashtra",
                        'domain': domain
                    })
                    continue
            
            # Gap
            results.append({
                'industry_skill': skill_name,
                'job_count': job_count,
                'demand_percentage': demand_pct,
                'gap_status': 'GAP',
                'matched_curriculum_skill': None,
                'similarity_score': 0.0,
                'location': location or "Maharashtra",
                'domain': domain
            })

        df = pd.DataFrame(results)
        
        # Priority Score = demand_percentage * (1 - similarity_score)
        if not df.empty and 'gap_status' in df.columns and df['gap_status'].iloc[0] != 'INSUFFICIENT_DATA':
            df['priority_score'] = df['demand_percentage'] * (1.0 - df['similarity_score'])
            df = df.sort_values('priority_score', ascending=False)
            
        # Handle NaN -> None
        df = df.replace({np.nan: None})
        return df

    def get_recommendations(self, gap_df: pd.DataFrame) -> pd.DataFrame:
        if gap_df.empty or ('gap_status' in gap_df.columns and gap_df['gap_status'].iloc[0] == 'INSUFFICIENT_DATA'):
            return pd.DataFrame()
            
        recs = []
        for _, row in gap_df.iterrows():
            st = row['gap_status']
            sk = row['industry_skill']
            dem = row['demand_percentage']
            pri = row['priority_score']
            
            if st == 'GAP' and pri > 1.0:
                recs.append({
                    'industry_skill': sk,
                    'gap_status': st,
                    'priority_score': pri,
                    'priority_level': 'High',
                    'recommendation': f"High demand ({dem:.1f}%) and completely missing. Consider adding '{sk}' to curriculum modules."
                })
            elif st == 'PARTIALLY_COVERED' and pri > 0.5:
                match = row['matched_curriculum_skill']
                recs.append({
                    'industry_skill': sk,
                    'gap_status': st,
                    'priority_score': pri,
                    'priority_level': 'Medium',
                    'recommendation': f"Moderate demand ({dem:.1f}%). Ensure '{match}' adequately covers industry expectations for '{sk}'."
                })
            elif st == 'COVERED':
                pass # No action needed
                
        rec_df = pd.DataFrame(recs)
        if not rec_df.empty:
            rec_df = rec_df.sort_values('priority_score', ascending=False)
        return rec_df
