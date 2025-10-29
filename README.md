### RecycloAI
 RecycloAI

## Overview:
RecycloAI is an interactive application that integrates a smart recycling assistant, combining an Image Classification Machine Learning model with local guidelines and context for users to quickly find out the recyclability of an object at hand. Along with this, there is the ability to track your progress and look/filter through charities that are aligned with our mission.

- HTML, CSS, JavaScript, and Python used
- /data is where all the training data lives, python scripts in /src were used to fetch and put the data in the correct folder. A training script is included in /src and the best model was saved as a best_efficientnet_model.pth
- /static holds all css and js files, along with a json with all of the charities and their info. It includes the html templates as well, listed under /templates.
- Other miscellaneous python files are used for integrating local guidelines and login information
- recycloai.db holds all the relevant user information
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
```

## Quickstart

### Run the Web App
```bash
python app.py
# open http://localhost:5000
```
