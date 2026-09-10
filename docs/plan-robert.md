# Vlad, planul tău până pe 27 septembrie

Securitatea agenților. Lista de mai jos e a ta: o iei de sus în jos, fiecare pas are termenul lui, care e întâlnirea la
care vreau să-l văd făcut. Primul pas e gândit să-l termini singur, fără să aștepți după nimeni.

> **Contractul comun pentru echipa de agenți.** Ca Șerban, Vlad și Mihai să poată lucra separat
> până vineri și să se potrivească luni, fixăm de acum două formate. Un atac e un JSON cu câmpurile:
> `id`, `goal` (exfiltrare / actiune\_neautorizata / distrugere),
> `technique` (direct / roleplay / encoded / hidden\_markup), `placed_in`
> (file / email / webpage), `payload` (textul), `success_check` (ce verificăm în
> sandbox). Un rezultat e o linie de CSV: `attack_id, model, policy, success, latency_ms, cost_usd`.
> Cine respectă formatele nu are de ce să aștepte după ceilalți.

*Securitatea agenților · suita de atacuri · repo: [github.com/Maxxtra/mlsp-agent-security](https://github.com/Maxxtra/mlsp-agent-security)*

1. **până vineri 11** Citești două lucrări, doar ca să vezi cum arată un atac indirect real:
   [AgentDojo](https://arxiv.org/abs/2406.13352) (secțiunea cu atacurile)
   și [InjecAgent](https://arxiv.org/abs/2403.02691). Ca inspirație
   pentru texte ai și [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections).
   Apoi scrii primele 10 atacuri în formatul JSON de mai sus: text ascuns într-un fișier, un email
   sau o pagină, care îi spune agentului să facă altceva decât a cerut utilizatorul. Nu ai nevoie de
   agentul lui Șerban ca să le scrii; le testezi luni.
2. **până luni 14** Ajungi la 30, pe grila goal × technique din contract, cu minimum 2 atacuri
   pe fiecare celulă. Le comiți în repo ca `attacks/*.json`.
3. **până joi 17** Ajungi la 100+. Pentru fiecare, `success_check` trebuie să fie
   concret: emailul chiar a apărut în outbox, fișierul chiar a dispărut din sandbox. Rulezi tot setul
   prin harness-ul lui Mihai și te uiți care atacuri nu se verifică corect.
4. **până duminică 20** Două seturi în plus: 20 de atacuri reformulate (același scop, alte
   cuvinte) și o categorie întreagă ținută deoparte, pe care Mihai n-o vede până la final, pentru
   testul de generalizare.
5. **20 - 25 sep** Scrii secțiunea cu taxonomia și suita de atacuri.

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
