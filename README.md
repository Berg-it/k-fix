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

## 🧠 Workflow Détaillé du Moteur IA

### 📥 Phase 1 : Réception & Enrichissement

#### 1.1 Réception Webhook Datadog
```python
# Payload Datadog brut reçu via /datadog-webhook
{
  "alert_id": "12345",
  "monitor_id": "67890",
  "event_type": "triggered",
  "title": "High CPU usage on pod xyz",
  "message": "CPU > 80% for 5 minutes",
  "tags": ["env:prod", "service:api", "namespace:backend"]
}
```

#### 1.2 Enrichissement Multi-Source
```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Datadog API   │    │ Kubernetes API  │    │  Vector DB      │
│                 │    │                 │    │                 │
│ • Monitor info  │    │ • Pod status    │    │ • Incidents     │
│ • Logs récents  │    │ • Deployment    │    │   similaires    │
│ • Métriques     │    │ • Events        │    │ • Solutions     │
│ • Historique    │    │ • Resources     │    │   passées       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │    context_bundle       │
                    │                         │
                    │ {                       │
                    │   "alert": {...},       │
                    │   "monitor": {...},     │
                    │   "k8s_context": {...}, │
                    │   "logs": [...],        │
                    │   "metrics": {...},     │
                    │   "similar_incidents": [│
                    │     {...}               │
                    │   ]                     │
                    │ }                       │
                    └─────────────────────────┘
```

### 🤖 Phase 2 : Raisonnement IA

#### 2.1 Recherche d'Incidents Similaires (PRIORITÉ)
```python
# Étape 1: Créer embedding du context_bundle actuel
current_embedding = create_embedding(context_bundle)

# Étape 2: Rechercher dans Vector DB
similar_incidents = vector_db.search(
    embedding=current_embedding,
    limit=3,
    threshold=0.8  # Similarité minimum
)

# Étape 3: Enrichir le contexte avec l'historique
enriched_context = {
    **context_bundle,
    "similar_incidents": similar_incidents,
    "lessons_learned": extract_lessons(similar_incidents),
    "successful_patterns": get_successful_solutions(similar_incidents),
    "failed_patterns": get_failed_solutions(similar_incidents)
}
```

```text
Vector Search Process:
1. Convertir context_bundle en embedding
2. Rechercher dans Vector DB (similarité cosinus > 0.8)
3. Récupérer top 3 incidents similaires
4. Extraire patterns de succès/échec
5. Enrichir le contexte pour l'IA
```

#### 2.2 Analyse Contextuelle (LLM avec Historique)
```text
Prompt Engineering Structure:

SYSTEM: Tu es un expert DevOps Kubernetes. Analyse ce context_bundle enrichi et propose des solutions optimisées.

CONTEXT ACTUEL: 
- Alert: {alert_details}
- K8s State: {k8s_context}
- Recent Logs: {logs_summary}

CONTEXTE HISTORIQUE:
- Similar Past Incidents: {similar_incidents}
- Solutions qui ont FONCTIONNÉ: {successful_patterns}
- Solutions qui ont ÉCHOUÉ: {failed_patterns}
- Leçons apprises: {lessons_learned}

RULES:
- Jamais d'auto-merge en production
- Dry-run obligatoire
- Respecter les quotas namespace
- Proposer 2-3 alternatives
- Justifier chaque action
- PRIORITÉ aux solutions ayant déjà réussi
- ÉVITER les solutions ayant échoué

TASK: En tenant compte de l'historique, génère un plan d'action optimisé avec justification basée sur l'expérience passée.
```

#### 2.3 Moteur de Règles (Safety Layer)
```python
class SafetyRules:
    def validate_action(self, action_plan, environment, historical_context):
        checks = [
            self.check_environment_policy(environment),
            self.check_resource_quotas(action_plan),
            self.check_scaling_limits(action_plan),
            self.check_dry_run_feasibility(action_plan),
            self.check_historical_failures(action_plan, historical_context)
        ]
        return all(checks)
    
    def check_environment_policy(self, env):
        if env == "production":
            return False  # Jamais d'auto-merge en prod
        return True
    
    def check_historical_failures(self, action_plan, historical_context):
        # Vérifier si cette solution a déjà échoué dans le passé
        failed_patterns = historical_context.get('failed_patterns', [])
        for failed_pattern in failed_patterns:
            if self.is_similar_solution(action_plan, failed_pattern):
                return False
        return True
```

