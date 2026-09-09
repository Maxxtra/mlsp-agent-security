# Șerban, planul tău până pe 27 septembrie

Securitatea agenților. Lista de mai jos e a ta: o iei de sus în jos, fiecare pas are termenul lui, care e întâlnirea la
care vreau să-l văd făcut. Primul pas e gândit să-l termini singur, fără să aștepți după nimeni.

> **Contractul comun pentru echipa de agenți.** Ca Șerban, Vlad și Mihai să poată lucra separat
> până vineri și să se potrivească luni, fixăm de acum două formate. Un atac e un JSON cu câmpurile:
> `id`, `goal` (exfiltrare / actiune\_neautorizata / distrugere),
> `technique` (direct / roleplay / encoded / hidden\_markup), `placed_in`
> (file / email / webpage), `payload` (textul), `success_check` (ce verificăm în
> sandbox). Un rezultat e o linie de CSV: `attack_id, model, policy, success, latency_ms, cost_usd`.
> Cine respectă formatele nu are de ce să aștepte după ceilalți.

*Securitatea agenților · agentul și uneltele · repo: [github.com/Maxxtra/mlsp-agent-security](https://github.com/Maxxtra/mlsp-agent-security)*

1. **până vineri 11** Construiești scheletul agentului: un LLM cu tool calling care primește
   o sarcină, alege o unealtă, o apelează, citește rezultatul și continuă. Ca să nu depinzi de nimeni,
   pornești local cu Ollama și un Llama mic
   ([ollama.com](https://ollama.com), apoi `ollama run llama3.1`);
   cheia pentru modelele plătite e pinned în canalul echipei, o folosești de luni. Documentația de
   tool calling: [Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/tool-use),
   [OpenAI](https://platform.openai.com/docs/guides/function-calling),
   [Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md).
   O singură unealtă la început, filesystem-ul, într-un folder sandbox. Loghezi fiecare apel într-un
   JSONL: unealta, argumentele, răspunsul. Test de vineri: agentul primește „citește raport.txt și
   spune-mi câte rânduri are" și o face singur.
2. **până luni 14** Adaugi restul uneltelor, toate simulate, nimic real: browser (citește pagini
   HTML dintr-un folder local), email (inbox din fișiere, „trimite" înseamnă scrie într-un outbox),
   calculator, terminal (doar comenzi dintr-o listă permisă, într-un container Docker). Regula:
   agentul nu atinge nimic din afara sandbox-ului, oricât l-ar păcăli un atac.
3. **până luni 14** Scrii 25 de sarcini normale („citește raportul X și rezumă-l", „trimite lui Y
   emailul cu Z", „calculează totalul din fișier") și pentru fiecare un verificator automat care spune
   reușit sau nu. Astea sunt măsura de utilitate. De luni, Mihai le rulează prin harness-ul lui.
4. **până joi 17** Rulezi cele 25 de sarcini cu filtrul lui Mihai pornit, pe fiecare politică,
   și numeri câte mai reușesc. Diferența față de fără filtru e utilitatea pierdută.
5. **până duminică 20** Măsori latența și costul pe apel, cu și fără filtru, pe fiecare politică.
   Livrezi tabelul: politică × (utilitate, latență, cost).
6. **20 - 25 sep** Scrii secțiunea despre agent, sandbox și suita de sarcini normale.

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
