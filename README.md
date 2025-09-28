# 🤖 K-Fix — Intelligent Kubernetes Fix Agent

K-Fix est un agent IA intelligent qui reçoit les alertes Datadog et propose des **correctifs Kubernetes automatisés** (via MR GitLab), avec raisonnement contextuel et apprentissage continu.

---

## 🎯 Objectif

- Réceptionner les alertes Datadog (CPU, mémoire, erreurs fréquentes).
- Enrichir avec contexte (logs, métriques, infos k8s).
- Raisonner avec un moteur IA (LLM + règles).
- Générer plusieurs plans de correction (patchs Kubernetes).
- Proposer une Merge Request GitLab justifiée.
- Apprendre des incidents passés (Vector DB + feedback).

---

## 🚀 Workflow Intelligent

```text
[1] Datadog → webhook
[2] K-Fix reçoit et enrichit alerte
[3] Récupère contexte (metrics, logs, kube API)
[4] Decision Engine (LLM + règles)
[5] Génère actions candidates (patch YAML)
[6] Safety Layer (dry-run, quotas)
[7] Crée MR GitLab + notif Slack/Teams
[8] Feedback (BDD relationnelle + Vector DB)
```

---

## ✅ Roadmap de Développement

### ✅ Phase 1 — Fondations (TERMINÉE)
- [x] Créer API FastAPI `/datadog-webhook`.
- [x] Parser payload Datadog → `enriched_alert` (namespace, pod, deployment, metric, value, threshold).
- [x] Charger secrets via `.env` (local) ou k8s Secrets.
- [x] Logs structurés (JSON).

### Phase 2 — Contexte & Enrichissement
- [ ] Connecter API Kubernetes (pod, deployment, quotas, HPA).
- [ ] Récupérer logs récents via Datadog Logs API.
- [ ] Ajouter métriques mémoire + erreurs applicatives.
- [ ] Construire `context_bundle` complet.

### Phase 3 — Mémoire & Apprentissage
- [ ] Intégrer Vector DB (Weaviate, Pinecone, Qdrant…).
- [ ] Stocker incidents + actions proposées + résultat.
- [ ] Activer recherche incidents similaires.
- [ ] Créer embeddings du `context_bundle`.

### Phase 4 — Decision Engine
- [ ] Intégrer un LLM (Claude, GPT, Mistral).
- [ ] Écrire prompts structurés pour raisonnement.
- [ ] Ajouter règles (policy engine) :
  - jamais auto-merge en prod,
  - dry-run obligatoire,
  - seuil max scaling.

### Phase 5 — Actions Candidates
- [ ] Générateur de correctifs Kubernetes (YAML templates).
- [ ] Proposer plusieurs plans d’action adaptés au type d’alerte reçu.
- [ ] Chaque plan doit inclure :
  - Justification (logs + métriques + contexte)
  - Alternatives possibles
  - Plan de rollback
- [ ] L’agent doit rester extensible : intégrer de nouveaux scénarios en fonction
      des incidents passés (apprentissage via Vector DB + feedback humain).

### Phase 6 — Safety Layer
- [ ] Implémenter `kubectl apply --dry-run=server`.
- [ ] Vérifier quotas namespace.
- [ ] Vérifier cohérence `request ≤ limit`.
- [ ] Rejeter plan si check échoue.

### Phase 7 — MR & Collaboration
- [ ] Intégrer GitLab API → création MR.
- [ ] MR contient patch, justification, alternatives, rollback plan.
- [ ] Notifier Slack/Teams avec résumé clair.
- [ ] Ajouter labels/tags (env, team).

### Phase 8 — Feedback & Learning
- [ ] Relier MR ↔ Incident en BDD relationnelle.
- [ ] Suivre statut MR (merged, closed, rejected).
- [ ] Stocker résultat dans Vector DB.
- [ ] Adapter prompts LLM en fonction du feedback.

---

## 📌 Notes

- ⚠️ **Production** : MR jamais auto-mergée.  
- ✅ **Staging/Dev** : auto-merge possible.  
- 🔄 Apprentissage continu via Vector DB.  

---

## 🗂 Structure prévue

```
kfix/
 ├── main.py          # API FastAPI (webhook Datadog)
 ├── context/         # modules de récupération contexte
 ├── decision/        # moteur de raisonnement (LLM + règles)
 ├── actions/         # générateur de patchs Kubernetes
 ├── safety/          # validations dry-run, quotas
 ├── gitlab/          # interaction GitLab (MR)
 ├── memory/          # Vector DB + BDD relationnelle
 └── tests/           # tests unitaires & intégration
```

---

## 🛠 Tech Stack

- **FastAPI** → serveur API.  
- **Python** → langage principal.  
- **Datadog API** → alertes + logs/metrics.  
- **Kubernetes Python client** → état cluster.  
- **GitLab API** → MR.  
- **Vector DB** → mémoire (Weaviate, Pinecone, Qdrant).  
- **Postgres** → base relationnelle incidents ↔ MR.  
- **LLM** → raisonnement (Claude, GPT, Mistral).  

---