#### 2.3 Analyse Contextuelle (LLM)
```text
Prompt Engineering Structure:

SYSTEM: Tu es un expert DevOps Kubernetes. Analyse ce context_bundle et propose des solutions.

CONTEXT: 
- Alert: {alert_details}
- K8s State: {k8s_context}
- Recent Logs: {logs_summary}
- Similar Past Incidents: {vector_search_results}

RULES:
- Jamais d'auto-merge en production
- Dry-run obligatoire
- Respecter les quotas namespace
- Proposer 2-3 alternatives
- Justifier chaque action

TASK: Génère un plan d'action structuré avec justification.
```

#### 2.2 Moteur de Règles (Safety Layer)
```python
class SafetyRules:
    def validate_action(self, action_plan, environment):
        checks = [
            self.check_environment_policy(environment),
            self.check_resource_quotas(action_plan),
            self.check_scaling_limits(action_plan),
            self.check_dry_run_feasibility(action_plan)
        ]
        return all(checks)
    
    def check_environment_policy(self, env):
        if env == "production":
            return False  # Jamais d'auto-merge en prod
        return True
```

#### 2.3 Recherche d'Incidents Similaires
```text
Vector Search Process:
1. Convertir context_bundle en embedding
2. Rechercher dans Vector DB (similarité cosinus)
3. Récupérer top 3 incidents similaires
4. Analyser succès/échecs des solutions passées
5. Adapter la stratégie en conséquence
```

### ⚙️ Phase 3 : Génération de Solutions

#### 3.1 Plans d'Action Candidats
```json
{
  "incident_id": "inc_2024_001",
  "analysis": {
    "root_cause": "CPU throttling due to insufficient requests/limits",
    "severity": "high",
    "affected_services": ["api-backend"],
    "estimated_impact": "Response time +200ms"
  },
  "action_plans": [
    {
      "plan_id": "plan_1",
      "title": "Augmenter les ressources CPU",
      "priority": 1,
      "confidence": 0.85,
      "justification": "Logs montrent CPU throttling constant depuis 10min",
      "kubernetes_changes": [
        {
          "resource": "deployment/api-backend",
          "action": "patch",
          "changes": {
            "spec.template.spec.containers[0].resources.requests.cpu": "500m",
            "spec.template.spec.containers[0].resources.limits.cpu": "1000m"
          }
        }
      ],
      "rollback_plan": "Revenir aux valeurs précédentes si CPU usage > 90%",
      "estimated_time": "2-3 minutes",
      "risks": ["Augmentation coût", "Possible sur-provisioning"]
    },
    {
      "plan_id": "plan_2", 
      "title": "Activer HPA (Horizontal Pod Autoscaler)",
      "priority": 2,
      "confidence": 0.70,
      "justification": "Alternative scaling automatique",
      "kubernetes_changes": [...],
      "rollback_plan": "Désactiver HPA et revenir au scaling manuel"
    }
  ]
}
```

#### 3.2 Validation Safety Layer
```text
Safety Checks Pipeline:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Dry-Run Test   │    │  Quota Check    │    │ Policy Engine   │
│                 │    │                 │    │                 │
│ kubectl apply   │    │ CPU/Memory      │    │ Environment     │
│ --dry-run=server│ -> │ limits respect  │ -> │ rules (prod/    │
│                 │    │                 │    │ staging/dev)    │
│ ✅ Valid YAML   │    │ ✅ Under quota  │    │ ✅ Authorized   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 🔄 Phase 4 : Exécution & Collaboration

#### 4.1 Création Merge Request GitLab
```python
class GitLabIntegration:
    def create_mr(self, action_plan):
        mr_content = {
            "title": f"🤖 K-Fix: {action_plan['title']}",
            "description": self.generate_mr_description(action_plan),
            "source_branch": f"kfix/incident-{action_plan['incident_id']}",
            "target_branch": "main",
            "labels": ["k-fix", "automated", action_plan['severity']],
            "assignee": self.get_team_lead(action_plan['namespace'])
        }
        return self.gitlab_api.create_merge_request(mr_content)
