import time
import pyupbit
import datetime
import logging
import os

# API 키
access = ""
secret = ""

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    filename="trading_bot.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_rsi(ticker, interval="minute15", period=14):
    """
    RSI (Relative Strength Index) 계산
    """
    try:
        df = pyupbit.get_ohlcv(ticker, interval=interval)
        delta = df['close'].diff(1)
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period, min_periods=1).mean()
        avg_loss = loss.rolling(window=period, min_periods=1).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except Exception as e:
        logging.error(f"Error calculating RSI: {e}")
        return None

def get_balance(ticker):
    """잔고 조회"""
    try:
        balances = upbit.get_balances()
        for b in balances:
            if b['currency'] == ticker:
                if b['balance'] is not None:
                    return float(b['balance'])
                else:
                    return 0
        return 0
    except Exception as e:
        logging.error(f"Error getting balance: {e}")
        return 0

def get_current_price(ticker):
    """현재가 조회"""
    try:
        return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]
    except Exception as e:
        logging.error(f"Error getting current price: {e}")
        return None

def get_total_assets():
    """전체 자산(원화 + COIN 현재가 기준 환산) 계산"""
    try:
        krw_balance = get_balance("KRW")
        coin_balance = get_balance(COIN)
        current_price = get_current_price(f"KRW-{COIN}")
        if current_price is None:
            return krw_balance, krw_balance  # 가격을 가져오지 못하면 원화 잔고만 반환
        total_assets = krw_balance + (coin_balance * current_price)
        return krw_balance, total_assets
    except Exception as e:
        logging.error(f"Error calculating total assets: {e}")
        return 0, 0

# 로그인
try:
    COIN = os.getenv("COIN", "XRP")  # 환경 변수에서 COIN 값 가져오기, 기본값으로 'BTC' 사용
    upbit = pyupbit.Upbit(access, secret)
    logging.info(f"RSI-based auto-trade started for {COIN}.")
except Exception as e:
    logging.error(f"Error during login: {e}")
    exit()

while True:
    try:
        # RSI 계산
        rsi = get_rsi(f"KRW-{COIN}", interval="minute15")
        current_price = get_current_price(f"KRW-{COIN}")

        if rsi is None or current_price is None:
            logging.warning("Skipping this iteration due to missing data.")
            time.sleep(15)
            continue

        # 전체 자산 및 원화 잔고 계산
        krw_balance, total_assets = get_total_assets()

        logging.info(f"RSI: {rsi}, Current Price: {current_price}, KRW Balance: {krw_balance}, Total Assets: {total_assets}")

        # 매수 로직
        if rsi <= 40 and krw_balance > 5000:
            # 전체 자산의 50%로 매수, 이미 매수된 자산 포함
            target_amount = (total_assets * 0.5) * 0.9995  # 수수료 반영
            already_invested = total_assets - krw_balance
            buy_amount = target_amount - already_invested
            if buy_amount > 5000 and buy_amount <= krw_balance:  # 최소 거래 가능 금액 고려
                upbit.buy_market_order(f"KRW-{COIN}", buy_amount)
                logging.info(f"Buy KRW-{COIN} with up to 50% of total assets: {buy_amount}, RSI: {rsi}")

        # RSI 35 이하 -> 남은 KRW의 95% 매수
        if rsi <= 35 and krw_balance > 5000:
            buy_amount = krw_balance * 0.95 * 0.9995  # 수수료 반영
            upbit.buy_market_order(f"KRW-{COIN}", buy_amount)
            logging.info(f"Buy KRW-{COIN} with 95% of remaining KRW: {buy_amount}, RSI: {rsi}")

        # 매도 로직
        coin_balance = get_balance(COIN)
        if 60 <= rsi <= 70 and coin_balance > 0.00008:
            target_krw_amount = total_assets * 0.5
            coin_to_sell = (target_krw_amount - krw_balance) / current_price
            if coin_to_sell > 0.00008 and coin_to_sell <= coin_balance:  # 최소 거래 가능 수량 고려
                upbit.sell_market_order(f"KRW-{COIN}", coin_to_sell * 0.9995)  # 수수료 고려
                logging.info(f"Sell {COIN} to convert 50% of total assets to KRW: {coin_to_sell}, RSI: {rsi}")

        # RSI 70 이상 -> 전체 자산 매도하여 KRW로 전환
        if rsi >= 70 and coin_balance > 0.00008:
            upbit.sell_market_order(f"KRW-{COIN}", coin_balance * 0.9995)  # 수수료 고려
            logging.info(f"Sell all {COIN} to convert total assets to KRW: {coin_balance}, RSI: {rsi}")

        time.sleep(20 - (datetime.datetime.now().second % 20))

    except Exception as e:
        logging.error(f"Error in main loop: {e}")
        time.sleep(15)
