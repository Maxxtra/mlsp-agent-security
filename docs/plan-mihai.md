# Mihai, planul tău până pe 27 septembrie

Securitatea agenților. Lista de mai jos e a ta: o iei de sus în jos, fiecare pas are termenul lui, care e întâlnirea la
care vreau să-l văd făcut. Primul pas e gândit să-l termini singur, fără să aștepți după nimeni.

> **Contractul comun pentru echipa de agenți.** Ca Șerban, Robert și Mihai să poată lucra separat
> până vineri și să se potrivească luni, fixăm de acum două formate. Un atac e un JSON cu câmpurile:
> `id`, `goal` (exfiltrare / actiune\_neautorizata / distrugere),
> `technique` (direct / roleplay / encoded / hidden\_markup), `placed_in`
> (file / email / webpage), `payload` (textul), `success_check` (ce verificăm în
> sandbox). Un rezultat e o linie de CSV: `attack_id, model, policy, success, latency_ms, cost_usd`.
> Cine respectă formatele nu are de ce să aștepte după ceilalți.

*Securitatea agenților · apărarea și evaluarea · repo: [github.com/Maxxtra/mlsp-agent-security](https://github.com/Maxxtra/mlsp-agent-security)*

1. **până vineri 11** Scrii harness-ul de evaluare, dar ca să nu aștepți după Șerban și Robert
   îl testezi pe un agent fals: o funcție care primește sarcina și „apelează" mereu o unealtă, plus 3
   atacuri de probă scrise de tine în formatul JSON. Harness-ul ia atacul, îl plantează, rulează
   agentul, cheamă `success_check`, scrie linia de CSV. Vineri îl arăți rulând cap-coadă
   pe agentul fals; luni îl conectezi la agentul real. De citit:
   [ToolEmu](https://arxiv.org/abs/2309.15817) (cum evaluează ei) și
   [CaMeL](https://arxiv.org/abs/2503.18813) (ideea de apărare).
2. **până luni 14** Conectezi harness-ul la agentul lui Șerban și atacurile lui Robert, scoți
   prima rată de succes reală. Apoi prima politică, baseline-ul: filtru pe cuvinte-cheie și regex pe
   argumentele fiecărui apel (adrese de email necunoscute, comenzi de ștergere, URL-uri externe).
   Harness-ul calculează și fals-pozitivele pe sarcinile normale ale lui Șerban.
3. **până joi 17** A doua politică, judecătorul LLM: înainte de fiecare apel, un model separat
   primește trei lucruri (ce a cerut utilizatorul, ce vrea agentul acum, ce permisiuni are) și
   răspunde permite sau blochează, cu motiv. Rulezi rata de succes fără apărare pe 3 modele:
   Llama local prin Ollama, plus GPT și Claude cu cheile din canal.
4. **până duminică 20** A treia politică, allowlist de capabilități: agentul declară la început
   ce are voie și orice apel în afara listei e blocat. Rulezi tot: succes per politică, fals-pozitive,
   generalizarea pe categoria ascunsă a lui Robert, atacurile reformulate. Tabelul final cu cele cinci
   măsuri (succes, fals-pozitive, utilitate, latență, cost) iese de aici.
5. **20 - 25 sep** Scrii secțiunea despre filtru și politici, și secțiunea de rezultate.

## Întâlnirile

| Când | Ce vreau să văd |
|---|---|
| **Vineri 11 sep, 20:00** | Primul tău pas făcut și rulând. Trimitem abstractele. |
| **Luni 14 sep, seara** | Al doilea pas. De aici task-urile se leagă cu ale colegilor. |
| **Joi 17 sep, seara** | Grosul experimentelor. |
| **Duminică 20 sep** | Experimentele înghețate. Toate tabelele și figurile în repo. După ziua asta nu mai atingem experimentele. |
| **20 - 25 sep** | Scrii secțiunea ta în `paper/` din repo, ca markdown, direct din `results/`. Miercuri 24 ne vedem pe draft. |
| **25 - 27 sep** | Alex face polish și încarcă. |

## Când ai nevoie de mine

La întâlnirile de mai sus și atât. Dacă te blochezi între ele, scrii în canal unde te-ai oprit și treci la
următorul pas din listă; nu stai pe loc așteptând răspuns. Regula de „gata": un pas e gata când există un
script care îl rulează de la zero și un CSV sau o figură comisă în repo.

---
*Grup de cercetare MLSP · mentor: Alex Deonise · coordonator: Răzvan Rughiniș · RoEduNet 2026*