```

#### 4.2 Notification Slack Structurée
```json
{
  "blocks": [
    {
      "type": "header",
      "text": "🚨 K-Fix: Incident Détecté & Solution Proposée"
    },
    {
      "type": "section",
      "fields": [
        {"type": "mrkdwn", "text": "*Incident:* High CPU usage"},
        {"type": "mrkdwn", "text": "*Service:* api-backend"},
        {"type": "mrkdwn", "text": "*Environnement:* production"},
        {"type": "mrkdwn", "text": "*Sévérité:* High"}
      ]
    },
    {
      "type": "section",
      "text": "*🔍 Diagnostic:* CPU throttling détecté. Requests/limits insuffisants."
    },
    {
      "type": "section",
      "text": "*💡 Solution Proposée:* Augmenter CPU requests à 500m, limits à 1000m"
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": "📋 Voir MR GitLab",
          "url": "https://gitlab.com/project/merge_requests/123"
        },
        {
          "type": "button", 
          "text": "📊 Diagnostic JSON",
          "url": "https://k-fix.internal/incidents/inc_2024_001"
        }
      ]
    }
  ]
}
```

### 📚 Phase 5 : Apprentissage & Feedback

#### 5.1 Stockage Vector DB
```python
class LearningEngine:
    def store_incident(self, context_bundle, action_plan, outcome):
        # Créer embedding du contexte
        embedding = self.create_embedding(context_bundle)
        
        # Stocker dans Vector DB
        incident_record = {
            "embedding": embedding,
            "context": context_bundle,
            "solution": action_plan,
            "outcome": outcome,  # success/failure/partial
            "feedback": None,    # À remplir par l'équipe
            "timestamp": datetime.now()
        }
        
        self.vector_db.store(incident_record)
```

#### 5.2 Boucle de Feedback
```text
Feedback Loop:
1. MR mergée/rejetée → outcome capturé
2. Monitoring post-déploiement (15min)
3. Métriques collectées (CPU, erreurs, latence)
4. Équipe peut ajouter feedback manuel
5. Mise à jour Vector DB avec résultat
6. Amélioration prompts LLM pour cas similaires
```

### 🎯 Résultat Final

#### Output JSON Complet
```json
{
  "incident_id": "inc_2024_001",
  "timestamp": "2024-01-15T10:30:00Z",
  "status": "solution_proposed",
  "context_bundle": { /* contexte enrichi */ },
  "ai_analysis": { /* diagnostic IA */ },
  "recommended_action": { /* plan choisi */ },
  "alternative_actions": [ /* autres options */ ],
  "safety_checks": { /* validations passées */ },
  "gitlab_mr": {
    "url": "https://gitlab.com/project/merge_requests/123",
    "branch": "kfix/incident-inc_2024_001"
  },
  "slack_notification": {
    "channel": "#devops-alerts",
    "message_ts": "1705312200.123456"
  },
  "learning": {
    "similar_incidents_found": 2,
    "confidence_score": 0.85,
    "vector_db_stored": true
  }
}
```

---

## ✅ Roadmap de Développement

### Phase 1 — Fondations
- [X] Créer API FastAPI `/datadog-webhook`.
- [X] Parser payload Datadog → `enriched_alert` (namespace, pod, deployment, metric, value, threshold).
- [X] Charger secrets via `.env` (local) ou k8s Secrets.
- [X] Logs structurés (JSON).

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

## 🧭 Principes de Conception

- **Pas d’automatisme aveugle** : K-Fix ne pousse jamais un correctif sans justification claire.
- **Contexte d’abord** : chaque proposition s’appuie sur les métriques, logs et état du cluster.
- **Explicabilité** : toutes les actions candidates sont accompagnées de leur justification et d’alternatives.
- **Sécurité** : dry-run obligatoire, politiques de quotas respectées, jamais d’auto-merge en production.
- **Évolutivité** : l’agent apprend de chaque incident et enrichit sa mémoire (Vector DB + feedback).
- **Collaboration** : les humains restent dans la boucle, K-Fix propose mais ne décide pas seul.

---

## 📌 Notes

- ⚠️ **Production** : MR jamais auto-mergée.  
- ✅ **Staging/Dev** : auto-merge possible.  
- 🔄 Apprentissage continu via Vector DB.  
- 🧠 **LLM seul** = Intelligence générale  
- 🎯 **LLM + Vector DB** = Intelligence spécialisée sur VOTRE infrastructure  

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





1. Réception & Enrichissement multi-source
	•	Recevoir le webhook natif Datadog (alerte brute).
	•	Appeler API Datadog → récupérer monitor_details (tags, query, seuils, groupes).
	•	Appeler API Kubernetes → récupérer pod, deployment, namespace, events.
	•	Optionnel : récupérer logs et métriques supplémentaires.
👉 Objectif : reconstituer un context_bundle complet sans dépendre du JSON custom.

2. Normalisation du contexte
	•	Transformer le context_bundle dans une forme stable :

{
  "alert": {...},
  "monitor": {...},
  "k8s_context": {...},
  "logs": [...],
  "metrics": {...}
}

	•	Peu importe si l’alerte est CPU, OOM ou CrashLoopBackOff → la structure reste la même.
👉 Objectif : rendre les données exploitables pour le moteur de raisonnement.


