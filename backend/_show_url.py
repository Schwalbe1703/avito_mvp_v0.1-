from configparser import ConfigParser
p = ConfigParser()
p.read("alembic.ini", encoding="utf-8")
url = p.get("alembic", "sqlalchemy.url")
print("URL repr:", repr(url))
