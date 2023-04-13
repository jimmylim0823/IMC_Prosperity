import math
from typing import Any, Dict, List, Tuple

from datamodel import OrderDepth, TradingState, Order


class Status:
    '''
    Class on cross-sectional status on given product and TradingState
    '''
    POSITION_LIMITS = {'PEARLS':20,
                       'BANANAS':20}
    
    def __init__(self, product: str, state: TradingState) -> None:
        self.product: str = product
        self.state: TradingState = state
        self.order_depth: OrderDepth = state.order_depths[product]
        self.timestamp = state.timestamp
        self.position = self.report_position()
        self.limit = Status.POSITION_LIMITS[product]
        self.best_ask = min(self.order_depth.sell_orders.keys())
        self.best_bid = max(self.order_depth.buy_orders.keys())
        self.spread, self.mid_price = self.spread_mid()
        self.eff_spread, self.mid_vwap = self.spread_vwap()
        
    def report_trade(self) -> None:
        '''
        Print trade of given status.
        '''
        if self.product in self.state.own_trades:
            for trade in self.state.own_trades[self.product]:
                if trade.timestamp == (self.timestamp - 100):
                    print(f"Trade {trade}")
        else:
            pass

    def report_position(self, print_=False) -> int:
        '''
        Print and return position of given status.
        '''
        if self.product in self.state.position:
            position = self.state.position[self.product]
        else:
            position = 0
        
        if print_:
            print(f"Position ({self.product}, {position})")
        else:
            pass
        return position
    
    def spread_mid(self) -> Tuple[int, float]:
        '''
        Return spread and mid-price of given product.
        '''
        spread = int(self.best_ask - self.best_bid)
        mid_price = (self.best_ask + self.best_bid) / 2
        return spread, mid_price
    
    def spread_vwap(self) -> Tuple[int, float]:
        '''
        Return effective spread and mid-vwap.
        '''
        # ask_vwap
        numerator = 0
        denominator = 0
        for price, quantity in self.order_depth.sell_orders.items():
            numerator += price * quantity
            denominator += quantity
        ask_vwap = numerator / denominator
        
        # bid_vwap
        numerator = 0
        denominator = 0
        for price, quantity in self.order_depth.buy_orders.items():
            numerator += price * quantity
            denominator += quantity
        bid_vwap = numerator / denominator
        
        # effective_spread
        eff_spread = round(ask_vwap - bid_vwap, 2)
        
        # mid_bid_ask_vwap
        mid_vwap = round((ask_vwap + bid_vwap) / 2, 2)
        return eff_spread, mid_vwap


class Calculate(Status):
    '''
    Class on calculating time-series data
    '''
    def __init__(self, product: str, state: TradingState) -> None:
        super(Calculate, self).__init__(product, state)

    def update_price(self, data: Dict) -> Dict[str, Dict[str, Any]]:
        '''
        Updates price data for sma calculation
        '''
        data_price = data[self.product]['price']
        
        if self.timestamp > 400:
            try:
                del data_price[0]
            except IndexError:
                pass
        else:
            pass
        data_price.append(self.mid_price)
        data[self.product]['price'] = data_price
        return data


