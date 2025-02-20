# -*- coding: utf-8 -*-
"""End-to-End Ever-Winning AI Trading Bot using Alpaca’s API.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1TRzqYfLdarN9hzziOYuWhaF9m9tbEIPu

**Building an End-to-End Trading Bot using Alpaca’s API, CircleCI, and Slack**

**Install Dependencies**
"""

"""**Import dependencies**"""

import os
import pandas as pd
import yfinance as yf
import alpaca as tradeapi
import alpaca_trade_api as tradeapi
import configparser
import pytz
import locale
import pandas_market_calendars as mcal

from alpaca_trade_api.rest import REST, TimeFrame, APIError
import alpaca_trade_api as alpaca
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator
from ta.trend import sma_indicator
from tqdm import tqdm
from requests_html import HTMLSession
from datetime import datetime
from slack import WebClient
from slack.errors import SlackApiError
import time
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Activation, Dense, Dropout, LSTM
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
import json
import logging
#import config
import asyncio
from lumibot.brokers import Alpaca
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader
from datetime import datetime
from alpaca_trade_api import REST
#from timedelta import Timedelta
time.sleep(1)
from google.colab import drive
drive.mount('/content/drive')

"""**Contains the TradingOpportunities and Alpaca classes, which handle scraping trading opportunities and executing buy/sell orders, respectively.**

**The TradingOpportunities Class**

The TradingOpportunities class is responsible for scraping YahooFinance! to identify trading opportunities based on the top losing stocks and popular crypto assets. It does this using the get_trading_opportunities and get_asset_info methods.
"""

