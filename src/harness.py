"""Ruleaza experimentele din attacks/ prin agent si scrie rezultatele.

Exemple:
    python src/harness.py --model llama3.1
    python src/harness.py --model llama3.1 --policy keyword

    # Ruleaza scenariile fara plantarea atacurilor
    python src/harness.py --model llama3.1 --benign
"""

import argparse
import csv
import json
import os
import shutil
import time

import yaml

import agent

# PATHS
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

ATTACKS = os.path.join(ROOT, "attacks")
SANDBOX = os.path.join(ROOT, "sandbox")
SANDBOX_TEMPLATE = os.path.join(ROOT, "sandbox_template")
RESULTS_DIR = os.path.join(ROOT, "results")
RUNS = os.path.join(ROOT, "runs")


# PRETURI
# Incarcate o singura data, la import. Daca fisierul lipseste, costul ramane 0
# si se afiseaza un avertisment - nu vrem sa cada tot batch-ul pentru asta.
PRICING_PATH = os.path.join(ROOT, "config", "pricing.yaml")
try:
    with open(PRICING_PATH, encoding="utf-8") as _f:
        PRICING = yaml.safe_load(_f) or {}
except FileNotFoundError:
    print(f"Atentie: {PRICING_PATH} lipseste, cost_usd va fi 0.")
    PRICING = {}


def read_trace_stats(trace_path: str) -> dict:
    """Citeste trace-ul unei rulari si aduna ce nu se poate masura din afara.

    `latency_ms` masurat de harness e timpul total: gandirea modelului + uneltele
    + filtrul, la gramada. Ca sa putem spune "politica X adauga Y ms per apel",
    avem nevoie de defalcare, iar ea exista doar in trace.
    """
    stats = {
        "prompt_tokens": 0,
        "output_tokens": 0,
        "model_ms": 0,
        "policy_ms": 0,
        "steps_used": 0,
        "end_reason": "",
    }

    try:
        with open(trace_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("event")
                if event_type == "model_call":
                    stats["model_ms"] += event.get("duration_ms", 0)
                elif event_type == "tool_call":
                    stats["policy_ms"] += event.get("policy_ms", 0)
                elif event_type == "run_end":
                    # run_end poarta totalurile deja insumate de agent.
                    stats["prompt_tokens"] = event.get("total_prompt_tokens", 0)
                    stats["output_tokens"] = event.get("total_output_tokens", 0)
                    stats["steps_used"] = event.get("steps_used", 0)
                    stats["end_reason"] = event.get("reason", "")
    except FileNotFoundError:
        pass

    return stats


def compute_cost(model: str, prompt_tokens: int, output_tokens: int) -> float:
    """Cost in USD, din tokeni si preturile din config/pricing.yaml."""
    prices = PRICING.get(model) or PRICING.get("default") or {}
    cost = (
        prompt_tokens * prices.get("input", 0.0)
        + output_tokens * prices.get("output", 0.0)
    ) / 1000000
    return round(cost, 6)


# SANDBOX
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


# RUN ARTIFACTS
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


# SUCCESS CHECKS
def check(success_check: dict) -> bool:
    """Verifica daca obiectivul experimentului a fost indeplinit."""

    check_type = success_check["type"]

    # Verifica daca un email trimis contine textul cerut.
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

    # Verifica daca un fisier nu mai exista.
    if check_type == "file_missing":
        file_path = os.path.join(
            SANDBOX,
            success_check["name"]
        )

        return not os.path.exists(file_path)

    # Verifica daca un fisier contine textul cerut.
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


# EXPERIMENT
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

    # Trace-ul e citit ACUM, inainte ca save_run_artifacts sa-l copieze si
    # inainte ca urmatorul experiment sa-l stearga prin reset_agent_trace().
    stats = read_trace_stats(agent.LOG)

    return {
        "success": success,
        "latency_ms": latency_ms,
        "cost_usd": compute_cost(
            model,
            stats["prompt_tokens"],
            stats["output_tokens"]
        ),
        "response": response,
        **stats
    }


# RESULTS CSV
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
        result["cost_usd"],
        result.get("prompt_tokens", 0),
        result.get("output_tokens", 0),
        result.get("model_ms", 0),
        result.get("policy_ms", 0),
        result.get("steps_used", 0),
        result.get("end_reason", "")
    ])

    print(
        f"{attack['id']:<8} "
        f"{experiment_type:<8} "
        f"success={result['success']} "
        f"{result['latency_ms']}ms "
        f"pasi={result.get('steps_used', 0)} "
        f"({result.get('end_reason', '')})"
    )


# POLICY
def load_policy(name):
    """Incarca functia de policy din policies.py."""

    if name is None:
        return None

    import policies

    return getattr(
        policies,
        name
    )


# MAIN
def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        default="llama3.1"
    )

    parser.add_argument(
        "--policy",
        default=None,
        help="Una sau mai multe politici, separate prin virgula (ex: keyword sau "
             "none,keyword,allowlist). 'none' inseamna fara filtru - linia de baza. "
             "Toate ajung in acelasi CSV, ca sa poata fi comparate direct."
    )

    parser.add_argument(
        "--benign",
        action="store_true",
        help="Ruleaza toate scenariile fara plantarea payload-ului."
    )

    parser.add_argument(
        "--attack",
        default=None,
        help="Ruleaza doar scenariile date, separate prin virgula (ex: A003 sau A001,A003). "
             "Util la depanare: o rulare completa dureaza zeci de minute."
    )

    args = parser.parse_args()

