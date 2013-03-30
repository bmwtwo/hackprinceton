# all the imports
import sqlite3
import time
from datetime import datetime, date
from flask import Flask, request, session, g, redirect, url_for, \
      abort, render_template, flash
from contextlib import closing
from string import replace, split
from urllib2 import urlopen
from bs4 import BeautifulSoup # $ pip install beautifulsoup4

# configuration
DATABASE = '/tmp/hockey.db'
# TODO: consider removing debug mode
DEBUG = True
# TODO: consider changing this key
SECRET_KEY = 'my super awesome key'
USERNAME = 'admin'
PASSWORD = 'default'

# create application
app = Flask(__name__)
app.config.from_object(__name__)

def connect_db():
   return sqlite3.connect(app.config['DATABASE'])

def init_db():
   with closing(connect_db()) as db:
      with app.open_resource('schema.sql') as f:
         db.cursor().executescript(f.read())
      db.commit()

def query_db(query, args=(), one=False):
   with app.test_request_context():
      app.preprocess_request()
      cur = g.db.execute(query, args)
      rv = [dict((cur.description[idx][0], value)
                 for idx, value in enumerate(row)) for row in cur.fetchall()]
   return (rv[0] if rv else None) if one else rv

def clear_game_data():
   with app.test_request_context():
      app.preprocess_request()
      g.db.execute("delete from games")
      g.db.commit()

def scrape_seasons():
   #TODO: prevent double insert of games
   for year in (range(2012, 2005, -1) + range(2004, 1967, -1)):
      url = "http://www.hockeydb.com/ihdb/stats/league_results.php?lid=nhl1927&sid=" + str(year)
      soup = BeautifulSoup(urlopen(url), "html5lib")
      tables = soup.find_all("table")

      for t in tables:
         rows = t.tbody.find_all("tr")
         for r in rows:
            data = [item.text for item in r.find_all("td")]

            home_team_id = query_db('select id from teams where city = ?', [data[2]], one=True)
            if home_team_id is None:
               # insert new team
               with app.test_request_context():
                  app.preprocess_request()
                  g.db.execute('insert into teams (city) values (?)', [data[2]])
                  g.db.commit()
               home_team_id = query_db('select id from teams where city = ?', [data[2]], one=True)
            home_team_id = home_team_id['id']

            away_team_id = query_db('select id from teams where city = ?', [data[4]],
                  one=True)
            if away_team_id is None:
               # insert new team
               with app.test_request_context():
                  app.preprocess_request()
                  g.db.execute('insert into teams (city) values (?)', [data[4]])
                  g.db.commit()
               away_team_id = query_db('select id from teams where city = ?', [data[4]],
                  one=True)
            away_team_id = away_team_id['id']

            date_tuple = split(data[0], "/")
            date = time.mktime(datetime(int(date_tuple[2]), int(date_tuple[0]),
                   int(date_tuple[1])).timetuple())
            weekday = data[1]

            home_score = int(data[3])
            away_score = int(data[5])

            if data[6] == "SO":
               ot_or_so = 2
            elif data[6] == "OT":
               ot_or_so = 1
            else:
               ot_or_so = 0

            att_string = replace(data[7], ",", "")
            if att_string == "":
               attendance = 0
            else:
               attendance = int(att_string)

            with app.test_request_context():
               app.preprocess_request()
               g.db.execute('insert into games (game_date, weekday, home_team, ' \
                         'away_team, home_score, away_score, ot_or_so, ' \
                         'attendance) values (?, ?, ?, ?, ?, ?, ?, ?)',
                         [date, weekday, home_team_id, away_team_id, home_score,
                          away_score, ot_or_so, attendance])
               g.db.commit()
      print("finished scraping " + str(year-1) + "-" + str(year) + " season")

@app.before_request
def before_request():
   g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
   g.db.close()

@app.route('/season/<season_end_year>')
def show_season(season_end_year):
   season_end_year = int(season_end_year)
   lo = time.mktime(datetime(season_end_year - 1, 8, 31).timetuple())
   hi = time.mktime(datetime(season_end_year, 7, 1).timetuple())
   cur = g.db.execute('select game_date, weekday, home_team, ' \
         'away_team, home_score, away_score, ot_or_so, attendance from games ' \
         'where game_date > ? and game_date < ? order by game_date desc',
         [lo, hi])
   games = [dict(date=date.fromtimestamp(row[0]), weekday=row[1],
         home_team=row[2], away_team=row[3], home_score=row[4],
         away_score=row[5], ot_or_so=row[6], attendance=row[7])
         for row in cur.fetchall()]
   cur = g.db.execute('select id, city from teams')
   teams = {}
   for row in cur.fetchall():
      teams[row[0]] = row[1]
   return render_template('show_season.html', games=games, teams=teams)


@app.route('/add', methods=['POST'])
def add_entry():
   # TODO: find a more concise method?
   for game in request.games:
      g.db.execute('insert into games (game_date, weekday, home_team, ' \
                   'away_team, home_score, away_score, ot_or_so, ' \
                   'attendance) values (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   [game['date'], game['weekday'], game['home_team'],
                    game['away_team'], game['home_score'], game['away_score'],
                    game['ot_or_so'], game['attendance']])
   g.db.commit()
   #flash('New entry was successfully posted')
   #return redirect(url_for('show_entries'))
   return 'New entries were successfully posted'

@app.route('/query/<query_string>')
def query(query_string):
   answer = "Hello, world!"
   return render_template('results.html', answer=answer)

if __name__ == '__main__':
   app.run()
