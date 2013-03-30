# all the imports
import sqlite3
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
   url = "http://www.hockeydb.com/ihdb/stats/team_results.php?tid=39&sid=2011"
   soup = BeautifulSoup(urlopen(url), "html5lib")
   tables = soup.find_all("table")

   for t in tables:
      rows = t.tbody.find_all("tr")
      for r in rows:
         data = [item.text for item in r.find_all("td")]

         other_team_id = query_db('select id from teams where city = ?', [data[2]],
               one=True)
         if other_team_id is None:
            # insert new team
            with app.test_request_context():
               app.preprocess_request()
               g.db.execute('insert into teams (city) values (?)', [data[2]])
               g.db.commit()
            other_team_id = query_db('select id from teams where city = ?', [data[2]],
               one=True)
         other_team_id = other_team_id['id']

         #TODO: fix this hard-coding
         team = "Vancouver"
         team_id = query_db('select id from teams where city = ?', [team], one=True)
         if team_id is None:
            # insert new team
            with app.test_request_context():
               app.preprocess_request()
               g.db.execute('insert into teams (city) values (?)', [team])
               g.db.commit()
            team_id = query_db('select id from teams where city = ?', [team], one=True)
         team_id = team_id['id']

         date_tuple = split(data[0], "/")
         date = date_tuple[2] + "-" + date_tuple[0] + "-" + date_tuple[1]
         #TODO
         weekday = 'TODO'

         if data[1] == "at":
            away_team = team_id
            home_team = other_team_id
            home_score = int(data[4])
            away_score = int(data[3])
         else:
            home_team = team_id
            away_team = other_team_id
            home_score = int(data[3])
            away_score = int(data[4])

         if data[6] == "SO":
            ot_or_so = 2
         elif data[6] == "OT":
            ot_or_so = 1
         else:
            ot_or_so = 0

         attendance = int( replace(data[7], ",", "") )

         with app.test_request_context():
            app.preprocess_request()
            g.db.execute('insert into games (game_date, weekday, home_team, ' \
                      'away_team, home_score, away_score, ot_or_so, ' \
                      'attendance) values (?, ?, ?, ?, ?, ?, ?, ?)',
                      [date, weekday, home_team, away_team, home_score,
                       away_score, ot_or_so, attendance])
            g.db.commit()
   print("finished scraping season ending on " + date)

@app.before_request
def before_request():
   g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
   g.db.close()

@app.route('/')
def show_entries():
   cur = g.db.execute('select game_date, home_team, away_team from games order by game_date desc')
   games = [dict(date=row[0], home_team=row[1], away_team=row[2]) for row in cur.fetchall()]
   cur = g.db.execute('select id, city from teams')
   teams = {}
   for row in cur.fetchall():
      teams[row[0]] = row[1]
   return render_template('show_entries.html', games=games, teams=teams)


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

if __name__ == '__main__':
   app.run()
