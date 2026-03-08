import numpy as np
import pandas as pd
from scipy.stats import poisson

class PoissonEngine:
    def __init__(self, df):
        self.df = df.copy()

    def _safe(self, row, col, fallback_cols=None, default=1.0):
        """Boş, string veya NaN değerleri güvenli şekilde sayıya çeviren getter."""
        val = row.get(col, np.nan)

        # 1) Boş veya geçersiz string kontrolü
        if pd.notna(val):
            s = str(val).strip()
            if s not in ["", "nan", "None", ":"]:
                try:
                    return float(val)
                except:
                    pass

        # 2) Fallback kolonlarını dene
        if fallback_cols:
            for fc in fallback_cols:
                fv = row.get(fc, np.nan)
                if pd.notna(fv):
                    s2 = str(fv).strip()
                    if s2 not in ["", "nan", "None", ":"]:
                        try:
                            return float(fv)
                        except:
                            pass

        # 3) Son çare
        return float(default)


    def compute_lambda(self, row):
        # Rating parametreleri
        home_att = self._safe(row, "home_att")
        away_att = self._safe(row, "away_att")
        home_def = self._safe(row, "home_def")
        away_def = self._safe(row, "away_def")

        # Rolling xG (fallback → goller)
        h_xgf = self._safe(
            row,
            "home_rolling_xGF_5",
            fallback_cols=["home_team_goals_for"],
            default=1.2
        )
        h_xga = self._safe(
            row,
            "home_rolling_xGA_5",
            fallback_cols=["home_team_goals_against"],
            default=1.0
        )
        a_xgf = self._safe(
            row,
            "away_rolling_xGF_5",
            fallback_cols=["away_team_goals_for"],
            default=1.0
        )
        a_xga = self._safe(
            row,
            "away_rolling_xGA_5",
            fallback_cols=["away_team_goals_against"],
            default=1.0
        )

        # Home xG
        lambda_home = (
            0.40 * home_att +
            0.20 * away_def +
            0.20 * h_xgf +
            0.20 * a_xga
        )

        # Away xG
        lambda_away = (
            0.40 * away_att +
            0.20 * home_def +
            0.20 * a_xgf +
            0.20 * h_xga
        )

        # Negatif/NaN koruması
        if pd.isna(lambda_home): lambda_home = 1.2
        if pd.isna(lambda_away): lambda_away = 1.0

        lambda_home = max(lambda_home, 0.05)
        lambda_away = max(lambda_away, 0.05)

        return lambda_home, lambda_away

    def predict_match(self, row, max_goals=6):
        λh, λa = self.compute_lambda(row)

        matrix = np.zeros((max_goals+1, max_goals+1))
        for hg in range(max_goals+1):
            for ag in range(max_goals+1):
                matrix[hg, ag] = poisson.pmf(hg, λh) * poisson.pmf(ag, λa)

        p_home = matrix[np.triu_indices(max_goals+1, 1)].sum()
        p_draw = np.diag(matrix).sum()
        p_away = matrix[np.tril_indices(max_goals+1, -1)].sum()

        totals = np.add.outer(np.arange(max_goals+1), np.arange(max_goals+1))
        p_over25 = matrix[totals > 2].sum()
        p_under25 = 1 - p_over25

        p_btts = matrix[1:, 1:].sum()

        return {
            "lambda_home": λh,
            "lambda_away": λa,
            "p_home": p_home,
            "p_draw": p_draw,
            "p_away": p_away,
            "p_over25": p_over25,
            "p_under25": p_under25,
            "p_btts": p_btts
        }

    def build_all(self):
        rows = []
        for idx, row in self.df.iterrows():
            rows.append(self.predict_match(row))
        return pd.DataFrame(rows)
