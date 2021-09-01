# shellcheck disable=SC2164
cd ~/citrend/
conda activate webapp
python manage.py makemigrations
python manage.py migrate
