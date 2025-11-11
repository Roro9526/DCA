# dca/dca_simulator.py
# Simulation du DCA (Dollar Cost Averaging)
# Calcule la valeur investie, la valeur du portefeuille, et la version avec dividendes réinvestis.

import pandas as pd
import numpy as np
from typing import Tuple, Optional


def last_business_day_each_month(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """
    Renvoie la dernière date ouvrée de chaque mois présente dans l'index.
    Exemple : [2020-01-31, 2020-02-28, 2020-03-31, ...]
    """
    if index.empty:
        return []

    s = pd.Series(1, index=index)
    result = []

    for _, chunk in s.groupby(pd.Grouper(freq="ME")):
        if not chunk.empty:
            result.append(chunk.index[-1])

    return result


def simulate_dca(
    price: pd.Series,
    monthly_invest: float,
    dividends: Optional[pd.Series] = None,
    reinvest: bool = False
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Simule un investissement mensuel constant (DCA).

    Retourne :
      invested            → capital total investi au fil du temps
      portfolio           → valeur du portefeuille sans dividendes
      portfolio_reinvest  → valeur du portefeuille avec dividendes réinvestis (si reinvest=True)
    """

    # Nettoyage
    price = price.dropna().astype(float)
    if len(price) < 10:
        raise ValueError("Série de prix trop courte pour simuler un DCA.")

    # Dates d'achat (dernier jour ouvré de chaque mois)
    buy_dates = [d for d in last_business_day_each_month(price.index) if d in price.index]

    # === Achat mensuel fixe ===
    shares_bought = pd.Series(0.0, index=price.index)
    shares_bought.loc[buy_dates] = monthly_invest / price.loc[buy_dates]

    total_shares = shares_bought.cumsum()

    # Capital investi cumulé
    invested = pd.Series(0.0, index=price.index)
    invested.loc[buy_dates] = monthly_invest
    invested = invested.cumsum()

    # Valeur du portefeuille sans dividendes
    portfolio = total_shares * price

    # === Gestion des dividendes ===
    if dividends is None:
        dividends = pd.Series(0.0, index=price.index)

    dividends = dividends.reindex(price.index).fillna(0.0)

    # Dividendes encaissés (non réinvestis)
    div_cash_flow = total_shares.shift(1).fillna(0.0) * dividends
    cum_div_cash = div_cash_flow.cumsum()

    # Valeur du portefeuille avec dividendes encaissés mais non réinvestis
    portfolio_with_div = portfolio + cum_div_cash

    # === Réinvestissement des dividendes ===
    if reinvest:
        shares_reinvested = pd.Series(0.0, index=price.index)
        accumulated_cash = 0.0

        for i, date in enumerate(price.index):
            # Montant de dividende reçu à cette date
            div_income = total_shares.iloc[i - 1] * dividends.iloc[i] if i > 0 else 0.0
            accumulated_cash += div_income

            # Réinvestissement intégral du cash accumulé
            if accumulated_cash > 0:
                new_shares = accumulated_cash / price.iloc[i]
                shares_reinvested.iloc[i] = new_shares
                accumulated_cash = 0.0

        total_shares_reinvested = total_shares + shares_reinvested.cumsum()
        portfolio_reinvest = total_shares_reinvested * price
    else:
        portfolio_reinvest = portfolio_with_div

    return invested, portfolio, portfolio_reinvest


# === Test local (si exécuté directement) ===
if __name__ == "__main__":
    import yfinance as yf

    print("🧮 Test local du simulateur DCA...")

    # Téléchargement de l’historique Apple
    data = yf.download("AAPL", period="5y", auto_adjust=True, progress=False)["Adj Close"]

    # Récupération des dividendes
    div = yf.Ticker("AAPL").dividends.reindex(data.index).fillna(0.0)

    invested, portfolio, portfolio_reinvest = simulate_dca(data, 100, div, reinvest=True)

    print(f"Investi total : {invested.iloc[-1]:.0f} €")
    print(f"Valeur finale (sans dividendes) : {portfolio.iloc[-1]:.0f} €")
    print(f"Valeur finale (avec réinvestissement) : {portfolio_reinvest.iloc[-1]:.0f} €")
