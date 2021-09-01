# Citrend
 The software for grading SMEs customers by transaction

![](https://img.shields.io/badge/dependencies-Python%203.8--3.9-blue)
![](https://img.shields.io/badge/dependencies-Django%203.2-green)

## Install

The `token/` folder is hidden, because it includes passwords and keys. 
These files should be in this folder:
- `django_secret_key` It contains a string encrypting sessions and cookies, 
  and can be generated in [Djecrety](https://djecrety.ir/).
- `smtp.json` Write your SMTP config like the following. This email address 
  belongs to the website maintainer, and is used to send registration 
  confirming email to users and donation reminder to anyone (receivers in 
 `django database -> payment -> Website Manager` table).
    ```json
    {
  "host": "smtp.example.com",
  "port": 465,
  "username": "sender@example.com",
  "password": "any"
    }
    ```
- `payment_methods/` This folder has been added to static file list. Write 
  your bank account (image, QR code) in blank HTML page, then save 
  the page into this folder. In `djngo database -> payment -> Paying
  Method` table, `/static/` address is equal to path of this folder. If using
  direct link like `paypal.me`, just write the link in above table. 

`${...}` contains variables that you need to replace according to your 
environment.

```bash
cd ${project_base_folder}
pip install -r requirements  # Note [1]
python manage.py migrate
python manage.py createsuperuser
# follow the instructions in command lines
python manage.py runserver
```

**Notes**:

[1] The provided `requirements` is generated from a developing Anaconda.
It is not a minimal requirement because I remove some functions during 
programming, and the dependent packages cannot be removed clearly.
