### RecycloAI
 RecycloAI

## Overview:
RecycloAI is an interactive application that integrates a smart recycling assistant, combining an Image Classification Machine Learning model with local guidelines and context for users to quickly find out the recyclability of an object at hand. Along with this, there is the ability to track your progress and look/filter through charities that are aligned with our mission.

---

## Objectives:
- Determine output class of an object at hand
- Combine with local guidelines + context given to reach a final recyclability consensus
- Give a tip relating to that object
- Update progress bars + logs
- Let users filter through charities across the globe to find collaboration

---

## Installation
**Python 3.10+** recommended.

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Additional packages used by the code but not listed in requirements.txt:
pip install flask datasets
```

## Quickstart

### Run the Web App
```bash
python app.py
# open http://localhost:5000
```
