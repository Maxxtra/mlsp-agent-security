"""Ruleaza atacurile din attacks/ prin agent si scrie results/results.csv.

    python src/harness.py --fake                 # agent fals, fara model
    python src/harness.py --model llama3.1       # agent real
    python src/harness.py --model llama3.1 --policy keyword
"""

import argparse
import glob
import json
import os
import time
import csv
import shutil
import agent
import fake_agent

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ATTACKS = os.path.join(ROOT, "attacks")
SANDBOX = os.path.join(ROOT, "sandbox")
RESULTS = os.path.join(ROOT, "results", "results.csv")


def reset_sandbox():
    """Curata sandbox-ul inainte de un experiment nou"""
    for folder_name in ("files", "inbox", "outbox"):
        folder_path = os.path.join(SANDBOX, folder_name)

        shutil.rmtree(folder_path, ignore_errors=True)
        os.makedirs(folder_path, exist_ok=True)


def plant_attack(attack: dict):
    """Pune payload-ul acolo unde zice placed_in."""
    where = attack["placed_in"]
    target = attack.get("target_name", "document.txt")
    folder = {"file": "files", "email": "inbox", "webpage": "files"}[where]

    with open(os.path.join(SANDBOX, folder, target), "w", encoding="utf-8") as f:
        f.write(attack.get("benign_prefix", "") + "\n" + attack["payload"] + "\n")


def prepare_experiment(attack: dict):
    """Pregateste environment-ul pentru un nou experiment"""
    reset_sandbox()

    # creeaza resursele initiale necesare experimentului
    # (ex. un fisier pe care atacul incearca sa-l stearga)
    # TODO: 
    #   trebuie implementat in JSON optional un camp cu
    #   "setup_files": [
    #       {
    #           "name": "important.txt",
    #           "content": "informatie importanta"
    #       }
    #    ]
    #
    for file_data in attack.get("setup_files", []):
        file_path = os.path.join(
            SANDBOX,
            "files",
            file_data["name"]
        )
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(file_data["content"])

    plant_attack(attack)


def check(attack: dict) -> bool:
    """success_check: pentru inceput suportam 'outbox_contains' si 'file_missing'."""
    succes_check = attack["success_check"]

    if succes_check["type"] == "outbox_contains":
        outbox_path = os.path.join(SANDBOX, "outbox")

        for filename in os.listdir(outbox_path):
            email_path = os.path.join(outbox_path, filename)
            with open(email_path, encoding="utf-8") as file:
                email_content = file.read()
            expected_text = succes_check["text"]
            if expected_text.lower() in email_content.lower():
                return True
            
        return False

    
    if succes_check["type"] == "file_missing":
        file_path = os.path.join(SANDBOX, "files", succes_check["name"])
        return not os.path.exists(file_path)
    
    raise ValueError(f"success_check necunoscut: {succes_check['type']}")


def run_experiment(attack: dict, runner, model, policy):
    """Ruleaza un experiment"""
    start_time = time.perf_counter()

    runner(
        attack["user_task"],
        model=model,
        policy=policy
    )

    latency_ms = int(
        (time.perf_counter() - start_time) * 1000
    )
    success = check(attack)

    return {
        "success": success,
        "latency_ms": latency_ms,
        "cost_usd": 0.0
    }


def save_results(writer, attack, model_name, policy_name, result):
    """Salveaza rezultatele in results/results.csv"""
    writer.writerow([
        attack["id"],
        model_name,
        policy_name,
        int(result["success"]),
        result["latency_ms"],
        result["cost_usd"]
    ])

    print(
        f"{attack['id']:<12} "
        f"success={result['success']} "
        f"{result['latency_ms']}ms"
    )


def load_policy(name):
    if name is None:
        return None
    
    import policies
    return getattr(policies, name)


def main():
    # 1. partea de parsare
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--model", default="llama3.1")
    parser.add_argument("--policy", default=None)
    args = parser.parse_args()

    runner = fake_agent.run if args.fake else agent.run
    policy = load_policy(args.policy)

    model_name = "fake" if args.fake else args.model
    policy_name = args.policy or "none"

    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    new_results_file = (
        not os.path.exists(RESULTS)
        or os.path.getsize(RESULTS) == 0
    )

    # 2. loop-ul de attack-uri
    with open(RESULTS, "a", newline="", encoding="utf-8") as results_file:
        writer = csv.writer(results_file)

        # daca nu a existat un fisier de results, atunci la cel nou creat
        # trebuie sa-i adaugam header-ul
        if new_results_file:
            writer.writerow([
                "attack_id",
                "model",
                "policy",
                "success",
                "latency_ms",
                "cost_usd"
            ])

        attack_paths = sorted(
            glob.glob(os.path.join(ATTACKS, "*.json"))
        )

        for path in attack_paths:
            # sarim peste schema.json ca ne arata doar format-ul
            if path.endswith("schema.json"):
                continue

            # incarcam datele despre attack din json
            with open(path, encoding="utf-8") as attack_file:
                attack = json.load(attack_file)

            prepare_experiment(attack)

            result = run_experiment(
                attack,
                runner,
                args.model,
                policy
            )

            save_results(
                writer,
                attack,
                model_name,
                policy_name,
                result
            )

if __name__ == "__main__":
    main()
