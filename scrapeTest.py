try:
   from urllib2 import urlopen
except ImportError:
   from urllib.request import urlopen # py3k

from bs4 import BeautifulSoup # $ pip install beautifulsoup4

url = "http://www.hockey-reference.com/teams/VAN/2008_games.html"
soup = BeautifulSoup(urlopen(url), "html5lib")

tables = soup.find_all("table", class_="stats_table")
data = []

for t in tables:
   headings = [heading.text for heading in t.thead.find_all("th")]
   #for h in headings:
   #   print(h)

   rows = t.tbody.find_all("tr", class_="")
   for r in rows:
      data.append([item.text for item in r.find_all("td")])

for d in data:
   print(d)

