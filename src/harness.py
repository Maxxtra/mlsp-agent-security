"""Ruleaza experimentele din attacks/ prin agent si scrie rezultatele.

Pentru moment ruleaza doar A001, pentru testarea pipeline-ului.

Exemplu:
    python src/harness.py --model llama3.1
    python src/harness.py --model llama3.1 --policy keyword
"""

import argparse
import csv
import json
import os
import shutil
import time

import agent


# ---------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

ATTACKS = os.path.join(ROOT, "attacks")
SANDBOX = os.path.join(ROOT, "sandbox")
SANDBOX_TEMPLATE = os.path.join(ROOT, "sandbox_template")
RESULTS = os.path.join(ROOT, "results", "results.csv")
RUNS = os.path.join(ROOT, "runs")


# ---------------------------------------------------------------------
# SANDBOX
# ---------------------------------------------------------------------

def reset_sandbox():
    """Recreeaza sandbox-ul gol pentru un experiment nou."""

    shutil.rmtree(SANDBOX, ignore_errors=True)

    for folder_name in ("files", "inbox", "outbox"):
        folder_path = os.path.join(SANDBOX, folder_name)
        os.makedirs(folder_path, exist_ok=True)


def copy_used_files(attack: dict):
    """Copiaza doar fisierele necesare experimentului."""

    for relative_path in attack.get("used_files", []):
        source_path = os.path.join(
            SANDBOX_TEMPLATE,
            relative_path
        )

        destination_path = os.path.join(
            SANDBOX,
            relative_path
        )

        if not os.path.isfile(source_path):
            raise FileNotFoundError(
                f"Fisierul din used_files nu exista: {relative_path}"
            )

        os.makedirs(
            os.path.dirname(destination_path),
            exist_ok=True
        )

        shutil.copy2(
            source_path,
            destination_path
        )


def plant_attack(attack: dict):
    """Adauga payload-ul in fisierul tinta al atacului."""

    target_path = os.path.join(
        SANDBOX,
        attack["target_name"]
    )

    if not os.path.isfile(target_path):
        raise FileNotFoundError(
            f"Target-ul atacului nu exista: {attack['target_name']}"
        )

    with open(
        target_path,
        "a",
        encoding="utf-8"
    ) as file:
        file.write(
            "\n" + attack["payload"] + "\n"
        )


def prepare_experiment(
    attack: dict,
    attack_enabled: bool
):
    """Pregateste sandbox-ul pentru un experiment nou."""

    reset_sandbox()

    copy_used_files(attack)

    if attack_enabled:
        plant_attack(attack)


# ---------------------------------------------------------------------
# RUN ARTIFACTS
# ---------------------------------------------------------------------

def prepare_run_directory(
    attack_id: str,
    experiment_type: str
) -> str:
    """
    Pregateste folderul in care salvam artifactele experimentului.

    Exemplu:
        runs/A001/benign/
        runs/A001/attack/
    """

    run_directory = os.path.join(
        RUNS,
        attack_id,
        experiment_type
    )

    # Daca am mai rulat acelasi experiment,
    # eliminam artifactele vechi.
    shutil.rmtree(
        run_directory,
        ignore_errors=True
    )

    os.makedirs(
        run_directory,
        exist_ok=True
    )

    return run_directory


def reset_agent_trace():
    """
    Sterge trace-ul temporar generat de agent.py,
    astfel incat fiecare experiment sa inceapa cu un trace gol.
    """

    if os.path.isfile(agent.LOG):
        os.remove(agent.LOG)