class TradingOpportunities:
    def __init__(self, n_stocks=100, n_crypto=100):
        """
        Description:
        Grabs top stock losers and highest valued crypto assets from YahooFinance! to determine trading opportunities using simple technical trading indicators
        such as Bollinger Bands and RSI.

        Arguments:
            •  n_stocks: number of top losing stocks that'll be pulled from YahooFinance! and considered in the algo
            •  n_crypto: number of top traded and most valuable crypto assets that'll be pulled from YahooFinance! and considered in the algo

        Methods:
            • raw_get_daily_info(): Grabs a provided site and transforms HTML to a pandas df
            • get_trading_opportunities(): Grabs df from raw_get_daily_info() and provides just the top "n" losers declared by user in n_stocks and "n" amount of top of most popular crypto assets to examine
            • get_asset_info(): a df can be provided to specify which assets you'd like info for since this method is used in the Alpaca class. If no df argument is passed then tickers from get_trading_opportunities() method are used.
        """

        self.n_stocks = n_stocks
        self.n_crypto = n_crypto

    def raw_get_daily_info(self, site):
        """
        Description:
        Grabs a provided site and transforms HTML to a pandas df

        Argument(s):
            • site: YahooFinance! top losers website provided in the get_day_losers() function below

        Other Notes:
        Commented out the conversion of market cap and volume from string to float since this threw an error.
        Can grab this from the yfinance API if needed or come back to this function and fix later.
        """

        session = HTMLSession()
        response = session.get(site)

        tables = pd.read_html(response.html.raw_html)
        df = tables[0].copy()
        df.columns = tables[0].columns

        session.close()
        return df

    def get_trading_opportunities(self, n_stocks=None, n_crypto=None):
        """
        Description:
        Grabs df from raw_get_daily_info() and provides just the top "n" losers
        declared by user in n_stocks and "n" amount of top of most popular crypto
        assets to examine

        This method scrapes YahooFinance! using the yfinance package to obtain
        the top losing stocks of the day and most popular crypto assets. It first
        gets the top losing stocks by percentage change for the day using
        get_day_losers. Then, it obtains the top traded crypto assets by market cap
        using get_top_crypto.

        Argument(s):
            • n_stocks: Number of top losers to analyze per YahooFinance! top losers
             site.
            • n_crypto: Number of most popular crypto assets to grab historical price
            info from.
        """

        #####################
        #####################
        # Crypto part
        df_crypto = []
        i = 0
        while True:
            try:
                df_crypto.append(
                    self.raw_get_daily_info(
                        "https://finance.yahoo.com/crypto?offset={}&count=100".format(i)
                    )
                )
                i += 100
                print("processing " + i)
            except:
                break

        df_crypto = pd.concat(df_crypto)
        df_crypto["asset_type"] = "crypto"

        df_crypto = df_crypto.head(self.n_crypto)

        #####################
        #####################
        # Stock part
        df_stock = self.raw_get_daily_info(
            "https://finance.yahoo.com/losers?offset=0&count=100"
        )
        df_stock["asset_type"] = "stock"

        df_stock = df_stock.head(self.n_stocks)

        #####################
        #####################
        # Merge df's and return as one
        dfs = [df_crypto, df_stock]
        df_opportunities = pd.concat(dfs, axis=0).reset_index(drop=True)

        # Create a list of all tickers scraped
        self.all_tickers = list(df_opportunities["Symbol"])

        return df_opportunities

    def get_asset_info(self, df=None):
        """
        Description:
        Grabs historical prices for assets, calculates RSI and Bollinger Bands tech
        signals, and returns a df with all this data for the assets meeting the
        buy criteria.

        This method filters the list of assets obtained from get_trading_opportunities
        by checking each asset's technical indicators and picking just the oversold
        assets as buying opportunities.

        Argument(s):
            • df: a df can be provided to specify which assets you'd like info for
            since this method is used in the Alpaca class. If no df argument is
            passed then tickers from get_trading_opportunities() method are used.
        """

        # Grab technical stock info:
        if df is None:
            all_tickers = self.all_tickers
        else:
            all_tickers = list(df["yf_ticker"])
        print(all_tickers)

        df_tech = []
        for i, symbol in tqdm(
            enumerate(all_tickers),
            desc="• Grabbing technical metrics for "
            + str(len(all_tickers))
            + " assets",
        ):
            try:
                Ticker = yf.Ticker(symbol)
                Hist = Ticker.history(period="1y", interval="1d")

                # Check if the historical data is empty
                if Hist.empty:
                    print(f"No historical data found for {symbol}, skipping...")
                    continue  # Skip to the next ticker
                    #print(Hist)

                for n in [14, 30, 50, 200]:
                # These technical indicators are commonly used in financial
                # analysis and algorithmic trading to assess trends, momentum,
                # and volatility.
                    # Initialize MA Indicator
                    # Simple Moving Average (SMA)
                    Hist["ma" + str(n)] = sma_indicator(
                        close=Hist["Close"], window=n, fillna=False
                    )
                    # Initialize RSI Indicator
                    # Relative Strength Index (RSI)
                    Hist["rsi" + str(n)] = RSIIndicator(
                        close=Hist["Close"], window=n
                    ).rsi()
                    # Initialize Hi BB Indicator
                    # Bollinger Band High Indicator
                    Hist["bbhi" + str(n)] = BollingerBands(
                        close=Hist["Close"], window=n, window_dev=2
                    ).bollinger_hband_indicator()
                    # Initialize Lo BB Indicator
                    # Bollinger Band Low Indicator
                    Hist["bblo" + str(n)] = BollingerBands(
                        close=Hist["Close"], window=n, window_dev=2
                    ).bollinger_lband_indicator()

                df_tech_temp = Hist.iloc[-1:].reset_index(drop=True)
                df_tech_temp.insert(0, "Symbol", Ticker.ticker)
                df_tech.append(df_tech_temp)
            except KeyError:
                print(f"KeyError encountered for {symbol}, skipping...")
            except Exception as e:
                print(f"An unexpected error occurred for {symbol}: {e}")

        # Check if df_tech is still empty after the loop
        if not df_tech:
            print("No data found for any of the tickers. Returning an empty DataFrame.")
            return pd.DataFrame()  # Return empty DataFrame to avoid the error
        #df_tech = [x for x in df_tech if not x.empty]
        df_tech = pd.concat(df_tech)

        # Define the buy criteria
        buy_criteria = (
            (df_tech[["bblo14", "bblo30", "bblo50", "bblo200"]] == 1).any(axis=1)
        ) | ((df_tech[["rsi14", "rsi30", "rsi50", "rsi200"]] <= 30).any(axis=1))

        # Filter the DataFrame
        buy_filtered_df = df_tech[buy_criteria]

        # Create a list of tickers to trade
        self.buy_tickers = list(buy_filtered_df["Symbol"])

        print(
            "• oversold assets meeting the buy criteria as buying opportunities: " + str(
            buy_filtered_df))
        print(
            "• list of tickers to trade: " + str(list(buy_filtered_df["Symbol"])))

        return buy_filtered_df

