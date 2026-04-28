import os
import yaml


_DEFAULT = {
    "junior_faculty_hard_cap": 2.0,
    "senior_faculty_soft_cap": 2.0,
    "visiting_faculty_soft_cap": 2.5,
    "visiting_faculty_target_annual": 5.0,
    "lab_director_soft_cap": 1.67,
    "lab_director_target_annual": 3.33,
    "junior_new_lab_preps_per_year_max": 1,
    "new_prep_bonus_count": 2,
    "new_prep_weight": 2.0,
    "foundational_experienced_weight": 1.67,
    "extra_section_weight_multiplier": 0.5,
    "target_annual_load": 4.0,
    "objective_weights": {
        "section_coverage": 1000,
        "junior_new_preps": 100,
        "load_balance": 50,
        "senior_over_cap": 75,
        "sci10_flavor_diversity": 10,
        "senior_takes_new_preps": 25,
    },
}


def load_config(path: str = None) -> dict:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "data", "config.yaml")
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        cfg = dict(_DEFAULT)
        cfg.update({k: v for k, v in data.items() if k != "objective_weights"})
        if "objective_weights" in data:
            cfg["objective_weights"] = dict(_DEFAULT["objective_weights"])
            cfg["objective_weights"].update(data["objective_weights"])
        return cfg
    except FileNotFoundError:
        return dict(_DEFAULT)
