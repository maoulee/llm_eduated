# test_reward_function.py

import re
import string
from typing import List, Dict, Tuple
import logging

# ==============================================================================
# --- Section 1: All Necessary Functions & Classes ---
# (从你的 plugin.py 中完整复制过来)
# ==============================================================================

# --- 1.1 Helper Functions ---

def normalize(s: str) -> str:
    """[V2 Updated] 更加保守和安全的 normalize 函数，专为 KGQA 优化。"""
    if not isinstance(s, str): s = str(s)
    s = s.lower()
    safe_chars = string.ascii_lowercase + string.digits + " .-'&"
    s = "".join(char for char in s if char in safe_chars)
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())

def get_evidence_triplets_from_messages(messages: list) -> Tuple[str, set]:
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            user_content = msg.get('content', '')
            triplets_match = re.search(r"Triplets:\n(.*?)\n\nQuestion:", user_content, re.DOTALL)
            if triplets_match:
                triplets_text = triplets_match.group(1).strip()
                evidence_triplets_raw = re.findall(r"\(([^,]+),([^,]+),([^)]+)\)", triplets_text)
                evidence_set = {
                    normalize(f"({h.strip()},{r.strip()},{t.strip()})") for h, r, t in evidence_triplets_raw
                }
                return triplets_text, evidence_set
    return "", set()

def extract_answers_from_completion(completion: str) -> List[str]:
    """[V4 Updated] 更鲁棒的答案提取函数。"""
    matches = re.findall(r"<answer[^>]*>(.*?)</answer>", completion, re.DOTALL)
    answers = sorted(list(set(match.strip() for match in matches if match.strip())))
    return answers

def calculate_f1(predictions: List[str], ground_truths: List[str]) -> float:
    predictions_set = set(map(normalize, predictions))
    ground_truths_set = set(map(normalize, ground_truths))
    if not ground_truths_set: return 1.0 if not predictions_set else 0.0
    if not predictions_set: return 0.0
    true_positives = len(predictions_set.intersection(ground_truths_set))
    precision = true_positives / len(predictions_set)
    recall = true_positives / len(ground_truths_set)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return f1

def extract_paths_as_triplets(completion: str) -> List[tuple]:
    """[V4 Final] 极度鲁棒的路径提取函数。"""
    paths_blocks = re.findall(r"<paths>(.*?)</paths>", completion, re.DOTALL)
    path_singles = re.findall(r"<path>(.*?)</path>", completion, re.DOTALL)
    mixed_paths = re.findall(r"<path>(.*?)</paths>", completion, re.DOTALL)
    all_paths_text = "\n".join(paths_blocks + path_singles + mixed_paths)
    if not all_paths_text.strip(): return []
    all_triplets = []
    for line in all_paths_text.split('\n'):
        line = line.strip()
        if not line: continue
        try:
            entities = [e.strip() for e in re.findall(r"\(([^)]+)\)", line)]
            relations = [r.strip() for r in re.findall(r"--\[([^]]+)\]-->", line)]
            if len(entities) >= 2 and len(entities) == len(relations) + 1:
                for i in range(len(relations)):
                    h, r, t = entities[i], relations[i], entities[i+1]
                    if h and r and t: all_triplets.append((h, r, t))
        except Exception: continue
    return all_triplets

# --- 1.2 Reward Class (包含了我们最终的修复方案) ---

