import pandas as pd
import numpy as np

class RollingFeatureBuilder:
    def __init__(self, df):
        self.df = df.copy()

    def add_match_ids(self):
        self.df = self.df.sort_values("date")
        self.df["match_id"] = range(len(self.df))
        return self.df

    def build_team_features(self):
        df = self.df.copy()

        teams = pd.unique(df[["home_team", "away_team"]].values.ravel())
        feats = []

        for team in teams:
            # Takıma ait maçlar
            tmp = df[(df["home_team"] == team) | (df["away_team"] == team)].copy()
            tmp = tmp.sort_values("date").reset_index(drop=True)

            # Takım adı (eksik olan sütun)
            tmp["team"] = team

            # Gol bilgisi
            tmp["team_goals_for"] = tmp.apply(
                lambda r: r["home_goals"] if r["home_team"] == team else r["away_goals"],
                axis=1
            )
            tmp["team_goals_against"] = tmp.apply(
                lambda r: r["away_goals"] if r["home_team"] == team else r["home_goals"],
                axis=1
            )

            # Form puanı
            def points(r):
                if r["home_team"] == team:
                    if r["result"] == 1: return 3
                    elif r["result"] == 0: return 1
                    else: return 0
                else:
                    if r["result"] == -1: return 3
                    elif r["result"] == 0: return 1
                    else: return 0

            tmp["team_points"] = tmp.apply(points, axis=1)

            # Rolling stats
            tmp["rolling_gf_5"] = tmp["team_goals_for"].rolling(5).mean()
            tmp["rolling_ga_5"] = tmp["team_goals_against"].rolling(5).mean()
            tmp["rolling_pts_5"] = tmp["team_points"].rolling(5).mean()

            # xG proxy = gol × rakip savunma katsayısı
            tmp["opp_def"] = tmp.apply(
                lambda r: r["away_def"] if r["home_team"] == team else r["home_def"],
                axis=1
            )
            tmp["rolling_xGF_5"] = (tmp["team_goals_for"] * tmp["opp_def"]).rolling(5).mean()

            # xGA proxy = yenilen gol × rakip hücum katsayısı
            tmp["opp_att"] = tmp.apply(
                lambda r: r["away_att"] if r["home_team"] == team else r["home_att"],
                axis=1
            )
            tmp["rolling_xGA_5"] = (tmp["team_goals_against"] * tmp["opp_att"]).rolling(5).mean()

            feats.append(tmp)

        out = pd.concat(feats)
        return out

    def merge_features(self):
        df = self.df.copy()
        tf = self.team_features.copy()

        # HOME merge
        home_feats = tf.rename(columns=lambda c: "home_" + c if c not in ["date","home_team","away_team","team"] else c)
        home_feats = home_feats[home_feats["team"] == home_feats["home_team"]]

        # AWAY merge
        away_feats = tf.rename(columns=lambda c: "away_" + c if c not in ["date","home_team","away_team","team"] else c)
        away_feats = away_feats[away_feats["team"] == away_feats["away_team"]]

        # Merge işlemleri
        df = df.merge(home_feats, on=["date","home_team","away_team"], how="left")
        df = df.merge(away_feats, on=["date","home_team","away_team"], how="left")

        return df

    def build(self):
        self.add_match_ids()
        self.team_features = self.build_team_features()
        final = self.merge_features()
        return final
