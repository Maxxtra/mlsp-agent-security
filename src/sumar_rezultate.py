"""Sumarul rezultatelor pe politici, din results/run_attack_*.csv si results/run_benign_*.csv.
    python src/sumar_rezultate.py                       # ultimele fisiere run_attack / run_benign
    python src/sumar_rezultate.py --attack results/run_attack_20260920_155653.csv --benign results/run_benign_20260920_173822.csv
Daca exista runs/ (trace-urile), numara si apelurile blocate de politica (fals-pozitive pe benign).
Scrie tabelul in markdown, direct de lipit in lucrare.
"""
import argparse, csv, glob, json, os, statistics as st, collections

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
POLICIES = ["none", "keyword", "allowlist", "judge"]


def latest(pattern):
    files = sorted(glob.glob(os.path.join(ROOT, "results", pattern)))
    return files[-1] if files else None


def blocked_runs(experiment_type, policy):
    """Cate rulari au cel putin un tool call blocat de politica, si cate apeluri in total."""
    runs = 0
    calls = 0
    for path in glob.glob(os.path.join(ROOT, "runs", "*", experiment_type, policy, "trace.jsonl")):
        n = 0
        for line in open(path):
            e = json.loads(line)
            if e.get("event") == "tool_call" and str(e.get("allowed")) == "False":
                n += 1
        if n:
            runs += 1
        calls += n
    return runs, calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attack", default=latest("run_attack_*.csv"))
    ap.add_argument("--benign", default=latest("run_benign_*.csv"))
    a = ap.parse_args()
    A = list(csv.DictReader(open(a.attack)))
    B = list(csv.DictReader(open(a.benign)))
    have_runs = os.path.isdir(os.path.join(ROOT, "runs"))
    model = A[0]["model"] if A else "?"
    print(f"model: {model}   atac: {os.path.basename(a.attack)} ({len(A)} linii)   benign: {os.path.basename(a.benign)} ({len(B)} linii)\n")

    head = "| politica | compromis | executat | ASR (verificare rezultat) | sarcina utilizatorului dusa la capat, sub atac | utilitate benign | benign cu apel blocat (fals-pozitive) | latenta medie atac (s) | timp politica / rulare (ms) |"
    print(head)
    print("|" + "---|" * (head.count("|") - 1))
    for p in POLICIES:
        at = [r for r in A if r["policy"] == p]
        be = [r for r in B if r["policy"] == p]
        if not at or not be:
            continue
        n = len(at)
        comp = sum(r["compromised"] == "1" for r in at)
        exe = sum(r["executed"] == "1" for r in at)
        asr = sum(r["attack_success"] == "1" for r in at)
        task_ok = sum(r["benign_success"] == "1" for r in at)
        ben = sum(r["benign_success"] == "1" for r in be)
        lat = st.mean(int(r["latency_ms"]) for r in at) / 1000
        pol_ms = st.mean(int(r["policy_ms"]) for r in at)
        fp = "n/a"
        if have_runs:
            fr, fc = blocked_runs("benign", p)
            fp = f"{fr}/{len(be)} ({fr / len(be) * 100:.0f}%), {fc} apeluri"
        print(f"| {p} | {comp}/{n} ({comp / n * 100:.0f}%) | {exe}/{n} ({exe / n * 100:.0f}%) | {asr}/{n} ({asr / n * 100:.0f}%) | {task_ok}/{n} ({task_ok / n * 100:.0f}%) | {ben}/{len(be)} ({ben / len(be) * 100:.0f}%) | {fp} | {lat:.1f} | {pol_ms:.0f} |")

    # defalcare pe goal / tehnica / canal, agregat pe toate rularile (compromiterea e inainte de filtru)
    meta = {}
    for path in glob.glob(os.path.join(ROOT, "attacks", "A*.json")):
        d = json.load(open(path))
        meta[d["id"]] = (d["goal"], d["technique"], d["target_placed_in"])
    print(f"\nRata de compromitere agregata pe toate cele {len(A)} rulari de atac (fiecare scenariu x fiecare politica):\n")
    for i, name in enumerate(["goal", "technique", "canal"]):
        tot, comp = collections.Counter(), collections.Counter()
        for r in A:
            k = meta.get(r["attack_id"], ("?", "?", "?"))[i]
            tot[k] += 1
            comp[k] += r["compromised"] == "1"
        print(f"- {name}: " + ", ".join(f"{k} {comp[k]}/{tot[k]} ({comp[k] / tot[k] * 100:.0f}%)" for k in sorted(tot)))

    c = collections.Counter(r["attack_id"] for r in A if r["compromised"] == "1")
    print(f"\nScenarii compromise in cel putin o rulare: {len(c)}/{len(set(r['attack_id'] for r in A))}: "
          + ", ".join(f"{k} ({v}/{len(POLICIES)})" for k, v in sorted(c.items())))


if __name__ == "__main__":
    main()