class KGQAReward:
    def __init__(self,
                 hallucination_penalty_factor: float = 0.8,
                 format_penalty_value: float = 0.1,
                 repetition_penalty_value: float = 0.05):
        self.hallucination_penalty_factor = hallucination_penalty_factor
        self.format_penalty_value = format_penalty_value
        self.repetition_penalty_value = repetition_penalty_value
        self.repetition_n_grams = 4
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        logging.info("KGQAReward initialized for testing.")

    def __call__(self, completions: List[str], **kwargs) -> List[float]:
        ground_truths = kwargs.get('ground_truth')
        messages_list = kwargs.get('messages')
        final_rewards = []
        for i, completion in enumerate(completions):
            gt_list = ground_truths[i]
            messages = messages_list[i]
            
            logging.info("\n" + "="*50 + f"\n[TESTING SAMPLE {i+1}]")
            
            triplets_text, evidence_set = get_evidence_triplets_from_messages(messages)
            predicted_answers = extract_answers_from_completion(completion)
            predicted_path_triplets = extract_paths_as_triplets(completion)

            logging.info(f"Predicted Answers: {predicted_answers}")
            logging.info(f"Predicted Path Triplets: {predicted_path_triplets}")

            evidence_entities = set()
            evidence_relations = set()
            evidence_triplets_raw = re.findall(r"\(([^,]+),([^,]+),([^)]+)\)", triplets_text)
            for h, r, t in evidence_triplets_raw:
                evidence_entities.add(normalize(h.strip()))
                evidence_entities.add(normalize(t.strip()))
                evidence_relations.add(normalize(r.strip()))

            base_reward = calculate_f1(predicted_answers, gt_list)
            logging.info(f"Step 1: Base F1 Score = {base_reward:.4f}")
            current_reward = base_reward
            
            # --- 2. 优先级 2: 幻觉惩罚 (回归严格验证) ---
            if predicted_path_triplets:
                grounded_steps = 0
                for h, r, t in predicted_path_triplets:
                    # 只使用严格标准 (Strict Match)
                    is_grounded = normalize(f"({h},{r},{t})") in evidence_set
                    
                    if is_grounded:
                        grounded_steps += 1
                        logging.info(f"  - Path step '({h},{r},{t})' is GROUNDED (Strict).")
                    else:
                        logging.info(f"  - Path step '({h},{r},{t})' is a HALLUCINATION (Strict).")

                hallucination_ratio = (len(predicted_path_triplets) - grounded_steps) / len(predicted_path_triplets)
                logging.info(f"Step 2: Hallucination Ratio = {hallucination_ratio:.4f}")
                
                reward_multiplier = (1.0 - self.hallucination_penalty_factor * hallucination_ratio)
                current_reward *= reward_multiplier
                logging.info(f"  - Reward after hallucination penalty: {base_reward:.4f} * {reward_multiplier:.4f} = {current_reward:.4f}")

            has_path_tags = "<path>" in completion or "<paths>" in completion
            
            if not predicted_answers:
                # ... 拒答逻辑 ...
                current_reward -= self.format_penalty_value
                logging.info(f"Step 3a: No answers found. Penalty applied. Current reward: {current_reward:.4f}")
            
            if not has_path_tags:
                current_reward -= self.format_penalty_value * 2
                logging.info(f"Step 3b: No path tags found. Heavy penalty applied. Current reward: {current_reward:.4f}")
            elif has_path_tags and not predicted_path_triplets:
                current_reward -= self.format_penalty_value
                logging.info(f"Step 3c: Path tags found but parsing failed. Penalty applied. Current reward: {current_reward:.4f}")

            words = completion.split()
            n = self.repetition_n_grams
            if len(words) >= n:
                ngrams = [" ".join(words[j:j+n]) for j in range(len(words) - n + 1)]
                if len(ngrams) > 0:
                    repetition_ratio = 1.0 - (len(set(ngrams)) / len(ngrams))
                    if repetition_ratio > 0.4:
                        current_reward -= self.repetition_penalty_value
                        logging.info(f"Step 3d: High repetition detected. Penalty applied. Current reward: {current_reward:.4f}")

            final_reward = max(-1.0, min(1.0, current_reward))
            logging.info(f"Step 4: Final Clipped Reward = {final_reward:.4f}")
            final_rewards.append(final_reward)
        return final_rewards

# ==============================================================================
# --- Section 2: Unit Test Execution ---
# ==============================================================================

