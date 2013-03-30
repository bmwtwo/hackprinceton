# all the imports
import sqlite3
import time
from datetime import datetime, date
from flask import Flask, request, session, g, redirect, url_for, \
      abort, render_template, flash
from contextlib import closing
from string import replace, split, find
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

def change_ids():
   with app.test_request_context():
      app.preprocess_request()
      g.db.execute("UPDATE games SET home_team=9999 WHERE home_team=1")
      g.db.execute("UPDATE games SET away_team=9999 WHERE away_team=1")
      g.db.execute("UPDATE teams SET id=9999 WHERE id=1")
      g.db.commit()

def get_teams_array():
   with app.test_request_context():
      app.preprocess_request()
      cur = g.db.execute('select id, city from teams')
      teams = {}
      for row in cur.fetchall():
         teams[row[0]] = row[1]
   return teams

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
   teams=get_teams_array()
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

@app.route('/query/<user_input>')
def query(user_input):
   options = ["most recent", "team", "victory", "defeat", "to team", "in city"]
   constraints = []
   interpretations = dict(zip(options, len(options) * [False]))
   query_string = user_input.lower()

   #TODO: be wary of usage of last (could mean opposite of first?)
   if (find(query_string, "last") > -1 or
      find(query_string, "most recent") > -1):
         interpretations["most recent"] = True

   teams = query_db('select * from teams')
   for team in teams:
      if (find(query_string, "in " + team["city"].lower()) > -1 or
         find(query_string, "at " + team["city"].lower()) > -1):
            interpretations["in city"] = team["id"]
            query_string = replace(query_string, "at " + team["city"].lower(), "")
            query_string = replace(query_string, "in " + team["city"].lower(), "")
            constraints.append("away_team = " + str(team["id"]))

      if find(query_string, "to " + team["city"].lower()) > -1:
         interpretations["to team"] = team["id"]
         query_string = replace(query_string, "to " + team["city"].lower(), "")
         constraints.append("home_team = " + str(team["id"]) +
                            " OR away_team = " + str(team["id"]))

      if find(query_string, team["city"].lower()) > -1:
         interpretations["team"] = team["id"]
         constraints.append("home_team = " + str(team["id"]) +
                            " OR away_team = " + str(team["id"]))
   #endfor

   if (find(query_string, "win") > -1 or
      find(query_string, "victory") > -1):
         interpretations["victory"] = True
         if interpretations["team"] != False:
            t = str(interpretations["team"])
            constraints.append("(home_team=" + t + " AND home_score > away_score) OR " \
               "(away_team=" + t + " AND away_score > home_score)");
         # TODO: add other cases (e.g. "last win in Boston")

   if (find(query_string, "loss") > -1 or
      find(query_string, "lose") > -1 or 
      find(query_string, "defeat") > -1):
         interpretations["defeat"] = True
         if interpretations["team"] != False:
            t = str(interpretations["team"])
            constraints.append("(home_team=" + t + " AND home_score < away_score) OR " \
               "(away_team=" + t + " AND away_score < home_score)");
         # TODO: add other cases (e.g. "last win in Boston")


   ### FIND ANSWER
   where_clause = ""
   for c in constraints:
      if len(where_clause) == 0:
         where_clause = "(" + c + ")"
      else:
         where_clause += " AND (" + c + ")"
   print('SELECT * FROM games WHERE ' + where_clause)
   answer = query_db('SELECT * FROM games WHERE ' + where_clause + ' ORDER BY ' \
                     'game_date DESC', one=True)
   my_date = date.fromtimestamp(answer["game_date"])
   answer["game_date"] = my_date.strftime("%A, %B ")#%d %Y")
   answer["game_date"] += my_date.strftime("%d, ").lstrip('0')
   answer["game_date"] += my_date.strftime("%Y")

   #print (get_teams_array())
   #print (interpretations)

   return render_template('results.html', options=options,
            interpretations=interpretations, teams=get_teams_array(),
            answer=answer, user_input=replace(user_input, "%3F", "?"))

if __name__ == '__main__':
   app.run()
