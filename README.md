# PyAppAPI

APIs extracted from Android APKs


### How to use it:

Create a virtual environment for the required python libraries,
and install the required libraries through pip:

```
virtualenv venv
source venv/bin/activate
pip install -r requirements.pip
```

Once you are finished, deactivate the virtualenv by simpy typing:
```
deactivate
```

Idealista
---------

```
python idealista/cmd.py

python idealista/cmd.py bbox <min_lat> <min_lon> <max_lat> <max_lon>
python idealista/cmd.py loc  <location_name>
```

Fotocasa
--------
```
python fotocasa/cmd.py

python fotocasa/cmd.py bbox <min_lat> <min_lon> <max_lat> <max_lon>
python fotocasa/cmd.py loc  <location_name>
```