if __name__ == "__main__":
    # --- 1. 定义测试数据 (样本2) ---
    
    # 模型的输出
    test_completion = """To find where Kaká lives, we need to find the specific location he resides in. From the triplets, we can directly infer two locations related to Kaká: 
- He was born in Gama, Federal District
- He has lived in Brasília

Since the user asked "where does Kaká live," we should provide both confirmed locations from the triplets. Therefore, the formatted logic paths are:
<paths>(Kaká) --[people.person.place_of_birth]--> (Gama, Federal District)</paths>
<paths>(Kaká) --[people.person.places_lived]--> (Brasília)</paths>

This means the formatted answers should be:
<response>
<answer>Gama, Federal District</answer>
<answer>Brasília</answer>
</response>"""

    # 对应的 messages 输入
    test_messages = [
        {"role": "system", "content": "You are an expert..."},
        {"role": "user", "content": """Triplets:
(Bosco Izecson Pereira Leite,people.person.children,Kaká)
(Bosco Izecson Pereira Leite,people.person.nationality,Brazil)
(Brasília,base.biblioness.bibs_location.city,Federal District)
(Brasília,base.biblioness.bibs_location.country,Brazil)
(Brasília,location.administrative_division.second_level_division_of,Brazil)
(Brasília,location.location.containedby,Brazil)
(Brasília,location.location.containedby,Federal District)
(Brazil national football team,base.x2010fifaworldcupsouthafrica.world_cup_squad.current_world_cup_squad,m.07m4b74)
(Brazil national football team,soccer.football_team.player_statistics,m.0w9k00d)
(Brazil national football team,sports.sports_team.location,Brazil)
(Brazil national football team,sports.sports_team.roster,m.0j_zz0c)
(Brazil,base.aareas.schema.administrative_area.administrative_children,Federal District)
(Brazil,location.country.administrative_divisions,Federal District)
(Brazil,location.country.capital,Brasília)
(Brazil,location.country.first_level_divisions,Federal District)
(Brazil,sports.sports_team_location.teams,Brazil national football team)
(Caroline Celico,people.person.nationality,Brazil)
(Caroline Celico,people.person.place_of_birth,São Paulo)
(Caroline Celico,people.person.spouse_s,m.0j863cg)
(Digão,people.person.nationality,Brazil)
(Federal District,base.biblioness.bibs_location.country,Brazil)
(Federal District,location.administrative_division.country,Brazil)
(Federal District,location.administrative_division.first_level_division_of,Brazil)
(Federal District,location.br_state.capital,Brasília)
(Federal District,location.location.containedby,Brazil)
(Federal District,location.location.contains,Brasília)
(Federal District,location.location.contains,Gama, Federal District)
(Gama, Federal District,location.administrative_division.second_level_division_of,Brazil)
(Gama, Federal District,location.location.containedby,Brazil)
(Gama, Federal District,location.location.containedby,Federal District)
(Gama, Federal District,location.location.people_born_here,Kaká)
(Gisele,people.person.nationality,Brazil)
(Isabella Celico Leite,people.person.parents,Kaká)
(KAKA,internet.blog.blogger,Kaká)
(Kaká,base.schemastaging.athlete_extra.salary,m.0lfvmwb)
(Kaká,base.schemastaging.athlete_extra.salary,m.0vxytw3)
(Kaká,base.schemastaging.athlete_extra.salary,m.0wy91xj)
(Kaká,base.x2010fifaworldcupsouthafrica.world_cup_participant.world_cup_team,m.07m4b74)
(Kaká,freebase.valuenotation.has_value,Education)
(Kaká,people.person.children,Isabella Celico Leite)
(Kaká,people.person.children,Luca Celico Leite)
(Kaká,people.person.ethnicity,White Latin American)
(Kaká,people.person.nationality,Brazil)
(Kaká,people.person.parents,Bosco Izecson Pereira Leite)
(Kaká,people.person.parents,Simone dos Santos)
(Kaká,people.person.place_of_birth,Gama, Federal District)
(Kaká,people.person.places_lived,m.03pfffm)
(Kaká,people.person.places_lived,m.0wlw7_3)
(Kaká,people.person.sibling_s,m.0k0jvs5)
(Kaká,people.person.spouse_s,m.0j863cg)
(Kaká,soccer.football_player.disciplinary_action,m.0g5h32z)
(Kaká,soccer.football_player.disciplinary_action,m.0g5h33d)
(Kaká,soccer.football_player.disciplinary_action,m.0g5mjkl)
(Kaká,soccer.football_player.matches_played,m.0c1d42w)
(Kaká,soccer.football_player.matches_played,m.0g5mh98)
(Kaká,soccer.football_player.matches_played,m.0g5npm_)
(Kaká,soccer.football_player.matches_played,m.0g9m42s)
(Kaká,soccer.football_player.matches_played,m.0gd32wm)
(Kaká,soccer.football_player.statistics,m.0w9bflc)
(Kaká,soccer.football_player.statistics,m.0w9j___)
(Kaká,soccer.football_player.statistics,m.0w9k00d)
(Kaká,sports.pro_athlete.teams,m.0113vws3)
(Kaká,sports.pro_athlete.teams,m.0113vxqx)
(Kaká,sports.pro_athlete.teams,m.04m2jtj)
(Kaká,sports.pro_athlete.teams,m.0hpjdcy)
(Kaká,sports.pro_athlete.teams,m.0j_zym6)
(Kaká,sports.pro_athlete.teams,m.0j_zz0c)
(Kaká,sports.pro_athlete.teams,m.0wy8n5m)
(Luca Celico Leite,people.person.parents,Kaká)
(Simone dos Santos,people.person.children,Kaká)
(Simone dos Santos,people.person.nationality,Brazil)
(São Paulo,location.administrative_division.second_level_division_of,Brazil)
(São Paulo,location.location.containedby,Brazil)
(São Paulo,sports.sports_team_location.teams,São Paulo FC)
(White Latin American,people.ethnicity.people,Kaká)
(m.0113vws3,sports.sports_team_roster.player,Kaká)
(m.03pfffm,people.place_lived.location,Brasília)
(m.03pfffm,people.place_lived.person,Kaká)
(m.04m2jtj,sports.sports_team_roster.team,A.C. Milan)
(m.07m4b74,base.x2010fifaworldcupsouthafrica.current_world_cup_squad.current_club,Real Madrid C.F.)
(m.07m4b74,base.x2010fifaworldcupsouthafrica.current_world_cup_squad.national_team,Brazil national football team)
(m.07m4b74,base.x2010fifaworldcupsouthafrica.current_world_cup_squad.players,Kaká)
(m.0c1d42w,soccer.football_player_match_participation.team,Brazil national football team)
(m.0g5mh98,soccer.football_player_match_participation.team,Brazil national football team)
(m.0g5npm_,soccer.football_player_match_participation.team,Brazil national football team)
(m.0g9m42s,soccer.football_player_match_participation.team,Brazil national football team)
(m.0gd32wm,soccer.football_player_match_participation.team,Brazil national football team)
(m.0hpjdcy,sports.sports_team_roster.team,Real Madrid C.F.)
(m.0j863cg,people.marriage.location_of_ceremony,São Paulo)
(m.0j863cg,people.marriage.spouse,Caroline Celico)
(m.0j863cg,people.marriage.spouse,Kaká)
(m.0j_zz0c,sports.sports_team_roster.player,Kaká)
(m.0j_zz0c,sports.sports_team_roster.team,Brazil national football team)
(m.0w9bflc,soccer.football_player_stats.team,Real Madrid C.F.)
(m.0w9j___,soccer.football_player_stats.player,Kaká)
(m.0w9k00d,soccer.football_player_stats.player,Kaká)
(m.0w9k00d,soccer.football_player_stats.team,Brazil national football team)
(m.0wlw7_3,people.place_lived.location,Gama, Federal District)
(m.0wlw7_3,people.place_lived.person,Kaká)
(m.0wy8n5m,sports.sports_team_roster.team,A.C. Milan)

Question:
where does kaka live"""}
    ]
    
    # 对应的 ground truth
    test_ground_truth = [["Brasília", "Gama, Federal District", "São Paulo"]]

    # --- 2. 初始化奖励模型 ---
    reward_model = KGQAReward()

    # --- 3. 运行评估 ---
    reward_model(
        completions=[test_completion],
        messages= [test_messages],
        ground_truth=test_ground_truth
    )