"""**The Alpaca Class**

The Alpaca class is responsible for executing buy and sell orders using the Alpaca API. It contains the sell_orders and buy_orders methods to handle these actions.
"""

class Alpaca:
    def __init__(self, api):
        """
        Description: Object providing Alpaca balance details and executes
        buy/sell trades

        Arguments:
        • api: this object should be created before instantiating the class
        and it should contain your Alpaca keys
        •

        Methods:
        • get_current_positions(): shows current balance of Alpaca account
        """

        # Access the file via the mounted drive
        config_path = "/content/drive/MyDrive/creds.cfg"
        config = configparser.ConfigParser()
        config.read(config_path)

        BASE_URL='https://paper-api.alpaca.markets'

        self.api = tradeapi.REST(
            key_id=os.environ["KEY_ID"],
            secret_key=os.environ["SECRET_KEY"],
            base_url=BASE_URL
        )

    def get_current_positions(self):
        """
        Description: Returns a df with current positions in account

        Argument(s):
        • api: this is the instantiated session you'll need to kick-off define
        before doing any analysis.
        """
        investments = pd.DataFrame({
            'asset': [x.symbol for x in self.api.list_positions()],
            'current_price': [x.current_price for x in self.api.list_positions()],
            'qty': [x.qty for x in self.api.list_positions()],
            'market_value': [x.market_value for x in self.api.list_positions()],
            'profit_dol': [x.unrealized_pl for x in self.api.list_positions()],
            'profit_pct': [x.unrealized_plpc for x in self.api.list_positions()]
        })

        cash = pd.DataFrame({
            'asset': 'Cash',
            'current_price': self.api.get_account().cash,
            'qty': self.api.get_account().cash,
            'market_value': self.api.get_account().cash,
            'profit_dol': 0,
            'profit_pct': 0
        }, index=[0])  # Need to set index=[0] since passing scalars in df

        assets = pd.concat([investments, cash], ignore_index=True)

        float_fmt = ['current_price', 'qty', 'market_value', 'profit_dol', 'profit_pct']
        str_fmt = ['asset']

        for col in float_fmt:
            assets[col] = assets[col].astype(float)

        for col in str_fmt:
            assets[col] = assets[col].astype(str)

        rounding_2 = ['market_value', 'profit_dol']
        rounding_4 = ['profit_pct']

        assets[rounding_2] = assets[rounding_2].apply(lambda x: pd.Series.round(x, 2))
        assets[rounding_4] = assets[rounding_4].apply(lambda x: pd.Series.round(x, 4))

        asset_sum = assets['market_value'].sum()
        assets['portfolio_pct'] = assets['market_value'] / asset_sum

        # Add yf_ticker column so look up of Yahoo Finance! prices is easier
        assets['yf_ticker'] = assets['asset'].apply(lambda x: x[:3] + '-' + x[3:] if len(x) == 6 else x)

        return assets

    @staticmethod
    def is_market_open():
        nyse = pytz.timezone('America/New_York')
        current_time = datetime.now(nyse)
        print(current_time)
        print("• Current Time: " + str(current_time))

        nyse_calendar = mcal.get_calendar('NYSE')
        market_schedule = nyse_calendar.schedule(start_date=current_time.date(), end_date=current_time.date())

        if not market_schedule.empty:
            market_open = market_schedule.iloc[0]['market_open'].to_pydatetime().replace(tzinfo=None)
            market_close = market_schedule.iloc[0]['market_close'].to_pydatetime().replace(tzinfo=None)
            current_time_no_tz = current_time.replace(tzinfo=None)

            if market_open <= current_time_no_tz <= market_close:
                return True

        return False

    def sell_orders(self):
        """
        Description:
        Liquidates positions of assets currently held based on technical
        signals or to free up cash for purchases.

        This method iterates through the assets in the user’s Alpaca account and
        checks if they meet the selling criteria based on technical indicators
        that signal they’re overbought. If they do, it generates a sell order
        for the asset. This is probably the most complex part of the project
        since we need to free up cash if no existing positions are overbought
        (and subsequently sold) so the algorithm can continue with buying
        oversold assets. I’ve incorporated logic that checks if cash is < 10%
        of the total portfolio and if so, sells an equal amount of the top 25%
        of performing assets in the portfolio to fill that gap.

        Argument(s):
        • self.df_current_positions: Needed to inform how much of each position
        should be sold.
        """

        # Get the current time in Eastern Time
        et_tz = pytz.timezone('US/Eastern')
        current_time = datetime.now(et_tz)

        # Define the sell criteria
        TradeOpps = TradingOpportunities()
        df_current_positions = self.get_current_positions()
        df_current_positions_hist = TradeOpps.get_asset_info(
            df=df_current_positions[df_current_positions['yf_ticker'] != 'Cash'])

        # Sales based on technical indicator
        sell_criteria = ((df_current_positions_hist[['bbhi14', 'bbhi30', 'bbhi50', 'bbhi200']] == 1).any(axis=1)) | \
                        ((df_current_positions_hist[['rsi14', 'rsi30', 'rsi50', 'rsi200']] >= 70).any(axis=1))

        # Filter the DataFrame
        sell_filtered_df = df_current_positions_hist[sell_criteria]
        sell_filtered_df['alpaca_symbol'] = sell_filtered_df['Symbol'].str.replace('-', '')
        symbols = list(sell_filtered_df['alpaca_symbol'])

        # Determine whether to trade all symbols or only those with "-USD" in their name
        if self.is_market_open():
            eligible_symbols = symbols
        else:
            eligible_symbols = [symbol for symbol in symbols if "-USD" in symbol]

            # Submit sell orders for eligible symbols
        executed_sales = []
        for symbol in eligible_symbols:
            try:
                if symbol in symbols:  # Check if the symbol is in the sell_filtered_df
                    print("• selling " + str(symbol))
                    qty = df_current_positions[df_current_positions['asset'] == symbol]['qty'].values[0]
                    self.api.submit_order(
                        symbol=symbol,
                        time_in_force='gtc',
                        qty=qty,
                        side="sell"
                    )
                    executed_sales.append([symbol, round(qty)])
            except Exception as e:
                continue

        executed_sales_df = pd.DataFrame(executed_sales, columns=['ticker', 'quantity'])

        if len(eligible_symbols) == 0:
            self.sold_message = "• liquidated no positions based on the sell criteria"
        else:
            self.sold_message = f"• executed sell orders for {''.join([symbol + ', ' if i < len(eligible_symbols) - 1 else 'and ' + symbol for i, symbol in enumerate(eligible_symbols)])}based on the sell criteria"

        print(self.sold_message)

        # Check if the Cash row in df_current_positions is at least 10% of total holdings
        cash_row = df_current_positions[df_current_positions['asset'] == 'Cash']
        total_holdings = df_current_positions['market_value'].sum()

        if cash_row['market_value'].values[0] / total_holdings < 0.1:
            # Sort the df_current_positions by profit_pct descending
            df_current_positions = df_current_positions.sort_values(by=['profit_pct'], ascending=False)

            # Sell the top 25% of performing assets evenly to make Cash 10% of the total portfolio
            top_half = df_current_positions.iloc[:len(df_current_positions) // 4]
            top_half_market_value = top_half['market_value'].sum()
            cash_needed = total_holdings * 0.1 - cash_row['market_value'].values[0]

            for index, row in top_half.iterrows():
                print("• selling " + str(row['asset']) + " for 10% portfolio cash requirement")
                amount_to_sell = int((row['market_value'] / top_half_market_value) * cash_needed)

                # If the amount_to_sell is zero or an APIError occurs, continue to the next iteration
                if amount_to_sell == 0:
                    continue

                try:
                    self.api.submit_order(
                        symbol=row['asset'],
                        time_in_force="day",
                        type="market",
                        notional=amount_to_sell,
                        side="sell"
                    )
                    executed_sales.append([row['asset'], amount_to_sell])
                except APIError:
                    continue

            # Set the locale to the US
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

            # Convert cash_needed to a string with dollar sign and commas
            cash_needed_str = locale.currency(cash_needed, grouping=True)

            print("• Sold " + cash_needed_str + " of top 25% of performing assets to reach 10% cash position")

        return executed_sales_df

    def buy_orders(self, tickers):
        """
        Description:
        Buys assets per buying opportunities uncovered in the get_asset_info()
        function.

        This method takes a list of tickers that meet the buying criteria based
        on YahooFinance! stocks and crypto assets and creates buy orders for
        each of them using the Alpaca API. It calculates the amount to buy based
        on the user’s available buying power and the current price of the asset.

        Argument(s):
        • df_current_positions: Needed to understand available cash for purchases.
        • symbols: Assets to be purchased.
        """

        # Get the current positions and available cash
        df_current_positions = self.get_current_positions()
        available_cash = df_current_positions[df_current_positions['asset'] == 'Cash']['market_value'].values[0]
        print("• Available cash: " + str(available_cash))
        # Get the current time in Eastern Time
        et_tz = pytz.timezone('US/Eastern')
        current_time = datetime.now(et_tz)

        # Determine whether to trade all symbols or only those with "-USD" in their name
        if self.is_market_open():
            eligible_symbols = tickers
        else:
            eligible_symbols = [symbol for symbol in tickers if "-USD" in symbol]

            # Submit buy orders for eligible symbols
        for symbol in eligible_symbols:
            try:
                if len(symbol) >= 6:
                    self.api.submit_order(
                        symbol=symbol,
                        time_in_force='gtc',
                        notional=available_cash / len(eligible_symbols),
                        side="buy"
                    )
                else:
                    self.api.submit_order(
                        symbol=symbol,
                        type='market',
                        notional=available_cash / len(eligible_symbols),
                        side="buy"
                    )

            except Exception as e:
                continue

        if len(eligible_symbols) == 0:
            self.bought_message = "• executed no buy orders based on the buy criteria"
        else:
            self.bought_message = f"• executed buy orders for {''.join([symbol + ', ' if i < len(eligible_symbols) - 1 else 'and ' + symbol for i, symbol in enumerate(eligible_symbols)])}based on the buy criteria"

        print(self.bought_message)

        self.tickers_bought = eligible_symbols

"""**slack_app_notification() Function**

The slack_app_notification function generates a formatted summary of the bot's trades and sends it as a Slack notification. It first retrieves the trade history from the Alpaca API using the get_activities method, then it parses the trade information and formats it into a human-readable message. Finally, it sends the message to a specified Slack channel using the Slack API. You can make tweaks in the main() function for when you’d like the bot to send notifications in the channel you’ve enabled your Slack app in.
"""

# Access the file via the mounted drive
config_path = "/content/drive/MyDrive/creds.cfg"
config = configparser.ConfigParser()
config.read(config_path)

os.environ["KEY_ID"] = config["alpaca"]["KEY_ID"]
os.environ["SECRET_KEY"] = config["alpaca"]["SECRET_KEY"]

BASE_URL='https://paper-api.alpaca.markets'

api = tradeapi.REST(
    key_id=os.environ["KEY_ID"],
    secret_key=os.environ["SECRET_KEY"],
    base_url=BASE_URL
    )

def slack_app_notification(days_hist=1):
    """
    Description: creates a formatted string detailing

    Arguments:
        • days_hist: examines how many days back you want the bot to gather trading info for
    """
    # Initialize variables for total sales and purchases
    total_sales = 0
    total_purchases = 0

    # Initialize dictionaries to store asset details
    crypto_sales = {}
    crypto_purchases = {}
    stock_sales = {}
    stock_purchases = {}

    # Get the current timestamp in seconds
    current_time = int(datetime.now().timestamp())

    # Calculate the start time for the trade history query (86.4k seconds = last 24hrs)
    start_time = datetime.utcfromtimestamp(current_time - days_hist * 864000).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # Get the trade history for the last 24 hours
    trades = api.get_activities(
        activity_types="FILL", direction="desc", after=start_time
    )

    # Parse the trade information
    for trade in trades:
        symbol = trade.symbol
        amount = round(float(trade.qty) * float(trade.price), 2)
        if trade.side == "sell":
            total_sales += amount
            if "USD" in symbol:
                crypto_sales[symbol] = crypto_sales.get(symbol, 0) + amount
            else:
                stock_sales[symbol] = stock_sales.get(symbol, 0) + amount
        else:
            total_purchases += amount
            if "USD" in symbol:
                crypto_purchases[symbol] = crypto_purchases.get(symbol, 0) + amount
            else:
                stock_purchases[symbol] = stock_purchases.get(symbol, 0) + amount

    # Format the results
    results = []

    total_sales_str = f"*`Total Sales: ${total_sales:,.2f}`*"
    total_purchases_str = f"*`Total Purchases: ${total_purchases:,.2f}`*"

    if crypto_sales:
        crypto_sales_sorted = sorted(
            crypto_sales.items(), key=lambda x: x[1], reverse=True
        )
        crypto_sales_formatted = [
            "  _*Crypto: $" + f"{sum(crypto_sales.values()):,.2f}*_"
        ]
        for symbol, amount in crypto_sales_sorted:
            crypto_sales_formatted.append(f"    {symbol} | Amount: ${amount:,.2f}")
        results.append(total_sales_str)
        results += crypto_sales_formatted
        results.append("")

    if stock_sales:
        stock_sales_sorted = sorted(
            stock_sales.items(), key=lambda x: x[1], reverse=True
        )
        stock_sales_formatted = [
            "  _*Stocks: $" + f"{sum(stock_sales.values()):,.2f}*_"
        ]
        for symbol, amount in stock_sales_sorted:
            stock_sales_formatted.append(f"    {symbol} | Amount: ${amount:,.2f}")
        if not crypto_sales:
            results.append(total_sales_str)
        results += stock_sales_formatted
        results.append("")

    if crypto_purchases:
        crypto_purchases_sorted = sorted(
            crypto_purchases.items(), key=lambda x: x[1], reverse=True
        )
        crypto_purchases_formatted = [
            "  _*Crypto: $" + f"{sum(crypto_purchases.values()):,.2f}*_"
        ]
        for symbol, amount in crypto_purchases_sorted:
            crypto_purchases_formatted.append(f"    {symbol} | Amount: ${amount:,.2f}")
        results.append(total_purchases_str)
        results += crypto_purchases_formatted
        results.append("")

    if stock_purchases:
        stock_purchases_sorted = sorted(
            stock_purchases.items(), key=lambda x: x[1], reverse=True
        )
        stock_purchases_formatted = [
            "  _*Stocks: $" + f"{sum(stock_purchases.values()):,.2f}*_"
        ]
        for symbol, amount in stock_purchases_sorted:
            stock_purchases_formatted.append(f"    {symbol} | Amount: ${amount:,.2f}")
        if not crypto_purchases:
            results.append(total_purchases_str)
        results += stock_purchases_formatted

    # Combine the results into a formatted string
    formatted_results = "\n".join(results)

    # Return the formatted results
    return formatted_results

"""**main.py — Bringing It All Together**

main.py is the entry point of the application and brings together the functionality of the TradingOpportunities, Alpaca, and slack_app_notification classes and functions. It gathers all user configuration details stored in the creds.cfg file to authenticate all the API connections.
"""

BASE_URL='https://paper-api.alpaca.markets'
def main(days_hist=1, st_hr_for_message=6, end_hr_for_message=9, n_stocks=100, n_crypto=100):
    """
    Description: Uses your Alpaca API credentials (including whether you're
    paper trading or live trading based on BASE_URL) and
    sells overbought assets in portfolio then buys oversold assets in the
    market per YahooFinance! opportunities.

    Arguments:
        • st_hr_for_message: starting hour for interval for considering when
        Slack notification will be sent
        • end_hr_for_message: ending hour for interval for considering when
        Slack notification will be sent
        • n_stocks: number of top losing stocks from YahooFinance! to be
        considered for trades
        • n_crypto: number of top traded/valued crypto assets from YahooFinance! to be considered for trades
    """

    # Access the file via the mounted drive
    config_path = "/content/drive/MyDrive/creds.cfg"
    config = configparser.ConfigParser()
    config.read(config_path)
    # Debugging print statements
    print("Loaded sections:", config.sections())
    print("Alpaca keys:", dict(config["alpaca"]) if "alpaca" in config else "Alpaca section missing.")

    os.environ["KEY_ID"] = config["alpaca"]["KEY_ID"]
    os.environ["SECRET_KEY"] = config["alpaca"]["SECRET_KEY"]
    os.environ["client"] = config["slack"]["client"]
    BASE_URL = config["alpaca"]["BASE_URL"]

    api = tradeapi.REST(
        key_id=os.environ["KEY_ID"],
        secret_key=os.environ["SECRET_KEY"],
        base_url=BASE_URL,
    )

    ##############################
    ##############################
    ### Run TradingOpps class

    # Instantiate TradingOpportunities class
    trades = TradingOpportunities(n_stocks=n_stocks, n_crypto=n_crypto)

    # Shows all scraped opportunities; defaults to 25 top losing stocks and 25 of the most popular crypto assets
    trades.get_trading_opportunities()

    # The all_tickers attribute is a list of all tickers in the get_trading_opportunities() method. Passing this list through the get_asset_info() method shows just the tickers that meet buying criteria
    trades.get_asset_info()

    ##############################
    ##############################
    ### Run Alpaca class

    # Instantiate Alpaca class
    Alpaca_instance = Alpaca(api=api)

    Alpaca_instance.get_current_positions()

    # Liquidates currently held assets that meet sell criteria and stores sales in a df
    Alpaca_instance.sell_orders()

    # Execute buy_orders using trades.buy_tickers and stores buys in a tickers_bought list
    Alpaca_instance.buy_orders(tickers=trades.buy_tickers)
    Alpaca_instance.tickers_bought

    ##############################
    ##############################
    ### Slack notification

    def part_of_day():
        current_time = datetime.now(pytz.timezone("CET"))
        if current_time.hour < 12:
            return "️💰☕️ *Good morning* ☕️💰"
        else:
            return "💰🌅 *Good afternoon* 🌅💰"

    current_time = datetime.now(pytz.timezone("CET"))
    hour = current_time.hour

    if st_hr_for_message <= hour < end_hr_for_message:
        print("• Sending message")

        # Authenticate to the Slack API via the generated token
        client = WebClient(os.environ["client"])

        message = (
            f"{part_of_day()}\n\n"
            "The trading bot has made the following trades over the past 24hrs:\n\n"
            f"{slack_app_notification(days_hist=days_hist)}\n\n"
            "Happy trading!\n"
            "June's Trading Bot 🤖"
        )

        try:
            response = client.chat_postMessage(
                channel="ENTER_CHANNEL_ID_HERE",
                text=message,
                mrkdwn=True,  # Enable Markdown formatting
            )
            print("Message sent successfully")
        except SlackApiError as e:
            print(f"Error sending message: {e}")
    else:
        print("Not sending message since it's not between 6 AM and 9 AM in CET.")

if __name__ == "__main__":
    main()