class Strategy(Status):
    '''
    Class on status on Strategy and parameters for each products
    '''
    def __init__(self, product: str, state: TradingState) -> None:
        super(Strategy, self).__init__(product, state)
    
    def market_making(self, trend: float, sma: float
                      ) -> Dict[str, List[Order]]:
        '''
        Return orders from market making strategy
        '''
        def mm_price(self,
                     sma: float,
                     sma_scale: float=0.75
                     ) -> float:
            '''
            Return pricing that is determined for market making.
            '''
            # sma
            if self.timestamp < 400:
                shift = 0
            else:
                shift = -sma_scale * (self.mid_price - sma)
            
            resv_price = self.mid_vwap + shift
            return resv_price
        
        def mm_spread(self, trend: float) -> float:
            '''
            Return spread that is determined for market making.
            '''
            atrend = 1 - trend
            order_spread = self.eff_spread * atrend
            return order_spread
            
        def inventory_skew(self, price: float,
                           spread: float,
                           skew: float=0.5,
                           sma_scale: float=2.0
                           ) -> Dict[str, List[Order]]:
            '''
            Return generated order for inventory skew strategy
            '''
            # determination of bid price
            bid_price = math.ceil(price - spread / 2)
            if bid_price >= price:
                bid_price = bid_price - 1
            else:
                pass
            
            # determination of ask price
            ask_price = math.floor(price + spread / 2)
            if ask_price <= price:
                ask_price = bid_price + 1
            else:
                pass
            
            if abs(self.position) >= 0.9 * self.limit:
                # stop loss if over 90 percent of position limit
                ask_quantity = self.order_depth.sell_orders[self.best_ask]
                bid_quantity = self.order_depth.buy_orders[self.best_bid]
                
                # market stop loss only with best order and its quantity
                if self.position > 0:
                    # 90 percent filled in long position
                    order_price = self.best_ask
                    order_quantity = ask_quantity
                else:
                    # 90 percent filled in short position
                    order_price = self.best_bid
                    order_quantity = bid_quantity
                
                # build order book
                orders = [Order(self.product, order_price, order_quantity)]
            
            else:
                # determination of bid ask quantity
                bid_limit = self.limit - max(self.position, 0)
                ask_limit = -self.limit - min(self.position, 0)
                bid_skew = math.floor(skew * max(self.position, 0))
                ask_skew = math.ceil(skew * min(self.position, 0))
                bid_quantity = max(bid_limit - bid_skew, 0)
                ask_quantity = min(ask_limit - ask_skew, 0)
                
                # sma
                if self.timestamp < 400:
                    shift = 0
                else:
                    shift = round(-sma_scale * (self.mid_price - sma))
                
                bid_quantity = max(min(bid_limit, bid_quantity + shift), 0)
                ask_quantity = min(max(ask_limit, ask_quantity + shift), 0)
                
                # build order book
                orders = [Order(self.product, bid_price, bid_quantity),
                         Order(self.product, ask_price, ask_quantity)]
                
                # check for any bad quote or taker quote
                if (bid_price > self.best_ask):
                    orders = []
                elif (ask_price < self.best_bid):
                    orders = []
                else:
                    pass
            
            return orders
        
        # get price spread orders with inventory skew market making
        mm_price = mm_price(self, sma)
        mm_spread = mm_spread(self, trend)
        orders = inventory_skew(self, mm_price, mm_spread)
        return orders


class Trader:
    _data = {'PEARLS':{'trend':0.2,
                       'price':[]},
             'BANANAS':{'trend':0.4,
                        'price':[]}
             }
    
    def _report_order(self, result: Dict[str, List[Order]]):
        '''
        Print all order to send
        '''
        if result:
            for product, orders in result.items():
                for order in orders:
                    print(f"Order {order}")
        else:
            pass
    
    def _count_order(self, orders: List[Order]):
        '''
        Return number of bid and ask orders
        '''
        bid_order_count = 0
        ask_order_count = 0
        if orders:
            for order in orders:
                if order.quantity > 0:
                    bid_order_count += order.quantity
                elif order.quantity < 0:
                    ask_order_count += order.quantity
                else:
                    pass
        else:
            pass
        return bid_order_count, ask_order_count
    
    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        # initialize output dict
        result = {}
        
        # iterate over all available products
        # for product in state.order_depths:
        for product in ['PEARLS']:
            # initialize list of orders
            orders: list[Order] = []
            
            # Status Class: report and get cross-section data
            status = Status(product, state)
            status.report_trade()
            status.report_position(print_=True)
            print("Bid", status.best_bid, "Ask", status.best_ask)
            
            # Calculate Class: calculate time-series data
            calculate = Calculate(status.product, status.state)
            Trader._data = calculate.update_price(Trader._data)
            
            # retrieve data from Trader._data
            trend = Trader._data[product]['trend']
            sma = sum(Trader._data[product]['price']) / 5
            
            # Strategy Class: generate order from strategy
            strategy = Strategy(status.product, status.state)
            # market making strategy order
            orders += strategy.market_making(trend, sma)
            
            # send order
            result[product] = orders
        
        # report and return orders
        self._report_order(result)
        return result
    