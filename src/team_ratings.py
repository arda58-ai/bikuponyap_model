import pandas as pd
import numpy as np

class TeamRatingEngine:
    def __init__(self, df):
        self.df = df.copy()
        self.ratings = {}  # {"TeamName": {"elo": X, "att": Y, "def": Z}}

    def init_team(self, team):
        if team not in self.ratings:
            self.ratings[team] = {"elo": 1500, "att": 1.0, "def": 1.0}

    def update_elo(self, home, away, result):
        K = 25

        Ra = self.ratings[home]["elo"]
        Rb = self.ratings[away]["elo"]

        Ea = 1/(1 + 10**((Rb - Ra)/400))
        Eb = 1 - Ea

        if result == 1:
            Sa, Sb = 1, 0
        elif result == 0:
            Sa, Sb = 0.5, 0.5
        else:
            Sa, Sb = 0, 1

        self.ratings[home]["elo"] += K*(Sa - Ea)
        self.ratings[away]["elo"] += K*(Sb - Eb)

    def update_strength(self, home, away, hg, ag):
        # Attack/Defense exponential moving average
        alpha = 0.10

        self.ratings[home]["att"] = (1 - alpha)*self.ratings[home]["att"] + alpha*hg
        self.ratings[away]["att"] = (1 - alpha)*self.ratings[away]["att"] + alpha*ag

        self.ratings[home]["def"] = (1 - alpha)*self.ratings[home]["def"] + alpha*ag
        self.ratings[away]["def"] = (1 - alpha)*self.ratings[away]["def"] + alpha*hg

    def build(self):
        rows = []

        for idx, row in self.df.iterrows():
            home, away = row["HomeTeam"], row["AwayTeam"]
            hg, ag = row["FTHG"], row["FTAG"]
            res = row["ResultNumeric"]

            self.init_team(home)
            self.init_team(away)

            # Before match ratings (input features)
            pre_home_elo = self.ratings[home]["elo"]
            pre_away_elo = self.ratings[away]["elo"]
            pre_home_att = self.ratings[home]["att"]
            pre_away_att = self.ratings[away]["att"]
            pre_home_def = self.ratings[home]["def"]
            pre_away_def = self.ratings[away]["def"]

            # Update them after match
            self.update_elo(home, away, res)
            self.update_strength(home, away, hg, ag)

            rows.append({
                "home_team": home,
                "away_team": away,
                "home_elo": pre_home_elo,
                "away_elo": pre_away_elo,
                "home_att": pre_home_att,
                "away_att": pre_away_att,
                "home_def": pre_home_def,
                "away_def": pre_away_def,
                "home_goals": hg,
                "away_goals": ag,
                "result": res,
                "date": row["Date"],
                "league": row["league"],
                "season": row["season"]
            })

        return pd.DataFrame(rows)
