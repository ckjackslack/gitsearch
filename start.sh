# python3 -m venv .venv
# source .venv/bin/activate
# pip install -r requirements.txt
# pip freeze > requirements.txt
CWD=`realpath .`
SRC_DIR=${CWD}/src
export PYTHONPATH=$PYTHONPATH:$SRC_DIR
PYTHONDONTWRITEBYTECODE=1 gunicorn src.main:app --reload