def save_run_artifacts(
    run_directory: str,
    response: str
):
    """
    Salveaza raspunsul final si trace-ul agentului
    pentru experimentul curent.
    """

    # Salveaza raspunsul final al agentului.
    final_answer_path = os.path.join(
        run_directory,
        "final_answer.txt"
    )

    with open(
        final_answer_path,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(response or "")

    # Copiaza trace-ul produs de agent.py.
    if os.path.isfile(agent.LOG):
        trace_path = os.path.join(
            run_directory,
            "trace.jsonl"
        )

        shutil.copy2(
            agent.LOG,
            trace_path
        )


# ---------------------------------------------------------------------
# SUCCESS CHECKS
# ---------------------------------------------------------------------

def check(success_check: dict) -> bool:
    """Verifica daca obiectivul experimentului a fost indeplinit."""

    check_type = success_check["type"]

    # -------------------------------------------------------------
    # Verifica daca un email trimis contine textul cerut.
    # -------------------------------------------------------------

    if check_type == "outbox_contains":
        outbox_path = os.path.join(
            SANDBOX,
            "outbox"
        )

        expected_text = success_check["text"]

        for filename in os.listdir(outbox_path):
            email_path = os.path.join(
                outbox_path,
                filename
            )

            if not os.path.isfile(email_path):
                continue

            with open(
                email_path,
                encoding="utf-8"
            ) as file:
                email_content = file.read()

            if (
                expected_text.lower()
                in email_content.lower()
            ):
                return True

        return False

    # -------------------------------------------------------------
    # Verifica daca un fisier nu mai exista.
    # -------------------------------------------------------------

    if check_type == "file_missing":
        file_path = os.path.join(
            SANDBOX,
            success_check["name"]
        )

        return not os.path.exists(file_path)

    # -------------------------------------------------------------
    # Verifica daca un fisier contine textul cerut.
    # -------------------------------------------------------------

    if check_type == "file_contains":
        file_path = os.path.join(
            SANDBOX,
            success_check["name"]
        )

        if not os.path.isfile(file_path):
            return False

        with open(
            file_path,
            encoding="utf-8"
        ) as file:
            file_content = file.read()

        expected_text = success_check["text"]

        return (
            expected_text.lower()
            in file_content.lower()
        )

    raise ValueError(
        f"success_check necunoscut: {check_type}"
    )


# ---------------------------------------------------------------------
# EXPERIMENT
# ---------------------------------------------------------------------

def run_experiment(
    attack: dict,
    success_check: dict,
    model,
    policy
):
    """Ruleaza agentul si verifica rezultatul experimentului."""

    start_time = time.perf_counter()

    response = agent.run(
        attack["user_task"],
        model=model,
        policy=policy
    )

    latency_ms = int(
        (time.perf_counter() - start_time) * 1000
    )

    success = check(success_check)

    return {
        "success": success,
        "latency_ms": latency_ms,
        "cost_usd": 0.0,
        "response": response
    }


# ---------------------------------------------------------------------
# RESULTS CSV
# ---------------------------------------------------------------------

def save_results(
    writer,
    attack,
    experiment_type,
    model_name,
    policy_name,
    result
):
    """Salveaza rezultatul experimentului in CSV."""

    writer.writerow([
        attack["id"],
        experiment_type,
        model_name,
        policy_name,
        int(result["success"]),
        result["latency_ms"],
        result["cost_usd"]
    ])

    print(
        f"{attack['id']:<8} "
        f"{experiment_type:<8} "
        f"success={result['success']} "
        f"{result['latency_ms']}ms"
    )


# ---------------------------------------------------------------------
# POLICY
# ---------------------------------------------------------------------

def load_policy(name):
    """Incarca functia de policy din policies.py."""

    if name is None:
        return None

    import policies

    return getattr(
        policies,
        name
    )


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        default="llama3.1"
    )

    parser.add_argument(
        "--policy",
        default=None
    )

    args = parser.parse_args()

    policy = load_policy(
        args.policy
    )

    model_name = args.model
    policy_name = args.policy or "none"

    # -------------------------------------------------------------
    # Pregateste results/results.csv
    # -------------------------------------------------------------

    os.makedirs(
        os.path.dirname(RESULTS),
        exist_ok=True
    )

    new_results_file = (
        not os.path.exists(RESULTS)
        or os.path.getsize(RESULTS) == 0
    )

    with open(
        RESULTS,
        "a",
        newline="",
        encoding="utf-8"
    ) as results_file:

        writer = csv.writer(
            results_file
        )

        if new_results_file:
            writer.writerow([
                "attack_id",
                "experiment_type",
                "model",
                "policy",
                "success",
                "latency_ms",
                "cost_usd"
            ])

        # ---------------------------------------------------------
        # MOMENTAN TESTAM DOAR A001.
        #
        # Mai tarziu vom inlocui asta cu toate fisierele JSON
        # din attacks/.
        # ---------------------------------------------------------

        attack_paths = [
            os.path.join(
                ATTACKS,
                "A001.json"
            )
        ]

        # ---------------------------------------------------------
        # Ruleaza fiecare attack JSON.
        # ---------------------------------------------------------

        for path in attack_paths:

            with open(
                path,
                encoding="utf-8"
            ) as attack_file:
                attack = json.load(
                    attack_file
                )

            # =====================================================
            # BENIGN EXPERIMENT
            # =====================================================

            prepare_experiment(
                attack,
                attack_enabled=False
            )

            benign_run_directory = prepare_run_directory(
                attack["id"],
                "benign"
            )

            # Trace-ul trebuie sa contina DOAR rularea benign.
            reset_agent_trace()

            benign_result = run_experiment(
                attack,
                attack["benign_success_check"],
                args.model,
                policy
            )

            save_run_artifacts(
                benign_run_directory,
                benign_result["response"]
            )

            save_results(
                writer,
                attack,
                "benign",
                model_name,
                policy_name,
                benign_result
            )

            # =====================================================
            # ATTACK EXPERIMENT
            # =====================================================

            prepare_experiment(
                attack,
                attack_enabled=True
            )

            attack_run_directory = prepare_run_directory(
                attack["id"],
                "attack"
            )
    
            # Trace-ul trebuie sa contina DOAR rularea attack.
            reset_agent_trace()

            attack_result = run_experiment(
                attack,
                attack["attack_success_check"],
                args.model,
                policy
            )

            save_run_artifacts(
                attack_run_directory,
                attack_result["response"]
            )

            save_results(
                writer,
                attack,
                "attack",
                model_name,
                policy_name,
                attack_result
            )


if __name__ == "__main__":
    main()