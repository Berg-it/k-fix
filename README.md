# 🚀 K-Fix — DevOps AI Agent (MVP)

**K-Fix** est un agent DevOps intelligent conçu pour :
- détecter automatiquement les erreurs fréquentes de Kubernetes,
- analyser et résumer les incidents,
- proposer un correctif sous forme de Merge Request (MR) GitLab,
- notifier l’équipe sur Slack/Teams,
- apprendre des incidents passés grâce à une base vectorielle.

---

## ✅ Roadmap MVP (Checklist)

### 1. Environnement
- [X Choisir Python comme langage principal
- [X] Créer un dépôt Git
- [X] Mettre en place un environnement virtuel (venv/poetry)
- [X] Préparer un `Dockerfile` de base

### 2. Réception des alertes
- [X] Mettre en place un petit serveur (FastAPI)
- [X] Créer un endpoint `/datadog-webhook`
- [X] Tester la réception d’alertes Datadog (payload JSON)

### 3. Connexion à Datadog
- [X] Configurer `datadog-api-client`
- [X] Récupérer les logs associés à une alerte
- [X] Récupérer les metrics associées

### 4. Stockage relationnel
- [ ] Installer une base SQL (Postgres conseillé)
- [ ] Créer une table `incidents` (id, service, résumé, statut, lien MR)
- [ ] Sauvegarder chaque alerte reçue

### 5. Résumé d’incident
- [ ] Implémenter un résumé simple par règles
- [ ] (Optionnel) Ajouter un LLM plus tard pour des résumés avancés

### 6. Mémoire vectorielle
- [ ] Choisir une Vector DB (FAISS ou PGVector)
- [ ] Générer un embedding pour chaque résumé
- [ ] Stocker embedding + métadonnées (incident_id, service)
- [ ] Rechercher des incidents similaires lors d’une nouvelle alerte

### 7. Création de MR GitLab
- [ ] Configurer `python-gitlab`
- [ ] Générer une branche et un patch simple (hardcodé pour MVP)
- [ ] Créer une MR automatiquement avec description

### 8. Notification équipe
- [ ] Configurer `slack_sdk` ou webhook Teams
- [ ] Envoyer résumé incident + lien MR dans le channel

### 9. Feedback et apprentissage
- [ ] Suivre le statut des MR (ouverte, mergée, rejetée)
- [ ] Mettre à jour la base SQL avec le feedback
- [ ] Enrichir la Vector DB avec les correctifs validés

---

## 🐳 Bugs Kubernetes gérés (MVP)

Dès le départ, **K-Fix** se concentre sur la **détection automatique des bugs connus et fréquents de Kubernetes**.  
L’objectif est de couvrir l’ensemble des erreurs courantes qui perturbent les workloads, par exemple :

- Pods en échec : `OOMKilled`, `CrashLoopBackOff`, `ImagePullBackOff`, `ErrImagePull`  
- Problèmes de scheduling : `Pod Pending` (pas de nœud disponible, quotas épuisés)  
- Problèmes de configuration : variables d’environnement manquantes, probes mal définies, volumes non montés  
- Erreurs de ressources : quotas CPU/mémoire dépassés, node pressure  
- Problèmes réseau fréquents : `Connection Refused`, `DNS lookup failed`  
- Et d’autres scénarios récurrents liés à Kubernetes en production  

👉 Le principe est simple :  
1. **Détection** via les logs/alertes Datadog.  
2. **Association** à une catégorie d’erreur connue.  
3. **Proposition** d’un correctif type (patch K8s/YAML).  
4. **Création d’une MR GitLab** pour validation par l’équipe.  

---

## 📌 Notes

- MVP = **un seul agent monolithique** qui gère toute la chaîne : Alerte → Résumé → MR → Notification.  
- Évolution prévue = séparation en plusieurs agents spécialisés (Logs, Infra, Diagnostic, GitOps, etc.).  
- La mémoire repose sur :  
  - une **base SQL** (historique exact des incidents et MR),  
  - une **Vector DB** (mémoire sémantique pour retrouver les cas similaires).



curl -X POST https://kfix.cloudcorner.org/datadog-webhook \
     -H "Content-Type: application/json" \
     -d '{"alert_type":"error","service":"checkout-service","message":"OOMKilled"}'

  