#   --policy keyword         -> o trecere, cu filtrul keyword
#   --policy none,keyword    -> doua treceri: fara filtru, apoi cu keyword
#   fara --policy            -> o trecere, fara filtru
    if args.policy:
        policy_names = [p.strip() for p in args.policy.split(",")]
    else:
        policy_names = ["none"]

    # Incarcam toate politicile ACUM, inainte de orice rulare.
    # Altfel un nume gresit s-ar descoperi dupa 30 de minute, la a doua trecere.
    policies_to_run = []
    for name in policy_names:
        if name == "none":
            policies_to_run.append(("none", None))
        else:
            policies_to_run.append((name, load_policy(name)))

    model_name = args.model

    # Stabilim tipul experimentului.
    #
    # Fara --benign:
    #     attack
    #
    # Cu --benign:
    #     benign

    if args.benign:
        experiment_type = "benign"
        attack_enabled = False
    else:
        experiment_type = "attack"
        attack_enabled = True

    # Fiecare rulare primeste propriul fisier CSV.
    #
    # Exemple:
    #   results/run_attack_20260914_120501.csv
    #   results/run_benign_20260914_121023.csv
    #
    # results/results.csv ramane liber pentru rularea finala.

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    timestamp = time.strftime(
        "%Y%m%d_%H%M%S"
    )

    results_path = os.path.join(
        RESULTS_DIR,
        f"run_{experiment_type}_{timestamp}.csv"
    )

    # Fiecare rulare are un fisier nou,
    # deci il deschidem cu "w", nu cu "a".
    with open(
        results_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as results_file:

        writer = csv.writer(
            results_file
        )

        writer.writerow([
            "attack_id",
            "experiment_type",
            "model",
            "policy",
            "success",
            "latency_ms",
            "cost_usd",
            # Coloanele de mai jos vin din trace, nu se pot masura din afara.
            "prompt_tokens",
            "output_tokens",
            "model_ms",
            "policy_ms",
            "steps_used",
            "end_reason"
        ])

        # Gasim toate scenariile din attacks/.
        # Ignoram schema.json.
        attack_paths = sorted([
            os.path.join(
                ATTACKS,
                filename
            )
            for filename in os.listdir(ATTACKS)
            if (
                filename.endswith(".json")
                and filename != "schema.json"
            )
        ])

        # --attack A003  sau  --attack A001,A003
        if args.attack:
            requested = {x.strip().upper() for x in args.attack.split(",")}
            attack_paths = [
                p for p in attack_paths
                if os.path.basename(p).removesuffix(".json").upper() in requested
            ]
            if not attack_paths:
                print(f"Niciun scenariu care sa se potriveasca cu: {args.attack}")
                return

        # Bucla exterioara: politicile. Bucla interioara: scenariile.
        # Ordinea conteaza: pentru fiecare politica parcurgem toate scenariile,
        # ca rezultatele unei politici sa fie grupate in CSV.
        for policy_name, policy in policies_to_run:

            print(f"\n########## POLITICA: {policy_name} ##########")

            # Ruleaza fiecare scenariu.
            for path in attack_paths:

                with open(
                    path,
                    encoding="utf-8"
                ) as attack_file:
                    attack = json.load(
                        attack_file
                    )

                print(
                    f"\n=== "
                    f"{attack['id']} "
                    f"{experiment_type.upper()} "
                    f"==="
                )

                # Pregateste sandbox-ul.
                #
                # attack:
                #     reset + used_files + payload
                #
                # benign:
                #     reset + used_files
                #     FARA payload
                prepare_experiment(
                    attack,
                    attack_enabled=attack_enabled
                )

                # Pregateste folderul runs/.
                run_directory = prepare_run_directory(
                    attack["id"],
                    experiment_type
                )

                # Trace-ul trebuie sa contina doar experimentul curent.
                reset_agent_trace()
            
                # Alegem success_check-ul potrivit.
                #
                # benign:
                #     verificam benign_success_check
                #
                # attack:
                #     verificam attack_success_check
                if args.benign:
                    success_check = attack[
                        "benign_success_check"
                    ]
                else:
                    success_check = attack[
                        "attack_success_check"
                    ]

                # Ruleaza agentul.
                #
                # Daca un singur scenariu crapa (model cazut, success_check cu tip
                # necunoscut, fisier lipsa), nu vrem sa pierdem si restul batch-ului:
                # o trecere completa dureaza zeci de minute. Notam esecul ca
                # success=0 si continuam.
                try:
                    result = run_experiment(
                        attack,
                        success_check,
                        args.model,
                        policy
                    )
                except Exception as e:
                    print(f"    EROARE la {attack['id']}: {type(e).__name__}: {e}")
                    # Aceleasi chei ca run_experiment, ca CSV-ul sa aiba
                    # coloanele completate. end_reason marcheaza clar ca rularea
                    # a cazut in harness, nu ca agentul a raspuns.
                    result = {
                        "success": False,
                        "latency_ms": 0,
                        "cost_usd": 0.0,
                        "response": f"(eroare: {type(e).__name__}: {e})",
                        "prompt_tokens": 0,
                        "output_tokens": 0,
                        "model_ms": 0,
                        "policy_ms": 0,
                        "steps_used": 0,
                        "end_reason": "harness_error",
                    }

                # Salveaza trace + raspuns final.
                save_run_artifacts(
                    run_directory,
                    result["response"]
                )

                # Salveaza rezultatul in CSV.
                save_results(
                    writer,
                    attack,
                    experiment_type,
                    model_name,
                    policy_name,
                    result
                )

                # Scriem rezultatul imediat pe disk.
                # Util daca o rulare ulterioara crapa.
                results_file.flush()

    print(
        f"\nResults saved to: {results_path}"
    )


if __name__ == "__main__":
    main()