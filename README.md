# TOTEM Scraper

# How to run it

1. Make sure you have a Chrome Browser installed on your computer
2. Create a TOTEM account at [https://www.totem-building.be](https://www.totem-building.be)
3. With your account credentials, create a `.env` file in the root directory as follows:

```
TOTEM_USERNAME="maxmustermann@ethz.ch"
TOTEM_PASSWORD="12345678"
```

3. Create a Python virtual environment by running `python -m venv venv`
4. Activate this environment by running:

- On macOS/Linux: `source venv/bin/activate`
- On Windows: `venv\Scripts\activate`

5. Install all Python requirements by running `pip install -r requirements.txt`
6. Run the scraper `python scrape.py`
